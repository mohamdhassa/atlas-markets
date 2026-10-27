from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class IbkrOnboarding(Base):
    __tablename__ = 'ibkr_onboarding'
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id',ondelete='RESTRICT'),unique=True)
    account_id: Mapped[str] = mapped_column(String(40),index=True)
    account_label: Mapped[str] = mapped_column(String(96))
    status: Mapped[str] = mapped_column(String(24),default='REQUESTED',index=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id',ondelete='SET NULL'),nullable=True,index=True)
    profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('broker_profiles.id',ondelete='SET NULL'),nullable=True,index=True)
    credentials_encrypted: Mapped[str | None] = mapped_column(Text,nullable=True)
    bridge_token_encrypted: Mapped[str | None] = mapped_column(Text,nullable=True)
    lease_hash: Mapped[str | None] = mapped_column(String(64),nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)
    attempts: Mapped[int] = mapped_column(Integer,default=0)
    error_code: Mapped[str | None] = mapped_column(String(48),nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())
