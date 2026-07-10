import json

import httpx
import pytest
import respx

from deepinfra import (
    NotFoundError,
    Sandbox,
    SandboxFailedError,
    SandboxTimeoutError,
    TooManySandboxesError,
)

from .conftest import BASE_URL

SB_ID = "sb_abc"


def _info(state="running", **kw):
    return {
        "sandbox_id": SB_ID,
        "plan": kw.get("plan", "medium"),
        "image": kw.get("image", ""),
        "state": state,
        "tags": kw.get("tags", {}),
        "created_at": 1,
        "provider": "kata-qemu",
    }


@respx.mock
def test_create_waits_until_running(client):
    create = respx.post(f"{BASE_URL}/v1/sandboxes").respond(json={"sandbox_id": SB_ID})
    get = respx.get(f"{BASE_URL}/v1/sandboxes/{SB_ID}")
    get.side_effect = [
        httpx.Response(200, json=_info("creating")),
        httpx.Response(200, json=_info("starting")),
        httpx.Response(200, json=_info("running")),
    ]
    sb = Sandbox.create(plan="medium", timeout="10m", tags={"job": "t"}, client=client)
    assert sb.id == SB_ID
    assert sb.state == "running"
    assert get.call_count == 3
    body = json.loads(create.calls.last.request.content)
    assert body == {
        "image": "",
        "plan": "medium",
        "tags": {"job": "t"},
        "timeout_seconds": 600,
    }


@respx.mock
def test_create_no_wait_populates_fields(client):
    respx.post(f"{BASE_URL}/v1/sandboxes").respond(json={"sandbox_id": SB_ID})
    get = respx.get(f"{BASE_URL}/v1/sandboxes/{SB_ID}").respond(json=_info("creating"))
    sb = Sandbox.create(wait=False, client=client)
    assert sb.id == SB_ID
    assert sb.state == "creating"
    assert sb.plan == "medium"
    assert get.call_count == 1


@respx.mock
def test_sandbox_id_is_url_quoted(client):
    quoted = f"{BASE_URL}/v1/sandboxes/..%2Fmodels"
    get = respx.get(quoted).respond(status_code=404, json={"error": "Sandbox not found"})
    with pytest.raises(NotFoundError):
        Sandbox.from_id("../models", client=client)
    assert get.call_count == 1
    assert get.calls.last.request.url.raw_path.endswith(b"/v1/sandboxes/..%2Fmodels")


def test_from_id_empty_raises(client):
    with pytest.raises(ValueError):
        Sandbox.from_id("", client=client)


@respx.mock
def test_create_failed_state_raises(client):
    respx.post(f"{BASE_URL}/v1/sandboxes").respond(json={"sandbox_id": SB_ID})
    respx.get(f"{BASE_URL}/v1/sandboxes/{SB_ID}").respond(json=_info("failed"))
    with pytest.raises(SandboxFailedError, match="failed"):
        Sandbox.create(client=client)


@respx.mock
def test_wait_timeout_mentions_id(client, monkeypatch):
    respx.post(f"{BASE_URL}/v1/sandboxes").respond(json={"sandbox_id": SB_ID})
    respx.get(f"{BASE_URL}/v1/sandboxes/{SB_ID}").respond(json=_info("creating"))
    with pytest.raises(SandboxTimeoutError, match=SB_ID):
        Sandbox.create(wait_timeout=0.5, client=client)


@respx.mock
def test_create_cap_error(client):
    respx.post(f"{BASE_URL}/v1/sandboxes").respond(
        status_code=429,
        json={"detail": {"error": "You have reached the maximum of 5 active sandboxes"}},
    )
    with pytest.raises(TooManySandboxesError, match="maximum of 5"):
        Sandbox.create(client=client)


@respx.mock
def test_from_id_and_refresh(client):
    get = respx.get(f"{BASE_URL}/v1/sandboxes/{SB_ID}")
    get.side_effect = [
        httpx.Response(200, json=_info("stopped")),
        httpx.Response(200, json=_info("running")),
    ]
    sb = Sandbox.from_id(SB_ID, client=client)
    assert sb.state == "stopped"
    sb.refresh()
    assert sb.state == "running"


@respx.mock
def test_from_id_not_found(client):
    respx.get(f"{BASE_URL}/v1/sandboxes/missing").respond(
        status_code=404, json={"detail": {"error": "Sandbox not found"}}
    )
    with pytest.raises(NotFoundError):
        Sandbox.from_id("missing", client=client)


@respx.mock
def test_list_with_client_side_tag_filter(client):
    respx.get(f"{BASE_URL}/v1/sandboxes").respond(
        json=[
            {**_info(), "sandbox_id": "sb_1", "tags": {"job": "etl", "env": "prod"}},
            {**_info(), "sandbox_id": "sb_2", "tags": {"job": "other"}},
        ]
    )
    all_sbs = Sandbox.list(client=client)
    assert [sb.id for sb in all_sbs] == ["sb_1", "sb_2"]
    filtered = Sandbox.list(tags={"job": "etl"}, client=client)
    assert [sb.id for sb in filtered] == ["sb_1"]


@respx.mock
def test_stop_start_terminate(client):
    stop = respx.post(f"{BASE_URL}/v1/sandboxes/{SB_ID}/stop").respond(json={})
    start = respx.post(f"{BASE_URL}/v1/sandboxes/{SB_ID}/start").respond(json={})
    respx.get(f"{BASE_URL}/v1/sandboxes/{SB_ID}").respond(json=_info("running"))
    delete = respx.delete(f"{BASE_URL}/v1/sandboxes/{SB_ID}").respond(json={})

    sb = Sandbox.from_id(SB_ID, client=client)
    sb.stop()
    sb.start()
    sb.terminate()
    assert stop.call_count == 1
    assert start.call_count == 1
    assert delete.call_count == 1


@respx.mock
def test_context_manager_terminates(client):
    respx.get(f"{BASE_URL}/v1/sandboxes/{SB_ID}").respond(json=_info("running"))
    delete = respx.delete(f"{BASE_URL}/v1/sandboxes/{SB_ID}").respond(json={})
    with Sandbox.from_id(SB_ID, client=client) as sb:
        assert sb.state == "running"
    assert delete.call_count == 1


@respx.mock
def test_context_manager_tolerates_already_deleted(client):
    respx.get(f"{BASE_URL}/v1/sandboxes/{SB_ID}").respond(json=_info("running"))
    respx.delete(f"{BASE_URL}/v1/sandboxes/{SB_ID}").respond(
        status_code=404, json={"error": "Sandbox not found"}
    )
    with Sandbox.from_id(SB_ID, client=client):
        pass


@respx.mock
async def test_async_lifecycle(client):
    respx.post(f"{BASE_URL}/v1/sandboxes").respond(json={"sandbox_id": SB_ID})
    get = respx.get(f"{BASE_URL}/v1/sandboxes/{SB_ID}")
    get.side_effect = [
        httpx.Response(200, json=_info("creating")),
        httpx.Response(200, json=_info("running")),
    ]
    stop = respx.post(f"{BASE_URL}/v1/sandboxes/{SB_ID}/stop").respond(json={})
    delete = respx.delete(f"{BASE_URL}/v1/sandboxes/{SB_ID}").respond(json={})

    sb = await Sandbox.acreate(client=client)
    assert sb.state == "running"
    await sb.astop()
    await sb.aterminate()
    assert stop.call_count == 1
    assert delete.call_count == 1


@respx.mock
async def test_async_context_manager(client):
    respx.get(f"{BASE_URL}/v1/sandboxes/{SB_ID}").respond(json=_info("running"))
    delete = respx.delete(f"{BASE_URL}/v1/sandboxes/{SB_ID}").respond(json={})
    async with await Sandbox.afrom_id(SB_ID, client=client):
        pass
    assert delete.call_count == 1
