from app.analysis.strategy_intelligence import detect_candlestick_patterns, detect_breakout, scenario_from_candles


def candles_up(n=80):
    out=[];price=100.0
    for i in range(n):
        o=price;c=price+0.6;out.append({"open":o,"high":c+0.25,"low":o-0.15,"close":c});price=c
    return out


def test_bullish_scenario_has_action_and_levels():
    s=scenario_from_candles(candles_up(),timeframe="5m",market="FX")
    assert s["action"] in {"BUY","WAIT"}
    assert 0 <= s["bullish_probability"] <= 100
    assert s["support"] < s["resistance"]
    assert "methodology" in s


def test_bullish_engulfing_detection():
    cs=candles_up(30);cs[-2]={"open":102,"high":102.2,"low":100.8,"close":101};cs[-1]={"open":100.9,"high":102.5,"low":100.7,"close":102.3}
    names=[p.name for p in detect_candlestick_patterns(cs)]
    assert "BULLISH_ENGULFING" in names


def test_breakout_detection():
    cs=candles_up(30);level=max(x["high"] for x in cs[-21:-1]);cs[-1]["close"]=level+2;cs[-1]["high"]=level+2.2
    assert detect_breakout(cs)["state"]=="BULLISH_BREAKOUT"
