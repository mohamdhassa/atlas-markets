from __future__ import annotations

from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class HistoricalCandle(Base):
    __tablename__="historical_candles"
    __table_args__=(UniqueConstraint("market","symbol","interval","timestamp_ms",name="uq_historical_candle"),)
    id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True)
    market:Mapped[str]=mapped_column(String(16),index=True)
    symbol:Mapped[str]=mapped_column(String(32),index=True)
    interval:Mapped[str]=mapped_column(String(16),index=True)
    timestamp_ms:Mapped[int]=mapped_column(BigInteger,index=True)
    open:Mapped[float]=mapped_column(Float)
    high:Mapped[float]=mapped_column(Float)
    low:Mapped[float]=mapped_column(Float)
    close:Mapped[float]=mapped_column(Float)
    volume:Mapped[float]=mapped_column(Float,default=0.0)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class HistoricalBacktestRun(Base):
    __tablename__="historical_backtest_runs"
    id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True)
    market:Mapped[str]=mapped_column(String(16),index=True)
    symbol:Mapped[str]=mapped_column(String(32),index=True)
    interval:Mapped[str]=mapped_column(String(16),index=True)
    sample_count:Mapped[int]=mapped_column(Integer,default=0)
    signals:Mapped[int]=mapped_column(Integer,default=0)
    wins:Mapped[int]=mapped_column(Integer,default=0)
    losses:Mapped[int]=mapped_column(Integer,default=0)
    win_rate:Mapped[float]=mapped_column(Float,default=0.0)
    avg_return_pct:Mapped[float]=mapped_column(Float,default=0.0)
    max_drawdown_pct:Mapped[float]=mapped_column(Float,default=0.0)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),index=True)
