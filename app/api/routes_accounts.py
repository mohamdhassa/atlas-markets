from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.brokers.bybit_private import BybitPrivateClient, BybitPrivateError
from app.core.config import get_settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.models.paper import PaperWallet
from app.db.session import get_db
from app.schemas.broker_profile import BrokerCredentialsUpdate, BrokerProfileCreate, BrokerProfilePublic, LiveExecutionUpdate

router = APIRouter(prefix="/accounts", tags=["accounts"])

PROVIDER_ENVIRONMENTS = {
    "ATLAS_PAPER": {"PAPER"},
    "BYBIT": {"DEMO", "TESTNET", "LIVE"},
    "MT5": {"DEMO", "LIVE"},
    "IBKR": {"PAPER", "LIVE"},
}


def _is_admin(user: User) -> bool:
    return user.role == "ADMIN"


def _authorized_profile(db: Session, user: User, profile_id: uuid.UUID) -> BrokerProfile:
    profile = db.get(BrokerProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="account not found")
    if not _is_admin(user) and profile.user_id != user.id:
        raise HTTPException(status_code=403, detail="account access denied")
    return profile


def _bybit_client(profile: BrokerProfile) -> BybitPrivateClient:
    if profile.provider != "BYBIT":
        raise HTTPException(status_code=400, detail="profile is not BYBIT")
    if not profile.credentials_configured or not profile.api_key_encrypted or not profile.api_secret_encrypted:
        raise HTTPException(status_code=400, detail="API credentials are not configured")
    settings = get_settings()
    if profile.environment == "LIVE":
        base_url = settings.bybit_public_base_url
    elif profile.environment == "DEMO":
        base_url = settings.bybit_demo_base_url
    else:
        base_url = settings.bybit_testnet_base_url
    return BybitPrivateClient(decrypt_secret(profile.api_key_encrypted), decrypt_secret(profile.api_secret_encrypted), base_url, settings.market_data_timeout_seconds)


def _validate_generic_credentials(provider: str, values: dict) -> dict:
    cleaned = {str(k): str(v).strip() for k, v in values.items() if str(v).strip()}
    required = {
        "MT5": {"login", "password", "server"},
        "IBKR": {"account_id", "host", "port", "client_id"},
    }.get(provider, set())
    missing = sorted(required - set(cleaned))
    if missing:
        raise HTTPException(status_code=400, detail=f"missing credentials: {', '.join(missing)}")
    return cleaned


@router.get("", response_model=list[BrokerProfilePublic])
def list_accounts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(BrokerProfile).order_by(BrokerProfile.provider, BrokerProfile.environment, BrokerProfile.created_at.desc())
    if not _is_admin(user):
        stmt = stmt.where(BrokerProfile.user_id == user.id)
    return list(db.scalars(stmt).all())


@router.get("/capabilities")
def account_capabilities(user: User = Depends(get_current_user)):
    settings = get_settings()
    return {
        "providers": {k: sorted(v) for k, v in PROVIDER_ENVIRONMENTS.items()},
        "credential_fields": {
            "BYBIT": ["api_key", "api_secret"],
            "MT5": ["login", "password", "server"],
            "IBKR": ["account_id", "host", "port", "client_id"],
            "ATLAS_PAPER": [],
        },
        "allow_live_trading": bool(settings.allow_live_trading),
        "can_manage_live": _is_admin(user),
    }


@router.post("", response_model=BrokerProfilePublic, status_code=status.HTTP_201_CREATED)
def create_account(payload: BrokerProfileCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owner_id = user.id
    if payload.owner_user_id is not None:
        if not _is_admin(user):
            raise HTTPException(status_code=403, detail="admin role required to assign another owner")
        owner = db.get(User, payload.owner_user_id)
        if owner is None:
            raise HTTPException(status_code=404, detail="owner user not found")
        owner_id = owner.id
    allowed = PROVIDER_ENVIRONMENTS.get(payload.provider)
    if allowed is None or payload.environment not in allowed:
        raise HTTPException(status_code=400, detail=f"{payload.provider} does not support {payload.environment} environment")
    profile = BrokerProfile(
        user_id=owner_id, provider=payload.provider, account_label=payload.account_label.strip(),
        environment=payload.environment, external_account_ref=(payload.external_account_ref or "").strip() or None,
        live_execution_enabled=False, is_active=False,
    )
    if payload.provider == "ATLAS_PAPER":
        profile.last_connection_status = "CONNECTED"
        profile.equity_usd = profile.wallet_balance_usd = profile.available_balance_usd = 100000.0
    db.add(profile); db.flush()
    if payload.provider == "ATLAS_PAPER": db.add(PaperWallet(profile_id=profile.id))
    sibling = db.scalar(select(BrokerProfile).where(BrokerProfile.user_id == owner_id, BrokerProfile.provider == payload.provider, BrokerProfile.id != profile.id, BrokerProfile.is_active.is_(True)))
    if sibling is None: profile.is_active = True
    db.commit(); db.refresh(profile); return profile


@router.put("/{profile_id}/credentials", response_model=BrokerProfilePublic)
def save_credentials(profile_id: uuid.UUID, payload: BrokerCredentialsUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _authorized_profile(db, user, profile_id)
    if profile.provider == "ATLAS_PAPER":
        raise HTTPException(status_code=400, detail="ATLAS PAPER does not require credentials")
    if profile.provider == "BYBIT":
        if not payload.api_key or not payload.api_secret:
            raise HTTPException(status_code=400, detail="BYBIT requires API key and API secret")
        profile.api_key_encrypted = encrypt_secret(payload.api_key.strip())
        profile.api_secret_encrypted = encrypt_secret(payload.api_secret.strip())
        profile.credential_blob_encrypted = None
    else:
        values = _validate_generic_credentials(profile.provider, payload.credentials or {})
        profile.credential_blob_encrypted = encrypt_secret(json.dumps(values, separators=(",", ":")))
        profile.api_key_encrypted = profile.api_secret_encrypted = None
    profile.credentials_configured = True
    profile.last_connection_status = "NOT_TESTED"
    db.commit(); db.refresh(profile); return profile


@router.post("/{profile_id}/activate", response_model=BrokerProfilePublic)
def activate_account(profile_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _authorized_profile(db, user, profile_id)
    db.execute(update(BrokerProfile).where(BrokerProfile.user_id == profile.user_id, BrokerProfile.provider == profile.provider).values(is_active=False))
    profile.is_active = True
    db.commit(); db.refresh(profile); return profile


@router.put("/{profile_id}/live-execution", response_model=BrokerProfilePublic)
def set_live_execution(profile_id: uuid.UUID, payload: LiveExecutionUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="ADMIN role required")
    profile = _authorized_profile(db, user, profile_id)
    if profile.environment != "LIVE":
        raise HTTPException(status_code=400, detail="live execution can only be changed for LIVE accounts")
    if payload.enabled and not get_settings().allow_live_trading:
        raise HTTPException(status_code=409, detail="global ALLOW_LIVE_TRADING is false")
    if payload.enabled and (not profile.credentials_configured or profile.last_connection_status != "CONNECTED"):
        raise HTTPException(status_code=409, detail="test and connect the live account before enabling live execution")
    profile.live_execution_enabled = payload.enabled
    profile.live_execution_armed_at = datetime.now(timezone.utc) if payload.enabled else None
    db.commit(); db.refresh(profile); return profile


@router.post("/{profile_id}/test", response_model=BrokerProfilePublic)
async def test_connection(profile_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _authorized_profile(db, user, profile_id)
    if profile.provider == "ATLAS_PAPER":
        profile.last_connection_status = "CONNECTED"
    elif profile.provider == "BYBIT":
        try:
            await _bybit_client(profile).wallet(); profile.last_connection_status = "CONNECTED"
        except (BybitPrivateError, ValueError, Exception) as exc:
            profile.last_connection_status = "FAILED"; profile.last_connection_test_at = datetime.now(timezone.utc); db.commit()
            raise HTTPException(status_code=502, detail=f"connection failed: {str(exc)[:180]}") from exc
    else:
        if not profile.credentials_configured:
            raise HTTPException(status_code=400, detail="credentials are not configured")
        profile.last_connection_status = "CONFIGURED"
    profile.last_connection_test_at = datetime.now(timezone.utc); db.commit(); db.refresh(profile); return profile


@router.post("/{profile_id}/sync", response_model=BrokerProfilePublic)
async def sync_account(profile_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _authorized_profile(db, user, profile_id)
    if profile.provider == "ATLAS_PAPER":
        wallet = db.scalar(select(PaperWallet).where(PaperWallet.profile_id == profile.id))
        balance = wallet.cash_balance if wallet else 100000.0
        profile.equity_usd = profile.wallet_balance_usd = profile.available_balance_usd = balance
        profile.last_connection_status = "CONNECTED"
    elif profile.provider == "BYBIT":
        client = _bybit_client(profile)
        try: wallet, positions, orders = await client.wallet(), await client.positions(), await client.open_orders()
        except Exception as exc: profile.last_connection_status = "FAILED"; db.commit(); raise HTTPException(status_code=502, detail=f"sync failed: {str(exc)[:180]}") from exc
        account = (wallet.get("list") or [{}])[0]
        profile.equity_usd = float(account.get("totalEquity") or 0); profile.wallet_balance_usd = float(account.get("totalWalletBalance") or 0); profile.available_balance_usd = float(account.get("totalAvailableBalance") or 0)
        profile.open_positions_count = sum(1 for p in positions.get("list", []) if float(p.get("size") or 0) != 0); profile.open_orders_count = len(orders.get("list", [])); profile.last_connection_status = "CONNECTED"
    else:
        raise HTTPException(status_code=501, detail=f"{profile.provider} sync adapter will be connected after the account is created")
    profile.last_sync_at = datetime.now(timezone.utc); db.commit(); db.refresh(profile); return profile


@router.patch("/{profile_id}/toggle", response_model=BrokerProfilePublic)
def toggle_account(profile_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _authorized_profile(db, user, profile_id); profile.is_enabled = not profile.is_enabled
    if not profile.is_enabled: profile.live_execution_enabled = False; profile.live_execution_armed_at = None
    db.commit(); db.refresh(profile); return profile
