from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.core.security import hash_password
from app.db.models.auth import User, UserSession
from app.db.session import get_db
from app.schemas.auth import CreateUserRequest, UserPublic
from app.services.auth import create_user, write_auth_audit

router = APIRouter(prefix="/admin", tags=["admin"])


class UserAdminPatch(BaseModel):
    role: Literal["ADMIN", "USER"] | None = None
    is_active: bool | None = None


class UserPasswordReset(BaseModel):
    password: str = Field(min_length=12, max_length=256)


def _active_admin_count(db: Session) -> int:
    return len(list(db.scalars(select(User).where(User.role == "ADMIN", User.is_active.is_(True))).all()))


@router.get("/users", response_model=list[UserPublic])
def list_users(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[UserPublic]:
    users = db.scalars(select(User).order_by(User.created_at.asc())).all()
    return [UserPublic.model_validate(user) for user in users]


@router.post("/users", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def add_user(
    payload: CreateUserRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserPublic:
    try:
        user = create_user(
            db,
            username=payload.username,
            email=payload.email,
            password=payload.password,
            role=payload.role,
            actor_user_id=admin.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return UserPublic.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserPublic)
def update_user(
    user_id: uuid.UUID,
    payload: UserAdminPatch,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserPublic:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, "user not found")

    demoting_last_admin = target.role == "ADMIN" and payload.role == "USER" and _active_admin_count(db) <= 1
    disabling_last_admin = target.role == "ADMIN" and target.is_active and payload.is_active is False and _active_admin_count(db) <= 1
    if demoting_last_admin or disabling_last_admin:
        raise HTTPException(409, "ATLAS must retain at least one active ADMIN user")
    if target.id == admin.id and payload.is_active is False:
        raise HTTPException(409, "you cannot disable your own active administrator account")

    if payload.role is not None:
        target.role = payload.role
    if payload.is_active is not None:
        target.is_active = payload.is_active
        if not payload.is_active:
            now = datetime.now(timezone.utc)
            db.execute(
                update(UserSession)
                .where(UserSession.user_id == target.id, UserSession.revoked_at.is_(None))
                .values(revoked_at=now)
            )

    write_auth_audit(
        db,
        action="user_updated",
        success=True,
        user_id=admin.id,
        detail=f"target_user={target.id};role={target.role};active={target.is_active}",
    )
    db.commit()
    db.refresh(target)
    return UserPublic.model_validate(target)


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: uuid.UUID,
    payload: UserPasswordReset,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, "user not found")
    target.password_hash = hash_password(payload.password)
    now = datetime.now(timezone.utc)
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == target.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    write_auth_audit(
        db,
        action="user_password_reset",
        success=True,
        user_id=admin.id,
        detail=f"target_user={target.id}",
    )
    db.commit()
    return {"status": "ok", "user_id": str(target.id), "sessions_revoked": True}


@router.get("/ping")
def admin_ping(admin: User = Depends(require_admin)) -> dict[str, str]:
    return {"status": "ok", "role": admin.role, "username": admin.username}
