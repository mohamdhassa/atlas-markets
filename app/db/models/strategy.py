from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StrategyProfile(Base):
    __tablename__ = "strategy_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, default="Default")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    timeframe: Mapped[str] = mapped_column(String(16), default="5m")
    minimum_signal_strength: Mapped[float] = mapped_column(Float, default=65.0)
    stop_atr_multiplier: Mapped[float] = mapped_column(Float, default=1.5)
    take_profit_rr: Mapped[float] = mapped_column(Float, default=2.0)
    max_position_notional_pct: Mapped[float] = mapped_column(Float, default=20.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
