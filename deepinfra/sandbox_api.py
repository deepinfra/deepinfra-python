"""DeepInfra Sandboxes: isolated microVMs for running untrusted code.

    from deepinfra import Sandbox

    sb = Sandbox.create(plan="medium", timeout="10m")
    r = sb.exec("bash", "-c", "pip install pandas && python -c 'import pandas'")
    print(r.stdout, r.returncode)
    sb.fs.write("/work/in.csv", b"a,b\n1,2\n")
    data = sb.fs.read("/work/in.csv")
    sb.terminate()

Every network method has an async twin prefixed with "a" (exec/aexec,
create/acreate, ...).
"""

from __future__ import annotations

import builtins
import time
from collections.abc import Mapping
from typing import Any, Union

from ._exceptions import NotFoundError, SandboxFailedError, SandboxTimeoutError
from ._sandbox_models import ExecResult, SandboxInfo
from ._streaming import afold_exec_events, aiter_ndjson, fold_exec_events, iter_ndjson
from ._utils import backoff_delays, parse_duration, tags_match
from .clients.deepinfra import DeepInfraClient, RequestSpec, default_client

_SANDBOXES = "/v1/sandboxes"
_DEFAULT_WAIT_TIMEOUT = 300.0
_DEFAULT_EXEC_TIMEOUT = 60
_EXEC_HTTP_GRACE = 30.0

_RUNNING = "running"
_TERMINAL_STATES = ("failed", "deleted")

Duration = Union[int, float, str]


class Sandbox:
    """Handle to one sandbox. Fields mirror the server; refresh() updates them."""

    def __init__(
        self,
        info: SandboxInfo,
        *,
        client: DeepInfraClient | None = None,
    ) -> None:
        self._info = info
        self._client = client or default_client()
        self.fs = SandboxFS(self)

    # -- cached server fields --

    @property
    def id(self) -> str:
        return self._info.sandbox_id

    @property
    def plan(self) -> str:
        return self._info.plan

    @property
    def image(self) -> str:
        return self._info.image

    @property
    def state(self) -> str:
        return self._info.state

    @property
    def tags(self) -> dict[str, str]:
        return self._info.tags

    @property
    def created_at(self) -> int:
        return self._info.created_at

    @property
    def provider(self) -> str:
        return self._info.provider

    def __repr__(self) -> str:
        return f"Sandbox(id={self.id!r}, state={self.state!r}, plan={self.plan!r})"

    # -- constructors --

    @classmethod
    def create(
        cls,
        *,
        image: str = "",
        plan: str = "",
        timeout: Duration | None = None,
        tags: Mapping[str, str] | None = None,
        wait: bool = True,
        wait_timeout: float = _DEFAULT_WAIT_TIMEOUT,
        client: DeepInfraClient | None = None,
    ) -> Sandbox:
        """Create a sandbox; by default block until it is running."""
        client = client or default_client()
        reply = client.request(cls._create_spec(image, plan, timeout, tags)).json()
        sandbox = cls(SandboxInfo(sandbox_id=reply["sandbox_id"]), client=client)
        if wait:
            sandbox.wait_until_running(timeout=wait_timeout)
        return sandbox

    @classmethod
    async def acreate(
        cls,
        *,
        image: str = "",
        plan: str = "",
        timeout: Duration | None = None,
        tags: Mapping[str, str] | None = None,
        wait: bool = True,
        wait_timeout: float = _DEFAULT_WAIT_TIMEOUT,
        client: DeepInfraClient | None = None,
    ) -> Sandbox:
        client = client or default_client()
        reply = (await client.arequest(cls._create_spec(image, plan, timeout, tags))).json()
        sandbox = cls(SandboxInfo(sandbox_id=reply["sandbox_id"]), client=client)
        if wait:
            await sandbox.await_until_running(timeout=wait_timeout)
        return sandbox

    @classmethod
    def from_id(
        cls, sandbox_id: str, *, client: DeepInfraClient | None = None
    ) -> Sandbox:
        client = client or default_client()
        info = SandboxInfo.model_validate(
            client.request(_get_spec(sandbox_id)).json()
        )
        return cls(info, client=client)

    @classmethod
    async def afrom_id(
        cls, sandbox_id: str, *, client: DeepInfraClient | None = None
    ) -> Sandbox:
        client = client or default_client()
        info = SandboxInfo.model_validate(
            (await client.arequest(_get_spec(sandbox_id))).json()
        )
        return cls(info, client=client)

    @classmethod
    def list(
        cls,
        *,
        tags: Mapping[str, str] | None = None,
        client: DeepInfraClient | None = None,
    ) -> builtins.list[Sandbox]:
        """List this account's sandboxes, optionally filtered by tag subset."""
        client = client or default_client()
        items = client.request(_list_spec()).json()
        return cls._from_list(items, tags, client)

    @classmethod
    async def alist(
        cls,
        *,
        tags: Mapping[str, str] | None = None,
        client: DeepInfraClient | None = None,
    ) -> builtins.list[Sandbox]:
        client = client or default_client()
        items = (await client.arequest(_list_spec())).json()
        return cls._from_list(items, tags, client)

    # -- lifecycle --

    def refresh(self) -> Sandbox:
        self._info = SandboxInfo.model_validate(
            self._client.request(_get_spec(self.id)).json()
        )
        return self

    async def arefresh(self) -> Sandbox:
        self._info = SandboxInfo.model_validate(
            (await self._client.arequest(_get_spec(self.id))).json()
        )
        return self

    def wait_until_running(self, timeout: float = _DEFAULT_WAIT_TIMEOUT) -> Sandbox:
        deadline = time.monotonic() + timeout
        for delay in backoff_delays():
            self.refresh()
            self._check_wait_state()
            if self.state == _RUNNING:
                return self
            if time.monotonic() + delay > deadline:
                raise SandboxTimeoutError(
                    f"Sandbox {self.id} still {self.state} after "
                    f"{timeout:.0f}s (terminate it if unwanted)"
                )
            time.sleep(delay)
        raise AssertionError("unreachable")

    async def await_until_running(
        self, timeout: float = _DEFAULT_WAIT_TIMEOUT
    ) -> Sandbox:
        import asyncio

        deadline = time.monotonic() + timeout
        for delay in backoff_delays():
            await self.arefresh()
            self._check_wait_state()
            if self.state == _RUNNING:
                return self
            if time.monotonic() + delay > deadline:
                raise SandboxTimeoutError(
                    f"Sandbox {self.id} still {self.state} after "
                    f"{timeout:.0f}s (terminate it if unwanted)"
                )
            await asyncio.sleep(delay)
        raise AssertionError("unreachable")

    def stop(self) -> None:
        self._client.request(_op_spec(self.id, "stop"))

    async def astop(self) -> None:
        await self._client.arequest(_op_spec(self.id, "stop"))

    def start(
        self, *, wait: bool = True, wait_timeout: float = _DEFAULT_WAIT_TIMEOUT
    ) -> None:
        self._client.request(_op_spec(self.id, "start"))
        if wait:
            self.wait_until_running(timeout=wait_timeout)

    async def astart(
        self, *, wait: bool = True, wait_timeout: float = _DEFAULT_WAIT_TIMEOUT
    ) -> None:
        await self._client.arequest(_op_spec(self.id, "start"))
        if wait:
            await self.await_until_running(timeout=wait_timeout)

    def terminate(self) -> None:
        self._client.request(_delete_spec(self.id))

    async def aterminate(self) -> None:
        await self._client.arequest(_delete_spec(self.id))

    # -- execution --

    def exec(self, *command: str, timeout: Duration | None = None) -> ExecResult:
        """Run a command and return its aggregated stdout/stderr/returncode."""
        with self._client.stream(self._exec_spec(command, timeout)) as response:
            return fold_exec_events(iter_ndjson(response.iter_lines()))

    async def aexec(
        self, *command: str, timeout: Duration | None = None
    ) -> ExecResult:
        async with self._client.astream(self._exec_spec(command, timeout)) as response:
            return await afold_exec_events(aiter_ndjson(response.aiter_lines()))

    def run_python(self, code: str, *, timeout: Duration | None = None) -> ExecResult:
        """Run a Python snippet (python3 -c).

        For large scripts prefer fs.write("/work/script.py", code) +
        exec("python3", "/work/script.py").
        """
        return self.exec("python3", "-c", code, timeout=timeout)

    async def arun_python(
        self, code: str, *, timeout: Duration | None = None
    ) -> ExecResult:
        return await self.aexec("python3", "-c", code, timeout=timeout)

    # -- context managers (terminate on exit) --

    def __enter__(self) -> Sandbox:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        try:
            self.terminate()
        except NotFoundError:
            pass

    async def __aenter__(self) -> Sandbox:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        try:
            await self.aterminate()
        except NotFoundError:
            pass

    # -- internals --

    def _check_wait_state(self) -> None:
        if self.state in _TERMINAL_STATES:
            raise SandboxFailedError(
                f"Sandbox {self.id} entered state {self.state!r}"
            )

    def _exec_spec(
        self, command: tuple[str, ...], timeout: Duration | None
    ) -> RequestSpec:
        if not command:
            raise ValueError("exec() needs at least one command argument")
        timeout_seconds = parse_duration(timeout) if timeout is not None else 0
        # Read timeout outlives the server-side command timeout so the
        # server's kill surfaces as a terminal error line, not a socket error.
        http_timeout = (timeout_seconds or _DEFAULT_EXEC_TIMEOUT) + _EXEC_HTTP_GRACE
        return RequestSpec(
            "POST",
            f"{_SANDBOXES}/{self.id}/exec",
            json={"command": list(command), "timeout_seconds": timeout_seconds},
            timeout=http_timeout,
        )

    @staticmethod
    def _create_spec(
        image: str,
        plan: str,
        timeout: Duration | None,
        tags: Mapping[str, str] | None,
    ) -> RequestSpec:
        return RequestSpec(
            "POST",
            _SANDBOXES,
            json={
                "image": image,
                "plan": plan,
                "tags": dict(tags or {}),
                "timeout_seconds": parse_duration(timeout) if timeout is not None else 0,
            },
        )

    @classmethod
    def _from_list(
        cls,
        items: builtins.list[dict[str, Any]],
        tags: Mapping[str, str] | None,
        client: DeepInfraClient,
    ) -> builtins.list[Sandbox]:
        sandboxes = [
            cls(SandboxInfo.model_validate(item), client=client) for item in items
        ]
        if tags:
            sandboxes = [sb for sb in sandboxes if tags_match(tags, sb.tags)]
        return sandboxes


class SandboxFS:
    """File transfer to/from a sandbox (absolute paths inside the guest)."""

    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox

    def write(self, path: str, data: bytes | str) -> None:
        self._client.request(self._write_spec(path, data))

    async def awrite(self, path: str, data: bytes | str) -> None:
        await self._client.arequest(self._write_spec(path, data))

    def read(self, path: str) -> bytes:
        return self._client.request(self._read_spec(path)).content

    async def aread(self, path: str) -> bytes:
        return (await self._client.arequest(self._read_spec(path))).content

    @property
    def _client(self) -> DeepInfraClient:
        return self._sandbox._client

    def _write_spec(self, path: str, data: bytes | str) -> RequestSpec:
        if isinstance(data, str):
            data = data.encode("utf-8")
        return RequestSpec(
            "PUT",
            self._content_path(),
            params={"path": path},
            content=data,
            headers={"Content-Type": "application/octet-stream"},
        )

    def _read_spec(self, path: str) -> RequestSpec:
        return RequestSpec("GET", self._content_path(), params={"path": path})

    def _content_path(self) -> str:
        return f"{_SANDBOXES}/{self._sandbox.id}/fs/content"


def _get_spec(sandbox_id: str) -> RequestSpec:
    return RequestSpec("GET", f"{_SANDBOXES}/{sandbox_id}", retry_connect=True)


def _list_spec() -> RequestSpec:
    return RequestSpec("GET", _SANDBOXES, retry_connect=True)


def _op_spec(sandbox_id: str, op: str) -> RequestSpec:
    return RequestSpec("POST", f"{_SANDBOXES}/{sandbox_id}/{op}")


def _delete_spec(sandbox_id: str) -> RequestSpec:
    return RequestSpec("DELETE", f"{_SANDBOXES}/{sandbox_id}")
