from app.db.models.broker import BrokerProfile


def test_broker_profile_has_persistent_execution_certification_fields():
    columns = BrokerProfile.__table__.columns
    assert "execution_certified" in columns
    assert "execution_certified_at" in columns
    assert "execution_certification_buy_passed" in columns
    assert "execution_certification_sell_passed" in columns


def test_execution_certification_defaults_are_safe():
    profile = BrokerProfile(user_id=None, account_label="test", provider="BYBIT", environment="TESTNET")
    assert profile.execution_certified is None or profile.execution_certified is False
    assert profile.execution_certification_buy_passed is None or profile.execution_certification_buy_passed is False
    assert profile.execution_certification_sell_passed is None or profile.execution_certification_sell_passed is False
    assert profile.live_execution_enabled is None or profile.live_execution_enabled is False
