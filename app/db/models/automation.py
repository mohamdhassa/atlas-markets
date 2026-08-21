from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
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
