import json

import httpx
import pytest
import respx

from deepinfra import CommandFailedError, ConflictError, Sandbox, SandboxExecError
from deepinfra._sandbox_models import SandboxInfo
from deepinfra._streaming import fold_exec_events, iter_ndjson

from .conftest import BASE_URL

SB_ID = "sb_test123"


def _sandbox(client):
    return Sandbox(SandboxInfo(sandbox_id=SB_ID, state="running"), client=client)


def _ndjson(*events):
    return "".join(json.dumps(e) + "\n" for e in events)


@respx.mock
def test_exec_aggregates_stream(client):
    route = respx.post(f"{BASE_URL}/v1/sandboxes/{SB_ID}/exec").respond(
        text=_ndjson(
            {"stdout": "hello "},
            {"stderr": "warn\n"},
            {"stdout": "world"},
            {},  # heartbeat
            {"returncode": 0},
        ),
        content_type="application/x-ndjson",
    )
    result = _sandbox(client).exec("bash", "-c", "echo hello world")
    assert result.stdout == "hello world"
    assert result.stderr == "warn\n"
    assert result.returncode == 0
    body = json.loads(route.calls.last.request.content)
    assert body == {"command": ["bash", "-c", "echo hello world"], "timeout_seconds": 0}


@respx.mock
def test_exec_timeout_param_and_check(client):
    route = respx.post(f"{BASE_URL}/v1/sandboxes/{SB_ID}/exec").respond(
        text=_ndjson({"stderr": "boom"}, {"returncode": 3}),
    )
    result = _sandbox(client).exec("false", timeout="2m")
    assert result.returncode == 3
    with pytest.raises(CommandFailedError, match="code 3"):
        result.check()
    body = json.loads(route.calls.last.request.content)
    assert body["timeout_seconds"] == 120


@respx.mock
def test_exec_mid_stream_error(client):
    respx.post(f"{BASE_URL}/v1/sandboxes/{SB_ID}/exec").respond(
        text=_ndjson({"stdout": "partial"}, {"error": "sandbox died"}),
    )
    with pytest.raises(SandboxExecError, match="sandbox died"):
        _sandbox(client).exec("sleep", "100")


@respx.mock
def test_exec_missing_terminal_line(client):
    respx.post(f"{BASE_URL}/v1/sandboxes/{SB_ID}/exec").respond(
        text=_ndjson({"stdout": "partial"}),
    )
    with pytest.raises(SandboxExecError, match="without a return code"):
        _sandbox(client).exec("true")


@respx.mock
def test_exec_pre_stream_http_error(client):
    respx.post(f"{BASE_URL}/v1/sandboxes/{SB_ID}/exec").respond(
        status_code=409, json={"detail": {"error": "Sandbox is stopped, not running"}}
    )
    with pytest.raises(ConflictError, match="not running"):
        _sandbox(client).exec("true")


@respx.mock
def test_run_python_wraps_exec(client):
    route = respx.post(f"{BASE_URL}/v1/sandboxes/{SB_ID}/exec").respond(
        text=_ndjson({"stdout": "2\n"}, {"returncode": 0}),
    )
    result = _sandbox(client).run_python("print(1+1)")
    assert result.stdout == "2\n"
    body = json.loads(route.calls.last.request.content)
    assert body["command"] == ["python3", "-c", "print(1+1)"]


def test_exec_requires_command(client):
    with pytest.raises(ValueError):
        _sandbox(client).exec()


def test_fold_handles_split_reads():
    # Lines arriving fragmented across reads are reassembled by iter_lines;
    # fold only sees whole lines. Simulate the folded path directly.
    lines = ['{"stdout": "a"}', "", '{"stdout": "b"}', '{"returncode": 1}']
    result = fold_exec_events(iter_ndjson(lines))
    assert result.stdout == "ab"
    assert result.returncode == 1


@respx.mock
async def test_aexec(client):
    respx.post(f"{BASE_URL}/v1/sandboxes/{SB_ID}/exec").respond(
        text=_ndjson({"stdout": "async"}, {"returncode": 0}),
    )
    result = await _sandbox(client).aexec("echo", "async")
    assert result.stdout == "async"
    assert result.returncode == 0


@respx.mock
async def test_arun_python_error(client):
    respx.post(f"{BASE_URL}/v1/sandboxes/{SB_ID}/exec").respond(
        text=_ndjson({"error": "gone"}),
    )
    with pytest.raises(SandboxExecError, match="gone"):
        await _sandbox(client).arun_python("print(1)")


@respx.mock
def test_exec_http_read_timeout_derived(client):
    captured = {}

    def _capture(request):
        captured["timeout"] = request.extensions.get("timeout")
        return httpx.Response(200, text=_ndjson({"returncode": 0}))

    respx.post(f"{BASE_URL}/v1/sandboxes/{SB_ID}/exec").mock(side_effect=_capture)
    _sandbox(client).exec("true", timeout=600)
    assert captured["timeout"]["read"] == 630.0
