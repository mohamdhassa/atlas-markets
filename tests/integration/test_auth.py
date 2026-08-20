from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete

from app.db.health import check_database
from app.db.models.auth import AuthAuditLog, User, UserRole, UserSession
from app.db.session import SessionLocal
from app.services.auth import authenticate_user, create_session, create_user, get_user_for_token, revoke_session


def test_authentication_session_lifecycle() -> None:
    database_ok, error = check_database()
    if not database_ok:
        pytest.skip(f"PostgreSQL unavailable: {error}")

    username = f"phase3_{uuid.uuid4().hex[:10]}"
    password = "phase3-test-password"
    user_id = None

    with SessionLocal() as db:
        try:
            user = create_user(
                db,
                username=username,
                password=password,
                role=UserRole.USER.value,
            )
            user_id = user.id

            authenticated = authenticate_user(db, username=username, password=password)
            assert authenticated is not None
            assert authenticated.id == user.id
            assert authenticate_user(db, username=username, password="incorrect") is None

            token, session = create_session(db, user=user)
            assert session.token_hash != token

            resolved = get_user_for_token(db, token)
            assert resolved is not None
            assert resolved.id == user.id

            assert revoke_session(db, token, user=user) is True
            assert get_user_for_token(db, token) is None
        finally:
            if user_id is not None:
                db.execute(delete(AuthAuditLog).where(AuthAuditLog.user_id == user_id))
                db.execute(delete(UserSession).where(UserSession.user_id == user_id))
                db.execute(delete(User).where(User.id == user_id))
                db.commit()
