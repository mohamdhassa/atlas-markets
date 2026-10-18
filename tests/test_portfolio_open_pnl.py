from types import SimpleNamespace as NS

import pytest

from app.api import routes_broker_native as native


@pytest.mark.parametrize('rows,expected', [([], 0),
    ([{'unrealized_pnl': 0}], 0),
    ([{'unrealized_pnl': 12.5}, {'unrealized_pnl': -2}], 10.5),
    ([{'unrealized_pnl': None}], None),
    ([{'unrealized_pnl': float('nan')}], None),
    ([{'unrealized_pnl': float('inf')}], None)])
def test_complete_position_pnl_only(rows, expected):
    assert native._position_pnl_total(rows) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('provider', ['BYBIT', 'IBKR'])
@pytest.mark.parametrize('holding', [True, False])
async def test_unvalued_holdings_are_unknown_but_flat_is_zero(monkeypatch, provider, holding):
    profile = NS(id=1, user_id=1, provider=provider, account_label='Simulation',
                 environment='PAPER', is_active=True, credentials_configured=True)
    class Broker:
        async def wallet(self):
            return {'list': [{'totalEquity': '100', 'totalAvailableBalance': '80'}]}
        async def account(self): return {'equity': 100, 'available': 80}
        async def positions(self):
            return {'list': [{'symbol': 'TSLA', 'quantity': 1, 'avg_cost': 100}] if holding else []}
    inventory = NS(symbol='ETHUSDT', managed_quantity=.00000386, average_entry_price=2751.87)
    db = NS(scalars=lambda query: NS(all=lambda: [inventory] if holding else []))
    monkeypatch.setattr(native, '_accounts', lambda *args: [profile])
    monkeypatch.setattr(native, '_symbol_market_map', lambda *args: {})
    monkeypatch.setattr(native, '_bybit', lambda p: Broker())
    monkeypatch.setattr(native, '_ibkr', lambda p: Broker())
    result = await native.portfolio(user=NS(role='ADMIN'), db=db)
    expected = None if holding else 0
    assert result['accounts'][0]['unrealized_pnl'] == expected
    assert result['totals']['unrealized_pnl'] == expected
    assert result['totals']['unrealized_pnl_complete'] is (not holding)
    assert result['totals']['open_positions'] == int(holding)
    assert result['totals']['equity'] == 100
    if holding:
        assert result['positions'][0]['unrealized_pnl'] is None
        assert result['positions'][0]['quantity'] > 0


@pytest.mark.asyncio
@pytest.mark.parametrize('profit', [12.5, None, float('nan')])
async def test_known_mt5_pnl_does_not_hide_unknown_other_provider(monkeypatch, profit):
    profiles = [NS(id=i, user_id=i, provider=provider, account_label=provider,
                   environment='PAPER', is_active=True, credentials_configured=True)
                for i, provider in enumerate(['BYBIT', 'MT5'], 1)]
    class Bybit:
        async def wallet(self): return {'list': [{'totalEquity': '100'}]}
    class MT5:
        async def account(self): return {'equity': 100, 'margin_free': 80}
        async def positions(self): return {'list': [{'symbol': 'EURUSD', 'profit': profit}]}
    inventory = NS(symbol='ETHUSDT', managed_quantity=.00000386, average_entry_price=2751.87)
    monkeypatch.setattr(native, '_accounts', lambda *args: profiles)
    monkeypatch.setattr(native, '_symbol_market_map', lambda *args: {})
    monkeypatch.setattr(native, '_bybit', lambda p: Bybit())
    monkeypatch.setattr(native, '_mt5', lambda p: MT5())
    result = await native.portfolio(user=NS(role='ADMIN'), db=NS(scalars=lambda q: NS(all=lambda: [inventory])))
    assert result['accounts'][1]['unrealized_pnl'] == (12.5 if profit == 12.5 else None)
    import json
    json.dumps(result, allow_nan=False)
    assert result['totals']['unrealized_pnl'] is None
    assert result['totals']['unrealized_pnl_complete'] is False
