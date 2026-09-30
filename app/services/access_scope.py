from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models.auth import User, UserRole
from app.db.models.broker import BrokerProfile


def is_admin(user: User) -> bool:
    """Return whether the authenticated principal has administrator authority."""
    return user.role == UserRole.ADMIN.value


def effective_owner_id(
    user: User,
    requested_owner_id: uuid.UUID | None = None,
) -> uuid.UUID | None:
    """Resolve the owner scope without allowing cross-user access.

    Administrators may omit the owner to see all users or select one owner.
    Ordinary users are always restricted to their own identifier.
    """
    if is_admin(user):
        return requested_owner_id
    if requested_owner_id is not None and requested_owner_id != user.id:
        raise HTTPException(status_code=403, detail="owner access denied")
    return user.id


def scope_broker_profiles(
    statement: Any,
    user: User,
    requested_owner_id: uuid.UUID | None = None,
) -> Any:
    owner_id = effective_owner_id(user, requested_owner_id)
    if owner_id is not None:
        statement = statement.where(BrokerProfile.user_id == owner_id)
    return statement


def authorized_broker_profile(
    db: Session,
    user: User,
    profile_id: uuid.UUID,
) -> BrokerProfile:
    profile = db.get(BrokerProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="account not found")
    if not is_admin(user) and profile.user_id != user.id:
        raise HTTPException(status_code=403, detail="account access denied")
    return profile
