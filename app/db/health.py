from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


settings = get_settings()
timeout_seconds = max(1, int(settings.dependency_health_timeout_seconds))
health_connect_args = {}
if make_url(settings.database_url).get_backend_name() == "postgresql":
    health_connect_args = {
        "connect_timeout": timeout_seconds,
        "options": f"-c statement_timeout={timeout_seconds * 1000}",
    }
health_engine = create_engine(
    settings.database_url,
    poolclass=NullPool,
    connect_args=health_connect_args,
    future=True,
)


def check_database() -> tuple[bool, str | None]:
    try:
        with health_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, None
    except SQLAlchemyError as exc:
        return False, exc.__class__.__name__
