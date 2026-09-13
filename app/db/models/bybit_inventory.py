from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BybitManagedInventory(Base):
    __tablename__ = "bybit_managed_inventory"
    __table_args__ = (
        UniqueConstraint("broker_profile_id", "symbol", name="uq_bybit_managed_inventory_profile_symbol"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    broker_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("broker_profiles.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    managed_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    average_entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    cumulative_bought_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cumulative_sold_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
