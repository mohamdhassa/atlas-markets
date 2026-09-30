from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.services.access_scope import (
    effective_owner_id,
    is_admin,
    scope_broker_profiles,
)


def _user(role: str = "USER") -> User:
    return User(
        id=uuid.uuid4(),
        username=f"user-{uuid.uuid4()}",
        password_hash="test-only",
        role=role,
    )


def test_user_scope_is_always_the_authenticated_owner():
    user = _user()

    assert is_admin(user) is False
    assert effective_owner_id(user) == user.id
    assert effective_owner_id(user, user.id) == user.id


def test_user_cannot_request_another_owner():
    user = _user()

    with pytest.raises(HTTPException) as error:
        effective_owner_id(user, uuid.uuid4())

    assert error.value.status_code == 403
    assert error.value.detail == "owner access denied"


def test_admin_can_view_all_or_filter_one_owner():
    admin = _user("ADMIN")
    owner_id = uuid.uuid4()

    assert is_admin(admin) is True
    assert effective_owner_id(admin) is None
    assert effective_owner_id(admin, owner_id) == owner_id


def test_scope_broker_profiles_adds_user_predicate():
    user = _user()
    sql = str(scope_broker_profiles(select(BrokerProfile), user))

    assert "broker_profiles.user_id" in sql


def test_admin_unfiltered_scope_has_no_owner_predicate():
    admin = _user("ADMIN")
    sql = str(scope_broker_profiles(select(BrokerProfile), admin))

    assert "WHERE broker_profiles.user_id" not in sql
