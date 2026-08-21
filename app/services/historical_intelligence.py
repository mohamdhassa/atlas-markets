from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from math import sqrt

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models.historical import HistoricalCandle
from app.db.session import SessionLocal
from app.market_data.bybit import BybitPublicMarketData, DEFAULT_WATCHLIST
from app.market_data.fx import FX_WATCHLIST, TwelveDataFxMarketData


def _feature(candles: list[dict], index: int) -> tuple[float, float, float, float]:
    close = float(candles[index]["close"])

    def ret(bars: int) -> float:
        previous = float(candles[index - bars]["close"])
        return ((close / previous) - 1.0) * 100 if previous else 0.0

    range_pct = ((float(candles[index]["high"]) - float(candles[index]["low"])) / close * 100) if close else 0.0
    return ret(3), ret(6), ret(12), range_pct


def historical_probability(candles: list[dict], horizon: int = 6, max_matches: int = 60) -> dict:
    if len(candles) < 80:
        return {
            "matches": 0,
            "up_probability": 50.0,
            "down_probability": 50.0,
            "avg_forward_return_pct": 0.0,
            "confidence": "INSUFFICIENT_DATA",
            "horizon_bars": horizon,
        }

    current = _feature(candles, len(candles) - 1)
    candidates: list[tuple[float, float]] = []
    for index in range(20, len(candles) - horizon - 1):
        features = _feature(candles, index)
        distance = sqrt(sum((a - b) ** 2 for a, b in zip(current, features)))
        entry = float(candles[index]["close"])
        future = float(candles[index + horizon]["close"])
        forward_return = ((future / entry) - 1.0) * 100 if entry else 0.0
        candidates.append((distance, forward_return))

    matches = sorted(candidates, key=lambda item: item[0])[:max_matches]
    if not matches:
        return {
            "matches": 0,
            "up_probability": 50.0,
            "down_probability": 50.0,
            "avg_forward_return_pct": 0.0,
            "confidence": "INSUFFICIENT_DATA",
            "horizon_bars": horizon,
        }

    up_count = sum(1 for _, result in matches if result > 0)
    average = sum(result for _, result in matches) / len(matches)
    up_probability = round(up_count / len(matches) * 100, 1)
    return {
        "matches": len(matches),
        "up_probability": up_probability,
        "down_probability": round(100 - up_probability, 1),
        "avg_forward_return_pct": round(average, 4),
        "confidence": "HIGH" if len(matches) >= 50 else "MEDIUM" if len(matches) >= 25 else "LOW",
        "horizon_bars": horizon,
    }


def db_candles(db, market: str, symbol: str, interval: str, limit: int = 5000) -> list[dict]:
    rows = list(
        db.scalars(
            select(HistoricalCandle)
            .where(
                HistoricalCandle.market == market.upper(),
                HistoricalCandle.symbol == symbol.upper().replace("/", ""),
                HistoricalCandle.interval == interval,
            )
            .order_by(HistoricalCandle.timestamp_ms.desc())
            .limit(limit)
        ).all()
    )
    rows.reverse()
    return [
        {
            "timestamp_ms": row.timestamp_ms,
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume,
        }
        for row in rows
    ]


def store_candles(db, market: str, symbol: str, interval: str, candles: list[dict]) -> int:
    market = market.upper()
    symbol = symbol.upper().replace("/", "")
    existing = set(
        db.scalars(
            select(HistoricalCandle.timestamp_ms).where(
                HistoricalCandle.market == market,
                HistoricalCandle.symbol == symbol,
                HistoricalCandle.interval == interval,
            )
        ).all()
    )
    added = 0
    for candle in candles:
        timestamp_ms = candle.get("timestamp_ms")
        if timestamp_ms is None:
            raw = candle.get("timestamp")
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            timestamp_ms = int(parsed.timestamp() * 1000)
        timestamp_ms = int(timestamp_ms)
        if timestamp_ms in existing:
            continue
        db.add(
            HistoricalCandle(
                market=market,
                symbol=symbol,
                interval=interval,
                timestamp_ms=timestamp_ms,
                open=float(candle["open"]),
                high=float(candle["high"]),
                low=float(candle["low"]),
                close=float(candle["close"]),
                volume=float(candle.get("volume") or 0),
            )
        )
        existing.add(timestamp_ms)
        added += 1
    db.commit()
    return added


async def refresh_history(interval: str = "5m") -> dict:
    settings = get_settings()
    crypto = BybitPublicMarketData(settings.bybit_public_base_url, settings.market_data_timeout_seconds)
    result = {"crypto_added": 0, "fx_added": 0}
    with SessionLocal() as db:
        for symbol in DEFAULT_WATCHLIST:
            try:
                candles = await crypto.get_candles(symbol=symbol, interval=interval, category="linear", limit=500)
                result["crypto_added"] += store_candles(db, "CRYPTO", symbol, interval, [c.model_dump() for c in candles])
            except Exception:
                pass
        if settings.fx_market_data_api_key:
            fx = TwelveDataFxMarketData(settings.fx_market_data_base_url, settings.fx_market_data_api_key, settings.market_data_timeout_seconds)
            for symbol in FX_WATCHLIST:
                try:
                    result["fx_added"] += store_candles(db, "FX", symbol, interval, await fx.get_candles(symbol, interval, 500))
                except Exception:
                    pass
    return result


async def historical_loop(stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            await refresh_history()
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=3600)
        except asyncio.TimeoutError:
            pass
