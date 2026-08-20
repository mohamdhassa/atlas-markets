from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.config import get_settings
from app.core.redis import check_redis
from app.db.health import check_database

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(response: Response) -> dict[str, object]:
    settings = get_settings()
    database_ok, database_error = check_database()
    redis_ok, redis_error = check_redis()
    overall_ok = database_ok and redis_ok

    if not overall_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if overall_ok else "degraded",
        "service": settings.app_name,
        "environment": settings.environment,
        "dependencies": {
            "database": {
                "status": "ok" if database_ok else "error",
                "error": database_error,
            },
            "redis": {
                "status": "ok" if redis_ok else "error",
                "error": redis_error,
            },
        },
    }
