from __future__ import annotations

import pytest

from app.brokers.bybit_private import BybitPrivateClient, BybitPrivateError


def test_normalize_spot_qty_floors_to_provider_step():
    assert BybitPrivateClient._normalize_spot_qty(0.002977, "0.00001", "0.00001") == "0.00297"


def test_normalize_spot_qty_preserves_valid_quantity():
    assert BybitPrivateClient._normalize_spot_qty(0.002977, "0.000001", "0.000001") == "0.002977"


def test_normalize_spot_qty_never_rounds_up():
    assert BybitPrivateClient._normalize_spot_qty(1.239, "0.01", "0.01") == "1.23"


def test_normalize_spot_qty_rejects_below_minimum():
    with pytest.raises(BybitPrivateError, match="SPOT_QUANTITY_BELOW_MINIMUM"):
        BybitPrivateClient._normalize_spot_qty(0.000009, "0.00001", "0.00001")


@pytest.mark.asyncio
async def test_spot_lot_size_falls_back_to_base_precision_when_qty_step_missing(monkeypatch):
    client = BybitPrivateClient("key", "secret", "https://api-testnet.bybit.com")

    async def fake_get(path, params=None):
        return {
            "list": [{
                "symbol": "SOLUSDT",
                "lotSizeFilter": {
                    "basePrecision": "0.001",
                    "minOrderQty": "0.001",
                },
            }]
        }

    monkeypatch.setattr(client, "get", fake_get)
    step, minimum = await client._spot_lot_size("SOLUSDT")
    assert step == "0.001"
    assert minimum == "0.001"


@pytest.mark.asyncio
async def test_spot_lot_size_prefers_qty_step_when_provider_supplies_it(monkeypatch):
    client = BybitPrivateClient("key", "secret", "https://api-testnet.bybit.com")

    async def fake_get(path, params=None):
        return {
            "list": [{
                "symbol": "BTCUSDT",
                "lotSizeFilter": {
                    "qtyStep": "0.00001",
                    "basePrecision": "0.000001",
                    "minOrderQty": "0.00001",
                },
            }]
        }

    monkeypatch.setattr(client, "get", fake_get)
    step, minimum = await client._spot_lot_size("BTCUSDT")
    assert step == "0.00001"
    assert minimum == "0.00001"
