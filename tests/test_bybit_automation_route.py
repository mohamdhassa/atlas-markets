from app.db.models.broker import BrokerProfile
from app.services.autotrade_readiness import _provider_execution_blockers
from app.services.safe_automation import automation_certification_blocker


def _profile(environment="TESTNET", certified=True):
    profile = BrokerProfile(user_id=None, account_label="bybit", provider="BYBIT", environment=environment)
    profile.execution_certified = certified
    profile.execution_certification_buy_passed = certified
    profile.execution_certification_sell_passed = certified
    return profile


def test_bybit_testnet_and_demo_are_certified_route_environments():
    assert automation_certification_blocker("BYBIT", "TESTNET") is None
    assert automation_certification_blocker("BYBIT", "DEMO") is None
    assert automation_certification_blocker("BYBIT", "LIVE") == "BYBIT_TESTNET_OR_DEMO_REQUIRED"


def test_bybit_readiness_requires_persisted_spot_certification():
    assert _provider_execution_blockers(_profile(certified=True)) == []
    assert _provider_execution_blockers(_profile(certified=False)) == ["BYBIT_SPOT_CERTIFICATION_REQUIRED"]


def test_bybit_live_never_passes_simulation_readiness():
    assert _provider_execution_blockers(_profile(environment="LIVE", certified=True)) == ["BYBIT_TESTNET_OR_DEMO_REQUIRED"]
