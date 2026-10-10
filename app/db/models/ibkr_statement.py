"""Immutable reviewed statement evidence, isolated from mutable protection audits."""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class IbkrStatementEvidence(Base):
    __tablename__ = 'ibkr_statement_evidence'
    action_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('automation_actions.id', ondelete='CASCADE'), primary_key=True)
    broker_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('broker_profiles.id', ondelete='CASCADE'), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    operator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    evidence_json: Mapped[str] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
