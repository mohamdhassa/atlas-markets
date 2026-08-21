from fastapi import APIRouter,Body,Depends,HTTPException,Query
from app.analysis.adaptive_strategy import select_strategy
from app.analysis.asset_universe import profile_for,universe_profiles,universe_summary
from app.analysis.strategy_intelligence import scenario_from_candles
from app.analysis.technical import analyze_candles
from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.models.auth import User
from app.market_data.bybit import BybitMarketDataError,BybitPublicMarketData
from app.market_data.fx import FxMarketDataError,TwelveDataFxMarketData
router=APIRouter(prefix="/analysis",tags=["analysis"])
def _client():
 s=get_settings();return BybitPublicMarketData(s.bybit_public_base_url,s.market_data_timeout_seconds)
def _fx_client():
 s=get_settings();return TwelveDataFxMarketData(s.fx_market_data_base_url,s.fx_market_data_api_key,s.market_data_timeout_seconds)
async def _analyze(client,symbol,interval,category,limit=200):
 candles=await client.get_candles(symbol=symbol,interval=interval,category=category,limit=limit);result=analyze_candles([c.model_dump() for c in candles]);return {"symbol":symbol.upper(),"interval":interval,"category":category,"candles":len(candles),**result}
@router.get("/universe")
async def asset_universe(_:User=Depends(get_current_user)):return {"groups":universe_summary(),"profiles":universe_profiles()}
@router.post("/adaptive/from-candles")
async def adaptive_from_candles(payload:dict=Body(...),_:User=Depends(get_current_user)):
 candles=payload.get("candles") or [];symbol=str(payload.get("symbol") or "").upper().replace("/","");profile=profile_for(symbol);families=payload.get("strategy_families") or (profile.strategy_families if profile else ("trend","momentum","breakout","mean_reversion"))
 if not isinstance(candles,list) or len(candles)<30:raise HTTPException(status_code=400,detail="at least 30 normalized OHLC candles are required")
 return {"symbol":symbol,"asset_profile":profile.__dict__ if profile else None,**select_strategy(candles,families)}
@router.get("/{symbol}/multi")
async def multi_timeframe_analysis(symbol:str,category:str=Query("linear"),_:User=Depends(get_current_user)):
 try:results=[await _analyze(_client(),symbol,f,category) for f in ("4h","1h","15m","5m")]
 except (BybitMarketDataError,ValueError) as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
 directions=[x["bias"] for x in results];lc=directions.count("LONG");sc=directions.count("SHORT");return {"symbol":symbol.upper(),"category":category,"alignment":"LONG_ALIGNED" if lc>=3 else "SHORT_ALIGNED" if sc>=3 else "MIXED","confidence":round(max(lc,sc)/4*100,1),"timeframes":results}
@router.get("/fx/{symbol}/scenario")
async def fx_strategy_scenario(symbol:str,interval:str=Query("5m"),limit:int=Query(200,ge=60,le=500),_:User=Depends(get_current_user)):
 try:
  candles=await _fx_client().get_candles(symbol,interval,limit);return {"symbol":symbol.upper().replace("/",""),**scenario_from_candles(candles,timeframe=interval,market="FX")}
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
