from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.session import get_db

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _is_admin(user: User) -> bool:
    return user.role == "ADMIN"


def _profile(db: Session, user: User, profile_id: uuid.UUID) -> BrokerProfile:
    profile = db.get(BrokerProfile, profile_id)
    if profile is None or profile.provider == "ATLAS_PAPER":
        raise HTTPException(404, "account not found")
    if not _is_admin(user) and profile.user_id != user.id:
        raise HTTPException(403, "account access denied")
    return profile


def _replacement(db: Session, profile: BrokerProfile) -> BrokerProfile | None:
    return db.scalar(
        select(BrokerProfile)
        .where(
            BrokerProfile.user_id == profile.user_id,
            BrokerProfile.provider == profile.provider,
            BrokerProfile.provider != "ATLAS_PAPER",
            BrokerProfile.id != profile.id,
            BrokerProfile.is_enabled.is_(True),
            BrokerProfile.last_connection_status == "CONNECTED",
        )
        .order_by(BrokerProfile.created_at.desc())
    )


@router.post("/{profile_id}/disconnect")
def disconnect_account(profile_id: uuid.UUID,user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    profile = _profile(db, user, profile_id)
    profile.live_execution_enabled = False
    profile.live_execution_armed_at = None
    profile.is_enabled = False
    profile.is_active = False
    profile.api_key_encrypted = None
    profile.api_secret_encrypted = None
    profile.credential_blob_encrypted = None
    profile.credentials_configured = False
    profile.last_connection_status = "DISCONNECTED"
    profile.last_connection_test_at = None
    profile.last_sync_at = None
    profile.equity_usd = None
    profile.wallet_balance_usd = None
    profile.available_balance_usd = None
    profile.open_positions_count = 0
    profile.open_orders_count = 0
    replacement = _replacement(db, profile)
    if replacement is not None: replacement.is_active = True
    db.commit()
    return {"id": str(profile.id),"status": "DISCONNECTED","message": f"{profile.account_label} disconnected and stored credentials removed."}


@router.patch("/{profile_id}/toggle")
def toggle_account(profile_id: uuid.UUID,user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    profile = _profile(db,user,profile_id);profile.is_enabled = not profile.is_enabled
    if not profile.is_enabled:
        profile.is_active=False;profile.live_execution_enabled=False;profile.live_execution_armed_at=None
        replacement=_replacement(db,profile)
        if replacement is not None:replacement.is_active=True
    db.commit();db.refresh(profile);return profile


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(profile_id: uuid.UUID,user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    profile = _profile(db, user, profile_id)
    if profile.open_positions_count or profile.open_orders_count:
        raise HTTPException(409, "close open positions and orders before removing this connection")
    was_active = profile.is_active
    replacement = _replacement(db, profile) if was_active else None
    db.delete(profile);db.flush()
    if replacement is not None: replacement.is_active = True
    db.commit();return Response(status_code=status.HTTP_204_NO_CONTENT)
