import os

import pytest
redis = pytest.importorskip("redis")
Redis = redis.Redis


def test_redis_ping() -> None:
    url = os.getenv("TEST_REDIS_URL")
    if not url:
        pytest.skip("TEST_REDIS_URL is not configured")
    client = Redis.from_url(url, decode_responses=True)
    assert client.ping() is True
