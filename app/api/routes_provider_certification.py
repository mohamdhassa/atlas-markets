from __future__ import annotations

import asyncio
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
async def bybit_diagnostics(profile_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _profile(db, user, profile_id, "BYBIT")
    if not profile.api_key_encrypted or not profile.api_secret_encrypted:
        raise HTTPException(409, "Bybit API key and secret are required")
    client = BybitPrivateClient(decrypt_secret(profile.api_key_encrypted), decrypt_secret(profile.api_secret_encrypted), _bybit_base(profile.environment), get_settings().market_data_timeout_seconds)
    errors: list[str] = []; wallet: dict = {}; account_info: dict = {}; api_info: dict = {}
    try: wallet = await client.wallet()
    except Exception as exc: errors.append(f"WALLET: {exc}")
    try: account_info = await client.account_info()
    except Exception as exc: errors.append(f"ACCOUNT_INFO: {exc}")
    try: api_info = await client.api_key_info()
    except Exception as exc: errors.append(f"API_KEY_INFO: {exc}")
    permissions = api_info.get("permissions") or {}; contract_permissions = set(permissions.get("ContractTrade") or [])
    read_write = int(api_info.get("readOnly", 1)) == 0 if api_info else False; has_order = "Order" in contract_permissions; has_position = "Position" in contract_permissions
    unified_status = int(account_info.get("unifiedMarginStatus") or 0) if account_info else 0; environment_ok = profile.environment in {"TESTNET", "DEMO"}
    blockers: list[str] = []
    if errors: blockers.append("BYBIT_DIAGNOSTIC_REQUEST_FAILED")
    if not environment_ok: blockers.append("BYBIT_SIMULATION_ENVIRONMENT_REQUIRED")
    if not read_write: blockers.append("BYBIT_API_KEY_READ_ONLY")
    if not has_order: blockers.append("BYBIT_CONTRACT_ORDER_PERMISSION_MISSING")
    if not has_position: blockers.append("BYBIT_CONTRACT_POSITION_PERMISSION_MISSING")
    if unified_status <= 0: blockers.append("BYBIT_UNIFIED_ACCOUNT_NOT_CONFIRMED")
    row = (wallet.get("list") or [{}])[0] if wallet else {}
    return {"provider":"BYBIT","profile_id":str(profile.id),"environment":profile.environment,"simulation_environment":environment_ok,"read_write":read_write,"contract_permissions":sorted(contract_permissions),"order_permission":has_order,"position_permission":has_position,"unified_margin_status":unified_status,"margin_mode":account_info.get("marginMode"),"api_key_type":api_info.get("type"),"kyc_region":api_info.get("kycRegion"),"equity":row.get("totalEquity"),"available":row.get("totalAvailableBalance"),"diagnostic_pass":not blockers,"blockers":blockers,"errors":errors,"note":"A diagnostic PASS confirms account/API configuration only. Bybit can still reject an order server-side for compliance or product restrictions."}


class IbkrWhatIfRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)
    side: str = Field(pattern="^(BUY|SELL)$")
    quantity: int = Field(ge=1, le=100)


class IbkrCertificationRequest(BaseModel):
    symbol: str = Field(default="IWM", min_length=1, max_length=24)
    side: str = Field(default="BUY", pattern="^(BUY|SELL)$")
    quantity: int = Field(default=1, ge=1, le=1)


def _ibkr_bridge(profile: BrokerProfile) -> tuple[IbkrBridgeClient, dict]:
    if profile.environment != "PAPER": raise HTTPException(409, "IBKR certification requires PAPER environment")
    if not profile.credential_blob_encrypted: raise HTTPException(409, "IBKR bridge configuration missing")
    creds = json.loads(decrypt_secret(profile.credential_blob_encrypted))
    bridge = IbkrBridgeClient(creds.get("bridge_url") or "http://host.docker.internal:8766", creds.get("bridge_token"), get_settings().market_data_timeout_seconds)
    return bridge, creds


def _ibkr_payload(creds: dict, symbol: str, side: str, quantity: int = 1) -> dict:
    return {"symbol":symbol.strip().upper(),"side":side,"quantity":quantity,"order_type":"MKT","sec_type":"STK","exchange":"SMART","currency":"USD","account_id":creds.get("account_id")}


@router.post("/ibkr/{profile_id}/what-if")
async def ibkr_what_if(profile_id: uuid.UUID, payload: IbkrWhatIfRequest, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    profile = db.get(BrokerProfile, profile_id)
    if profile is None or profile.provider != "IBKR": raise HTTPException(404, "IBKR account not found")
    bridge, creds = _ibkr_bridge(profile); health = await bridge.health()
    if not health.get("simulation"): raise HTTPException(409, "IBKR bridge is not in PAPER/simulation mode")
    result = await bridge.order_check(_ibkr_payload(creds, payload.symbol, payload.side, payload.quantity))
    if not result.get("what_if"): raise HTTPException(409, {"message":"IBKR bridge upgrade required: /order-check is still local validation only.","bridge_result":result})
    return {"provider":"IBKR","environment":"PAPER","purpose":"BROKER_NATIVE_WHAT_IF_NO_EXECUTION","symbol":payload.symbol.strip().upper(),"side":payload.side,"quantity":payload.quantity,"what_if_pass":bool(result.get("ok")),"margin":result.get("margin") or {},"commission":result.get("commission"),"warning":result.get("warning"),"broker_result":result}


@router.post("/ibkr/{profile_id}/certify-single")
async def ibkr_certify_single(profile_id: uuid.UUID, payload: IbkrCertificationRequest, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    profile = db.get(BrokerProfile, profile_id)
    if profile is None or profile.provider != "IBKR": raise HTTPException(404, "IBKR account not found")
    bridge, creds = _ibkr_bridge(profile); health = await bridge.health()
    if not health.get("simulation"): raise HTTPException(409, "IBKR bridge is not in PAPER/simulation mode")
    symbol = payload.symbol.strip().upper(); side = payload.side; order_payload = _ibkr_payload(creds, symbol, side, 1)
    positions = (await bridge.positions()).get("list", []); orders = (await bridge.orders()).get("list", [])
    if any(str(x.get("symbol") or "").upper() == symbol and float(x.get("quantity") or 0) != 0 for x in positions): raise HTTPException(409, "IBKR_CERTIFICATION_SYMBOL_ALREADY_HAS_POSITION")
    if any(str(x.get("symbol") or "").upper() == symbol for x in orders): raise HTTPException(409, "IBKR_CERTIFICATION_SYMBOL_ALREADY_HAS_OPEN_ORDER")
    check = await bridge.order_check(order_payload)
    if not check.get("what_if") or not check.get("ok"): raise HTTPException(409, {"message":"IBKR broker-native WhatIf did not pass","broker_result":check})
    placed = await bridge.place_order(order_payload)
    if not placed.get("accepted"): raise HTTPException(409, {"message":"IBKR PAPER certification order was rejected","broker_result":placed})
    order_id = int(placed.get("order_id")); status = placed.get("status")
    for _ in range(10):
        status_result = await bridge.order_status(order_id); status = status_result.get("status") or status
        if status and (float(status.get("filled") or 0) >= 1 or str(status.get("status") or "").upper() in {"FILLED","CANCELLED","INACTIVE"}): break
        await asyncio.sleep(0.5)
    positions_after = (await bridge.positions()).get("list", []); position = next((x for x in positions_after if str(x.get("symbol") or "").upper() == symbol and abs(float(x.get("quantity") or 0)) >= 1), None)
    return {"provider":"IBKR","environment":"PAPER","purpose":"CONTROLLED_SINGLE_SHARE_CERTIFICATION","certification_pass":bool(position),"symbol":symbol,"side":side,"quantity":1,"what_if":check,"order_id":order_id,"order_status":status,"position":position,"next_action":"Run controlled close using the returned symbol after certification_pass=true."}


@router.post("/ibkr/{profile_id}/certify-close")
async def ibkr_certify_close(profile_id: uuid.UUID, payload: IbkrCertificationRequest, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    profile = db.get(BrokerProfile, profile_id)
    if profile is None or profile.provider != "IBKR": raise HTTPException(404, "IBKR account not found")
    bridge, creds = _ibkr_bridge(profile); health = await bridge.health()
    if not health.get("simulation"): raise HTTPException(409, "IBKR bridge is not in PAPER/simulation mode")
    symbol = payload.symbol.strip().upper(); positions = (await bridge.positions()).get("list", [])
    position = next((x for x in positions if str(x.get("symbol") or "").upper() == symbol and abs(float(x.get("quantity") or 0)) == 1), None)
    if not position: raise HTTPException(409, "IBKR_CERTIFICATION_EXACT_ONE_SHARE_POSITION_REQUIRED")
    qty = float(position.get("quantity") or 0); close_side = "SELL" if qty > 0 else "BUY"; close_payload = _ibkr_payload(creds, symbol, close_side, 1)
    check = await bridge.order_check(close_payload)
    if not check.get("what_if") or not check.get("ok"): raise HTTPException(409, {"message":"IBKR close WhatIf did not pass","broker_result":check})
    # Close intentionally calls the bridge order endpoint through the client transport because normal place_order duplicate protection correctly blocks symbols with an existing position.
    placed = await bridge._post('/orders', close_payload)
    if not placed.get("accepted"): raise HTTPException(409, {"message":"IBKR PAPER certification close was rejected","broker_result":placed})
    order_id = int(placed.get("order_id")); status = placed.get("status")
    for _ in range(10):
        status_result = await bridge.order_status(order_id); status = status_result.get("status") or status
        if status and (float(status.get("filled") or 0) >= 1 or str(status.get("status") or "").upper() in {"FILLED","CANCELLED","INACTIVE"}): break
        await asyncio.sleep(0.5)
    remaining = [x for x in (await bridge.positions()).get("list", []) if str(x.get("symbol") or "").upper() == symbol and float(x.get("quantity") or 0) != 0]
    executions = await bridge.executions(1)
    return {"provider":"IBKR","environment":"PAPER","purpose":"CONTROLLED_SINGLE_SHARE_CERTIFICATION_CLOSE","close_pass":not remaining,"symbol":symbol,"side":close_side,"quantity":1,"what_if":check,"order_id":order_id,"order_status":status,"remaining_positions":remaining,"executions":[x for x in executions.get("list", []) if str(x.get("symbol") or "").upper() == symbol],"certification_complete":not remaining}
