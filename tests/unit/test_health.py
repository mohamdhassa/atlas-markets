import pytest
pytest.importorskip("redis")
from fastapi.testclient import TestClient
import app.api.health as health_module
from app.main import app
client=TestClient(app)
def test_root_endpoint_serves_frontend():
    r=client.get("/");assert r.status_code==200;assert "ATLAS MARKETS" in r.text;assert "/static/app.js" in r.text;assert "/static/phase6.css" in r.text;assert "/static/phase7.js" in r.text;assert "/static/phase8.js" in r.text
def test_system_info_endpoint():
    r=client.get("/api/system");assert r.status_code==200;p=r.json();assert p["name"]=="ATLAS MARKETS";assert p["phase"]=="9"
def test_health_ok(monkeypatch):
    monkeypatch.setattr(health_module,"check_database",lambda:(True,None));monkeypatch.setattr(health_module,"check_redis",lambda:(True,None));r=client.get("/health");assert r.status_code==200;p=r.json();assert p["status"]=="ok";assert p["dependencies"]["database"]["status"]=="ok";assert p["dependencies"]["redis"]["status"]=="ok"
def test_health_degraded(monkeypatch):
    monkeypatch.setattr(health_module,"check_database",lambda:(False,"OperationalError"));monkeypatch.setattr(health_module,"check_redis",lambda:(True,None));r=client.get("/health");assert r.status_code==503;p=r.json();assert p["status"]=="degraded";assert p["dependencies"]["database"]["status"]=="error"
