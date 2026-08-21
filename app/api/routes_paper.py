from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.models.paper import PaperOrder, PaperPosition, PaperWallet
from app.db.session import get_db

router = APIRouter(prefix="/paper", tags=["paper"])


def _account(db: Session, user: User, profile_id: uuid.UUID) -> BrokerProfile:
    profile = db.get(BrokerProfile, profile_id)
    if profile is None:
        raise HTTPException(404, "account not found")
    if user.role != "ADMIN" and profile.user_id != user.id:
        raise HTTPException(403, "account access denied")
    if profile.provider != "ATLAS_PAPER":
        raise HTTPException(400, "account is not an ATLAS PAPER profile")
    return profile


def _wallet(db: Session, profile_id: uuid.UUID) -> PaperWallet:
    wallet = db.scalar(select(PaperWallet).where(PaperWallet.profile_id == profile_id))
    if wallet is None:
        wallet = PaperWallet(profile_id=profile_id)
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
    return wallet


@router.get("/{profile_id}/summary")
def paper_summary(profile_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _account(db, user, profile_id)
    wallet = _wallet(db, profile_id)
    positions = list(db.scalars(select(PaperPosition).where(PaperPosition.profile_id == profile_id).order_by(PaperPosition.opened_at.desc())).all())
    orders = list(db.scalars(select(PaperOrder).where(PaperOrder.profile_id == profile_id).order_by(PaperOrder.created_at.desc()).limit(50)).all())
    unrealized = sum((p.mark_price - p.entry_price) * p.quantity * (1 if p.side == "BUY" else -1) for p in positions)
    equity = wallet.cash_balance + sum(p.mark_price * p.quantity for p in positions)
    return {
        "profile_id": profile_id,
        "starting_balance": wallet.starting_balance,
        "cash_balance": wallet.cash_balance,
        "equity": equity,
        "realized_pnl": wallet.realized_pnl,
        "unrealized_pnl": unrealized,
        "positions": [{"id": p.id, "symbol": p.symbol, "side": p.side, "quantity": p.quantity, "entry_price": p.entry_price, "mark_price": p.mark_price, "stop_loss": p.stop_loss, "take_profit": p.take_profit, "opened_at": p.opened_at} for p in positions],
        "orders": [{"id": o.id, "signal_id": o.signal_id, "symbol": o.symbol, "side": o.side, "quantity": o.quantity, "fill_price": o.fill_price, "notional": o.notional, "status": o.status, "created_at": o.created_at} for o in orders],
    }
