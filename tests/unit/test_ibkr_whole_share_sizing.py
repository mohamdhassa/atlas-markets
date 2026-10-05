import asyncio
from types import SimpleNamespace as NS

import pytest
from app.services import autotrade_readiness as readiness
from app.services import autotrade_preflight as preflight
from app.services import safe_automation as execution


@pytest.fixture
def route(monkeypatch):
    profile = NS(id=1, provider='IBKR', environment='PAPER', is_enabled=True, is_active=True,
                 credentials_configured=True, last_connection_status='CONNECTED', simulation_capital_override_usd=None)
    cfg = NS(profile_id=1, market='STOCK', symbol='TSLA', mode='AUTO_TRADE')
    settings = NS(ibkr_fractional_api_enabled=False, bybit_public_base_url='unused', market_data_timeout_seconds=1)
    class DB:
        def __init__(self): self.calls = 0
        def scalars(self, query):
            self.calls += 1
            return NS(all=lambda: [cfg] if self.calls % 2 else [profile])
        def scalar(self, query): return cfg
        def get(self, model, key): return profile
    class Broker:
        checks = []
        async def candles(self, *args, **kwargs): return {'list': []}
        async def account(self): return {'equity': 252677.49, 'available': 252677.49}
        async def positions(self): return {'list': []}
        async def quote(self, *args, **kwargs): return {'last': 100}
        async def order_check(self, payload):
            self.checks.append(payload)
            return {'ok': True, 'what_if': True, 'simulation': True}
    async def refresh(*args): pass
    for module in (readiness, preflight, execution):
        monkeypatch.setattr(module, 'get_settings', lambda: settings)
        monkeypatch.setattr(module, '_secret', lambda p: {'account_id': 'DU123'})
        monkeypatch.setattr(module, 'IbkrBridgeClient', lambda *args: Broker())
    monkeypatch.setattr(readiness, '_refresh_ibkr_connection', refresh)
    monkeypatch.setattr(readiness, '_risk', lambda db: NS(max_open_positions=10))
    monkeypatch.setattr(readiness, '_strategy', lambda db: None)
    monkeypatch.setattr(readiness, '_params', lambda *args: ('5m', 1, 1, 1, 2, 20))
    monkeypatch.setattr(readiness, 'generate_signal', lambda *args, **kwargs: NS(decision='BUY', classification='BUY', strength=90))
    monkeypatch.setattr(readiness, 'evaluate_risk', lambda *args, **kwargs: (True, '', {}))
    monkeypatch.setattr(readiness, 'route_strategy', lambda *args: {'strategy': 'trend', 'regime': 'TRENDING_UP'})
    return DB, Broker, settings


def test_readiness_rounds_entry_and_preflight_uses_exact_whole_quantity(route, monkeypatch):
    DB, Broker, _ = route
    monkeypatch.setattr(readiness, 'build_execution_plan', lambda **kwargs: NS(quantity=12.7, side='BUY', notional=1270, risk_amount=12.7, stop_loss=99, take_profit=102))
    report = asyncio.run(readiness.autotrade_readiness(DB(), user_id=1))
    row = report['items'][0]
    assert row['readiness'] == 'PASS', row.get('reason')
    proposal = row['proposed_order']
    assert proposal['shares'] == proposal['quantity'] == 12
    assert proposal['notional'] == 1200
    assert proposal['strategy_requested_shares'] == 12.7
    assert proposal['sizing_policy'] == 'RISK_SIZED_WHOLE_SHARES'
    async def fake_readiness(*args, **kwargs): return report
    monkeypatch.setattr(preflight, 'autotrade_readiness', fake_readiness)
    checked = asyncio.run(preflight.autotrade_preflight(DB(), user_id=1))
    assert checked['items'][0]['preflight'] == 'PASS'
    assert Broker.checks[-1]['quantity'] == 12


def test_below_one_share_remains_blocked_without_rounding_up(route, monkeypatch):
    DB, _, _ = route
    monkeypatch.setattr(readiness, 'build_execution_plan', lambda **kwargs: NS(quantity=0.99, side='BUY', notional=99, risk_amount=.99, stop_loss=99, take_profit=102))
    row = asyncio.run(readiness.autotrade_readiness(DB(), user_id=1))['items'][0]
    assert 'blockers' in row, row.get('reason')
    assert row['readiness'] == 'BLOCK'
    assert 'IBKR_QUANTITY_BELOW_ONE_SHARE' in row['blockers']
    assert row['proposed_order']['shares'] == 0


def test_execution_rejects_stale_fractional_request_before_broker_calls(route):
    DB, Broker, _ = route
    result = asyncio.run(execution._execute_ibkr(DB(), user_id=1,
                        item={'market': 'STOCK', 'symbol': 'TSLA', 'request': {'side': 'BUY', 'shares': 12.7}}))
    assert result['reason'] == 'IBKR_FRACTIONAL_API_UNSUPPORTED'
    assert Broker.checks == []
