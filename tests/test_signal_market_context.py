from pathlib import Path

from app.services import signal_risk


def _candles():
    return [
        {'open': 1.0, 'high': 1.2, 'low': 0.9, 'close': 1.1},
        {'open': 1.1, 'high': 1.3, 'low': 1.0, 'close': 1.2},
        {'open': 1.2, 'high': 1.4, 'low': 1.1, 'close': 1.3},
    ]


def test_generate_signal_passes_market_and_timeframe(monkeypatch):
    seen = {}

    def fake_scenario(candles, *, timeframe, market):
        seen['timeframe'] = timeframe
        seen['market'] = market
        return {
            'action': 'WAIT',
            'bullish_probability': 50.0,
            'bearish_probability': 50.0,
            'trend': 'NEUTRAL',
            'reasons': [],
        }

    monkeypatch.setattr(signal_risk, 'scenario_from_candles', fake_scenario)
    signal_risk.generate_signal(_candles(), timeframe='15m', market='FX')
    assert seen == {'timeframe': '15m', 'market': 'FX'}


def test_automation_and_exit_paths_use_configured_context():
    readiness = Path('app/services/autotrade_readiness.py').read_text(encoding='utf-8')
    lifecycle = Path('app/services/position_lifecycle.py').read_text(encoding='utf-8')
    assert 'timeframe=timeframe,market=signal_market' in readiness
    assert "timeframe=timeframe, market=market or 'FX'" in lifecycle
    assert 'scenario_from_candles(candles,timeframe="5m",market="CRYPTO")' not in Path('app/services/signal_risk.py').read_text(encoding='utf-8')
