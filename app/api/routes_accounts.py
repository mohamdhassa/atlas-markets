from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.session import get_db
from app.schemas.broker_profile import BrokerProfileCreate, BrokerProfilePublic

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _is_admin(user: User) -> bool:
    return user.role == "ADMIN"


@router.get("", response_model=list[BrokerProfilePublic])
def list_accounts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(BrokerProfile).order_by(BrokerProfile.created_at.desc())
    if not _is_admin(user):
        stmt = stmt.where(BrokerProfile.user_id == user.id)
    return list(db.scalars(stmt).all())


@router.post("", response_model=BrokerProfilePublic, status_code=status.HTTP_201_CREATED)
def create_account(payload: BrokerProfileCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owner_id = user.id
    if payload.owner_user_id is not None:
        if not _is_admin(user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin role required to assign another owner")
        owner = db.get(User, payload.owner_user_id)
        if owner is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="owner user not found")
        owner_id = owner.id
    profile = BrokerProfile(
        user_id=owner_id,
        provider=payload.provider,
        account_label=payload.account_label.strip(),
        environment=payload.environment,
        external_account_ref=(payload.external_account_ref or "").strip() or None,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.patch("/{profile_id}/toggle", response_model=BrokerProfilePublic)
def toggle_account(profile_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.get(BrokerProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="account not found")
    if not _is_admin(user) and profile.user_id != user.id:
        raise HTTPException(status_code=403, detail="account access denied")
    profile.is_enabled = not profile.is_enabled
    db.commit()
    db.refresh(profile)
    return profile
