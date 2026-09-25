import asyncio
from pathlib import Path

import httpx

from app.brokers.ibkr_bridge import IbkrBridgeClient


def test_ibkr_safe_get_retries_gateway_timeout(monkeypatch):
    calls = []

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, **kwargs):
            calls.append(url)
            request = httpx.Request("GET", url)
            return httpx.Response(504, request=request)

    async def no_sleep(_):
        return None

    monkeypatch.setattr("app.brokers.ibkr_bridge.httpx.AsyncClient", Client)
    monkeypatch.setattr("app.brokers.ibkr_bridge.asyncio.sleep", no_sleep)
    client = IbkrBridgeClient("http://ibkr-bridge")
    try:
        asyncio.run(client.account())
    except httpx.HTTPStatusError as exc:
        assert exc.response.status_code == 504
    else:
        raise AssertionError("expected the exhausted read to fail")
    assert calls == ["http://ibkr-bridge/account"] * 3


def test_ibkr_post_is_never_automatically_retried():
    source = Path("app/brokers/ibkr_bridge.py").read_text()
    post_body = source.split("async def _post", 1)[1].split("async def health", 1)[0]
    assert "for attempt" not in post_body


def test_watchdog_requires_account_round_trip():
    source = Path("ops/ibkr_bridge_watchdog.sh").read_text()
    assert "BRIDGE_ACCOUNT_URL" in source
    assert 'account_probe=passed' in source
    assert 'd.get("account_id")' in source
    assert 'd.get("simulation") is True' in source
