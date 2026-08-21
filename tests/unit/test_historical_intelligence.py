from app.services.historical_backtest import backtest_strategy
from app.services.historical_intelligence import historical_probability

def candles(n=160,step=0.15):
    out=[];price=100.0
    for i in range(n):
        price+=step if i%9!=0 else -step*2
        out.append({"open":price-0.05,"high":price+0.15,"low":price-0.15,"close":price,"volume":1000+i,"timestamp_ms":i*300000})
    return out

def test_historical_probability_returns_matches():
    result=historical_probability(candles(),horizon=6,max_matches=40)
    assert result["matches"]==40
    assert 0<=result["up_probability"]<=100
    assert result["down_probability"]==round(100-result["up_probability"],1)

def test_historical_probability_handles_small_sample():
    result=historical_probability(candles(40))
    assert result["matches"]==0
    assert result["confidence"]=="INSUFFICIENT_DATA"

def test_walk_forward_backtest_returns_metrics():
    result=backtest_strategy(candles(180),market="CRYPTO",interval="5m",horizon=6)
    assert result["sample_count"]==180
    assert result["signals"]>=0
    assert 0<=result["win_rate"]<=100
    assert result["max_drawdown_pct"]>=0
