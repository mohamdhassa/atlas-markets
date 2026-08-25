from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import Boolean,DateTime,Float,ForeignKey,String,UniqueConstraint,func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped,mapped_column
from app.db.base import Base

class SymbolStrategy(Base):
    __tablename__='symbol_strategies'
    __table_args__=(UniqueConstraint('user_id','profile_id','market','symbol',name='uq_symbol_strategy_scope'),)
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    user_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('users.id',ondelete='CASCADE'),nullable=False,index=True)
    profile_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('broker_profiles.id',ondelete='CASCADE'),nullable=False,index=True)
    market:Mapped[str]=mapped_column(String(16),nullable=False,default='CRYPTO')
    symbol:Mapped[str]=mapped_column(String(32),nullable=False)
    mode:Mapped[str]=mapped_column(String(16),nullable=False,default='WATCH')
    enabled:Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    timeframe:Mapped[str|None]=mapped_column(String(16),nullable=True)
    minimum_signal_strength:Mapped[float|None]=mapped_column(Float,nullable=True)
    risk_per_trade_pct:Mapped[float|None]=mapped_column(Float,nullable=True)
    stop_atr_multiplier:Mapped[float|None]=mapped_column(Float,nullable=True)
    take_profit_rr:Mapped[float|None]=mapped_column(Float,nullable=True)
    max_position_notional_pct:Mapped[float|None]=mapped_column(Float,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())
