from fastapi import APIRouter, Depends, HTTPException, Query

from app.analysis.technical import analyze_candles
from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.models.auth import User
from app.market_data.bybit import BybitMarketDataError, BybitPublicMarketData

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/{symbol}")
async def technical_analysis(
    symbol: str,
    interval: str = Query("5m"),
    category: str = Query("linear"),
    limit: int = Query(200, ge=60, le=500),
    _: User = Depends(get_current_user),
):
    settings = get_settings()
    client = BybitPublicMarketData(settings.bybit_public_base_url, settings.market_data_timeout_seconds)
    try:
        candles = await client.get_candles(symbol=symbol, interval=interval, category=category, limit=limit)
        result = analyze_candles([c.model_dump() for c in candles])
    except (BybitMarketDataError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"symbol": symbol.upper(), "interval": interval, "category": category, "candles": len(candles), **result}
