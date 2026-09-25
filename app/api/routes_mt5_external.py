from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.session import get_db
from app.services.mt5_runtime import mt5_runtime_readiness

router = APIRouter(prefix="/mt5", tags=["mt5"])


@router.get("/readiness")
async def readiness(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    query = select(BrokerProfile).where(BrokerProfile.provider == "MT5", BrokerProfile.is_enabled.is_(True))
    if user.role != "ADMIN":
        query = query.where(BrokerProfile.user_id == user.id)
    profiles = list(db.scalars(query).all())
    runtime = await mt5_runtime_readiness()
    runtime["profiles"] = len(profiles)
    runtime["active_profiles"] = sum(bool(profile.is_active) for profile in profiles)
    runtime["markets"] = ["FX", "METAL", "COMMODITY"]
    runtime["live_money_ready"] = False
    runtime["safety"] = "MT5 readiness never enables Live Money execution."
    return runtime
