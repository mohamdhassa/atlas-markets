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
