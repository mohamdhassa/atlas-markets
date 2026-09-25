import asyncio
from pathlib import Path

import httpx

from app.brokers.mt5_bridge import Mt5BridgeClient, Mt5BridgeError
from app.main import app
from app.services import mt5_runtime


def test_mt5_readiness_route_is_registered():
    assert "/mt5/readiness" in {getattr(route, "path", None) for route in app.routes}


def test_mt5_runtime_reports_pending_without_central_url(monkeypatch):
    monkeypatch.setattr(mt5_runtime, "get_settings", lambda: type("S", (), {"mt5_bridge_url": ""})())
    result = asyncio.run(mt5_runtime.mt5_runtime_readiness())
    assert result["status"] == "PENDING_CONFIGURATION"
    assert result["blockers"] == ["MT5_BRIDGE_URL_NOT_CONFIGURED"]


def test_mt5_symbol_response_is_flattened(monkeypatch):
    client = Mt5BridgeClient("http://mt5.internal", "secret")

    async def fake_get(path):
        assert path == "/symbol/EURUSD"
        return {"symbol": "EURUSD", "info": {"trade_contract_size": 100000}, "tick": {"bid": 1.1, "ask": 1.2}}

    monkeypatch.setattr(client, "_get", fake_get)
    result = asyncio.run(client.symbol("eur/usd"))
    assert result == {"symbol": "EURUSD", "trade_contract_size": 100000, "bid": 1.1, "ask": 1.2}


def test_mt5_get_retries_gateway_failures_but_post_does_not(monkeypatch):
    calls = []

    class Response:
        status_code = 504

        def raise_for_status(self):
            request = httpx.Request("GET", "http://mt5.internal/health")
            raise httpx.HTTPStatusError("gateway timeout", request=request, response=httpx.Response(504, request=request))

        def json(self):
            return {}

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def request(self, method, url, **kwargs):
            calls.append(method)
            return Response()

    async def no_sleep(_):
        return None

    monkeypatch.setattr("app.brokers.mt5_bridge.httpx.AsyncClient", Client)
    monkeypatch.setattr("app.brokers.mt5_bridge.asyncio.sleep", no_sleep)
    client = Mt5BridgeClient("http://mt5.internal")
    try:
        asyncio.run(client.health())
    except Mt5BridgeError:
        pass
    assert calls == ["GET", "GET", "GET"]

    calls.clear()
    try:
        asyncio.run(client.order_check({"symbol": "EURUSD"}))
    except Mt5BridgeError:
        pass
    assert calls == ["POST"]


def test_application_mt5_paths_use_central_runtime():
    root = Path(__file__).parents[2]
    offenders = []
    for path in [*(root / "app" / "api").glob("*.py"), *(root / "app" / "services").glob("*.py")]:
        if path.name == "mt5_runtime.py":
            continue
        text = path.read_text()
        if "http://host.docker.internal:8765" in text:
            offenders.append(str(path.relative_to(root)))
    assert offenders == []


def test_mt5_account_sync_counts_payload_lists():
    source = (Path(__file__).parents[2] / "app" / "api" / "routes_accounts.py").read_text()
    assert "len(positions.get('list') or [])" in source
    assert "len(orders.get('list') or [])" in source
