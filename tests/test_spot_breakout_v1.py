import copy
import json
from datetime import datetime, timezone

import pytest
from app.backtesting import spot_breakout_v1 as model
from app.backtesting.spot_history import digest, STEP_MS
from test_spot_walk_forward import bundle


def bars(count=650):
    return [dict(timestamp_ms=i * STEP_MS, open=100., high=101., low=99.,
                 close=100., volume=100.) for i in range(count)]


def rules():
    return dict(step=.001, minimum_quantity=.001, minimum_notional=1., maximum_quantity=100.)


def run(rows, features, slip=5):
    return model.simulate(rows, features, 1, rules(), 100., slip)


def feature(side, atr=1.):
    return dict(side=side, atr=atr)


def test_prior_box_excludes_breakout_bar_and_volume_is_required():
    rows = bars()
    # First decision at index 599 is the end of the 200th complete 15m bar.
    for row in rows[597:600]:
        row.update(open=102., high=103., low=101.5, close=102., volume=200.)
    result = model.decisions(rows)
    assert result[599]['side'] == 'BUY'
    assert result[599]['decision_end_ms'] == rows[600]['timestamp_ms']
    assert result[598] is None and result[600] is None
    for row in rows[597:600]: row['volume'] = 100.
    assert model.decisions(rows)[599]['side'] != 'BUY'


def test_exit_does_not_require_breakout_volume_or_router():
    rows = bars()
    for row in rows[597:600]:
        row.update(open=99., high=99.5, low=98., close=99., volume=0.)
    assert model.decisions(rows)[599]['side'] == 'SELL'


def test_future_candles_cannot_change_prior_decisions():
    rows = bars(720)
    first = model.decisions(rows)
    changed = copy.deepcopy(rows)
    for row in changed[630:]:
        row.update(open=200., high=202., low=198., close=200., volume=200.)
    assert model.decisions(changed)[:630] == first[:630]


def test_next_open_fill_precise_costs_and_atr_risk():
    rows = bars(4)
    rows[1].update(open=102., high=103., low=101., close=102.)
    features = [feature('BUY'), feature('SELL'), None, None]
    result = run(rows, features)
    trade = result['trades'][0]
    assert trade['index'] == 1 and trade['exit_index'] == 2
    assert trade['price'] == pytest.approx(102 * 1.0005)
    assert trade['exit_price'] == pytest.approx(100 * .9995)
    assert trade['stop_loss'] == pytest.approx(trade['price'] - 2)
    assert trade['take_profit'] == pytest.approx(trade['price'] + 6)
    qty = trade['quantity']
    assert qty * trade['price'] <= 20
    assert qty * 2 <= 1
    assert trade['pnl'] == pytest.approx(qty * (trade['exit_price'] - trade['price']) - trade['fee'] - trade['exit_fee'])
    assert result['end_marked_equity'] == pytest.approx(100 + trade['pnl'])


def test_both_touched_uses_stop_first_on_entry_bar():
    rows = bars(3)
    rows[1].update(high=110., low=90.)
    result = run(rows, [feature('BUY'), None, None], slip=0)
    assert result['trades'][0]['exit_reason'] == 'BOTH_TOUCHED_STOP_FIRST'
    assert result['trades'][0]['exit_price'] == 98


@pytest.mark.parametrize('opening,expected,reason', [(90., 90., 'GAP_STOP'),
                                                   (110., 106., 'GAP_TARGET')])
def test_stop_gap_uses_open_and_target_gap_is_capped(opening, expected, reason):
    rows = bars(3)
    rows[2].update(open=opening, high=opening + 1, low=opening - 1, close=opening)
    result = run(rows, [feature('BUY'), None, None], slip=0)
    trade = result['trades'][0]
    assert trade['exit_price'] == expected
    assert trade['exit_reason'] == reason


def test_position_carries_without_duplicate_entries_and_final_inventory_is_marked():
    rows = bars(5)
    result = run(rows, [feature('BUY')] * 5)
    assert result['trades'] == []
    assert result['open_entry']['index'] == 1
    assert result['open_quantity'] > 0
    assert result['end_marked_equity'] < 100


def test_sell_without_inventory_cannot_short():
    assert run(bars(4), [feature('SELL')] * 4)['open_quantity'] == 0


@pytest.mark.parametrize('atr', [0., None, float('nan'), 1000.])
def test_invalid_stop_distance_never_opens(atr):
    result = run(bars(3), [feature('BUY', atr), None, None])
    assert result['open_quantity'] == 0
    assert result['blockers']['INVALID_STOP_DISTANCE'] == 1


def test_entry_below_minimum_does_not_create_inventory():
    metadata = rules() | {'minimum_notional': 50}
    result = model.simulate(bars(3), [feature('BUY'), None, None], 1, metadata, 100., 5)
    assert result['open_quantity'] == 0
    assert result['blockers']['ENTRY_SIZE_OR_CASH'] == 1


def test_old_data_rejected_and_freeze_date_is_exact():
    data = bundle()
    start = model.POLICY['prospective_start_ms'] - 1000 * STEP_MS
    for i, row in enumerate(data['candles']): row['timestamp_ms'] = start + i * STEP_MS
    data.update(start_ms=start, end_ms_exclusive=start + len(data['candles']) * STEP_MS,
                collected_at_ms=start + len(data['candles']) * STEP_MS + 1000,
                candles_sha256=digest(data['candles']))
    with pytest.raises(ValueError, match='Previously inspected'):
        model.evaluate(data)
    assert datetime.fromtimestamp(model.POLICY['prospective_start_ms'] / 1000, timezone.utc).isoformat() == '2026-10-20T00:00:00+00:00'
    assert model.POLICY_SHA256 == digest(model.POLICY)


def test_prospective_flat_data_reports_no_trades_without_mutation():
    data = bundle(4700)
    start = model.POLICY['prospective_start_ms']
    for i, row in enumerate(data['candles']): row['timestamp_ms'] = start + i * STEP_MS
    data.update(start_ms=start, end_ms_exclusive=start + 4700 * STEP_MS,
                collected_at_ms=start + 4700 * STEP_MS + 1000,
                candles_sha256=digest(data['candles']))
    saved = copy.deepcopy(data)
    report = model.evaluate(data)
    assert report['executable'] is report['live_eligible'] is False
    assert data == saved
    for case in report['scenarios']:
        assert case['closed_trades'] == 0
        assert case['end_marked_equity'] == 100
        assert case['open_quantity'] == 0
    json.dumps(report, allow_nan=False)
