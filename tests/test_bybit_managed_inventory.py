from app.db.models.bybit_inventory import BybitManagedInventory


def test_bybit_managed_inventory_schema_tracks_atlas_owned_quantity():
    columns = BybitManagedInventory.__table__.columns
    assert "user_id" in columns
    assert "broker_profile_id" in columns
    assert "symbol" in columns
    assert "managed_quantity" in columns
    assert "average_entry_price" in columns
    assert "cumulative_bought_quantity" in columns
    assert "cumulative_sold_quantity" in columns


def test_bybit_managed_inventory_defaults_do_not_claim_manual_holdings():
    row = BybitManagedInventory(user_id=None, broker_profile_id=None, symbol="BTCUSDT")
    assert row.managed_quantity is None or row.managed_quantity == 0.0
    assert row.cumulative_bought_quantity is None or row.cumulative_bought_quantity == 0.0
    assert row.cumulative_sold_quantity is None or row.cumulative_sold_quantity == 0.0
