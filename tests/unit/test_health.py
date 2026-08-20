import pytest
pytest.importorskip("redis")
from fastapi.testclient import TestClient

import app.api.health as health_module
from app.main import app

client = TestClient(app)


def test_root_endpoint_serves_frontend() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "ATLAS MARKETS" in response.text
    assert "/static/app.js" in response.text


def test_system_info_endpoint() -> None:
    response = client.get("/api/system")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "ATLAS MARKETS"
    assert payload["phase"] == "5"


def test_health_ok(monkeypatch) -> None:
    monkeypatch.setattr(health_module, "check_database", lambda: (True, None))
    monkeypatch.setattr(health_module, "check_redis", lambda: (True, None))
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["dependencies"]["database"]["status"] == "ok"
    assert payload["dependencies"]["redis"]["status"] == "ok"


def test_health_degraded(monkeypatch) -> None:
    monkeypatch.setattr(health_module, "check_database", lambda: (False, "OperationalError"))
    monkeypatch.setattr(health_module, "check_redis", lambda: (True, None))
    response = client.get("/health")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["dependencies"]["database"]["status"] == "error"
