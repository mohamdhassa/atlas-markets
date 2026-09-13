import pytest

from app.db.models.bybit_inventory import BybitManagedInventory
from app.services.bybit_spot_execution import (
    _matching_history_row,
    apply_managed_fill,
)


def _inventory(qty=0.0, avg=None, bought=0.0, sold=0.0):
    return BybitManagedInventory(
        user_id=None,
        broker_profile_id=None,
        symbol="BTCUSDT",
        managed_quantity=qty,
        average_entry_price=avg,
        cumulative_bought_quantity=bought,
        cumulative_sold_quantity=sold,
    )


def test_buy_fill_creates_only_atlas_managed_quantity():
    row = _inventory()
    apply_managed_fill(row, side="BUY", quantity=0.001, price=100000.0)
    assert row.managed_quantity == pytest.approx(0.001)
    assert row.cumulative_bought_quantity == pytest.approx(0.001)
    assert row.cumulative_sold_quantity == pytest.approx(0.0)
    assert row.average_entry_price == pytest.approx(100000.0)


def test_second_buy_uses_weighted_average_cost():
    row = _inventory(qty=0.001, avg=100000.0, bought=0.001)
    apply_managed_fill(row, side="BUY", quantity=0.001, price=120000.0)
    assert row.managed_quantity == pytest.approx(0.002)
    assert row.average_entry_price == pytest.approx(110000.0)
    assert row.cumulative_bought_quantity == pytest.approx(0.002)


def test_sell_fill_cannot_exceed_atlas_managed_inventory():
    row = _inventory(qty=0.001, avg=100000.0, bought=0.001)
    with pytest.raises(ValueError, match="SELL_EXCEEDS_ATLAS_MANAGED_INVENTORY"):
        apply_managed_fill(row, side="SELL", quantity=0.0011, price=110000.0)
    assert row.managed_quantity == pytest.approx(0.001)


def test_full_sell_closes_managed_inventory_without_touching_manual_balance():
    row = _inventory(qty=0.001, avg=100000.0, bought=0.001)
    apply_managed_fill(row, side="SELL", quantity=0.001, price=110000.0)
    assert row.managed_quantity == pytest.approx(0.0)
    assert row.cumulative_sold_quantity == pytest.approx(0.001)
    assert row.average_entry_price is None


def test_fill_reconciliation_requires_exact_atlas_auto_order_link_id():
    history = [
        {"orderLinkId": "manual", "orderStatus": "Filled", "orderId": "1"},
        {"orderLinkId": "atlas-auto-abc", "orderStatus": "Cancelled", "orderId": "2"},
        {"orderLinkId": "atlas-auto-abc", "orderStatus": "Filled", "orderId": "3"},
    ]
    match = _matching_history_row(history, "atlas-auto-abc")
    assert match is not None
    assert match["orderId"] == "3"
    assert _matching_history_row(history, "atlas-auto-other") is None
