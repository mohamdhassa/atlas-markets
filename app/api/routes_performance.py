from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.models.paper import PaperOrder, PaperWallet
from app.db.models.strategy import StrategyProfile
from app.db.session import get_db
from app.services.performance import performance_summary

router = APIRouter(tags=["performance", "strategy"])


class StrategyUpdate(BaseModel):
    enabled: bool = True
    timeframe: str = Field("5m", pattern="^(5m|15m|1h|4h)$")
    minimum_signal_strength: float = Field(65.0, ge=50.0, le=100.0)
    stop_atr_multiplier: float = Field(1.5, ge=0.5, le=5.0)
    take_profit_rr: float = Field(2.0, ge=0.5, le=5.0)
    max_position_notional_pct: float = Field(20.0, ge=1.0, le=50.0)


def _strategy(db: Session) -> StrategyProfile:
    row = db.scalar(select(StrategyProfile).where(StrategyProfile.name == "Default"))
    if row is None:
        row = StrategyProfile(name="Default")
        db.add(row); db.commit(); db.refresh(row)
    return row


def _authorized_account(db: Session, user: User, profile_id: uuid.UUID) -> BrokerProfile:
    profile = db.get(BrokerProfile, profile_id)
    if profile is None:
        raise HTTPException(404, "account not found")
    if user.role != "ADMIN" and profile.user_id != user.id:
        raise HTTPException(403, "account access denied")
    if profile.provider != "ATLAS_PAPER":
        raise HTTPException(400, "performance analytics currently require ATLAS PAPER")
    return profile


@router.get("/performance/{profile_id}")
def account_performance(profile_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _authorized_account(db, user, profile_id)
    wallet = db.scalar(select(PaperWallet).where(PaperWallet.profile_id == profile_id))
    starting = wallet.starting_balance if wallet else 100000.0
    orders = list(db.scalars(select(PaperOrder).where(PaperOrder.profile_id == profile_id).order_by(PaperOrder.created_at.asc())).all())
    rows = [{"symbol": o.symbol, "realized_pnl": o.realized_pnl, "created_at": o.created_at, "exit_reason": o.exit_reason} for o in orders]
    result = performance_summary(rows, starting)
    result["profile_id"] = profile_id
    result["starting_balance"] = starting
    return result


@router.get("/strategy/profile")
def get_strategy(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _strategy(db)
    return {"name": row.name, "enabled": row.enabled, "timeframe": row.timeframe, "minimum_signal_strength": row.minimum_signal_strength, "stop_atr_multiplier": row.stop_atr_multiplier, "take_profit_rr": row.take_profit_rr, "max_position_notional_pct": row.max_position_notional_pct, "updated_at": row.updated_at}


@router.put("/strategy/profile")
def update_strategy(payload: StrategyUpdate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = _strategy(db)
    row.enabled = payload.enabled
    row.timeframe = payload.timeframe
    row.minimum_signal_strength = payload.minimum_signal_strength
    row.stop_atr_multiplier = payload.stop_atr_multiplier
    row.take_profit_rr = payload.take_profit_rr
    row.max_position_notional_pct = payload.max_position_notional_pct
    db.commit(); db.refresh(row)
    return {"name": row.name, "enabled": row.enabled, "timeframe": row.timeframe, "minimum_signal_strength": row.minimum_signal_strength, "stop_atr_multiplier": row.stop_atr_multiplier, "take_profit_rr": row.take_profit_rr, "max_position_notional_pct": row.max_position_notional_pct, "updated_at": row.updated_at}
