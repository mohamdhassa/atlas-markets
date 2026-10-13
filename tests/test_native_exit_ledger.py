import copy
import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace as NS

import pytest
from app.api.routes_broker_native import _pair_execution_lots, _stats
from app.services.ibkr_ledger_history import merge_saved_fills

PROFILE = NS(id=uuid.uuid4(), user_id=uuid.uuid4(), account_label='Paper', environment='PAPER')


def entry(order, qty, price, stamp, key=None):
    return NS(id=key or uuid.uuid4(), provider='IBKR', environment='PAPER',
        broker_profile_id=PROFILE.id, user_id=PROFILE.user_id, symbol='META', market='STOCK',
        side='SELL', status='EXECUTED', reason=None, quantity=qty, broker_order_id=str(order),
        created_at=datetime.fromisoformat(stamp), raw_json=json.dumps({'result': {'broker_result': {
            'account_id': 'DU_TEST', 'final_status': {'order_id': order, 'status': {
                'order_id': order, 'status': 'Filled', 'filled': qty, 'remaining': 0,
                'avg_fill_price': price}}}}}))


def close(opening, order, fills, stamp):
    return NS(id=uuid.uuid5(opening.id, 'IBKR_NATIVE_PROTECTIVE_EXIT'), provider='IBKR',
        environment='PAPER', broker_profile_id=PROFILE.id, user_id=PROFILE.user_id,
        symbol='META', market='STOCK', side='BUY', status='EXIT_EXECUTED',
        reason='BROKER_NATIVE_PROTECTIVE_EXIT', quantity=opening.quantity,
        broker_order_id=str(order), created_at=datetime.fromisoformat(stamp),
        raw_json=json.dumps({'position': {'entry_action_id': str(opening.id),
            'entry_order_id': opening.broker_order_id, 'symbol': 'META', 'quantity': opening.quantity,
            'protection': {'oca_group': 'atlas-protect-' + opening.id.hex, 'order_ids': [order, order+1]},
            'executions': fills}, 'result': {'status': 'EXIT_EXECUTED',
            'reason': 'BROKER_NATIVE_PROTECTIVE_EXIT', 'close_side': 'BUY',
            'broker_result': {'order_id': order, 'execution_ids': [f['execution_id'] for f in fills]}}}))


def fill(order, key, qty, price, stamp, pnl, fee):
    return dict(account='DU_TEST', symbol='META', sec_type='STK', side='BOT', order_id=order,
                execution_id=key, quantity=qty, price=price, time=stamp,
                realized_pnl=pnl, pnl_available=pnl is not None,
                commission=fee, commission_currency='USD')


@pytest.fixture
def audits():
    first = entry(214, 62, 718.84, '2026-10-09T18:42:32+00:00')
    first_exit = close(first, 228, [
        fill(228, 'oct12-a', 40, 732.82, '20261012  13:30:18', -561.437733, 1.00012),
        fill(228, 'oct12-b', 22, 732.76, '20261012  13:30:19', -306.920753, .000066),
    ], '2026-10-12T17:59:29+00:00')
    second = entry(241, 63, 741.48, '2026-10-13T13:32:00+00:00')
    second_exit = close(second, 243, [
        fill(243, 'oct13-a', 63, 754.41, '20261013  13:46:07', -817.552671, 1.000189),
    ], '2026-10-13T13:47:29+00:00')
    return [first, first_exit, second, second_exit]


def test_missing_native_history_survives_empty_live_feed_and_pairs_exact_entries(audits):
    # An unrelated older orphan must never supply the entry for either native close.
    orphan = entry(600, 1, 700, '2026-09-25T13:30:00+00:00')
    rows = merge_saved_fills([], [orphan] + audits, PROFILE, 'DU_TEST')
    _pair_execution_lots(rows)
    closes = sorted([r for r in rows if r.get('closed_trade')], key=lambda r: r['time'])
    assert len(closes) == 3
    assert [r['entry_price'] for r in closes] == [718.84, 718.84, 741.48]
    assert [r['quantity'] for r in closes] == [40, 22, 63]
    assert [r['opened_at_iso'] for r in closes] == [
        '2026-10-09T18:42:32+00:00', '2026-10-09T18:42:32+00:00', '2026-10-13T13:32:00+00:00']
    assert closes[-1]['duration_seconds'] == 847
    assert closes[-1]['closed_at_iso'] == '2026-10-13T13:46:07+00:00'
    assert round(sum(r['pnl'] for r in closes[:2]), 2) == -868.36
    assert _stats(rows)['realized_pnl'] == -1685.91
    assert closes[-1]['commission'] == 1.000189
    assert all(r['side'] == 'BUY' for r in closes)


def test_live_and_saved_callbacks_deduplicate_and_keep_updated_broker_values(audits):
    live = dict(profile_id=str(PROFILE.id), symbol='META', side='BUY', quantity=40,
                execution_price=732.82, broker_order_id=228, execution_id='oct12-a',
                time=1791811818000, pnl_available=True, pnl=-560, commission=1.5)
    rows = merge_saved_fills([live], audits + audits, PROFILE, 'DU_TEST')
    assert len([r for r in rows if r.get('execution_id') == 'oct12-a']) == 1
    assert live['pnl'] == -560 and live['commission'] == 1.5
    _pair_execution_lots(rows)
    assert live['entry_price'] == 718.84


def test_saved_fees_complete_pending_live_callback(audits):
    live = dict(profile_id=str(PROFILE.id), symbol='META', side='BUY', quantity=40,
                execution_price=732.82, broker_order_id=228, execution_id='oct12-a',
                time=1791811818000, pnl_available=False, commission=None)
    merge_saved_fills([live], audits, PROFILE, 'DU_TEST')
    assert live['pnl_available'] and live['pnl'] == -561.437733
    assert live['commission'] == 1.00012


@pytest.mark.parametrize('change', ['owner', 'profile', 'environment', 'status', 'id', 'entry',
    'account', 'side', 'quantity', 'duplicate', 'order', 'timestamp', 'pnl', 'price', 'oca'])
def test_invalid_native_proof_is_never_recovered(audits, change):
    opening, exit = audits[:2]
    raw = json.loads(exit.raw_json)
    if change == 'owner': exit.user_id = uuid.uuid4()
    if change == 'profile': exit.broker_profile_id = uuid.uuid4()
    if change == 'environment': exit.environment = 'LIVE'
    if change == 'status': exit.status = 'EXIT_SUBMITTED'
    if change == 'id': exit.id = uuid.uuid4()
    if change == 'entry': raw['position']['entry_action_id'] = str(uuid.uuid4())
    if change == 'account': raw['position']['executions'][0]['account'] = 'OTHER'
    if change == 'side': raw['position']['executions'][0]['side'] = 'SLD'
    if change == 'quantity': raw['position']['executions'].pop()
    if change == 'duplicate': raw['position']['executions'][1]['execution_id'] = 'oct12-a'
    if change == 'order': raw['position']['executions'][0]['order_id'] = 999
    if change == 'timestamp': raw['position']['executions'][0]['time'] = 'unknown'
    if change == 'pnl': raw['position']['executions'][0]['realized_pnl'] = float('nan')
    if change == 'price': raw['position']['executions'][0]['price'] = 0
    if change == 'oca': raw['position']['protection']['oca_group'] = 'other'
    exit.raw_json = json.dumps(raw)
    rows = merge_saved_fills([], [opening, exit], PROFILE, 'DU_TEST')
    assert not any(r.get('execution_id') for r in rows)


def test_partial_missing_financial_data_stays_pending(audits):
    raw = json.loads(audits[1].raw_json)
    raw['position']['executions'][0].update(pnl_available=False, realized_pnl=None, commission=None)
    audits[1].raw_json = json.dumps(raw)
    rows = merge_saved_fills([], audits[:2], PROFILE, 'DU_TEST')
    pending = next(r for r in rows if r.get('execution_id') == 'oct12-a')
    assert pending['closed_trade'] and not pending['pnl_available']
    assert pending['pnl'] is None and pending['commission'] is None


def test_conflicting_execution_identity_does_not_merge_stored_group(audits):
    live = dict(profile_id=str(PROFILE.id), symbol='META', quantity=40, execution_price=999,
                broker_order_id=228, execution_id='oct12-a')
    rows = merge_saved_fills([live], audits[:2], PROFILE, 'DU_TEST')
    assert not any(r.get('execution_id') == 'oct12-b' for r in rows)
    assert 'entry_action_id' not in live


def test_performance_endpoint_restores_prior_day_fills_and_daily_pnl(monkeypatch, audits):
    import asyncio
    import app.api.routes_broker_native as route
    from app.db.models.automation import AutomationAction
    profile = copy.copy(PROFILE)
    profile.provider = 'IBKR'
    profile.credentials_configured = True
    profile.simulation_capital_override_usd = None
    current = dict(profile_id=str(profile.id), symbol='META', side='BOT', quantity=63,
        price=754.41, order_id=243, execution_id='oct13-a', time='20261013  13:46:07',
        realized_pnl=-817.552671, pnl_available=True, commission=1.000189)
    class Broker:
        async def account(self): return {'equity': 1000, 'available': 500}
        async def executions(self, days): return {'list': [current]}
    class DB:
        def scalars(self, query):
            rows = audits if query.column_descriptions[0]['entity'] is AutomationAction else []
            return NS(all=lambda: rows)
    monkeypatch.setattr(route, '_accounts', lambda *args: [profile])
    monkeypatch.setattr(route, '_symbol_market_map', lambda *args: {})
    monkeypatch.setattr(route, '_creds', lambda *args: {'account_id': 'DU_TEST'})
    monkeypatch.setattr(route, '_ibkr', lambda *args: Broker())
    monkeypatch.setattr(route, '_trade_context', lambda *args: None)
    monkeypatch.setattr(route, 'get_settings', lambda: NS(ibkr_execution_timezone='Etc/UTC'))
    result = asyncio.run(route.broker_performance.__wrapped__(days=30, user=NS(role='ADMIN'), db=DB()))
    closes = [r for r in result['trades'] if r.get('closed_trade')]
    assert len(closes) == 3
    assert result['overall']['realized_pnl'] == -1685.91
    assert result['daily'] == [{'date': '2026-10-12', 'realized_pnl': -868.36},
                               {'date': '2026-10-13', 'realized_pnl': -817.55}]
    today = next(r for r in closes if r['quantity'] == 63)
    assert today['entry_price'] == 741.48 and today['duration_seconds'] == 847
    assert today['side'] == 'BUY'
