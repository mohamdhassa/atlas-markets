import copy
import json
from types import SimpleNamespace as NS

import pytest

from app.api.routes_broker_native import _pair_execution_lots
from app.services.strategy_evaluation import attach_entry_strategies, strategy_evaluation
from app.services.autotrade_readiness import _strategy_snapshot


def fixture_rows(profile='p1', owner='u1', stop=1.5):
    cfg = NS(id='config1', profile_id=profile, market='STOCK', symbol='META', mode='AUTO_TRADE')
    snapshot = _strategy_snapshot(cfg, ('5m', 65, 1, stop, 2, 20))
    raw = json.dumps({'preflight': {'strategy_snapshot': snapshot,
                     'strategy_route': {'strategy': 'trend', 'regime': 'TRENDING_DOWN'}}})
    entry = NS(id='entry1', broker_profile_id=profile, user_id=owner, provider='IBKR',
               environment='PAPER', market='STOCK', symbol='META', side='SELL',
               status='EXECUTED', broker_order_id='214', quantity=62, raw_json=raw)
    close = NS(id='close1', broker_profile_id=profile, user_id=owner, provider='IBKR',
               environment='PAPER', market='STOCK', symbol='META', side='BUY',
               status='EXIT_EXECUTED', broker_order_id='228', quantity=62, raw_json='{}')
    rows = [dict(profile_id=profile, account='Paper', provider='IBKR', market='STOCK',
                 symbol='META', side='BUY', broker_order_id='228', audit_action_id='close1',
                 entry_action_ids=['entry1'], execution_id=identity, quantity=qty,
                 execution_price=price, pnl_available=True, closed_trade=True,
                 pnl=pnl, time=stamp)
            for identity,qty,price,pnl,stamp in [
                ('exec1',40,732.82,-561.437733,2000),
                ('exec2',22,732.76,-306.920753,2001)]]
    return rows, [entry, close]


def test_partial_fills_count_once_without_subtracting_commissions_again():
    rows, actions = fixture_rows()
    rows[0]['commission'] = 1.00012
    attach_entry_strategies(rows, actions)
    report = strategy_evaluation(rows)
    cohort = report['cohorts'][0]
    assert cohort['closed_orders'] == cohort['losses'] == 1
    assert cohort['fill_rows'] == 2
    assert cohort['net_pnl'] == cohort['expectancy_per_close'] == -868.36
    assert cohort['max_realized_drawdown'] == 868.36
    assert cohort['max_drawdown_pct'] is None
    assert report['known_closed_orders'] == 1
    assert cohort['strategy'] == 'trend'
    assert report['live_readiness'] == 'NOT_ASSESSED'


@pytest.mark.parametrize('mutation', ['no_snapshot','owner','profile','symbol','environment','same_side','bad_params','no_trade','mixed_lots'])
def test_missing_or_mismatched_entry_evidence_stays_unknown(mutation):
    rows, actions = fixture_rows()
    entry = actions[0]
    if mutation == 'no_snapshot': entry.raw_json = '{}'
    elif mutation == 'owner': entry.user_id = 'other-user'
    elif mutation == 'profile': entry.broker_profile_id = 'other-profile'
    elif mutation == 'symbol': entry.symbol = 'AAPL'
    elif mutation == 'environment': entry.environment = 'LIVE'
    elif mutation == 'same_side': entry.side = 'BUY'
    elif mutation == 'mixed_lots':
        for row in rows: row['entry_action_ids'] = ['entry1','entry2']
    else:
        raw = json.loads(entry.raw_json)
        if mutation == 'bad_params': raw['preflight']['strategy_snapshot']['effective_parameters']['risk_per_trade_pct'] = float('nan')
        else: raw['preflight']['strategy_route']['strategy'] = 'NO_TRADE'
        entry.raw_json = json.dumps(raw)
    attach_entry_strategies(rows, actions)
    report = strategy_evaluation(rows)
    assert report['known_closed_orders'] == 0
    assert report['unknown_closed_orders'] == 1
    assert report['cohorts'][0]['strategy'] == 'UNKNOWN'
    assert report['cohorts'][0]['settings'] is None


def test_duplicate_fills_deduplicate_and_conflicting_finance_is_excluded():
    rows, actions = fixture_rows()
    attach_entry_strategies(rows, actions)
    report = strategy_evaluation(rows + [copy.deepcopy(rows[0])])
    assert report['cohorts'][0]['net_pnl'] == -868.36
    conflict = copy.deepcopy(rows[0]); conflict['pnl'] = 100
    assert strategy_evaluation(rows + [conflict])['excluded'] == {'CONFLICTING_EXECUTION': 1}


def test_pending_missing_fragment_and_aggregate_mixture_are_excluded():
    rows, actions = fixture_rows()
    attach_entry_strategies(rows, actions)
    assert strategy_evaluation(rows[:1])['excluded'] == {'INCOMPLETE_CLOSING_ORDER': 1}
    rows[1]['pnl_available'] = False
    assert strategy_evaluation(rows)['excluded'] == {'PNL_PENDING': 1}
    rows[1]['pnl_available'] = True; rows[1]['execution_id'] = None
    assert strategy_evaluation(rows)['excluded'] == {'MIXED_ORDER_AGGREGATE': 1}


def test_provider_and_date_filters_do_not_invent_net_evidence():
    rows, actions = fixture_rows()
    attach_entry_strategies(rows, actions)
    assert strategy_evaluation(rows, cutoff_ms=3000)['cohorts'] == []
    rows[0]['provider'] = 'BYBIT'
    report = strategy_evaluation(rows[:1], errors=[{'error': 'timeout'}])
    assert report['cohorts'] == []
    assert report['excluded'] == {'UNSUPPORTED_NET_EVIDENCE': 1}
    assert report['provider_errors'] == 1


def test_settings_profiles_and_entry_sides_separate_cohorts():
    rows1, actions1 = fixture_rows()
    rows2, actions2 = fixture_rows(stop=2)
    rows3, actions3 = fixture_rows(profile='p2',owner='u2')
    for row in rows2:
        row['broker_order_id'] = '229'; row['execution_id'] += '-2'
    actions2[1].broker_order_id = '229'
    for rows, actions in [(rows1,actions1),(rows2,actions2),(rows3,actions3)]:
        attach_entry_strategies(rows, actions)
    report = strategy_evaluation(rows1+rows2+rows3)
    assert len(report['cohorts']) == 3
    assert report['known_closed_orders'] == 3


def test_fifo_preserves_entry_ids_only_for_complete_unambiguous_lots():
    opening = dict(profile_id='p1',symbol='META',side='SELL',quantity=62,
                   execution_price=718.84,time=1000,pnl_available=False,audit_action_id='entry1')
    rows, _ = fixture_rows()
    for row in rows: row.pop('entry_action_ids')
    _pair_execution_lots([opening,*rows])
    assert all(row['entry_action_ids'] == ['entry1'] for row in rows)
    unknown = dict(opening, audit_action_id=None)
    rows, _ = fixture_rows()
    for row in rows: row.pop('entry_action_ids')
    _pair_execution_lots([unknown,*rows])
    assert all('entry_action_ids' not in row for row in rows)


def test_profile_environment_is_preserved_when_closing_audit_is_unavailable():
    rows, actions = fixture_rows()
    for row in rows: row['environment'] = 'PAPER'
    attach_entry_strategies(rows, actions)
    unmatched = dict(rows[0], broker_order_id='999', audit_action_id=None,
                     execution_id='other-close', quantity=1, pnl=-10)
    attach_entry_strategies([unmatched], actions)
    report = strategy_evaluation([unmatched])
    assert report['cohorts'][0]['environment'] == 'PAPER'
    assert report['cohorts'][0]['strategy'] == 'UNKNOWN'


def test_closing_audit_cannot_override_authorized_profile_environment():
    rows, actions = fixture_rows()
    for row in rows: row['environment'] = 'PAPER'
    for action in actions: action.environment = 'LIVE'
    attach_entry_strategies(rows, actions)
    assert all(row['environment'] == 'PAPER' for row in rows)
    assert strategy_evaluation(rows)['known_closed_orders'] == 0
