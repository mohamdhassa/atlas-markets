from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BrokerProfile(Base):
    __tablename__ = "broker_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="BYBIT")
    account_label: Mapped[str] = mapped_column(String(96))
    environment: Mapped[str] = mapped_column(String(24), default="DEMO")
    external_account_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_connection_status: Mapped[str] = mapped_column(String(24), default="NOT_TESTED")
    last_connection_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    credentials_configured: Mapped[bool] = mapped_column(Boolean, default=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    equity_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    wallet_balance_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    available_balance_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    open_positions_count: Mapped[int] = mapped_column(Integer, default=0)
    open_orders_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User")
