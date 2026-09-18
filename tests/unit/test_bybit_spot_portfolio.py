from pathlib import Path


def test_bybit_portfolio_uses_managed_spot_inventory_not_derivatives_positions():
    source=Path('app/api/routes_broker_native.py').read_text()
    bybit=source.split("if p.provider=='BYBIT':",1)[1].split("elif p.provider=='MT5':",1)[0]
    assert 'BybitManagedInventory' in bybit
    assert 'position_source' in bybit
    assert 'ATLAS_MANAGED_SPOT' in bybit
    assert 'await c.positions()' not in bybit


def test_bybit_portfolio_chart_uses_spot_candles():
    source=Path('app/api/routes_portfolio_market.py').read_text()
    assert 'category="spot"' in source
    assert 'category="linear"' not in source
