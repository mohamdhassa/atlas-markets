import pytest
pytest.importorskip("redis")
from fastapi.testclient import TestClient
import app.api.health as health_module
from app.main import app

client = TestClient(app)


def test_root_endpoint_serves_consolidated_frontend():
    r = client.get("/")
    assert r.status_code == 200
    assert "ATLAS MARKETS" in r.text
    assert "/static/app.js?v=53.0" in r.text
    assert "/static/atlas-core.js?v=53.0" in r.text
    assert "/static/phase17.js" not in r.text
    assert "/static/phase38-operations.js" not in r.text
    assert "/static/phase49-live-certification.js" not in r.text


def test_system_info_endpoint():
    r = client.get("/api/system")
    assert r.status_code == 200
    p = r.json()
    assert p["name"] == "ATLAS MARKETS"
    assert p["version"] == "2.0.0"
    assert p["architecture"] == "CONSOLIDATED_CORE"
    assert p["account_model"] == "MULTI_USER_EXTERNAL_PROVIDERS"
    assert p["roles"] == ["ADMIN", "USER"]
    assert "BYBIT" in p["providers"]
    assert "IBKR" in p["providers"]
    assert p["execution_policy"] == "CERTIFIED_ROUTES_ONLY"
    assert p["live_money_policy"] == "EXPLICITLY_GATED"
    assert "VERIFIED_ATTRIBUTION" in p["analytics"]
    assert "METALS" in p["market_scope"]


def test_health_ok(monkeypatch):
    monkeypatch.setattr(health_module, "check_database", lambda: (True, None))
    monkeypatch.setattr(health_module, "check_redis", lambda: (True, None))
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_degraded(monkeypatch):
    monkeypatch.setattr(health_module, "check_database", lambda: (False, "OperationalError"))
    monkeypatch.setattr(health_module, "check_redis", lambda: (True, None))
    r = client.get("/health")
    assert r.status_code == 503
    assert r.json()["status"] == "degraded"
