from fastapi import APIRouter,Body,Depends,HTTPException,Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.analysis.adaptive_strategy import select_strategy
from app.analysis.asset_universe import profile_for,universe_profiles,universe_summary
from app.analysis.strategy_intelligence import scenario_from_candles
from app.analysis.shadow_strategy import evaluate_shadow_strategy,walk_forward_shadow_backtest
from app.analysis.technical import analyze_candles
from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.models.auth import User
from app.db.models.shadow import ShadowObservation
from app.db.session import get_db
from app.market_data.bybit import BybitMarketDataError,BybitPublicMarketData
from app.market_data.fx import FxMarketDataError,TwelveDataFxMarketData
from app.services.provider_credentials import active_twelve_data_key
router=APIRouter(prefix="/analysis",tags=["analysis"])
def _client():
 s=get_settings();return BybitPublicMarketData(s.bybit_public_base_url,s.market_data_timeout_seconds)
def _fx_client(db:Session,user:User):
 s=get_settings();return TwelveDataFxMarketData(s.fx_market_data_base_url,active_twelve_data_key(db,user.id) or s.fx_market_data_api_key,s.market_data_timeout_seconds)
async def _analyze(client,symbol,interval,category,limit=200):
 candles=await client.get_candles(symbol=symbol,interval=interval,category=category,limit=limit);result=analyze_candles([c.model_dump() for c in candles]);return {"symbol":symbol.upper(),"interval":interval,"category":category,"candles":len(candles),**result}
@router.get("/universe")
async def asset_universe(_:User=Depends(get_current_user)):return {"groups":universe_summary(),"profiles":universe_profiles()}
@router.post("/adaptive/from-candles")
async def adaptive_from_candles(payload:dict=Body(...),_:User=Depends(get_current_user)):
 candles=payload.get("candles") or [];symbol=str(payload.get("symbol") or "").upper().replace("/","");profile=profile_for(symbol);families=payload.get("strategy_families") or (profile.strategy_families if profile else ("trend","momentum","breakout","mean_reversion"))
 if not isinstance(candles,list) or len(candles)<30:raise HTTPException(status_code=400,detail="at least 30 normalized OHLC candles are required")
 return {"symbol":symbol,"asset_profile":profile.__dict__ if profile else None,**select_strategy(candles,families)}
@router.post("/shadow/from-candles")
async def shadow_from_candles(payload:dict=Body(...),_:User=Depends(get_current_user)):
 candles=payload.get("candles") or []
 if not isinstance(candles,list) or len(candles)<30:raise HTTPException(status_code=400,detail="at least 30 normalized OHLC candles are required")
 try:
  return evaluate_shadow_strategy(candles,symbol=str(payload.get("symbol") or "UNKNOWN"),market=str(payload.get("market") or "STOCK"),timeframe=str(payload.get("timeframe") or "5m"),higher_timeframes=payload.get("higher_timeframes") or [],news_score=payload.get("news_score"),vision_observation=payload.get("vision_observation"))
 except (KeyError,TypeError,ValueError) as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
@router.post("/shadow/backtest")
async def shadow_backtest(payload:dict=Body(...),_:User=Depends(get_current_user)):
 candles=payload.get("candles") or []
 try:
  return walk_forward_shadow_backtest(candles,symbol=str(payload.get("symbol") or "UNKNOWN"),market=str(payload.get("market") or "STOCK"),timeframe=str(payload.get("timeframe") or "5m"),horizon=int(payload.get("horizon") or 6),cost_bps=float(payload.get("cost_bps") or 8.0))
 except (KeyError,TypeError,ValueError) as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
@router.get("/shadow/observations")
async def shadow_observations(limit:int=Query(100,ge=1,le=500),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 rows=list(db.scalars(select(ShadowObservation).where(ShadowObservation.user_id==user.id).order_by(ShadowObservation.created_at.desc()).limit(limit)).all())
 return [{"id":x.id,"provider":x.provider,"market":x.market,"symbol":x.symbol,"timeframe":x.timeframe,"action":x.action,"confidence":x.confidence,"regime":x.regime,"confirmations":x.confirmations,"contradictions":x.contradictions,"entry_price":x.entry_price,"exit_price":x.exit_price,"net_return_pct":x.net_return_pct,"outcome":x.outcome,"evaluation_due_at":x.evaluation_due_at,"settled_at":x.settled_at,"created_at":x.created_at} for x in rows]
@router.get("/shadow/performance")
async def shadow_performance(days:int=Query(30,ge=1,le=366),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 from datetime import datetime,timedelta,timezone
 since=datetime.now(timezone.utc)-timedelta(days=days);rows=list(db.scalars(select(ShadowObservation).where(ShadowObservation.user_id==user.id,ShadowObservation.created_at>=since).order_by(ShadowObservation.created_at.desc())).all());groups={}
 for x in rows:
  key=(x.provider,x.market,x.symbol,x.timeframe);g=groups.setdefault(key,{"provider":x.provider,"market":x.market,"symbol":x.symbol,"timeframe":x.timeframe,"observations":0,"directional":0,"settled":0,"wins":0,"losses":0,"pending":0,"net_return_pct":0.0,"latest_action":x.action,"latest_confidence":x.confidence,"latest_regime":x.regime,"latest_at":x.created_at})
  g["observations"]+=1;g["directional"]+=int(x.action in {"BUY","SELL"});g["pending"]+=int(x.outcome=="PENDING")
  if x.settled_at is not None and x.action in {"BUY","SELL"}:g["settled"]+=1;g["wins"]+=int(x.outcome=="WIN");g["losses"]+=int(x.outcome=="LOSS");g["net_return_pct"]+=float(x.net_return_pct or 0)
 out=[]
 for g in groups.values():g["win_rate"]=round(g["wins"]/g["settled"]*100,2) if g["settled"] else None;g["net_return_pct"]=round(g["net_return_pct"],4);g["eligible"]=g["settled"]>=30 and g["net_return_pct"]>0 and (g["win_rate"] or 0)>=50;out.append(g)
 return {"days":days,"mode":"SHADOW","execution_enabled":False,"summary":{"observations":len(rows),"settled":sum(x["settled"] for x in out),"pending":sum(x["pending"] for x in out),"eligible":sum(x["eligible"] for x in out)},"strategies":out,"safety":"Shadow performance cannot enable broker execution."}
@router.get("/{symbol}/multi")
async def multi_timeframe_analysis(symbol:str,category:str=Query("linear"),_:User=Depends(get_current_user)):
 try:results=[await _analyze(_client(),symbol,f,category) for f in ("4h","1h","15m","5m")]
 except (BybitMarketDataError,ValueError) as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
 directions=[x["bias"] for x in results];lc=directions.count("LONG");sc=directions.count("SHORT");return {"symbol":symbol.upper(),"category":category,"alignment":"LONG_ALIGNED" if lc>=3 else "SHORT_ALIGNED" if sc>=3 else "MIXED","confidence":round(max(lc,sc)/4*100,1),"timeframes":results}
@router.get("/fx/{symbol}/scenario")
async def fx_strategy_scenario(symbol:str,interval:str=Query("5m"),limit:int=Query(200,ge=60,le=500),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 try:
  candles=await _fx_client(db,user).get_candles(symbol,interval,limit);return {"symbol":symbol.upper().replace("/",""),**scenario_from_candles(candles,timeframe=interval,market="FX")}
 except ValueError as exc:raise HTTPException(status_code=503,detail=str(exc)) from exc
 except FxMarketDataError as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
@router.get("/{symbol}/scenario")
async def strategy_scenario(symbol:str,interval:str=Query("5m"),category:str=Query("linear"),limit:int=Query(200,ge=60,le=500),_:User=Depends(get_current_user)):
 try:
  candles=await _client().get_candles(symbol=symbol,interval=interval,category=category,limit=limit);return {"symbol":symbol.upper(),**scenario_from_candles([c.model_dump() for c in candles],timeframe=interval,market="CRYPTO")}
 except (BybitMarketDataError,ValueError) as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
@router.post("/scenario/from-candles")
async def scenario_from_external_candles(payload:dict=Body(...),_:User=Depends(get_current_user)):
 candles=payload.get("candles") or []
 if not isinstance(candles,list) or len(candles)<30:raise HTTPException(status_code=400,detail="at least 30 normalized OHLC candles are required")
 try:return scenario_from_candles(candles,timeframe=str(payload.get("timeframe") or "5m"),market=str(payload.get("market") or "FX"))
 except (KeyError,TypeError,ValueError) as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
@router.get("/{symbol}")
async def technical_analysis(symbol:str,interval:str=Query("5m"),category:str=Query("linear"),limit:int=Query(200,ge=60,le=500),_:User=Depends(get_current_user)):
 try:return await _analyze(_client(),symbol,interval,category,limit)
 except (BybitMarketDataError,ValueError) as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
