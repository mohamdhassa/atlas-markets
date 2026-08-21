from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.brokers.bybit_private import BybitPrivateClient, BybitPrivateError
from app.core.config import get_settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.models.paper import PaperWallet
from app.db.session import get_db
from app.schemas.broker_profile import BrokerCredentialsUpdate, BrokerProfileCreate, BrokerProfilePublic

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _is_admin(user: User) -> bool:
    return user.role == "ADMIN"


def _authorized_profile(db: Session, user: User, profile_id: uuid.UUID) -> BrokerProfile:
    profile = db.get(BrokerProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="account not found")
    if not _is_admin(user) and profile.user_id != user.id:
        raise HTTPException(status_code=403, detail="account access denied")
    return profile


def _client(profile: BrokerProfile) -> BybitPrivateClient:
    if profile.provider != "BYBIT":
        raise HTTPException(status_code=400, detail="credentials are only used by BYBIT profiles")
    if not profile.credentials_configured or not profile.api_key_encrypted or not profile.api_secret_encrypted:
        raise HTTPException(status_code=400, detail="API credentials are not configured")
    settings = get_settings()
    base_url = settings.bybit_demo_base_url if profile.environment == "DEMO" else settings.bybit_testnet_base_url
    return BybitPrivateClient(decrypt_secret(profile.api_key_encrypted), decrypt_secret(profile.api_secret_encrypted), base_url, settings.market_data_timeout_seconds)


@router.get("", response_model=list[BrokerProfilePublic])
def list_accounts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(BrokerProfile).order_by(BrokerProfile.created_at.desc())
    if not _is_admin(user):
        stmt = stmt.where(BrokerProfile.user_id == user.id)
    return list(db.scalars(stmt).all())


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
    if payload.provider == "ATLAS_PAPER" and payload.environment != "PAPER":
        raise HTTPException(status_code=400, detail="ATLAS PAPER profiles must use PAPER environment")
    if payload.provider == "BYBIT" and payload.environment == "PAPER":
        raise HTTPException(status_code=400, detail="BYBIT profiles must use DEMO or TESTNET")
    profile = BrokerProfile(user_id=owner_id, provider=payload.provider, account_label=payload.account_label.strip(), environment=payload.environment, external_account_ref=(payload.external_account_ref or "").strip() or None)
    if payload.provider == "ATLAS_PAPER":
        profile.last_connection_status = "CONNECTED"
        profile.credentials_configured = False
        profile.equity_usd = 100000.0
        profile.wallet_balance_usd = 100000.0
        profile.available_balance_usd = 100000.0
    db.add(profile)
    db.flush()
    if payload.provider == "ATLAS_PAPER":
        db.add(PaperWallet(profile_id=profile.id))
    db.commit()
    db.refresh(profile)
    return profile


@router.put("/{profile_id}/credentials", response_model=BrokerProfilePublic)
def save_credentials(profile_id: uuid.UUID, payload: BrokerCredentialsUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _authorized_profile(db, user, profile_id)
    if profile.provider != "BYBIT":
        raise HTTPException(status_code=400, detail="ATLAS PAPER does not require API credentials")
    profile.api_key_encrypted = encrypt_secret(payload.api_key.strip())
    profile.api_secret_encrypted = encrypt_secret(payload.api_secret.strip())
    profile.credentials_configured = True
    profile.last_connection_status = "NOT_TESTED"
    db.commit(); db.refresh(profile); return profile


@router.post("/{profile_id}/test", response_model=BrokerProfilePublic)
async def test_connection(profile_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _authorized_profile(db, user, profile_id)
    if profile.provider == "ATLAS_PAPER":
        profile.last_connection_status = "CONNECTED"; profile.last_connection_test_at = datetime.now(timezone.utc); db.commit(); db.refresh(profile); return profile
    try:
        await _client(profile).wallet(); profile.last_connection_status = "CONNECTED"
    except (BybitPrivateError, ValueError, Exception) as exc:
        profile.last_connection_status = "FAILED"; profile.last_connection_test_at = datetime.now(timezone.utc); db.commit()
        raise HTTPException(status_code=502, detail=f"connection failed: {str(exc)[:180]}") from exc
    profile.last_connection_test_at = datetime.now(timezone.utc); db.commit(); db.refresh(profile); return profile


@router.post("/{profile_id}/sync", response_model=BrokerProfilePublic)
async def sync_account(profile_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _authorized_profile(db, user, profile_id)
    if profile.provider == "ATLAS_PAPER":
        wallet = db.scalar(select(PaperWallet).where(PaperWallet.profile_id == profile.id))
        profile.equity_usd = wallet.cash_balance if wallet else 100000.0
        profile.wallet_balance_usd = wallet.cash_balance if wallet else 100000.0
        profile.available_balance_usd = wallet.cash_balance if wallet else 100000.0
        profile.last_connection_status = "CONNECTED"; profile.last_sync_at = datetime.now(timezone.utc); db.commit(); db.refresh(profile); return profile
    client = _client(profile)
    try:
        wallet = await client.wallet(); positions = await client.positions(); orders = await client.open_orders()
    except Exception as exc:
        profile.last_connection_status = "FAILED"; db.commit(); raise HTTPException(status_code=502, detail=f"sync failed: {str(exc)[:180]}") from exc
    account = (wallet.get("list") or [{}])[0]
    profile.equity_usd = float(account.get("totalEquity") or 0); profile.wallet_balance_usd = float(account.get("totalWalletBalance") or 0); profile.available_balance_usd = float(account.get("totalAvailableBalance") or 0)
    profile.open_positions_count = sum(1 for p in positions.get("list", []) if float(p.get("size") or 0) != 0); profile.open_orders_count = len(orders.get("list", [])); profile.last_connection_status = "CONNECTED"; profile.last_sync_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(profile); return profile


@router.patch("/{profile_id}/toggle", response_model=BrokerProfilePublic)
def toggle_account(profile_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _authorized_profile(db, user, profile_id); profile.is_enabled = not profile.is_enabled; db.commit(); db.refresh(profile); return profile
