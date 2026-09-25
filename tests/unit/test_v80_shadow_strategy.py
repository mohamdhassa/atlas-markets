from app.analysis.shadow_strategy import detect_regime,evaluate_shadow_strategy,walk_forward_shadow_backtest


def candles(count=180,start=100.0,step=0.45):
    rows=[]
    for index in range(count):
        close=start+(index*step)+(0.18 if index%3==0 else -0.06)
        rows.append({"open":close-0.2,"high":close+0.5,"low":close-0.5,"close":close,"volume":1000+index})
    return rows


def test_shadow_decision_is_never_executable():
    result=evaluate_shadow_strategy(candles(),symbol="AAPL",market="STOCK",timeframe="5m",higher_timeframes=[{"trend":"BULLISH"}],news_score=0.5,vision_observation={"direction":"BUY","confidence":80})
    assert result["mode"]=="SHADOW"
    assert result["executable"] is False
    assert result["action"] in {"BUY","HOLD"}
    assert result["confirmations"]>=2


def test_vision_cannot_create_direction_without_base_signal():
    flat=candles(step=0.0)
    result=evaluate_shadow_strategy(flat,symbol="AAPL",market="STOCK",timeframe="5m",vision_observation={"direction":"BUY","confidence":99})
    assert result["executable"] is False
    assert result["action"]=="HOLD"


def test_symbol_calibration_is_stricter_for_high_volatility_names():
    aapl=evaluate_shadow_strategy(candles(),symbol="AAPL",market="STOCK",timeframe="5m")
    tsla=evaluate_shadow_strategy(candles(),symbol="TSLA",market="STOCK",timeframe="5m")
    assert tsla["threshold"]>aapl["threshold"]
    assert tsla["calibration"]["min_confirmations"]>aapl["calibration"]["min_confirmations"]


def test_regime_and_walk_forward_validation_are_reported_separately():
    rows=candles(200)
    assert detect_regime(rows)["name"] in {"TRENDING_UP","HIGH_VOLATILITY"}
    result=walk_forward_shadow_backtest(rows,symbol="SPY",market="STOCK",timeframe="5m",horizon=4,cost_bps=10)
    assert result["training"] is not result["validation"]
    assert result["cost_bps_per_round_trip"]==10
    assert result["promotion"]["eligible"] is False
    assert result["executable"] is False
