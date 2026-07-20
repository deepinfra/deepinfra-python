import httpx
import pytest
import respx

from deepinfra import (
    APITimeoutError,
    AuthenticationError,
    CapacityError,
    ConflictError,
    MaxRetriesExceededError,
    NotFoundError,
    RateLimitError,
    TooManySandboxesError,
)
from deepinfra._exceptions import APIConnectionError, APIStatusError, InternalServerError
from deepinfra.clients.deepinfra import USER_AGENT, DeepInfraClient, RequestSpec

from .conftest import API_KEY, BASE_URL


@respx.mock
def test_auth_and_user_agent_headers(client):
    route = respx.get(f"{BASE_URL}/v1/sandboxes").respond(json=[])
    client.request(RequestSpec("GET", "/v1/sandboxes"))
    request = route.calls.last.request
    assert request.headers["Authorization"] == f"Bearer {API_KEY}"
    assert request.headers["User-Agent"] == USER_AGENT
    assert USER_AGENT.startswith("deepinfra-python/")


def test_api_key_from_env(monkeypatch):
    monkeypatch.setenv("DEEPINFRA_API_KEY", "env-key")
    assert DeepInfraClient().api_key == "env-key"


def test_missing_api_key_raises_with_hint(monkeypatch):
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
    with pytest.raises(AuthenticationError, match="DEEPINFRA_API_KEY"):
        _ = DeepInfraClient().api_key


def test_base_url_from_env(monkeypatch):
    monkeypatch.setenv("DEEPINFRA_BASE_URL", "https://example.deepinfra.com/")
    assert DeepInfraClient("k").base_url == "https://example.deepinfra.com"


@pytest.mark.parametrize(
    "status,exc",
    [
        (401, AuthenticationError),
        (404, NotFoundError),
        (409, ConflictError),
        (429, RateLimitError),
        (503, CapacityError),
        (500, InternalServerError),
        (418, APIStatusError),
    ],
)
@pytest.mark.parametrize(
    "body",
    [
        {"error": "boom"},
        {"detail": {"error": "boom"}},
        {"detail": "boom"},
        {"error": {"message": "boom"}},
    ],
)
@respx.mock
def test_error_mapping_and_body_shapes(client, status, exc, body):
    respx.get(f"{BASE_URL}/x").respond(status_code=status, json=body)
    with pytest.raises(exc) as excinfo:
        client.request(RequestSpec("GET", "/x"))
    assert excinfo.value.status_code == status
    assert excinfo.value.message == "boom"


@respx.mock
def test_error_non_json_body(client):
    respx.get(f"{BASE_URL}/x").respond(status_code=502, text="bad gateway page")
    with pytest.raises(InternalServerError, match="bad gateway page"):
        client.request(RequestSpec("GET", "/x"))


@respx.mock
def test_get_retries_connect_errors(client):
    route = respx.get(f"{BASE_URL}/x")
    route.side_effect = [httpx.ConnectError("refused"), httpx.Response(200, json={"ok": 1})]
    response = client.request(RequestSpec("GET", "/x", retry_connect=True))
    assert response.json() == {"ok": 1}
    assert route.call_count == 2


@respx.mock
def test_get_retries_502(client):
    route = respx.get(f"{BASE_URL}/x")
    route.side_effect = [httpx.Response(502), httpx.Response(200, json={})]
    client.request(RequestSpec("GET", "/x", retry_connect=True))
    assert route.call_count == 2


@respx.mock
def test_post_never_retries_502(client):
    route = respx.post(f"{BASE_URL}/x").respond(status_code=502)
    with pytest.raises(InternalServerError):
        client.request(RequestSpec("POST", "/x", retry_connect=True))
    assert route.call_count == 1


@respx.mock
def test_post_retries_connect_errors_when_marked(client):
    route = respx.post(f"{BASE_URL}/x")
    route.side_effect = [httpx.ConnectError("refused"), httpx.Response(200, json={})]
    client.request(RequestSpec("POST", "/x", retry_connect=True))
    assert route.call_count == 2


@respx.mock
def test_unmarked_request_never_retries(client):
    route = respx.post(f"{BASE_URL}/x")
    route.side_effect = httpx.ConnectError("refused")
    with pytest.raises(APIConnectionError):
        client.request(RequestSpec("POST", "/x"))
    assert route.call_count == 1


@respx.mock
def test_retries_exhausted_raises_max_retries(client):
    route = respx.get(f"{BASE_URL}/x")
    route.side_effect = httpx.ConnectError("refused")
    with pytest.raises(MaxRetriesExceededError):
        client.request(RequestSpec("GET", "/x", retry_connect=True))
    assert route.call_count == client.max_retries + 1


def test_legacy_exception_compat():
    assert issubclass(MaxRetriesExceededError, APIConnectionError)
    from deepinfra.exceptions import MaxRetriesExceededError as legacy

    assert legacy is MaxRetriesExceededError
    assert TooManySandboxesError is RateLimitError


@respx.mock
def test_timeout_maps_to_api_timeout_error(client):
    respx.get(f"{BASE_URL}/x").side_effect = httpx.ReadTimeout("too slow")
    with pytest.raises(APITimeoutError):
        client.request(RequestSpec("GET", "/x"))
    assert issubclass(APITimeoutError, APIConnectionError)


@respx.mock
def test_absolute_url_bypasses_base_url(client):
    route = respx.post("https://other.example.com/v1/inference/m").respond(json={})
    client.request(RequestSpec("POST", "https://other.example.com/v1/inference/m"))
    assert route.call_count == 1


@respx.mock
async def test_async_get_retries_connect_errors(client):
    route = respx.get(f"{BASE_URL}/x")
    route.side_effect = [httpx.ConnectError("refused"), httpx.Response(200, json={"ok": 1})]
    response = await client.arequest(RequestSpec("GET", "/x", retry_connect=True))
    assert response.json() == {"ok": 1}
    assert route.call_count == 2
    await client.aclose()


@respx.mock
async def test_async_get_retries_502(client):
    route = respx.get(f"{BASE_URL}/x")
    route.side_effect = [httpx.Response(502), httpx.Response(200, json={})]
    await client.arequest(RequestSpec("GET", "/x", retry_connect=True))
    assert route.call_count == 2
    await client.aclose()


@respx.mock
async def test_async_retries_exhausted_raises_max_retries(client):
    route = respx.get(f"{BASE_URL}/x")
    route.side_effect = httpx.ConnectError("refused")
    with pytest.raises(MaxRetriesExceededError):
        await client.arequest(RequestSpec("GET", "/x", retry_connect=True))
    assert route.call_count == client.max_retries + 1
    await client.aclose()


@respx.mock
async def test_async_request_and_errors(client):
    respx.get(f"{BASE_URL}/x").respond(json={"ok": 1})
    respx.get(f"{BASE_URL}/missing").respond(status_code=404, json={"error": "nope"})
    response = await client.arequest(RequestSpec("GET", "/x"))
    assert response.json() == {"ok": 1}
    with pytest.raises(NotFoundError, match="nope"):
        await client.arequest(RequestSpec("GET", "/missing"))
    await client.aclose()
