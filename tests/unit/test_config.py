from app.core.config import Settings


def test_live_trading_disabled_by_default() -> None:
    settings = Settings(_env_file=None)
    assert settings.allow_live_trading is False
