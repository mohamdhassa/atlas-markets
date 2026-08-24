import pytest
pytest.importorskip("redis")
from fastapi.testclient import TestClient
import app.api.health as health_module
from app.main import app
client=TestClient(app)
def test_root_endpoint_serves_frontend():
    r=client.get("/");assert r.status_code==200;assert "ATLAS MARKETS" in r.text;assert "/static/app.js" in r.text;assert "/static/phase17.js" in r.text;assert "/static/phase18.js" in r.text;assert "/static/phase19.js" in r.text;assert "/static/phase20.js" in r.text;assert "/static/phase21.js" in r.text;assert "/static/phase21-credentials.js" in r.text;assert "/static/phase21.css" in r.text;assert "/static/phase22.js" in r.text;assert "/static/phase23.js" in r.text;assert "/static/phase23.css" in r.text;assert "/static/phase24-integrations.js" in r.text;assert "/static/phase24.css" in r.text;assert "/static/phase25.js" in r.text;assert "/static/phase25.css" in r.text
def test_system_info_endpoint():
    r=client.get("/api/system");assert r.status_code==200;p=r.json();assert p["name"]=="ATLAS MARKETS";assert p["phase"]=="25";assert p["broker_accounts"]=="BYBIT+MT5_FUSION+IBKR";assert p["live_execution"]=="GATED";assert p["provider_switching"]=="FRONTEND";assert p["historical_learning"]=="ACTIVE";assert "METALS" in p["market_scope"]
def test_health_ok(monkeypatch):
    monkeypatch.setattr(health_module,"check_database",lambda:(True,None));monkeypatch.setattr(health_module,"check_redis",lambda:(True,None));r=client.get("/health");assert r.status_code==200;assert r.json()["status"]=="ok"
def test_health_degraded(monkeypatch):
    monkeypatch.setattr(health_module,"check_database",lambda:(False,"OperationalError"));monkeypatch.setattr(health_module,"check_redis",lambda:(True,None));r=client.get("/health");assert r.status_code==503;assert r.json()["status"]=="degraded"
