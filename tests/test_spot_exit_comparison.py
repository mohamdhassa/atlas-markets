import copy

import pytest

from app.backtesting import spot_exit_comparison as comparison
from app.backtesting import spot_walk_forward as baseline
from test_spot_walk_forward import bundle, signal


def setup_case():
    rows, rules = baseline.validate_bundle(bundle())
    signals = [None] * len(rows)
    signals[199] = signal('BUY')
    return rows, rules, signals


def run(rows, rules, signals, *, end=210, fee=10, slip=5):
    return comparison._simulate_atr(rows, signals, 200, end, rules, 100, fee, slip)


def test_prior_completed_atr_and_unchanged_initial_size_fill_and_fee():
    rows, rules, signals = setup_case()
    assert comparison._entry_atr(rows, 200) == 2
    rows[200]['high'] = 1000  # Must not change ATR captured for the entry.
    assert comparison._entry_atr(rows, 200) == 2
    rows[200]['high'] = 101
    original = baseline._simulate(rows, signals, 200, 210, baseline.PARAMS, rules, 100, 10, 5)
    result = run(rows, rules, signals)
    for key in ('index', 'quantity', 'price', 'fee', 'route'):
        assert result['open_entry'][key] == original['open_entry'][key]
    assert result['open_entry']['stop_loss'] == pytest.approx(97.05)
    assert result['open_entry']['take_profit'] == pytest.approx(106.05)
    assert result['end_equity'] == original['end_equity']


@pytest.mark.parametrize('opening,low,high,reason,nominal', [
    (100, 96, 101, 'STOP', 97.05),
    (100, 99, 107, 'TARGET', 106.05),
    (100, 96, 107, 'BOTH_TOUCHED_STOP_FIRST', 97.05),
    (90, 89, 107, 'GAP_STOP', 90),
    (110, 96, 111, 'GAP_TARGET', 106.05),
])
def test_conservative_protective_execution(opening, low, high, reason, nominal):
    rows, rules, signals = setup_case()
    rows[201].update(open=opening, low=low, high=high)
    result = run(rows, rules, signals)
    trade, = result['trades']
    assert trade['exit_index'] == 201
    assert trade['exit_reason'] == reason
    assert trade['exit_price'] == pytest.approx(nominal * .9995)
    expected = trade['quantity'] * (trade['exit_price'] - trade['price']) - trade['fee'] - trade['exit_fee']
    assert trade['pnl'] == pytest.approx(expected)
    assert result['end_equity'] == pytest.approx(100 + expected)


def test_entry_bar_ambiguous_touch_uses_stop_and_does_not_reenter():
    rows, rules, signals = setup_case()
    rows[200].update(low=96, high=107)
    trade, = run(rows, rules, signals)['trades']
    assert trade['exit_index'] == trade['index'] == 200
    assert trade['exit_reason'] == 'BOTH_TOUCHED_STOP_FIRST'


def test_buy_while_holding_does_not_reenter_after_protective_exit():
    rows, rules, signals = setup_case()
    signals[200] = signal('BUY')
    rows[201]['low'] = 96
    result = run(rows, rules, signals)
    assert len(result['trades']) == 1
    assert result['open_quantity'] == 0


def test_signal_exit_precedes_intrabar_trigger_and_matches_baseline():
    rows, rules, signals = setup_case()
    signals[200] = signal('SELL')
    rows[201].update(low=96, high=107)
    result = run(rows, rules, signals)
    original = baseline._simulate(rows, signals, 200, 210, baseline.PARAMS, rules, 100, 10, 5)
    assert result['trades'][0]['exit_reason'] == 'SIGNAL'
    for key in ('exit_price', 'pnl', 'exit_fee'):
        assert result['trades'][0][key] == original['trades'][0][key]
    assert result['end_equity'] == original['end_equity']
    rows[201]['open'] = 90
    assert run(rows, rules, signals)['trades'][0]['exit_reason'] == 'GAP_STOP'


def test_fixed_levels_remain_after_later_atr_change():
    rows, rules, signals = setup_case()
    rows[201].update(low=97.1, high=106)
    result = run(rows, rules, signals, end=202)
    assert comparison._entry_atr(rows, 202) > 2
    assert result['open_entry']['atr'] == 2
    assert result['open_entry']['stop_loss'] == pytest.approx(97.05)
    assert result['open_entry']['take_profit'] == pytest.approx(106.05)


def test_exit_dust_is_blocked_not_reported_as_fill():
    rows, rules, signals = setup_case()
    rows[201].update(open=1, low=.5, high=2, close=1)
    rules['minimum_notional'] = 5
    result = run(rows, rules, signals, end=202)
    assert result['blockers'] == {'EXIT_DUST': 1}
    assert result['trades'] == []
    assert result['open_quantity'] == .2


@pytest.mark.parametrize('blocked,strength,min_notional', [
    ('ROUTER_BLOCK', 80, 1), (None, 60, 1), (None, 80, 50)])
def test_entry_gates_and_sizes_still_apply(blocked, strength, min_notional):
    rows, rules, signals = setup_case()
    signals[199].update(blocked=blocked, strength=strength)
    rules['minimum_notional'] = min_notional
    assert run(rows, rules, signals)['open_quantity'] == 0


def test_invalid_atr_does_not_create_unprotected_position(monkeypatch):
    rows, rules, signals = setup_case()
    monkeypatch.setattr(comparison, '_entry_atr', lambda *args: float('nan'))
    result = run(rows, rules, signals)
    assert result['open_quantity'] == 0
    assert result['blockers'] == {'INVALID_ATR_PROTECTION': 1}


def test_report_reproduces_baseline_carries_inventory_and_never_certifies(monkeypatch):
    b = bundle()
    before = copy.deepcopy(b)
    signals = [None] * len(b['candles'])
    signals[399] = signal('BUY')
    signals[649] = signal('SELL')
    monkeypatch.setattr(baseline, '_signals', lambda rows: signals)
    kwargs = dict(capital=100, fee_bps=10, slippage_cases=[2,5,10], train_bars=200, test_bars=100)
    original = baseline.walk_forward_spot(b, **kwargs)
    result = comparison.compare_spot_exits(b, **kwargs)
    assert b == before
    assert result['executable'] is result['live_eligible'] is False
    assert result['parameter_optimization'] is False
    assert result['evaluation_status'] == 'EXPLORATORY_PREVIOUSLY_INSPECTED_DATA'
    for old, new in zip(original['scenarios'], result['scenarios']):
        assert new['policies']['signal'] == old['validation']
        assert new['policies']['signal_plus_atr']['closed_trades'] == 1
        assert new['folds'][0]['signal_plus_atr']['closed_trades'] == 0
        assert new['folds'][2]['signal_plus_atr']['closed_trades'] == 1
    signals[649] = None
    result = comparison.compare_spot_exits(b, **kwargs)
    assert result['scenarios'][0]['policies']['signal_plus_atr']['open_quantity'] == .2
    assert result['scenarios'][0]['policies']['signal_plus_atr']['closed_trades'] == 0


def test_cli_writes_exclusive_output_and_cannot_overwrite_data(monkeypatch, tmp_path):
    path = tmp_path / 'existing.json'
    path.write_text('{}')
    monkeypatch.setattr(comparison, 'compare_spot_exits', lambda *args, **kwargs: {})
    monkeypatch.setattr('sys.argv', ['compare', '--input', str(path), '--output', str(path),
                                  '--capital', '100', '--fee-bps', '10', '--slippage-bps', '5'])
    with pytest.raises(FileExistsError):
        comparison.main()
    assert path.read_text() == '{}'
