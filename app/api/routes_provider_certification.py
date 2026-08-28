from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.brokers.bybit_private import BybitPrivateClient
from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.session import get_db

router = APIRouter(prefix="/provider-certification", tags=["provider-certification"])


def _profile(db: Session, user: User, profile_id: uuid.UUID, provider: str) -> BrokerProfile:
    profile = db.get(BrokerProfile, profile_id)
    if profile is None or profile.provider != provider:
        raise HTTPException(404, f"{provider} account not found")
    if user.role != "ADMIN" and profile.user_id != user.id:
        raise HTTPException(403, "account access denied")
    if not profile.credentials_configured:
        raise HTTPException(409, "account credentials are not configured")
    return profile


def _bybit_base(environment: str) -> str:
    settings = get_settings()
    if environment == "LIVE":
        return settings.bybit_public_base_url
    if environment == "DEMO":
        return settings.bybit_demo_base_url
    return settings.bybit_testnet_base_url


@router.get("/bybit/{profile_id}/diagnostics")
async def bybit_diagnostics(
    profile_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _profile(db, user, profile_id, "BYBIT")
    if not profile.api_key_encrypted or not profile.api_secret_encrypted:
        raise HTTPException(409, "Bybit API key and secret are required")

    client = BybitPrivateClient(
        decrypt_secret(profile.api_key_encrypted),
        decrypt_secret(profile.api_secret_encrypted),
        _bybit_base(profile.environment),
        get_settings().market_data_timeout_seconds,
    )

    errors: list[str] = []
    wallet: dict = {}
    account_info: dict = {}
    api_info: dict = {}
    try:
        wallet = await client.wallet()
    except Exception as exc:
        errors.append(f"WALLET: {exc}")
    try:
        account_info = await client.account_info()
    except Exception as exc:
        errors.append(f"ACCOUNT_INFO: {exc}")
    try:
        api_info = await client.api_key_info()
    except Exception as exc:
        errors.append(f"API_KEY_INFO: {exc}")

    permissions = api_info.get("permissions") or {}
    contract_permissions = set(permissions.get("ContractTrade") or [])
    read_write = int(api_info.get("readOnly", 1)) == 0 if api_info else False
    has_order = "Order" in contract_permissions
    has_position = "Position" in contract_permissions
    unified_status = int(account_info.get("unifiedMarginStatus") or 0) if account_info else 0
    environment_ok = profile.environment in {"TESTNET", "DEMO"}

    blockers: list[str] = []
    if errors:
        blockers.append("BYBIT_DIAGNOSTIC_REQUEST_FAILED")
    if not environment_ok:
        blockers.append("BYBIT_SIMULATION_ENVIRONMENT_REQUIRED")
    if not read_write:
        blockers.append("BYBIT_API_KEY_READ_ONLY")
    if not has_order:
        blockers.append("BYBIT_CONTRACT_ORDER_PERMISSION_MISSING")
    if not has_position:
        blockers.append("BYBIT_CONTRACT_POSITION_PERMISSION_MISSING")
    if unified_status <= 0:
        blockers.append("BYBIT_UNIFIED_ACCOUNT_NOT_CONFIRMED")

    row = (wallet.get("list") or [{}])[0] if wallet else {}
    return {
        "provider": "BYBIT",
        "profile_id": str(profile.id),
        "environment": profile.environment,
        "simulation_environment": environment_ok,
        "read_write": read_write,
        "contract_permissions": sorted(contract_permissions),
        "order_permission": has_order,
        "position_permission": has_position,
        "unified_margin_status": unified_status,
        "margin_mode": account_info.get("marginMode"),
        "api_key_type": api_info.get("type"),
        "kyc_region": api_info.get("kycRegion"),
        "equity": row.get("totalEquity"),
        "available": row.get("totalAvailableBalance"),
        "diagnostic_pass": not blockers,
        "blockers": blockers,
        "errors": errors,
        "note": "A diagnostic PASS confirms account/API configuration only. Bybit can still reject an order server-side for compliance or product restrictions.",
    }


class IbkrWhatIfRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)
    side: str = Field(pattern="^(BUY|SELL)$")
    quantity: int = Field(ge=1, le=100)


@router.post("/ibkr/{profile_id}/what-if")
async def ibkr_what_if(
    profile_id: uuid.UUID,
    payload: IbkrWhatIfRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    profile = db.get(BrokerProfile, profile_id)
    if profile is None or profile.provider != "IBKR":
        raise HTTPException(404, "IBKR account not found")
    if profile.environment != "PAPER":
        raise HTTPException(409, "IBKR WhatIf certification requires PAPER environment")
    if not profile.credential_blob_encrypted:
        raise HTTPException(409, "IBKR bridge configuration missing")

    creds = json.loads(decrypt_secret(profile.credential_blob_encrypted))
    bridge = IbkrBridgeClient(
        creds.get("bridge_url") or "http://host.docker.internal:8766",
        creds.get("bridge_token"),
        get_settings().market_data_timeout_seconds,
    )
    health = await bridge.health()
    if not health.get("simulation"):
        raise HTTPException(409, "IBKR bridge is not in PAPER/simulation mode")

    result = await bridge.order_check({
        "symbol": payload.symbol.strip().upper(),
        "side": payload.side,
        "quantity": payload.quantity,
        "order_type": "MKT",
        "sec_type": "STK",
        "exchange": "SMART",
        "currency": "USD",
        "account_id": creds.get("account_id"),
    })

    if not result.get("what_if"):
        raise HTTPException(409, {
            "message": "IBKR bridge upgrade required: /order-check is still local validation only.",
            "bridge_result": result,
        })

    margin = result.get("margin") or {}
    return {
        "provider": "IBKR",
        "environment": "PAPER",
        "purpose": "BROKER_NATIVE_WHAT_IF_NO_EXECUTION",
        "symbol": payload.symbol.strip().upper(),
        "side": payload.side,
        "quantity": payload.quantity,
        "what_if_pass": bool(result.get("ok")),
        "margin": margin,
        "commission": result.get("commission"),
        "warning": result.get("warning"),
        "broker_result": result,
    }
