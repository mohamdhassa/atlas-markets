from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.session import get_db
from app.services.autotrade_readiness import autotrade_readiness
from app.services.universe_scanner import scan_user_universe
from app.services.universe_seed import seed_validated_universe

router = APIRouter(prefix='/strategies/symbols', tags=['strategies'])


class ValidatedSeedRequest(BaseModel):
    markets: list[str] | None = None
    mode: str = 'SIGNALS'


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
