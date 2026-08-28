from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.session import get_db
from app.services.autotrade_preflight import autotrade_preflight
from app.services.autotrade_readiness import autotrade_readiness
from app.services.demo_execution_certification import certify_single_mt5_demo_order
from app.services.mt5_position_inspection import inspect_mt5_position
from app.services.universe_scanner import scan_user_universe
from app.services.universe_seed import seed_validated_universe

router = APIRouter(prefix='/strategies/symbols', tags=['strategies'])


class ValidatedSeedRequest(BaseModel):
    markets: list[str] | None = None
    mode: str = 'SIGNALS'


class DemoCertificationRequest(BaseModel):
    market: str
    symbol: str


@router.post('/universe/seed-validated')
async def seed_validated(payload: ValidatedSeedRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profiles = list(db.scalars(select(BrokerProfile).where(BrokerProfile.user_id == user.id, BrokerProfile.provider != 'ATLAS_PAPER')).all())
    try:
        return await seed_validated_universe(db, user_id=user.id, profiles=profiles, markets=payload.markets, mode=payload.mode)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get('/universe/scan-preview')
async def scan_preview(include_watch: bool = Query(False), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return await scan_user_universe(db, user_id=user.id, include_watch=include_watch)


@router.get('/universe/autotrade-readiness')
async def auto_trade_readiness(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Evaluate signals, broker exposure, risk gates and proposed sizing without placing orders."""
    return await autotrade_readiness(db, user_id=user.id)


@router.post('/universe/autotrade-preflight')
async def auto_trade_preflight(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Run broker-native validation for current PASS proposals without submitting any order."""
    return await autotrade_preflight(db, user_id=user.id)


@router.post('/universe/demo-certify-single')
async def demo_certify_single(payload: DemoCertificationRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Certification-only: submit one MT5 demo order after a fresh readiness and broker preflight cycle."""
    try:
        return await certify_single_mt5_demo_order(db, user_id=user.id, market=payload.market, symbol=payload.symbol)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get('/universe/mt5-position')
async def mt5_position(market: str, symbol: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the current MT5 position including broker-stored stop loss and take profit."""
    try:
        return await inspect_mt5_position(db, user_id=user.id, market=market, symbol=symbol)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
