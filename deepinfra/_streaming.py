"""NDJSON decoding for the sandbox exec stream.

The wire format is one JSON object per line:
    {"stdout": "chunk"} / {"stderr": "chunk"}   interleaved output
    {"returncode": 0}                            terminal line
    {"error": "message"}                         terminal line on failure
    {}                                           heartbeat (ignored)
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterable, Iterator
from typing import Any

from ._exceptions import SandboxExecError
from ._sandbox_models import ExecResult


def _parse_event(line: str) -> dict[str, Any] | None:
    """Decode one NDJSON line; None for blank lines and {} heartbeats."""
    line = line.strip()
    if not line:
        return None
    event = json.loads(line)
    if isinstance(event, dict) and event:
        return event
    return None


def iter_ndjson(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    for line in lines:
        event = _parse_event(line)
        if event is not None:
            yield event


async def aiter_ndjson(lines: AsyncIterator[str]) -> AsyncIterator[dict[str, Any]]:
    async for line in lines:
        event = _parse_event(line)
        if event is not None:
            yield event


class _ExecFolder:
    """Accumulate exec-stream events into an ExecResult."""

    def __init__(self) -> None:
        self._stdout: list[str] = []
        self._stderr: list[str] = []
        self._returncode: int | None = None

    def feed(self, event: dict[str, Any]) -> None:
        if "error" in event:
            raise SandboxExecError(str(event["error"]))
        if "stdout" in event:
            self._stdout.append(event["stdout"])
        if "stderr" in event:
            self._stderr.append(event["stderr"])
        if "returncode" in event:
            self._returncode = int(event["returncode"])

    def result(self) -> ExecResult:
        if self._returncode is None:
            raise SandboxExecError("Exec stream ended without a return code")
        return ExecResult(
            stdout="".join(self._stdout),
            stderr="".join(self._stderr),
            returncode=self._returncode,
        )


def fold_exec_events(events: Iterable[dict[str, Any]]) -> ExecResult:
    folder = _ExecFolder()
    for event in events:
        folder.feed(event)
    return folder.result()


async def afold_exec_events(events: AsyncIterator[dict[str, Any]]) -> ExecResult:
    folder = _ExecFolder()
    async for event in events:
        folder.feed(event)
    return folder.result()
