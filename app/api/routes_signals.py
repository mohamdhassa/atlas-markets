from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.core.config import get_settings
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.models.signal import RiskEvent, RiskProfile, Signal
from app.db.session import get_db
from app.market_data.bybit import BybitMarketDataError, BybitPublicMarketData
from app.services.signal_risk import evaluate_risk, generate_signal, reasons_json

router = APIRouter(tags=["signals", "risk"])


class RiskProfileUpdate(BaseModel):
    minimum_signal_score: float = Field(65.0, ge=50.0, le=100.0)
    risk_per_trade_pct: float = Field(1.0, gt=0.0, le=5.0)
    max_daily_loss_pct: float = Field(3.0, gt=0.0, le=20.0)
    max_open_positions: int = Field(3, ge=1, le=20)


def _default_risk_profile(db: Session) -> RiskProfile:
    profile = db.scalar(select(RiskProfile).where(RiskProfile.name == "Default"))
    if profile is None:
        profile = RiskProfile(name="Default")
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def _authorized_profile(db: Session, user: User, profile_id: uuid.UUID) -> BrokerProfile:
    profile = db.get(BrokerProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="account not found")
    if user.role != "ADMIN" and profile.user_id != user.id:
        raise HTTPException(status_code=403, detail="account access denied")
    return profile


@router.get("/signals")
def list_signals(
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Signal).join(BrokerProfile, BrokerProfile.id == Signal.profile_id).order_by(Signal.created_at.desc()).limit(limit)
    if user.role != "ADMIN":
        stmt = stmt.where(BrokerProfile.user_id == user.id)
    rows = db.scalars(stmt).all()
    return [
        {
            "id": row.id,
            "profile_id": row.profile_id,
            "symbol": row.symbol,
            "timeframe": row.timeframe,
            "decision": row.decision,
            "classification": row.classification,
            "score": row.score,
            "reasons": json.loads(row.reasons_json or "[]"),
            "risk_status": row.risk_status,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.post("/signals/generate")
async def create_signal(
    profile_id: uuid.UUID,
    symbol: str = Query("BTCUSDT", min_length=3, max_length=32),
    interval: str = Query("5m"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = _authorized_profile(db, user, profile_id)
    settings = get_settings()
    market = BybitPublicMarketData(settings.bybit_public_base_url, settings.market_data_timeout_seconds)
    try:
        candles = await market.get_candles(symbol=symbol, interval=interval, category="linear", limit=200)
        generated = generate_signal([c.model_dump() for c in candles])
    except (BybitMarketDataError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    risk_profile = _default_risk_profile(db)
    approved, reason_code, details = evaluate_risk(
        generated,
        minimum_signal_score=risk_profile.minimum_signal_score,
        account_enabled=account.is_enabled,
        allow_live_trading=settings.allow_live_trading,
        account_environment=account.environment,
    )
    signal = Signal(
        profile_id=account.id,
        symbol=symbol.upper(),
        timeframe=interval,
        decision=generated.decision,
        classification=generated.classification,
        score=generated.score,
        reasons_json=reasons_json(generated.reasons),
        risk_status="APPROVED" if approved else "REJECTED",
    )
    db.add(signal)
    db.flush()
    event = RiskEvent(
        profile_id=account.id,
        signal_id=signal.id,
        approved=approved,
        reason_code=reason_code,
        details_json=json.dumps(details, separators=(",", ":")),
    )
    db.add(event)
    db.commit()
    db.refresh(signal)
    return {
        "id": signal.id,
        "profile_id": signal.profile_id,
        "symbol": signal.symbol,
        "timeframe": signal.timeframe,
        "decision": signal.decision,
        "classification": signal.classification,
        "score": signal.score,
        "strength": generated.strength,
        "reasons": generated.reasons,
        "risk": {"approved": approved, "status": signal.risk_status, "reason_code": reason_code, "details": details},
        "created_at": signal.created_at,
    }


@router.get("/risk/profile")
def get_risk_profile(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _default_risk_profile(db)
    return {
        "name": profile.name,
        "minimum_signal_score": profile.minimum_signal_score,
        "risk_per_trade_pct": profile.risk_per_trade_pct,
        "max_daily_loss_pct": profile.max_daily_loss_pct,
        "max_open_positions": profile.max_open_positions,
        "is_active": profile.is_active,
    }


@router.put("/risk/profile")
def update_risk_profile(
    payload: RiskProfileUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    profile = _default_risk_profile(db)
    profile.minimum_signal_score = payload.minimum_signal_score
    profile.risk_per_trade_pct = payload.risk_per_trade_pct
    profile.max_daily_loss_pct = payload.max_daily_loss_pct
    profile.max_open_positions = payload.max_open_positions
    db.commit()
    db.refresh(profile)
    return {
        "name": profile.name,
        "minimum_signal_score": profile.minimum_signal_score,
        "risk_per_trade_pct": profile.risk_per_trade_pct,
        "max_daily_loss_pct": profile.max_daily_loss_pct,
        "max_open_positions": profile.max_open_positions,
        "is_active": profile.is_active,
    }
