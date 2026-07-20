import pytest

from deepinfra.clients.deepinfra import DeepInfraClient

BASE_URL = "https://api.deepinfra.com"
API_KEY = "test-key"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
    monkeypatch.delenv("DEEPINFRA_BASE_URL", raising=False)
    c = DeepInfraClient(API_KEY)
    yield c
    c.close()


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _s: None)

    async def _async_noop(_s):
        pass

    monkeypatch.setattr("asyncio.sleep", _async_noop)
