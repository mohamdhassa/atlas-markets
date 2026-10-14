import copy
import json

import pytest

from app.backtesting import spot_cost_diagnostics as diagnostics
from app.backtesting import spot_exit_comparison as exits
from app.backtesting import spot_walk_forward as baseline
from test_spot_walk_forward import bundle, signal


def test_cost_decomposition_reconciles_and_exposes_fee_erased_gain():
    rows, rules = baseline.validate_bundle(bundle())
    signals = [None] * len(rows)
    signals[199] = signal('BUY'); signals[200] = signal('SELL')
    rows[201]['open'] = 100.1
    result = baseline._simulate(rows, signals, 200, 202, baseline.PARAMS, rules, 100, 10, 5)
    trade, = result['trades']
    cost = diagnostics._closed_costs(trade, rows, 5)
    assert cost['reference_price_move_pnl'] == pytest.approx(.02)
    assert cost['slippage_drag'] == pytest.approx(.02001)
    assert cost['fees'] == pytest.approx(trade['fee'] + trade['exit_fee'])
    assert cost['reference_price_move_pnl'] - cost['slippage_drag'] - cost['fees'] == pytest.approx(trade['pnl'])
    assert cost['positive_reference_move_but_net_loss'] is True


@pytest.mark.parametrize('slip', [0,2,5,10])
def test_target_estimate_matches_protective_target_fill(slip):
    rows, rules = baseline.validate_bundle(bundle())
    signals = [None] * len(rows); signals[199] = signal('BUY')
    rows[201]['high'] = 110
    trade, = exits._simulate_atr(rows, signals, 200, 202, rules, 100, 10, slip)['trades']
    costs = diagnostics._entry_costs(trade, rows, 10, slip)
    assert costs['hypothetical_target_net_pnl'] == pytest.approx(trade['pnl'])
    assert trade['exit_reason'] == 'TARGET'


def test_cost_buckets_zero_cost_invalid_atr_and_completed_bars(monkeypatch):
    rows, _ = baseline.validate_bundle(bundle())
    entry = dict(index=200, price=100, quantity=.2, fee=.02, route='trend')
    monkeypatch.setattr(exits, '_entry_atr', lambda *args: .05)
    record = diagnostics._entry_costs(entry, rows, 10, 5)
    assert record['atr_target_bps'] == pytest.approx(15)
    assert record['target_cost_bucket'] == 'TARGET_LE_COST'
    assert record['hypothetical_target_net_pnl'] < 0
    monkeypatch.setattr(exits, '_entry_atr', lambda *args: .15)
    assert diagnostics._entry_costs(entry, rows, 10, 5)['target_cost_bucket'] == 'TARGET_LE_2X_COST'
    assert diagnostics._entry_costs(entry, rows, 0, 0)['target_to_approximate_cost_ratio'] is None
    assert diagnostics._entry_costs(entry, rows, 0, 0)['target_cost_bucket'] == 'ZERO_MODELED_COST'
    monkeypatch.setattr(exits, '_entry_atr', lambda *args: float('nan'))
    invalid = diagnostics._entry_costs(entry, rows, 10, 5)
    assert invalid['target_cost_bucket'] == 'INVALID_ATR'
    json.dumps(invalid, allow_nan=False)


def test_report_preserves_both_policies_and_groups_open_entries_separately(monkeypatch):
    b = bundle(); before = copy.deepcopy(b)
    signals = [None] * len(b['candles'])
    signals[399] = signal('BUY'); signals[649] = signal('SELL')
    signals[699] = signal('BUY')
    monkeypatch.setattr(baseline, '_signals', lambda rows: signals)
    kwargs = dict(capital=100, fee_bps=10, slippage_cases=[5], train_bars=200, test_bars=100)
    comparison = exits.compare_spot_exits(b, **kwargs)
    report = diagnostics.diagnose_spot_costs(b, **kwargs)
    assert b == before
    assert report['entry_filters_changed'] is report['parameter_optimization'] is False
    assert report['executable'] is report['live_eligible'] is False
    for name, policy in report['scenarios'][0]['policies'].items():
        original = comparison['scenarios'][0]['policies'][name]
        assert policy['summary']['closed_net_pnl'] == original['net_realized_pnl']
        assert policy['end_marked_equity'] == original['end_marked_equity']
        assert policy['summary']['closed_fees'] == original['modeled_fees']
        assert policy['summary']['entries'] == 2
        assert policy['summary']['closes'] == 1
        assert policy['summary']['open_entries'] == 1
        assert policy['open_entry_fee'] > 0
        assert sum(v['closes'] for v in policy['entry_routes'].values()) == 1
        assert sum(v['entries'] for v in policy['cost_buckets'].values()) == 2
    json.dumps(report, allow_nan=False)


def test_empty_cohorts_do_not_invent_ratios_or_pnl():
    group = diagnostics._group([])
    assert group['entries'] == group['closes'] == 0
    assert group['median_target_to_approximate_cost_ratio'] is None
    assert group['closed_net_pnl'] == 0


def test_diagnostics_reject_wrong_product_and_invalid_assumptions():
    b = bundle(); b['product'] = 'LINEAR'
    with pytest.raises(ValueError):
        diagnostics.diagnose_spot_costs(b, capital=100, fee_bps=10, slippage_cases=[5])
    with pytest.raises(ValueError):
        diagnostics.diagnose_spot_costs(bundle(), capital=100, fee_bps=10, slippage_cases=[101])


def test_decomposition_fails_if_trade_evidence_does_not_reconcile():
    rows, _ = baseline.validate_bundle(bundle())
    trade = dict(index=200, exit_index=201, price=100, exit_price=101,
                 quantity=1, fee=.1, exit_fee=.1, pnl=99)
    with pytest.raises(ValueError, match='decomposition'):
        diagnostics._closed_costs(trade, rows, 0)


def test_cli_refuses_overwriting(monkeypatch, tmp_path):
    path = tmp_path / 'input.json'; path.write_text('{}')
    monkeypatch.setattr(diagnostics, 'diagnose_spot_costs', lambda *args, **kwargs: {})
    monkeypatch.setattr('sys.argv', ['diagnose', '--input', str(path), '--output', str(path),
                                  '--capital', '100', '--fee-bps', '10', '--slippage-bps', '5'])
    with pytest.raises(FileExistsError):
        diagnostics.main()
    assert path.read_text() == '{}'
