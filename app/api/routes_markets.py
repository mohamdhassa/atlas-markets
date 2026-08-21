from __future__ import annotations
from fastapi import APIRouter,Depends,HTTPException,Query,status
from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.models.auth import User
from app.market_data.bybit import BybitMarketDataError,BybitPublicMarketData,DEFAULT_WATCHLIST
from app.market_data.fx import FX_WATCHLIST,FxMarketDataError,TwelveDataFxMarketData
from app.schemas.market import MarketCandle,MarketSnapshot
router=APIRouter(prefix="/markets",tags=["markets"])
def _provider()->BybitPublicMarketData:
 s=get_settings();return BybitPublicMarketData(s.bybit_public_base_url,s.market_data_timeout_seconds)
def _fx_provider()->TwelveDataFxMarketData:
 s=get_settings();return TwelveDataFxMarketData(s.fx_market_data_base_url,s.fx_market_data_api_key,s.market_data_timeout_seconds)
@router.get("/tickers",response_model=MarketSnapshot)
async def market_tickers(category:str=Query(default="linear",pattern="^(linear|spot)$"),_:User=Depends(get_current_user))->MarketSnapshot:
 try:return await _provider().get_tickers(category=category,symbols=DEFAULT_WATCHLIST)
 except (BybitMarketDataError,ValueError) as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
@router.get("/candles/{symbol}",response_model=list[MarketCandle])
async def market_candles(symbol:str,interval:str=Query(default="5m"),category:str=Query(default="linear",pattern="^(linear|spot)$"),limit:int=Query(default=120,ge=1,le=500),_:User=Depends(get_current_user))->list[MarketCandle]:
 try:return await _provider().get_candles(symbol=symbol,interval=interval,category=category,limit=limit)
 except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
 except BybitMarketDataError as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
@router.get("/fx")
async def fx_quotes(_:User=Depends(get_current_user)):
 try:
  provider=_fx_provider();return {"market":"FX","provider":"TWELVE_DATA","symbols":[await provider.get_quote(s) for s in FX_WATCHLIST]}
 except ValueError as exc:raise HTTPException(status_code=503,detail=str(exc)) from exc
 except FxMarketDataError as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
@router.get("/fx/{symbol}/candles")
async def fx_candles(symbol:str,interval:str=Query(default="5m"),limit:int=Query(default=120,ge=20,le=500),_:User=Depends(get_current_user)):
 try:return await _fx_provider().get_candles(symbol,interval,limit)
 except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
 except FxMarketDataError as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
