"""Exception hierarchy for the DeepInfra SDK."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx

    from ._sandbox_models import ExecResult


class DeepInfraError(Exception):
    """Base class for all errors raised by this SDK."""


class APIConnectionError(DeepInfraError):
    """The request never received a response (DNS, connect, TLS, socket errors)."""

    def __init__(self, message: str = "Connection error") -> None:
        super().__init__(message)


class APITimeoutError(APIConnectionError):
    """The request timed out on the client side."""

    def __init__(self, message: str = "Request timed out") -> None:
        super().__init__(message)


class MaxRetriesExceededError(APIConnectionError):
    """Retries were exhausted without getting a response.

    Kept name-compatible with the pre-0.2 SDK (`deepinfra.exceptions`).
    """

    def __init__(self, message: str = "Maximum retries exceeded") -> None:
        super().__init__(message)


class APIStatusError(DeepInfraError):
    """The API returned a non-success HTTP status code."""

    status_code: int
    message: str
    response: httpx.Response | None

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        response: httpx.Response | None = None,
    ) -> None:
        super().__init__(f"{status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.response = response


class BadRequestError(APIStatusError):
    pass


class AuthenticationError(APIStatusError):
    def __init__(
        self,
        message: str = "No API key provided. Pass api_key= or set the "
        "DEEPINFRA_API_KEY environment variable "
        "(https://deepinfra.com/dash/api_keys).",
        *,
        status_code: int = 401,
        response: httpx.Response | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, response=response)


class PermissionDeniedError(APIStatusError):
    pass


class NotFoundError(APIStatusError):
    pass


class ConflictError(APIStatusError):
    pass


class ContentTooLargeError(APIStatusError):
    pass


class TooManySandboxesError(APIStatusError):
    pass


class CapacityError(APIStatusError):
    pass


class InternalServerError(APIStatusError):
    pass


_STATUS_TO_EXCEPTION: dict[int, type[APIStatusError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    413: ContentTooLargeError,
    429: TooManySandboxesError,
    503: CapacityError,
}


def extract_error_message(body: Any) -> str | None:
    """Pull a human-readable message out of the known API error body shapes.

    Handles ``{"error": "..."}``, the OpenAI-style ``{"error": {"message": ...}}``,
    and FastAPI's ``{"detail": ...}`` wrapping of either.
    """
    if not isinstance(body, dict):
        return None
    for key in ("error", "detail"):
        value = body.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, dict):
            nested = extract_error_message(value) or value.get("message")
            if isinstance(nested, str) and nested:
                return nested
    return None


def exception_from_response(response: httpx.Response) -> APIStatusError:
    """Build the right APIStatusError subclass from an error response."""
    try:
        message = extract_error_message(response.json())
    except Exception:
        message = None
    if not message:
        message = response.text[:500] or response.reason_phrase or "API error"
    status = response.status_code
    cls = _STATUS_TO_EXCEPTION.get(status)
    if cls is None:
        cls = InternalServerError if status >= 500 else APIStatusError
    if cls is AuthenticationError:
        return AuthenticationError(message, status_code=status, response=response)
    return cls(message, status_code=status, response=response)


class SandboxError(DeepInfraError):
    """Base class for sandbox-lifecycle errors raised client-side."""


class SandboxTimeoutError(SandboxError):
    """Waiting for a sandbox state transition timed out."""


class SandboxFailedError(SandboxError):
    """The sandbox entered a terminal failed/deleted state."""


class SandboxExecError(SandboxError):
    """The exec stream reported an error or ended without a return code."""


class CommandFailedError(SandboxError):
    """Raised by ExecResult.check() when the command exited non-zero."""

    result: ExecResult

    def __init__(self, result: ExecResult) -> None:
        stderr_tail = result.stderr[-500:] if result.stderr else ""
        super().__init__(
            f"Command exited with code {result.returncode}"
            + (f": {stderr_tail}" if stderr_tail else "")
        )
        self.result = result
