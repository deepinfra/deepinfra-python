"""Pydantic models for the sandbox API wire format."""

from __future__ import annotations

import pydantic


class SandboxInfo(pydantic.BaseModel):
    """Server-side view of a sandbox (GET /v1/sandboxes/{id})."""

    sandbox_id: str
    plan: str = ""
    image: str = ""
    state: str = ""
    tags: dict[str, str] = pydantic.Field(default_factory=dict)
    created_at: int = 0
    provider: str = ""

    model_config = pydantic.ConfigDict(extra="ignore")


class SandboxPlan(pydantic.BaseModel):
    """A plan offered by GET /v1/sandboxes/catalog."""

    id: str
    vcpu: int
    ram_gb: int
    disk_gb: int
    price_per_hour: float

    model_config = pydantic.ConfigDict(extra="ignore")


class ExecResult(pydantic.BaseModel):
    """Aggregated result of a sandbox command."""

    stdout: str = ""
    stderr: str = ""
    returncode: int

    def check(self) -> ExecResult:
        """Return self, or raise CommandFailedError if the command exited non-zero."""
        if self.returncode != 0:
            from ._exceptions import CommandFailedError

            raise CommandFailedError(self)
        return self
