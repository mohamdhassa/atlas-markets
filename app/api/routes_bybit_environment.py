from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.brokers.bybit_private import BybitPrivateClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.session import get_db

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _is_admin(user: User) -> bool:
    return user.role == "ADMIN"


def _profile(db: Session, user: User, profile_id: uuid.UUID) -> BrokerProfile:
    profile = db.get(BrokerProfile, profile_id)
    if profile is None or profile.provider != "BYBIT":
        raise HTTPException(404, "Bybit account not found")
    if not _is_admin(user) and profile.user_id != user.id:
        raise HTTPException(403, "account access denied")
    if not profile.credentials_configured or not profile.api_key_encrypted or not profile.api_secret_encrypted:
        raise HTTPException(409, "Bybit credentials are not configured")
    return profile


def _base(environment: str) -> str:
    settings = get_settings()
    if environment == "LIVE":
        return settings.bybit_public_base_url
    if environment == "DEMO":
        return settings.bybit_demo_base_url
    return settings.bybit_testnet_base_url


@router.post("/{profile_id}/detect-bybit-environment")
async def detect_bybit_environment(
    profile_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _profile(db, user, profile_id)
    api_key = decrypt_secret(profile.api_key_encrypted)
    api_secret = decrypt_secret(profile.api_secret_encrypted)
    timeout = get_settings().market_data_timeout_seconds

    successes: list[tuple[str, dict]] = []
    errors: dict[str, str] = {}
    for environment in ("DEMO", "TESTNET", "LIVE"):
        try:
            client = BybitPrivateClient(api_key, api_secret, _base(environment), timeout)
            wallet = await client.wallet()
            row = (wallet.get("list") or [{}])[0]
            successes.append((environment, row))
        except Exception as exc:
            errors[environment] = str(exc)[:240]

    if not successes:
        raise HTTPException(502, {"message": "Saved Bybit credentials did not authenticate against any configured Bybit environment.", "errors": errors})
    if len(successes) > 1:
        raise HTTPException(409, {"message": "Bybit credentials authenticated against more than one configured environment; ATLAS will not reclassify automatically.", "matches": [x[0] for x in successes]})

    environment, row = successes[0]
    previous = profile.environment
    profile.environment = environment
    profile.last_connection_status = "CONNECTED"
    profile.last_connection_test_at = datetime.now(timezone.utc)
    profile.equity_usd = float(row.get("totalEquity") or 0)
    profile.wallet_balance_usd = float(row.get("totalWalletBalance") or 0)
    profile.available_balance_usd = float(row.get("totalAvailableBalance") or row.get("totalWalletBalance") or 0)
    profile.live_execution_enabled = False
    profile.live_execution_armed_at = None
    db.commit()
    db.refresh(profile)

    return {
        "id": str(profile.id),
        "previous_environment": previous,
        "detected_environment": environment,
        "mode": "LIVE MONEY" if environment == "LIVE" else "SIMULATION",
        "equity": profile.equity_usd,
        "available": profile.available_balance_usd,
        "status": profile.last_connection_status,
        "message": f"Bybit environment detected as {environment}; account profile synchronized.",
    }
