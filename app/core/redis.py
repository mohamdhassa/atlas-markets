from __future__ import annotations

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

settings = get_settings()
redis_client = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=settings.dependency_health_timeout_seconds,
    socket_timeout=settings.dependency_health_timeout_seconds,
    health_check_interval=30,
)


def check_redis() -> tuple[bool, str | None]:
    try:
        return bool(redis_client.ping()), None
    except RedisError as exc:
        return False, exc.__class__.__name__
