from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ATLAS MARKETS"
    environment: str = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "postgresql+psycopg://atlas:atlas@postgres:5432/atlas_markets"
    redis_url: str = "redis://redis:6379/0"

    atlas_markets_master_key: str = "change-me-in-real-environments"
    session_secret: str = "change-me-in-real-environments"
    allow_live_trading: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
