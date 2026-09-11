import asyncio
from types import SimpleNamespace

from app.api import routes_ibkr_external as ibkr_routes


def test_live_profile_ready_uses_current_bridge_health(monkeypatch):
    profile = SimpleNamespace(credential_blob_encrypted="enc", environment="PAPER")

    monkeypatch.setattr(ibkr_routes, "decrypt_secret", lambda _: '{"account_id":"DU123","bridge_url":"http://bridge"}')

    class Client:
        async def health(self):
            return {"connected": False, "simulation": True}

    monkeypatch.setattr(ibkr_routes, "_client", lambda _: Client())

    assert asyncio.run(ibkr_routes._live_profile_ready(profile)) is False


def test_live_profile_ready_accepts_connected_paper_bridge(monkeypatch):
    profile = SimpleNamespace(credential_blob_encrypted="enc", environment="PAPER")

    monkeypatch.setattr(ibkr_routes, "decrypt_secret", lambda _: '{"account_id":"DU123","bridge_url":"http://bridge"}')

    class Client:
        async def health(self):
            return {"connected": True, "simulation": True}

    monkeypatch.setattr(ibkr_routes, "_client", lambda _: Client())

    assert asyncio.run(ibkr_routes._live_profile_ready(profile)) is True


def test_live_profile_ready_rejects_environment_mismatch(monkeypatch):
    profile = SimpleNamespace(credential_blob_encrypted="enc", environment="LIVE")

    monkeypatch.setattr(ibkr_routes, "decrypt_secret", lambda _: '{"account_id":"DU123","bridge_url":"http://bridge"}')

    class Client:
        async def health(self):
            return {"connected": True, "simulation": True}

    monkeypatch.setattr(ibkr_routes, "_client", lambda _: Client())

    assert asyncio.run(ibkr_routes._live_profile_ready(profile)) is False


def test_live_profile_ready_fails_closed_on_bridge_error(monkeypatch):
    profile = SimpleNamespace(credential_blob_encrypted="enc", environment="PAPER")

    monkeypatch.setattr(ibkr_routes, "decrypt_secret", lambda _: '{"account_id":"DU123","bridge_url":"http://bridge"}')

    class Client:
        async def health(self):
            raise OSError("bridge unavailable")

    monkeypatch.setattr(ibkr_routes, "_client", lambda _: Client())

    assert asyncio.run(ibkr_routes._live_profile_ready(profile)) is False
