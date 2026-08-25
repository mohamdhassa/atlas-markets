from __future__ import annotations
import json
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.auth import User
from app.db.session import get_db
from app.market_data.bybit import BybitMarketDataError,BybitPublicMarketData,DEFAULT_WATCHLIST
from app.market_data.fx import FX_WATCHLIST,FxMarketDataError,TwelveDataFxMarketData
from app.schemas.market import MarketCandle,MarketSnapshot
from app.services.provider_credentials import active_provider_profile,active_twelve_data_key
router=APIRouter(prefix='/markets',tags=['markets'])
def _provider()->BybitPublicMarketData:
 s=get_settings();return BybitPublicMarketData(s.bybit_public_base_url,s.market_data_timeout_seconds)
def _fx_provider(db:Session,user:User)->TwelveDataFxMarketData:
 s=get_settings();key=active_twelve_data_key(db,user.id) or s.fx_market_data_api_key
 return TwelveDataFxMarketData(s.fx_market_data_base_url,key,s.market_data_timeout_seconds)
def _mt5_fx(db:Session,user:User)->Mt5BridgeClient|None:
 p=active_provider_profile(db,user.id,'MT5')
 if not p or p.environment!='DEMO' or p.last_connection_status!='CONNECTED' or not p.credential_blob_encrypted:return None
 c=json.loads(decrypt_secret(p.credential_blob_encrypted));return Mt5BridgeClient(c.get('bridge_url') or 'http://host.docker.internal:8765',c.get('bridge_token'),get_settings().market_data_timeout_seconds)
@router.get('/tickers',response_model=MarketSnapshot)
async def market_tickers(category:str=Query(default='linear',pattern='^(linear|spot)$'),_:User=Depends(get_current_user))->MarketSnapshot:
 try:return await _provider().get_tickers(category=category,symbols=DEFAULT_WATCHLIST)
 except (BybitMarketDataError,ValueError) as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
@router.get('/candles/{symbol}',response_model=list[MarketCandle])
async def market_candles(symbol:str,interval:str=Query(default='5m'),category:str=Query(default='linear',pattern='^(linear|spot)$'),limit:int=Query(default=120,ge=1,le=500),_:User=Depends(get_current_user))->list[MarketCandle]:
 try:return await _provider().get_candles(symbol=symbol,interval=interval,category=category,limit=limit)
 except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
 except BybitMarketDataError as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
@router.get('/fx')
async def fx_quotes(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 mt5=_mt5_fx(db,user)
 if mt5:
  try:
   rows=[]
   for s in FX_WATCHLIST:
    info=await mt5.symbol(s);bid=float(info.get('bid') or 0);ask=float(info.get('ask') or 0);price=(bid+ask)/2 if bid and ask else bid or ask
    candles=(await mt5.candles(s,'1d',2)).get('list',[]);prev=float(candles[-2]['close']) if len(candles)>1 else price;change=price-prev;change_pct=(change/prev*100) if prev else 0
    rows.append({'symbol':s,'display_symbol':f'{s[:3]}/{s[3:]}','price':price,'bid':bid,'ask':ask,'change':change,'change_percent':change_pct,'provider':'MT5_FUSION','as_of':info.get('time_msc')})
   return {'market':'FX','provider':'MT5_FUSION','symbols':rows,'fallback_provider':'TWELVE_DATA'}
  except Exception:
   pass
 rows=[];errors=[]
 try:
  provider=_fx_provider(db,user)
  for s in FX_WATCHLIST:
   try:rows.append(await provider.get_quote(s))
   except Exception as exc:errors.append({'symbol':s,'error':str(exc)[:180]})
  if rows:return {'market':'FX','provider':'TWELVE_DATA','symbols':rows,'errors':errors}
  raise HTTPException(503,detail='FX data unavailable from both Fusion MT5 and Twelve Data')
 except ValueError as exc:raise HTTPException(status_code=503,detail=str(exc)) from exc
 except FxMarketDataError as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
@router.get('/fx/{symbol}/candles')
async def fx_candles(symbol:str,interval:str=Query(default='5m'),limit:int=Query(default=120,ge=20,le=500),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 mt5=_mt5_fx(db,user)
 if mt5:
  try:return (await mt5.candles(symbol,interval,limit)).get('list',[])
  except Exception:pass
 try:return await _fx_provider(db,user).get_candles(symbol,interval,limit)
 except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
 except FxMarketDataError as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
