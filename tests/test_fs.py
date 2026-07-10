import pytest
import respx

from deepinfra import BadRequestError, NotFoundError, Sandbox
from deepinfra._sandbox_models import SandboxInfo

from .conftest import BASE_URL

SB_ID = "sb_fs"
FS_URL = f"{BASE_URL}/v1/sandboxes/{SB_ID}/fs/content"


def _sandbox(client):
    return Sandbox(SandboxInfo(sandbox_id=SB_ID, state="running"), client=client)


@respx.mock
def test_fs_write_bytes(client):
    route = respx.put(FS_URL).respond(json={})
    payload = bytes(range(256))
    _sandbox(client).fs.write("/work/blob.bin", payload)
    request = route.calls.last.request
    assert request.url.params["path"] == "/work/blob.bin"
    assert request.headers["Content-Type"] == "application/octet-stream"
    assert request.content == payload


@respx.mock
def test_fs_write_str_encodes_utf8(client):
    route = respx.put(FS_URL).respond(json={})
    _sandbox(client).fs.write("/work/т.txt", "здрасти")
    assert route.calls.last.request.content == "здрасти".encode()


@respx.mock
def test_fs_read_bytes_roundtrip(client):
    payload = bytes(range(256)) * 3
    respx.get(FS_URL).respond(content=payload, content_type="application/octet-stream")
    assert _sandbox(client).fs.read("/work/blob.bin") == payload


@respx.mock
def test_fs_read_missing_file(client):
    respx.get(FS_URL).respond(status_code=404, json={"detail": {"error": "File not found"}})
    with pytest.raises(NotFoundError, match="File not found"):
        _sandbox(client).fs.read("/nope")


@respx.mock
def test_fs_read_directory_rejected(client):
    respx.get(FS_URL).respond(status_code=400, json={"error": "Is a directory"})
    with pytest.raises(BadRequestError, match="directory"):
        _sandbox(client).fs.read("/work")


@respx.mock
async def test_fs_async_roundtrip(client):
    respx.put(FS_URL).respond(json={})
    respx.get(FS_URL).respond(content=b"abc")
    sb = _sandbox(client)
    await sb.fs.awrite("/work/a", b"abc")
    assert await sb.fs.aread("/work/a") == b"abc"
