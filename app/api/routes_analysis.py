from fastapi import APIRouter, Depends, HTTPException, Query

from app.analysis.technical import analyze_candles
from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.models.auth import User
from app.market_data.bybit import BybitMarketDataError, BybitPublicMarketData

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _client() -> BybitPublicMarketData:
    settings = get_settings()
    return BybitPublicMarketData(settings.bybit_public_base_url, settings.market_data_timeout_seconds)


async def _analyze(client: BybitPublicMarketData, symbol: str, interval: str, category: str, limit: int = 200) -> dict:
    candles = await client.get_candles(symbol=symbol, interval=interval, category=category, limit=limit)
    result = analyze_candles([c.model_dump() for c in candles])
    return {"symbol": symbol.upper(), "interval": interval, "category": category, "candles": len(candles), **result}


@router.get("/{symbol}/multi")
async def multi_timeframe_analysis(
    symbol: str,
    category: str = Query("linear"),
    _: User = Depends(get_current_user),
):
    client = _client()
    frames = ("4h", "1h", "15m", "5m")
    try:
        results = [await _analyze(client, symbol, frame, category) for frame in frames]
    except (BybitMarketDataError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    directions = [item["bias"] for item in results]
    long_count = directions.count("LONG")
    short_count = directions.count("SHORT")
    alignment = "LONG_ALIGNED" if long_count >= 3 else "SHORT_ALIGNED" if short_count >= 3 else "MIXED"
    confidence = round(max(long_count, short_count) / len(frames) * 100, 1)
    return {"symbol": symbol.upper(), "category": category, "alignment": alignment, "confidence": confidence, "timeframes": results}


@router.get("/{symbol}")
async def technical_analysis(
    symbol: str,
    interval: str = Query("5m"),
    category: str = Query("linear"),
    limit: int = Query(200, ge=60, le=500),
    _: User = Depends(get_current_user),
):
    try:
        return await _analyze(_client(), symbol, interval, category, limit)
    except (BybitMarketDataError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
