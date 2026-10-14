import copy
import json
from types import SimpleNamespace as NS

import pytest

from app.backtesting import spot_timeframe_comparison as comparison
from app.backtesting import spot_walk_forward as baseline
from app.backtesting.spot_history import STEP_MS
from test_spot_walk_forward import bundle, signal


def test_utc_aggregation_preserves_ohlcv_and_discards_partial_edges_only():
    rows = bundle(12)['candles']
    for i, row in enumerate(rows):
        row.update(timestamp_ms=row['timestamp_ms'] + STEP_MS, open=100+i,
                   high=102+i, low=98+i, close=101+i, volume=i+1)
    before = copy.deepcopy(rows)
    candles, indices = comparison.aggregate_fifteen(rows)
    assert len(candles) == 3
    assert indices == [4,7,10]
    assert candles[0] == dict(timestamp_ms=rows[2]['timestamp_ms'], open=102.,
                              high=106., low=100., close=105., volume=12.)
    assert all(c['timestamp_ms'] % comparison.FIFTEEN_MS == 0 for c in candles)
    assert rows == before


def test_interior_missing_bar_is_never_aggregated_into_fake_candle():
    rows = bundle(12)['candles']; rows.pop(4)
    with pytest.raises(ValueError, match='Incomplete interior'):
        comparison.aggregate_fifteen(rows)


def test_15m_signals_wait_for_completed_window_and_are_not_forward_filled(monkeypatch):
    rows = bundle(1200)['candles']
    candles, indices = comparison.aggregate_fifteen(rows)
    windows = []
    def generate(window, **kwargs):
        windows.append(copy.deepcopy(window))
        assert kwargs == {'timeframe': '15m', 'market': 'CRYPTO'}
        return NS(decision='BUY', strength=80)
    monkeypatch.setattr(baseline, 'generate_signal', generate)
    monkeypatch.setattr(baseline, 'route_strategy', NS(__wrapped__=lambda window: signal('BUY')['route']))
    monkeypatch.setattr(baseline, '_router_blocker', lambda *args: None)
    decisions = comparison.fifteen_signals(rows, candles, indices)
    assert decisions[598] is None
    assert decisions[599]['side'] == 'BUY'
    assert decisions[600] is decisions[601] is None
    assert len(windows[0]) == 200
    assert windows[0][-1]['timestamp_ms'] + comparison.FIFTEEN_MS == rows[600]['timestamp_ms']
    assert decisions[-1] is None
    changed = copy.deepcopy(rows); changed[600]['high'] = 1000
    new_candles, new_indices = comparison.aggregate_fifteen(changed)
    comparison.fifteen_signals(changed, new_candles, new_indices)
    assert windows[0] == windows[len(windows)//2]


def test_common_window_sizing_next_open_and_fold_inventory_are_unchanged(monkeypatch):
    b = bundle(1200); before = copy.deepcopy(b)
    signals = [None] * 1200
    signals[599] = signal('BUY'); signals[899] = signal('SELL')
    monkeypatch.setattr(baseline, '_signals', lambda rows: signals)
    monkeypatch.setattr(comparison, 'fifteen_signals', lambda *args: signals)
    report = comparison.compare_spot_timeframes(b, capital=100, fee_bps=10,
        slippage_cases=[2,5,10], train_bars=200, test_bars=100)
    assert b == before
    assert report['validation_start_ms'] == b['candles'][600]['timestamp_ms']
    assert report['validation_end_exclusive_ms'] == b['end_ms_exclusive']
    assert report['baseline_start_shift_5m_bars'] == 200
    assert report['live_eligible'] is report['executable'] is report['parameter_optimization'] is False
    rows, rules = baseline.validate_bundle(b)
    for scenario in report['scenarios']:
        assert scenario['policies']['5m'] == scenario['policies']['15m']
        p = scenario['policies']['15m']
        expected = baseline._simulate(rows, signals, 600, 1200, baseline.PARAMS, rules,
                                      100, 10, scenario['slippage_bps_per_leg'])
        assert p['validation']['net_realized_pnl'] == baseline._metrics(expected['trades'])['net_realized_pnl']
        assert p['validation']['end_marked_equity'] == round(expected['end_equity'], 6)
        assert p['folds'][0]['closed_trades'] == 0
        assert p['folds'][3]['closed_trades'] == 1
        assert p['eligible_decisions'] == {'BUY': 1, 'SELL': 1}
    json.dumps(report, allow_nan=False)


def test_15m_execution_occurs_next_open_once_after_close():
    rows, rules = baseline.validate_bundle(bundle(1200))
    signals = [None] * len(rows)
    signals[599] = signal('BUY'); signals[602] = signal('SELL')
    rows[600]['open'] = 102
    result = baseline._simulate(rows, signals, 600, 1200, baseline.PARAMS, rules, 100, 10, 5)
    trade, = result['trades']
    assert trade['index'] == 600 and trade['exit_index'] == 603
    assert trade['price'] == pytest.approx(102 * 1.0005)
    assert trade['quantity'] == .2


def test_final_holdings_remain_open_without_forced_close(monkeypatch):
    signals = [None] * 1200; signals[599] = signal('BUY')
    monkeypatch.setattr(baseline, '_signals', lambda rows: signals)
    monkeypatch.setattr(comparison, 'fifteen_signals', lambda *args: signals)
    report = comparison.compare_spot_timeframes(bundle(1200), capital=100, fee_bps=10,
        slippage_cases=[5], train_bars=200, test_bars=100)
    for policy in report['scenarios'][0]['policies'].values():
        assert policy['validation']['closed_trades'] == 0
        assert policy['validation']['open_quantity'] == .2
        assert policy['validation']['open_entry_fee'] > 0


def test_common_calendar_alignment_and_short_final_fold(monkeypatch):
    b = bundle(1250)
    signals = [None] * len(b['candles'])
    monkeypatch.setattr(baseline, '_signals', lambda rows: signals)
    monkeypatch.setattr(comparison, 'fifteen_signals', lambda *args: signals)
    report = comparison.compare_spot_timeframes(b, capital=100, fee_bps=10,
        slippage_cases=[5], train_bars=401, test_bars=100)
    assert report['validation_start_ms'] == b['candles'][603]['timestamp_ms']
    assert report['validation_end_exclusive_ms'] == b['candles'][1247]['timestamp_ms'] + STEP_MS
    assert report['discarded_partial_edge_5m_bars'] == 2
    policies = report['scenarios'][0]['policies']
    assert policies['5m']['folds'] == policies['15m']['folds']
    assert policies['5m']['folds'][-1]['source_5m_bars'] == 45


@pytest.mark.parametrize('bad', ['product', 'gap', 'cost', 'short'])
def test_invalid_inputs_or_insufficient_common_history_fail(bad):
    b = bundle(1200)
    if bad == 'product': b['product'] = 'LINEAR'
    elif bad == 'gap': b['candles'].pop(600)
    elif bad == 'short': b = bundle(799)
    with pytest.raises(ValueError):
        comparison.compare_spot_timeframes(b, capital=100, fee_bps=10,
            slippage_cases=[101 if bad == 'cost' else 5], train_bars=200, test_bars=100)


def test_cli_cannot_overwrite_dataset(monkeypatch, tmp_path):
    path = tmp_path / 'existing.json'; path.write_text('{}')
    monkeypatch.setattr(comparison, 'compare_spot_timeframes', lambda *args, **kwargs: {})
    monkeypatch.setattr('sys.argv', ['compare', '--input', str(path), '--output', str(path),
                                  '--capital', '100', '--fee-bps', '10', '--slippage-bps', '5'])
    with pytest.raises(FileExistsError): comparison.main()
    assert path.read_text() == '{}'
