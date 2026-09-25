from __future__ import annotations
import asyncio,json
from datetime import datetime,timedelta,timezone
from sqlalchemy import select
from app.analysis.shadow_strategy import evaluate_shadow_strategy
from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.broker import BrokerProfile
from app.db.models.shadow import ShadowObservation
from app.db.models.symbol_strategy import SymbolStrategy
from app.db.session import SessionLocal
from app.market_data.bybit import BybitPublicMarketData
from app.services.news_intelligence import context_for_symbol

HORIZON_BARS=6
ROUND_TRIP_COST_BPS=8.0

def timeframe_seconds(value:str)->int:
 units={"m":60,"h":3600,"d":86400,"w":604800};value=str(value or "5m").strip().lower()
 try:return max(60,int(value[:-1])*units[value[-1]])
 except (KeyError,TypeError,ValueError):return 300

def _secret(profile):return json.loads(decrypt_secret(profile.credential_blob_encrypted)) if profile.credential_blob_encrypted else {}
def _timestamp_ms(value):
 if isinstance(value,(int,float)):return int(value)
 try:
  parsed=datetime.fromisoformat(str(value).replace("Z","+00:00"));return int(parsed.timestamp()*1000)
 except (TypeError,ValueError):return 0
def _rows(payload):
 if isinstance(payload,dict):payload=payload.get("candles") or payload.get("list") or payload.get("data") or []
 out=[]
 for x in payload or []:
  if hasattr(x,"model_dump"):x=x.model_dump()
  out.append({"timestamp_ms":_timestamp_ms(x.get("timestamp_ms") or x.get("time") or x.get("timestamp")),"open":float(x["open"]),"high":float(x["high"]),"low":float(x["low"]),"close":float(x["close"]),"volume":float(x.get("volume") or 0)})
 return sorted(out,key=lambda x:x["timestamp_ms"])

async def candles_for(profile,symbol,timeframe,limit=240):
 s=get_settings();c=_secret(profile)
 if profile.provider=="IBKR":return _rows(await IbkrBridgeClient(c.get("bridge_url") or "http://host.docker.internal:8766",c.get("bridge_token"),s.market_data_timeout_seconds).candles(symbol,timeframe,limit))
 if profile.provider=="MT5":return _rows(await Mt5BridgeClient(c.get("bridge_url") or "http://host.docker.internal:8765",c.get("bridge_token"),s.market_data_timeout_seconds).candles(symbol,timeframe,limit))
 if profile.provider=="BYBIT":return _rows(await BybitPublicMarketData(s.bybit_public_base_url,s.market_data_timeout_seconds).get_candles(symbol=symbol,interval=timeframe,category="spot",limit=limit))
 return []

def settle_due(db,strategy,latest_price,now):
 rows=list(db.scalars(select(ShadowObservation).where(ShadowObservation.strategy_id==strategy.id,ShadowObservation.outcome=="PENDING",ShadowObservation.evaluation_due_at<=now)).all());settled=0
 for x in rows:
  raw=((latest_price/x.entry_price)-1)*100 if x.entry_price else 0;gross=raw if x.action=="BUY" else -raw if x.action=="SELL" else 0;net=gross-(ROUND_TRIP_COST_BPS/100) if x.action in {"BUY","SELL"} else 0
  x.exit_price=latest_price;x.gross_return_pct=round(gross,6);x.net_return_pct=round(net,6);x.outcome="WIN" if net>0 else "LOSS" if net<0 else "FLAT";x.settled_at=now;settled+=1
 return settled

async def observe_strategy(db,strategy,profile,now):
 timeframe=strategy.timeframe or "5m";candles=await candles_for(profile,strategy.symbol,timeframe)
 if len(candles)<80:return {"status":"SKIP","reason":"INSUFFICIENT_CANDLES","symbol":strategy.symbol}
 latest=candles[-1];timestamp_ms=int(latest.get("timestamp_ms") or int(now.timestamp()*1000));settled=settle_due(db,strategy,float(latest["close"]),now)
 if db.scalar(select(ShadowObservation.id).where(ShadowObservation.strategy_id==strategy.id,ShadowObservation.source_timestamp_ms==timestamp_ms)):return {"status":"EXISTS","symbol":strategy.symbol,"settled":settled}
 news=context_for_symbol(db,strategy.symbol);decision=evaluate_shadow_strategy(candles,symbol=strategy.symbol,market=strategy.market,timeframe=timeframe,news_score=news.sentiment if news.article_count else None)
 db.add(ShadowObservation(user_id=strategy.user_id,broker_profile_id=profile.id,strategy_id=strategy.id,provider=profile.provider,market=strategy.market,symbol=strategy.symbol,timeframe=timeframe,action=decision["action"],confidence=decision["confidence"],regime=decision["regime"],confirmations=decision["confirmations"],contradictions=decision["contradictions"],entry_price=float(latest["close"]),source_timestamp_ms=timestamp_ms,horizon_bars=HORIZON_BARS,evaluation_due_at=now+timedelta(seconds=timeframe_seconds(timeframe)*HORIZON_BARS),news_score=news.sentiment if news.article_count else None,outcome="PENDING",details_json=json.dumps({"reasons":decision["reasons"],"calibration":decision["calibration"],"regime_details":decision["regime_details"],"news_articles":news.article_count})))
 return {"status":"OBSERVED","symbol":strategy.symbol,"action":decision["action"],"settled":settled}

async def run_shadow_scan():
 now=datetime.now(timezone.utc);result={"observed":0,"settled":0,"skipped":0,"errors":[]}
 with SessionLocal() as db:
  for strategy in db.scalars(select(SymbolStrategy).where(SymbolStrategy.enabled.is_(True))).all():
   profile=db.get(BrokerProfile,strategy.profile_id)
   if not profile or not profile.is_enabled or not profile.is_active:result["skipped"]+=1;continue
   try:
    row=await observe_strategy(db,strategy,profile,now);result["observed"]+=int(row["status"]=="OBSERVED");result["settled"]+=int(row.get("settled") or 0);result["skipped"]+=int(row["status"] in {"SKIP","EXISTS"});db.commit()
   except Exception as exc:db.rollback();result["errors"].append({"symbol":strategy.symbol,"error":f"{type(exc).__name__}: {str(exc)[:160]}"})
 return result

async def shadow_monitor_loop(stop_event,interval_seconds=300):
 while not stop_event.is_set():
  try:await run_shadow_scan()
  except Exception:pass
  try:await asyncio.wait_for(stop_event.wait(),timeout=max(60,interval_seconds))
  except asyncio.TimeoutError:continue
