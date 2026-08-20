import uuid

import pytest
from sqlalchemy import delete, select

from app.db.health import check_database
from app.db.models.auth import AuthAuditLog, User, UserRole, UserSession
from app.db.models.broker import BrokerProfile
from app.db.session import SessionLocal
from app.services.auth import create_user


def test_broker_profile_is_owned_by_user():
    database_ok, error = check_database()
    if not database_ok:
        pytest.skip(f"PostgreSQL unavailable: {error}")

    username = f"account_{uuid.uuid4().hex[:10]}"
    user_id = None
    profile_id = None
    with SessionLocal() as db:
        try:
            user = create_user(db, username=username, password="phase6-test-password", role=UserRole.USER.value)
            user_id = user.id
            profile = BrokerProfile(user_id=user.id, provider="BYBIT", account_label="Demo", environment="DEMO")
            db.add(profile)
            db.commit()
            db.refresh(profile)
            profile_id = profile.id

            owned = db.scalar(select(BrokerProfile).where(BrokerProfile.user_id == user.id))
            assert owned is not None
            assert owned.id == profile.id
            assert owned.account_label == "Demo"
            assert owned.is_enabled is True
        finally:
            if profile_id is not None:
                db.execute(delete(BrokerProfile).where(BrokerProfile.id == profile_id))
            if user_id is not None:
                db.execute(delete(AuthAuditLog).where(AuthAuditLog.user_id == user_id))
                db.execute(delete(UserSession).where(UserSession.user_id == user_id))
                db.execute(delete(User).where(User.id == user_id))
            db.commit()
