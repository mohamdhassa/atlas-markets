from __future__ import annotations

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

settings = get_settings()
redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


def check_redis() -> tuple[bool, str | None]:
    try:
        return bool(redis_client.ping()), None
    except RedisError as exc:
        return False, exc.__class__.__name__
