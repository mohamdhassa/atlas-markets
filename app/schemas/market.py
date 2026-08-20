from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MarketTicker(BaseModel):
    provider: str = "BYBIT"
    category: str
    symbol: str
    last_price: float
    bid_price: float | None = None
    ask_price: float | None = None
    change_24h_pct: float | None = None
    high_24h: float | None = None
    low_24h: float | None = None
    volume_24h: float | None = None
    turnover_24h: float | None = None
    updated_at: datetime


class MarketCandle(BaseModel):
    provider: str = "BYBIT"
    category: str
    symbol: str
    interval: str
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: float | None = None


class MarketSnapshot(BaseModel):
    provider: str = "BYBIT"
    category: str
    tickers: list[MarketTicker]
    count: int = Field(ge=0)
    fetched_at: datetime
