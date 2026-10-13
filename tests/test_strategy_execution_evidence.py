import asyncio
import json
from types import SimpleNamespace as NS

import pytest

from app.services import autotrade_preflight as preflight
from app.services import safe_automation as execution
from app.services.autotrade_readiness import _params, _strategy_snapshot


def test_snapshot_records_resolved_overrides_and_risk_caps():
    cfg = NS(id='strategy-1', profile_id='profile-1', market='STOCK',
             symbol='TSLA', mode='AUTO_TRADE', timeframe='3m',
             minimum_signal_strength=60, risk_per_trade_pct=2,
             stop_atr_multiplier=None, take_profit_rr=3,
             max_position_notional_pct=None)
    default = NS(timeframe='5m', minimum_signal_strength=65,
                 stop_atr_multiplier=1.5, take_profit_rr=2,
                 max_position_notional_pct=20)
    risk = NS(minimum_signal_score=70, risk_per_trade_pct=1)
    snapshot = _strategy_snapshot(cfg, _params(cfg, default, risk))
    assert snapshot['strategy_id'] == 'strategy-1'
    assert snapshot['profile_id'] == 'profile-1'
    assert snapshot['router_role'] == 'ENTRY_FILTER'
    assert snapshot['effective_parameters'] == {
        'timeframe': '3m', 'minimum_signal_strength': 70,
        'risk_per_trade_pct': 1, 'stop_atr_multiplier': 1.5,
        'take_profit_rr': 3, 'max_position_notional_pct': 20,
    }
    cfg.timeframe = '1h'
    default.stop_atr_multiplier = 4
    assert snapshot['effective_parameters']['timeframe'] == '3m'
    assert snapshot['effective_parameters']['stop_atr_multiplier'] == 1.5


@pytest.mark.parametrize('outcome', ['PASS', 'SKIP', 'BLOCK', 'ERROR'])
def test_preflight_and_persisted_action_keep_decision_evidence(monkeypatch, outcome):
    profile = NS(id=1, provider='BYBIT', environment='TESTNET',
                 execution_certified=True, execution_certification_buy_passed=True,
                 execution_certification_sell_passed=True)
    cfg = NS(market='CRYPTO', symbol='BTCUSDT', profile_id=1)
    snapshot = {'schema_version': 1, 'effective_parameters': {'timeframe': '5m'}}
    route = {'strategy': 'darvas_box', 'regime': 'BOX_BREAKOUT',
             'box': {'breakout': 'UP'}, 'confidence': 75}
    row = {'market': 'CRYPTO', 'symbol': 'BTCUSDT', 'provider': 'BYBIT',
           'environment': 'TESTNET', 'readiness': 'BLOCK' if outcome == 'SKIP' else 'PASS',
           'blockers': ['SIGNAL_SCORE_BELOW_MINIMUM'],
           'strategy_snapshot': snapshot, 'strategy_route': route,
           'timeframe': '5m', 'decision': 'BUY', 'classification': 'SIGNAL',
           'strength': 75, 'signal_reason': 'APPROVED_FOR_SIMULATION',
           'account': {'private': 'must not copy'},
           'proposed_order': {'side': 'BUY', 'quantity': .01}}
    class DB:
        def __init__(self): self.calls = 0; self.actions = []
        def scalars(self, query):
            self.calls += 1
            return NS(all=lambda: [cfg] if self.calls == 1 else [profile])
        def scalar(self, query): return cfg
        def get(self, model, key): return profile
        def add(self, action): self.actions.append(action)
    class Broker:
        async def spot_open_orders(self):
            if outcome == 'ERROR': raise TimeoutError('read timeout')
            return {'list': [{'symbol': 'BTCUSDT'}] if outcome == 'BLOCK' else []}
    async def readiness(*args, **kwargs): return {'items': [row]}
    monkeypatch.setattr(preflight, 'autotrade_readiness', readiness)
    monkeypatch.setattr(preflight, '_bybit_client', lambda *args: Broker())
    db = DB()
    item = asyncio.run(preflight.autotrade_preflight(db, user_id=1))['items'][0]
    assert item['preflight'] == ('BLOCK' if outcome == 'ERROR' else outcome)
    assert 'account' not in item
    # The preflight snapshot remains independent of later readiness mutations.
    row['strategy_route']['confidence'] = 0
    row['strategy_snapshot']['effective_parameters']['timeframe'] = '1h'
    action = execution._persist_action(db, NS(id=1), 1, item,
                                     {'status': 'EXECUTED', 'quantity': .01})
    saved = json.loads(action.raw_json)['preflight']
    assert saved['strategy_route']['confidence'] == 75
    assert saved['strategy_route']['strategy'] == 'darvas_box'
    assert saved['strategy_snapshot']['effective_parameters']['timeframe'] == '5m'
    assert saved['decision'] == 'BUY'
    assert saved['strength'] == 75
    assert db.actions == [action]


def test_snapshot_does_not_read_current_configuration_for_historical_actions(monkeypatch):
    monkeypatch.setattr(execution, '_profile_for_item', lambda *args: (None, None))
    db = NS(add=lambda action: None)
    action = execution._persist_action(db, NS(id=1), 1,
                                     {'market': 'STOCK', 'symbol': 'TSLA'},
                                     {'status': 'BLOCK', 'reason': 'NO_DIRECTION'})
    saved = json.loads(action.raw_json)['preflight']
    assert 'strategy_route' not in saved
    assert 'strategy_snapshot' not in saved
