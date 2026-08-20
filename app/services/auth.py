from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import generate_session_token, hash_password, hash_session_token, verify_password
from app.db.models.auth import AuthAuditLog, User, UserRole, UserSession


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def write_auth_audit(
    db: Session,
    *,
    action: str,
    success: bool,
    user_id=None,
    detail: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    db.add(
        AuthAuditLog(
            user_id=user_id,
            action=action,
            success=success,
            detail=detail,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    role: str = UserRole.USER.value,
    email: str | None = None,
    actor_user_id=None,
) -> User:
    normalized_username = username.strip().lower()
    if db.scalar(select(User).where(User.username == normalized_username)) is not None:
        raise ValueError("username already exists")
    if email and db.scalar(select(User).where(User.email == email.strip().lower())) is not None:
        raise ValueError("email already exists")
    if role not in {UserRole.ADMIN.value, UserRole.USER.value}:
        raise ValueError("invalid role")

    user = User(
        username=normalized_username,
        email=email.strip().lower() if email else None,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    write_auth_audit(
        db,
        action="user_created",
        success=True,
        user_id=actor_user_id,
        detail=f"created_user={user.id};role={role}",
    )
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(
    db: Session,
    *,
    username: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> User | None:
    normalized_username = username.strip().lower()
    user = db.scalar(select(User).where(User.username == normalized_username))
    valid = user is not None and user.is_active and verify_password(password, user.password_hash)
    write_auth_audit(
        db,
        action="login_attempt",
        success=bool(valid),
        user_id=user.id if user else None,
        detail=None if valid else f"username={normalized_username}",
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.commit()
    return user if valid else None


def create_session(
    db: Session,
    *,
    user: User,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, UserSession]:
    settings = get_settings()
    token = generate_session_token()
    expires_at = _utcnow() + timedelta(hours=settings.session_ttl_hours)
    session = UserSession(
        user_id=user.id,
        token_hash=hash_session_token(token, settings.session_secret),
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(session)
    write_auth_audit(
        db,
        action="login_success",
        success=True,
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(session)
    return token, session


def get_user_for_token(db: Session, token: str) -> User | None:
    settings = get_settings()
    token_hash = hash_session_token(token, settings.session_secret)
    session = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash))
    if session is None or session.revoked_at is not None:
        return None
    if session.expires_at <= _utcnow():
        return None
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None
    return user


def revoke_session(
    db: Session,
    token: str,
    *,
    user: User | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> bool:
    settings = get_settings()
    token_hash = hash_session_token(token, settings.session_secret)
    session = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash))
    if session is None or session.revoked_at is not None:
        return False
    session.revoked_at = _utcnow()
    write_auth_audit(
        db,
        action="logout",
        success=True,
        user_id=user.id if user else session.user_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.commit()
    return True
