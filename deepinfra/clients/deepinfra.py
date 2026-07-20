"""The unified DeepInfra HTTP client (sync + async), built on httpx.

Every SDK feature (sandboxes, the inference wrappers) funnels through this
client. Operations are described as immutable RequestSpec values and executed
by thin sync/async executors so the logic exists once.
"""

from __future__ import annotations

import os
import platform
import threading
import time
from collections.abc import AsyncIterator, Iterator, Mapping
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from typing import Any

import httpx

from deepinfra._exceptions import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    MaxRetriesExceededError,
    exception_from_response,
)
from deepinfra._utils import backoff_delays
from deepinfra._version import __version__

DEFAULT_BASE_URL = "https://api.deepinfra.com"
DEFAULT_TIMEOUT = 60.0
DEFAULT_MAX_RETRIES = 2
_RETRYABLE_STATUSES = frozenset({502, 503, 504})

USER_AGENT = (
    f"deepinfra-python/{__version__}"
    f" python/{platform.python_version()} httpx/{httpx.__version__}"
)


@dataclass(frozen=True)
class RequestSpec:
    """A single API operation, independent of sync/async execution.

    path is relative to the client base URL, or a full absolute URL
    (the legacy inference wrappers pass absolute endpoint URLs).
    retry_connect: retry on transport errors (and, for GETs, 502/503/504).
    """

    method: str
    path: str
    params: Mapping[str, Any] | None = None
    json: Any = None
    content: bytes | None = None
    data: Mapping[str, Any] | None = None
    files: Mapping[str, Any] | None = None
    headers: Mapping[str, str] | None = None
    retry_connect: bool = False
    timeout: float | None = None


class DeepInfraClient:
    """Holds auth/base-url config and lazily-created httpx clients.

    The sync and async httpx clients are only instantiated on first use, so
    sync-only callers never create an event-loop-bound client and vice versa.

    The async client's connection pool is bound to the event loop that first
    uses it. Reusing one DeepInfraClient across event loops (e.g. calling
    asyncio.run() several times against the module-level default client) can
    fail with "Event loop is closed"; call aclose() before the loop exits, or
    create one client per loop.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self._api_key = api_key
        self.base_url = (
            base_url or os.getenv("DEEPINFRA_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._sync_client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None
        self._lock = threading.Lock()

    @property
    def api_key(self) -> str:
        if self._api_key is None:
            self._api_key = os.getenv("DEEPINFRA_API_KEY")
        if self._api_key is None:
            raise AuthenticationError()
        return self._api_key

    def close(self) -> None:
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None

    async def aclose(self) -> None:
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

    # -- request execution --

    def request(self, spec: RequestSpec) -> httpx.Response:
        delays = backoff_delays()
        for attempt in range(self.max_retries + 1):
            try:
                response = self._sync().request(**self._request_kwargs(spec))
            except httpx.TransportError as exc:
                error = _map_transport_error(exc)
            else:
                if self._should_retry_status(spec, response, attempt):
                    time.sleep(next(delays))
                    continue
                return self._checked(response)
            if spec.retry_connect and attempt < self.max_retries:
                time.sleep(next(delays))
                continue
            raise self._final_error(spec, error, attempt)
        raise AssertionError("unreachable")

    async def arequest(self, spec: RequestSpec) -> httpx.Response:
        import asyncio

        delays = backoff_delays()
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._async().request(**self._request_kwargs(spec))
            except httpx.TransportError as exc:
                error = _map_transport_error(exc)
            else:
                if self._should_retry_status(spec, response, attempt):
                    await asyncio.sleep(next(delays))
                    continue
                return self._checked(response)
            if spec.retry_connect and attempt < self.max_retries:
                await asyncio.sleep(next(delays))
                continue
            raise self._final_error(spec, error, attempt)
        raise AssertionError("unreachable")

    @contextmanager
    def stream(self, spec: RequestSpec) -> Iterator[httpx.Response]:
        """Issue a streaming request; error statuses raise before yielding.

        Streaming requests are never retried (exec is not idempotent).
        """
        client = self._sync()
        request = client.build_request(**self._request_kwargs(spec))
        try:
            response = client.send(request, stream=True)
        except httpx.TransportError as exc:
            raise _map_transport_error(exc) from exc
        try:
            if response.is_error:
                response.read()
                raise exception_from_response(response)
            yield response
        finally:
            response.close()

    @asynccontextmanager
    async def astream(self, spec: RequestSpec) -> AsyncIterator[httpx.Response]:
        client = self._async()
        request = client.build_request(**self._request_kwargs(spec))
        try:
            response = await client.send(request, stream=True)
        except httpx.TransportError as exc:
            raise _map_transport_error(exc) from exc
        try:
            if response.is_error:
                await response.aread()
                raise exception_from_response(response)
            yield response
        finally:
            await response.aclose()

    # -- internals --

    def _request_kwargs(self, spec: RequestSpec) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": USER_AGENT,
        }
        if spec.headers:
            headers.update(spec.headers)
        url = spec.path
        if not url.startswith(("http://", "https://")):
            url = self.base_url + url
        kwargs: dict[str, Any] = {
            "method": spec.method,
            "url": url,
            "headers": headers,
        }
        if spec.params is not None:
            kwargs["params"] = spec.params
        if spec.json is not None:
            kwargs["json"] = spec.json
        if spec.content is not None:
            kwargs["content"] = spec.content
        if spec.data is not None:
            kwargs["data"] = spec.data
        if spec.files is not None:
            kwargs["files"] = spec.files
        if spec.timeout is not None:
            kwargs["timeout"] = spec.timeout
        return kwargs

    def _should_retry_status(
        self, spec: RequestSpec, response: httpx.Response, attempt: int
    ) -> bool:
        # Status-code retries only for GETs: a 502/503/504 on a POST may have
        # already had a side effect (created a sandbox, billed an inference).
        return (
            spec.retry_connect
            and spec.method == "GET"
            and response.status_code in _RETRYABLE_STATUSES
            and attempt < self.max_retries
        )

    @staticmethod
    def _checked(response: httpx.Response) -> httpx.Response:
        if response.is_error:
            raise exception_from_response(response)
        return response

    def _final_error(
        self, spec: RequestSpec, error: APIConnectionError, attempt: int
    ) -> APIConnectionError:
        if spec.retry_connect and attempt >= self.max_retries:
            return MaxRetriesExceededError(
                f"Maximum retries exceeded ({self.max_retries}): {error}"
            )
        return error

    def _sync(self) -> httpx.Client:
        if self._sync_client is None:
            with self._lock:
                if self._sync_client is None:
                    self._sync_client = httpx.Client(
                        timeout=self.timeout, limits=_default_limits()
                    )
        return self._sync_client

    def _async(self) -> httpx.AsyncClient:
        if self._async_client is None:
            with self._lock:
                if self._async_client is None:
                    self._async_client = httpx.AsyncClient(
                        timeout=self.timeout, limits=_default_limits()
                    )
        return self._async_client


def _map_transport_error(exc: httpx.TransportError) -> APIConnectionError:
    if isinstance(exc, httpx.TimeoutException):
        return APITimeoutError(str(exc) or "Request timed out")
    return APIConnectionError(str(exc) or "Connection error")


def _default_limits() -> httpx.Limits:
    return httpx.Limits(max_connections=20, max_keepalive_connections=10)


_default_client: DeepInfraClient | None = None
_default_client_lock = threading.Lock()


def default_client() -> DeepInfraClient:
    """Lazy process-wide client backing zero-config Sandbox.create() etc."""
    global _default_client
    if _default_client is None:
        with _default_client_lock:
            if _default_client is None:
                _default_client = DeepInfraClient()
    return _default_client
