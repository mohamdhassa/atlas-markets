from app.analysis.technical import analyze_candles, ema, rsi


def sample_candles(count: int = 80):
    rows = []
    price = 100.0
    for i in range(count):
        close = price + i * 0.5
        rows.append({"open": close - 0.2, "high": close + 0.8, "low": close - 0.8, "close": close, "volume": 1000 + i})
    return rows


def test_ema_and_rsi_are_calculated():
    values = [float(i) for i in range(1, 80)]
    assert ema(values, 20) is not None
    assert rsi(values, 14) == 100.0


def test_analysis_returns_bullish_bias_for_rising_market():
    result = analyze_candles(sample_candles())
    assert result["trend"] == "BULLISH"
    assert result["structure"] == "BULLISH"
    assert result["bias"] == "LONG"
    assert result["score"] >= 65
    assert result["support"] < result["resistance"]


def test_analysis_requires_enough_candles():
    try:
        analyze_candles(sample_candles(20))
    except ValueError as exc:
        assert "30 candles" in str(exc)
    else:
        raise AssertionError("expected ValueError")
