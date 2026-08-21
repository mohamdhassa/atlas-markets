from __future__ import annotations

from app.analysis.strategy_intelligence import scenario_from_candles


def backtest_strategy(candles:list[dict],*,market:str,interval:str,horizon:int=6,warmup:int=80)->dict:
    if len(candles)<warmup+horizon+1:
        return {"sample_count":len(candles),"signals":0,"wins":0,"losses":0,"win_rate":0.0,"avg_return_pct":0.0,"max_drawdown_pct":0.0}
    outcomes=[];equity=1.0;peak=1.0;max_dd=0.0
    for i in range(warmup,len(candles)-horizon):
        window=candles[:i+1]
        scenario=scenario_from_candles(window,timeframe=interval,market=market)
        action=scenario.get("action")
        if action not in {"BUY","SELL"}:continue
        entry=float(candles[i]["close"]);future=float(candles[i+horizon]["close"]);raw=((future/entry)-1.0)*100 if entry else 0.0
        result=raw if action=="BUY" else -raw
        outcomes.append(result);equity*=1+(result/100);peak=max(peak,equity);dd=((peak-equity)/peak*100) if peak else 0.0;max_dd=max(max_dd,dd)
    wins=sum(1 for x in outcomes if x>0);losses=sum(1 for x in outcomes if x<=0);signals=len(outcomes)
    return {"sample_count":len(candles),"signals":signals,"wins":wins,"losses":losses,"win_rate":round(wins/signals*100,1) if signals else 0.0,"avg_return_pct":round(sum(outcomes)/signals,4) if signals else 0.0,"max_drawdown_pct":round(max_dd,3),"horizon_bars":horizon}
