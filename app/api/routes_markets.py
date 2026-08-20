from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.models.auth import User
from app.market_data.bybit import BybitMarketDataError, BybitPublicMarketData, DEFAULT_WATCHLIST
from app.schemas.market import MarketCandle, MarketSnapshot

router = APIRouter(prefix="/markets", tags=["markets"])


def _provider() -> BybitPublicMarketData:
    settings = get_settings()
    return BybitPublicMarketData(settings.bybit_public_base_url, settings.market_data_timeout_seconds)


@router.get("/tickers", response_model=MarketSnapshot)
async def market_tickers(
    category: str = Query(default="linear", pattern="^(linear|spot)$"),
    _: User = Depends(get_current_user),
) -> MarketSnapshot:
    try:
        return await _provider().get_tickers(category=category, symbols=DEFAULT_WATCHLIST)
    except (BybitMarketDataError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/candles/{symbol}", response_model=list[MarketCandle])
async def market_candles(
    symbol: str,
    interval: str = Query(default="5m"),
    category: str = Query(default="linear", pattern="^(linear|spot)$"),
    limit: int = Query(default=120, ge=1, le=500),
    _: User = Depends(get_current_user),
) -> list[MarketCandle]:
    try:
        return await _provider().get_candles(
            symbol=symbol,
            interval=interval,
            category=category,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except BybitMarketDataError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
