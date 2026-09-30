from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.db.models.broker import BrokerProfile
from app.services.live_execution import (
    disarm_live_execution,
    live_execution_blockers,
    live_execution_is_armed,
)


def _profile() -> BrokerProfile:
    now = datetime.now(timezone.utc)
    profile = BrokerProfile(
        account_label="Live test",
        provider="BYBIT",
        environment="LIVE",
        is_enabled=True,
        is_active=True,
        credentials_configured=True,
        last_connection_status="CONNECTED",
        execution_certified=True,
        execution_certification_buy_passed=True,
        execution_certification_sell_passed=True,
        live_execution_enabled=True,
        live_execution_armed_at=now,
        live_execution_expires_at=now + timedelta(minutes=15),
    )
    return profile


def test_fully_certified_connected_live_profile_can_be_temporarily_armed():
    profile = _profile()

    assert live_execution_blockers(profile) == []
    assert live_execution_is_armed(profile) is True


def test_expired_profile_is_never_considered_armed():
    profile = _profile()
    profile.live_execution_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    assert "ARMING_EXPIRED" in live_execution_blockers(profile)
    assert live_execution_is_armed(profile) is False


def test_simulation_certification_does_not_arm_live_money():
    profile = _profile()
    profile.environment = "TESTNET"

    assert "LIVE_ENVIRONMENT_REQUIRED" in live_execution_blockers(profile)
    assert live_execution_is_armed(profile) is False


def test_disconnect_and_safety_failures_block_arming():
    profile = _profile()
    profile.last_connection_status = "FAILED"
    profile.execution_certification_sell_passed = False

    blockers = live_execution_blockers(profile)
    assert "PROVIDER_NOT_CONNECTED" in blockers
    assert "SELL_CERTIFICATION_REQUIRED" in blockers


def test_disarm_clears_every_arming_field():
    profile = _profile()

    disarm_live_execution(profile, "Emergency stop")

    assert profile.live_execution_enabled is False
    assert profile.live_execution_armed_at is None
    assert profile.live_execution_expires_at is None
    assert profile.live_execution_last_disarm_reason == "Emergency stop"


def test_live_lifecycle_migration_and_routes_are_present():
    migration = Path("migrations/versions/20260930_0021_live_execution_lifecycle.py").read_text()
    routes = Path("app/api/routes_accounts.py").read_text()
    workspace = Path("app/static/management-workspaces.js").read_text()
    index = Path("app/static/index.html").read_text()

    assert 'revision = "20260930_0021"' in migration
    assert 'down_revision = "20260930_0020"' in migration
    assert '"live_execution_events"' in migration
    assert "duration_minutes" in routes
    assert "live_execution_blockers" in routes
    assert "AUTO_DISARMED" in routes
    assert "integration-live-disarm:" in workspace
    assert "management-workspaces.js?v=83.0" in index
