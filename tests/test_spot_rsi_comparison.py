import copy
import json

import pytest

from app.analysis import technical
from app.backtesting import spot_rsi_comparison as research
from app.services.signal_risk import generate_signal
from test_spot_walk_forward import bundle


@pytest.mark.parametrize('values,expected', [
    ([100.] * 15, 50), ([1.] * 15, 50), ([100.] * 14, None),
    (list(range(15)), 100), (list(reversed(range(15))), 0),
    ([100., 101.] * 8, None),
])
def test_only_flat_lookback_changes(values, expected):
    original = research._ORIGINAL_RSI(values)
    result = research.research_rsi(values)
    if expected is None and len(values) > 14:
        assert result == original
    else:
        assert result == expected
    assert technical.rsi is research._ORIGINAL_RSI


def test_prior_moves_outside_lookback_do_not_prevent_neutral_flat_rsi():
    assert research.research_rsi([500., 200.] + [100.] * 15) == 50
    assert research.research_rsi([100., 101.] + [100.] * 14) == technical.rsi([100., 101.] + [100.] * 14)


def test_flat_market_false_sell_reproduced_and_candidate_neutral(monkeypatch):
    rows = bundle()['candles'][:200]
    before = generate_signal(rows)
    assert before.decision == 'SELL' and before.strength == 90
    monkeypatch.setattr(technical, 'rsi', research.research_rsi)
    after = generate_signal(rows)
    assert after.decision == 'HOLD'
    assert 'rsi_overbought_risk' not in after.reasons


def test_replay_keeps_baseline_restores_indicator_and_preserves_data():
    data = bundle()
    saved = copy.deepcopy(data)
    report = research.compare_rsi(data, capital=100, fee_bps=10,
                                  slippage_cases=[2, 5], train_bars=200, test_bars=100)
    assert technical.rsi is research._ORIGINAL_RSI
    assert data == saved
    assert report['validation_decisions_with_flat_rsi_lookback'] == 400
    assert report['executable'] is report['live_eligible'] is False
    for policy in report['policies'].values():
        assert policy['frozen_settings'] == research.baseline.PARAMS
        assert policy['dataset_sha256'] == data['candles_sha256']
        assert policy['scenarios'][0]['validation']['closed_trades'] == 0
        assert policy['scenarios'][0]['validation']['end_marked_equity'] == 100
    json.dumps(report, allow_nan=False)


def test_indicator_restored_if_candidate_fails(monkeypatch):
    calls = []
    def evaluate(*args, **kwargs):
        calls.append(technical.rsi)
        if len(calls) == 2:
            raise RuntimeError('research failed')
        return {}
    monkeypatch.setattr(research.baseline, 'walk_forward_spot', evaluate)
    with pytest.raises(RuntimeError, match='research failed'):
        research.compare_rsi(bundle(), capital=100, fee_bps=10, slippage_cases=[5])
    assert calls == [research._ORIGINAL_RSI, research.research_rsi]
    assert technical.rsi is research._ORIGINAL_RSI
