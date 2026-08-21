from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from math import sqrt
from sqlalchemy import select
from app.db.models.historical import HistoricalCandle
from app.db.session import SessionLocal
from app.market_data.bybit import BybitPublicMarketData, DEFAULT_WATCHLIST
from app.market_data.fx import FX_WATCHLIST, TwelveDataFxMarketData
from app.core.config import get_settings


def _feature(candles:list[dict],i:int)->tuple[float,float,float,float]:
    c=float(candles[i]["close"])
    def ret(n:int)->float:
        p=float(candles[i-n]["close"]);return ((c/p)-1)*100 if p else 0.0
    rng=(float(candles[i]["high"])-float(candles[i]["low"]))/c*100 if c else 0.0
    return ret(3),ret(6),ret(12),rng

def historical_probability(candles:list[dict],horizon:int=6,max_matches:int=60)->dict:
    if len(candles)<80:return {"matches":0,"up_probability":50.0,"down_probability":50.0,"avg_forward_return_pct":0.0,"confidence":"INSUFFICIENT_DATA"}
    current=_feature(candles,len(candles)-1);candidates=[]
    for i in range(20,len(candles)-horizon-1):
        f=_feature(candles,i);distance=sqrt(sum((a-b)**2 for a,b in zip(current,f)));entry=float(candles[i]["close"]);future=float(candles[i+horizon]["close"]);forward=((future/entry)-1)*100 if entry else 0.0;candidates.append((distance,forward))
    matches=sorted(candidates,key=lambda x:x[0])[:max_matches]
    if not matches:return {"matches":0,"up_probability":50.0,"down_probability":50.0,"avg_forward_return_pct":0.0,"confidence":"INSUFFICIENT_DATA"}
    ups=sum(1 for _,r in matches if r>0);avg=sum(r for _,r in matches)/len(matches);up=round(ups/len(matches)*100,1)
    return {"matches":len(matches),"up_probability":up,"down_probability":round(100-up,1),"avg_forward_return_pct":round(avg,4),"confidence":"HIGH" if len(matches)>=50 else "MEDIUM" if len(matches)>=25 else "LOW","horizon_bars":horizon}

def db_candles(db,market:str,symbol:str,interval:str,limit:int=5000)->list[dict]:
    rows=list(db.scalars(select(HistoricalCandle).where(HistoricalCandle.market==market,HISTORICAL_PLACEHOLDER if False else HistoricalCandle.symbol==symbol,HistoricalCandle.interval==interval).order_by(HistoricalCandle.timestamp_ms.asc()).limit(limit)).all())
    return [{"timestamp_ms":r.timestamp_ms,"open":r.open,"high":r.high,"low":r.low,"close":r.close,"volume":r.volume} for r in rows]

def store_candles(db,market:str,symbol:str,interval:str,candles:list[dict])->int:
    existing=set(db.scalars(select(HistoricalCandle.timestamp_ms).where(HistoricalCandle.market==market,HistoricalCandle.symbol==symbol,HistoricalCandle.interval==interval)).all());added=0
    for c in candles:
        ts=c.get("timestamp_ms")
        if ts is None:
            raw=c.get("timestamp");dt=datetime.fromisoformat(str(raw).replace("Z","+00:00"));ts=int(dt.replace(tzinfo=dt.tzinfo or timezone.utc).timestamp()*1000)
        ts=int(ts)
        if ts in existing:continue
        db.add(HistoricalCandle(market=market,symbol=symbol,interval=interval,timestamp_ms=ts,open=float(c["open"]),high=float(c["high"]),low=float(c["low"]),close=float(c["close"]),volume=float(c.get("volume") or 0)));existing.add(ts);added+=1
    db.commit();return added

async def refresh_history(interval:str="5m"):
    s=get_settings();crypto=BybitPublicMarketData(s.bybit_public_base_url,s.market_data_timeout_seconds)
    with SessionLocal() as db:
        for symbol in DEFAULT_WATCHLIST:
            try:store_candles(db,"CRYPTO",symbol,interval,[c.model_dump() for c in await crypto.get_candles(symbol=symbol,interval=interval,category="linear",limit=500)])
            except Exception:pass
        if s.fx_market_data_api_key:
            fx=TwelveDataFxMarketData(s.fx_market_data_base_url,s.fx_market_data_api_key,s.market_data_timeout_seconds)
            for symbol in FX_WATCHLIST:
                try:store_candles(db,"FX",symbol,interval,await fx.get_candles(symbol,interval,500))
                except Exception:pass

async def historical_loop(stop_event:asyncio.Event):
    while not stop_event.is_set():
        try:await refresh_history()
        except Exception:pass
        try:await asyncio.wait_for(stop_event.wait(),timeout=3600)
        except asyncio.TimeoutError:pass
