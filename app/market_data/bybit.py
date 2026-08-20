from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.schemas.market import MarketCandle, MarketSnapshot, MarketTicker


SUPPORTED_CATEGORIES = {"linear", "spot"}
INTERVAL_MAP = {
    "1m": "1",
    "3m": "3",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "2h": "120",
    "4h": "240",
    "6h": "360",
    "12h": "720",
    "1d": "D",
    "1w": "W",
}
DEFAULT_WATCHLIST = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT")


class BybitMarketDataError(RuntimeError):
    pass


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


class BybitPublicMarketData:
    def __init__(self, base_url: str, timeout_seconds: float = 8.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds) as client:
                response = await client.get(path, params=params)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise BybitMarketDataError(f"Bybit request failed: {exc.__class__.__name__}") from exc

        payload = response.json()
        if payload.get("retCode") != 0:
            raise BybitMarketDataError(payload.get("retMsg") or "Bybit returned an error")
        return payload

    async def get_tickers(
        self,
        *,
        category: str = "linear",
        symbols: tuple[str, ...] = DEFAULT_WATCHLIST,
    ) -> MarketSnapshot:
        if category not in SUPPORTED_CATEGORIES:
            raise ValueError("unsupported market category")

        payload = await self._get("/v5/market/tickers", {"category": category})
        rows = payload.get("result", {}).get("list", [])
        wanted = {symbol.upper() for symbol in symbols}
        now = datetime.now(timezone.utc)
        tickers: list[MarketTicker] = []

        for row in rows:
            symbol = str(row.get("symbol", "")).upper()
            if symbol not in wanted:
                continue
            tickers.append(
                MarketTicker(
                    category=category,
                    symbol=symbol,
                    last_price=float(row["lastPrice"]),
                    bid_price=_float(row.get("bid1Price")),
                    ask_price=_float(row.get("ask1Price")),
                    change_24h_pct=(float(row["price24hPcnt"]) * 100 if row.get("price24hPcnt") not in (None, "") else None),
                    high_24h=_float(row.get("highPrice24h")),
                    low_24h=_float(row.get("lowPrice24h")),
                    volume_24h=_float(row.get("volume24h")),
                    turnover_24h=_float(row.get("turnover24h")),
                    updated_at=now,
                )
            )

        tickers.sort(key=lambda item: symbols.index(item.symbol) if item.symbol in symbols else len(symbols))
        return MarketSnapshot(category=category, tickers=tickers, count=len(tickers), fetched_at=now)

    async def get_candles(
        self,
        *,
        symbol: str,
        interval: str = "5m",
        category: str = "linear",
        limit: int = 120,
    ) -> list[MarketCandle]:
        if category not in SUPPORTED_CATEGORIES:
            raise ValueError("unsupported market category")
        if interval not in INTERVAL_MAP:
            raise ValueError("unsupported candle interval")
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")

        symbol = symbol.upper()
        payload = await self._get(
            "/v5/market/kline",
            {
                "category": category,
                "symbol": symbol,
                "interval": INTERVAL_MAP[interval],
                "limit": limit,
            },
        )
        rows = payload.get("result", {}).get("list", [])
        candles = [
            MarketCandle(
                category=category,
                symbol=symbol,
                interval=interval,
                timestamp_ms=int(row[0]),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
                turnover=_float(row[6] if len(row) > 6 else None),
            )
            for row in rows
        ]
        candles.sort(key=lambda item: item.timestamp_ms)
        return candles
