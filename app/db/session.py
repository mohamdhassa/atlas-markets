from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

database_url = make_url(settings.database_url)
connect_args = {}
if database_url.get_backend_name() == "postgresql":
    connect_args = {"connect_timeout": max(1, int(settings.dependency_health_timeout_seconds))}

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_timeout=settings.dependency_health_timeout_seconds,
    pool_recycle=1800,
    connect_args=connect_args,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
