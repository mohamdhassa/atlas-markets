import asyncio

import pytest

from app.brokers.ibkr_bridge import IbkrBridgeClient


def test_place_order_blocks_disconnected_bridge(monkeypatch):
    client = IbkrBridgeClient("http://bridge")

    async def health():
        return {"connected": False, "simulation": True}

    async def unexpected(*args, **kwargs):
        raise AssertionError("broker state/order endpoints must not be called while disconnected")

    monkeypatch.setattr(client, "health", health)
    monkeypatch.setattr(client, "positions", unexpected)
    monkeypatch.setattr(client, "orders", unexpected)
    monkeypatch.setattr(client, "_post", unexpected)

    with pytest.raises(RuntimeError, match="IBKR_BRIDGE_DISCONNECTED"):
        asyncio.run(client.place_order({"symbol": "AAPL", "account_id": "DU123"}))


def test_place_order_blocks_non_simulation_bridge(monkeypatch):
    client = IbkrBridgeClient("http://bridge")

    async def health():
        return {"connected": True, "simulation": False}

    async def unexpected(*args, **kwargs):
        raise AssertionError("entry workflow must not continue outside the simulation bridge")

    monkeypatch.setattr(client, "health", health)
    monkeypatch.setattr(client, "positions", unexpected)
    monkeypatch.setattr(client, "orders", unexpected)
    monkeypatch.setattr(client, "_post", unexpected)

    with pytest.raises(RuntimeError, match="IBKR_PAPER_BRIDGE_REQUIRED"):
        asyncio.run(client.place_order({"symbol": "AAPL", "account_id": "DU123"}))
