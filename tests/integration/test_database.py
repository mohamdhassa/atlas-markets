import os

import pytest
from sqlalchemy import create_engine, text


def test_database_roundtrip() -> None:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
