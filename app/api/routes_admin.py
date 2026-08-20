from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.db.models.auth import User
from app.db.session import get_db
from app.schemas.auth import CreateUserRequest, UserPublic
from app.services.auth import create_user

router = APIRouter(prefix="/admin", tags=["admin"])


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


@router.get("/ping")
def admin_ping(admin: User = Depends(require_admin)) -> dict[str, str]:
    return {"status": "ok", "role": admin.role, "username": admin.username}
