from __future__ import annotations

from datetime import datetime, timezone

from app.db.models.broker import BrokerProfile


def live_execution_blockers(profile: BrokerProfile, now: datetime | None = None) -> list[str]:
    moment = now or datetime.now(timezone.utc)
    blockers: list[str] = []
    if str(profile.environment).upper() != "LIVE":
        blockers.append("LIVE_ENVIRONMENT_REQUIRED")
    if not profile.is_enabled:
        blockers.append("ACCOUNT_DISABLED")
    if not profile.is_active:
        blockers.append("ACCOUNT_NOT_ACTIVE")
    if not profile.credentials_configured:
        blockers.append("CREDENTIALS_NOT_CONFIGURED")
    if profile.last_connection_status != "CONNECTED":
        blockers.append("PROVIDER_NOT_CONNECTED")
    if not profile.execution_certified:
        blockers.append("LIVE_EXECUTION_NOT_CERTIFIED")
    if not profile.execution_certification_buy_passed:
        blockers.append("BUY_CERTIFICATION_REQUIRED")
    if not profile.execution_certification_sell_passed:
        blockers.append("SELL_CERTIFICATION_REQUIRED")
    expires_at = profile.live_execution_expires_at
    if expires_at is not None and expires_at <= moment:
        blockers.append("ARMING_EXPIRED")
    return blockers


def live_execution_is_armed(profile: BrokerProfile, now: datetime | None = None) -> bool:
    return bool(
        profile.live_execution_enabled
        and profile.live_execution_expires_at is not None
        and not live_execution_blockers(profile, now)
    )


def disarm_live_execution(profile: BrokerProfile, reason: str) -> None:
    profile.live_execution_enabled = False
    profile.live_execution_armed_at = None
    profile.live_execution_expires_at = None
    profile.live_execution_last_disarm_reason = reason[:500]
