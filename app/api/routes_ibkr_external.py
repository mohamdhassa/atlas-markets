from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.session import get_db
from app.schemas.broker_profile import BrokerConnectRequest, BrokerConnectResult, BrokerCredentialsUpdate, BrokerProfilePublic, BrokerValidateRequest, BrokerValidationResult

router = APIRouter(prefix="/ibkr", tags=["ibkr"])


def _is_admin(user: User) -> bool:
    return user.role == "ADMIN"


def _profile(db: Session, user: User, profile_id: uuid.UUID) -> BrokerProfile:
    p = db.get(BrokerProfile, profile_id)
    if p is None or p.provider != "IBKR":
        raise HTTPException(404, "IBKR account not found")
    if not _is_admin(user) and p.user_id != user.id:
        raise HTTPException(403, "account access denied")
    return p


def _clean(values: dict | None) -> dict[str, str]:
    data = {str(k): str(v).strip() for k, v in (values or {}).items() if str(v).strip()}
    if not data.get("account_id"):
        raise HTTPException(400, "IBKR account_id is required")
    data.setdefault("bridge_url", "http://host.docker.internal:8766")
    return data


def _client(values: dict[str, str]) -> IbkrBridgeClient:
    return IbkrBridgeClient(values["bridge_url"], values.get("bridge_token"), get_settings().market_data_timeout_seconds)


async def _validate(environment: str, values: dict | None) -> BrokerValidationResult:
    if environment not in {"PAPER", "LIVE"}:
        raise HTTPException(400, "IBKR supports Simulation (PAPER) or Live Money")
    creds = _clean(values)
    bridge = _client(creds)
    health = await bridge.health()
    if not health.get("connected"):
        raise HTTPException(400, "IBKR bridge is reachable but TWS/IB Gateway is not connected")
    account = await bridge.account()
    actual = str(account.get("account_id") or "").strip()
    expected = creds["account_id"]
    if not actual:
        raise HTTPException(409, "IBKR bridge did not report an account ID")
    if actual != expected:
        raise HTTPException(409, f"IBKR account mismatch: entered {expected}, bridge reports {actual}")
    simulation = bool(account.get("simulation", health.get("simulation")))
    if environment == "PAPER" and not simulation:
        raise HTTPException(409, "IBKR profile is Simulation but the connected TWS/IB Gateway session is Live Money")
    if environment == "LIVE" and simulation:
        raise HTTPException(409, "IBKR profile is Live Money but the connected TWS/IB Gateway session is Simulation")
    details = {
        "account_id": actual,
        "equity": account.get("equity"),
        "cash": account.get("cash"),
        "available": account.get("available"),
        "buying_power": account.get("buying_power"),
        "simulation": simulation,
        "bridge_url": creds["bridge_url"],
    }
    warnings = []
    if environment == "LIVE":
        warnings.append("Live Money connectivity does not enable ATLAS live execution; the global and per-account gates remain required.")
    return BrokerValidationResult(
        valid=True,
        provider="IBKR",
        environment=environment,
        connection_status="CONNECTED",
        message=f"IBKR account {actual} validated through the ATLAS bridge.",
        detected_account_ref=actual,
        detected_account_name="Interactive Brokers",
        warnings=warnings,
        details=details,
    )


@router.post("/validate", response_model=BrokerValidationResult)
async def validate_ibkr(payload: BrokerValidateRequest, _: User = Depends(get_current_user)):
    if payload.provider != "IBKR":
        raise HTTPException(400, "IBKR provider required")
    try:
        return await _validate(payload.environment, payload.credentials)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"IBKR validation failed: {str(exc)[:300]}") from exc


@router.post("/connect", response_model=BrokerConnectResult, status_code=status.HTTP_201_CREATED)
async def connect_ibkr(payload: BrokerConnectRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.provider != "IBKR":
        raise HTTPException(400, "IBKR provider required")
    validation = await _validate(payload.environment, payload.credentials)
    owner_id = payload.owner_user_id or user.id
    if payload.owner_user_id and not _is_admin(user):
        raise HTTPException(403, "admin role required to assign another owner")
    duplicate = db.scalar(select(BrokerProfile).where(BrokerProfile.user_id == owner_id, BrokerProfile.provider == "IBKR", BrokerProfile.environment == payload.environment, BrokerProfile.external_account_ref == validation.detected_account_ref))
    if duplicate:
        raise HTTPException(409, f"IBKR account already connected as {duplicate.account_label}")
    creds = _clean(payload.credentials)
    p = BrokerProfile(
        user_id=owner_id,
        provider="IBKR",
        account_label=payload.account_label.strip(),
        environment=payload.environment,
        external_account_ref=validation.detected_account_ref,
        is_enabled=True,
        is_active=False,
        live_execution_enabled=False,
        credentials_configured=True,
        credential_blob_encrypted=encrypt_secret(json.dumps(creds, separators=(",", ":"))),
        last_connection_status="CONNECTED",
        last_connection_test_at=datetime.now(timezone.utc),
        equity_usd=float(validation.details.get("equity") or 0),
        wallet_balance_usd=float(validation.details.get("cash") or 0),
        available_balance_usd=float(validation.details.get("available") or 0),
    )
    db.add(p)
    db.flush()
    if payload.activate:
        db.execute(update(BrokerProfile).where(BrokerProfile.user_id == owner_id, BrokerProfile.provider == "IBKR", BrokerProfile.id != p.id).values(is_active=False))
        p.is_active = True
    db.commit()
    db.refresh(p)
    return BrokerConnectResult(profile=p, connected=True, message=validation.message, next_action="Configure STOCK/ETF symbols and strategies")


@router.put("/{profile_id}/credentials", response_model=BrokerProfilePublic)
async def replace_ibkr_credentials(profile_id: uuid.UUID, payload: BrokerCredentialsUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _profile(db, user, profile_id)
    validation = await _validate(p.environment, payload.credentials)
    creds = _clean(payload.credentials)
    p.credential_blob_encrypted = encrypt_secret(json.dumps(creds, separators=(",", ":")))
    p.credentials_configured = True
    p.external_account_ref = validation.detected_account_ref
    p.last_connection_status = "CONNECTED"
    p.last_connection_test_at = datetime.now(timezone.utc)
    p.equity_usd = float(validation.details.get("equity") or 0)
    p.wallet_balance_usd = float(validation.details.get("cash") or 0)
    p.available_balance_usd = float(validation.details.get("available") or 0)
    db.commit(); db.refresh(p); return p


@router.post("/{profile_id}/test", response_model=BrokerProfilePublic)
async def test_ibkr(profile_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _profile(db, user, profile_id)
    if not p.credential_blob_encrypted:
        raise HTTPException(400, "IBKR bridge configuration is missing")
    creds = json.loads(decrypt_secret(p.credential_blob_encrypted))
    try:
        validation = await _validate(p.environment, creds)
    except Exception as exc:
        p.last_connection_status = "FAILED"; p.last_connection_test_at = datetime.now(timezone.utc); db.commit(); raise
    p.last_connection_status = "CONNECTED"; p.last_connection_test_at = datetime.now(timezone.utc)
    p.equity_usd = float(validation.details.get("equity") or 0); p.wallet_balance_usd = float(validation.details.get("cash") or 0); p.available_balance_usd = float(validation.details.get("available") or 0)
    db.commit(); db.refresh(p); return p


@router.post("/{profile_id}/sync", response_model=BrokerProfilePublic)
async def sync_ibkr(profile_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _profile(db, user, profile_id)
    if not p.credential_blob_encrypted:
        raise HTTPException(400, "IBKR bridge configuration is missing")
    creds = json.loads(decrypt_secret(p.credential_blob_encrypted)); c = _client(creds)
    account, positions, orders = await c.account(), await c.positions(), await c.orders()
    p.equity_usd = float(account.get("equity") or 0); p.wallet_balance_usd = float(account.get("cash") or 0); p.available_balance_usd = float(account.get("available") or 0)
    p.open_positions_count = len([x for x in positions.get("list", []) if float(x.get("quantity") or 0) != 0]); p.open_orders_count = len(orders.get("list", [])); p.last_connection_status = "CONNECTED"; p.last_sync_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(p); return p


@router.get("/readiness")
def readiness(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(BrokerProfile).where(BrokerProfile.provider == "IBKR", BrokerProfile.is_enabled.is_(True))
    if not _is_admin(user): q = q.where(BrokerProfile.user_id == user.id)
    rows = list(db.scalars(q).all())
    connected = [p for p in rows if p.last_connection_status == "CONNECTED"]
    return {"provider": "IBKR", "adapter_ready": True, "bridge_port": 8766, "accounts": len(rows), "connected": len(connected), "simulation_ready": any(p.environment == "PAPER" for p in connected), "live_money_ready": any(p.environment == "LIVE" for p in connected), "markets": ["STOCK", "ETF"]}
