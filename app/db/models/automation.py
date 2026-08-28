from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class AutomationState(Base):
    __tablename__="automation_state"
    id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    name: Mapped[str]=mapped_column(String(64),unique=True,default="default")
    enabled: Mapped[bool]=mapped_column(Boolean,default=True)
    killed: Mapped[bool]=mapped_column(Boolean,default=False)
    auto_execute_paper: Mapped[bool]=mapped_column(Boolean,default=True)
    interval_seconds: Mapped[int]=mapped_column(Integer,default=300)
    symbols_csv: Mapped[str]=mapped_column(Text,default="BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT")
    last_scan_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    next_scan_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())

class AutomationScan(Base):
    __tablename__="automation_scans"
    id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    status: Mapped[str]=mapped_column(String(24),default="RUNNING",index=True)
    symbols_count: Mapped[int]=mapped_column(Integer,default=0)
    accounts_count: Mapped[int]=mapped_column(Integer,default=0)
    signals_count: Mapped[int]=mapped_column(Integer,default=0)
    approved_count: Mapped[int]=mapped_column(Integer,default=0)
    executed_count: Mapped[int]=mapped_column(Integer,default=0)
    error_message: Mapped[str|None]=mapped_column(Text,nullable=True)
    started_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),index=True)
    finished_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class AutomationAction(Base):
    __tablename__="automation_actions"
    id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('automation_scans.id',ondelete='CASCADE'),index=True)
    user_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('users.id',ondelete='CASCADE'),index=True)
    broker_profile_id: Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('broker_profiles.id',ondelete='SET NULL'),nullable=True)
    provider: Mapped[str]=mapped_column(String(32))
    environment: Mapped[str|None]=mapped_column(String(24),nullable=True)
    market: Mapped[str]=mapped_column(String(24))
    symbol: Mapped[str]=mapped_column(String(32),index=True)
    side: Mapped[str|None]=mapped_column(String(8),nullable=True)
    status: Mapped[str]=mapped_column(String(24),index=True)
    reason: Mapped[str|None]=mapped_column(String(128),nullable=True)
    quantity: Mapped[float|None]=mapped_column(Float,nullable=True)
    sizing_policy: Mapped[str|None]=mapped_column(String(64),nullable=True)
    broker_order_id: Mapped[str|None]=mapped_column(String(128),nullable=True)
    broker_position_id: Mapped[str|None]=mapped_column(String(128),nullable=True)
    raw_json: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),index=True)
