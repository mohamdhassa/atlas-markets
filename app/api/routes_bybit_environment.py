from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
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


def _client(profile: BrokerProfile) -> BybitPrivateClient:
    return BybitPrivateClient(
        decrypt_secret(profile.api_key_encrypted or ""),
        decrypt_secret(profile.api_secret_encrypted or ""),
        _base(profile.environment),
        get_settings().market_data_timeout_seconds,
    )


class BybitCertificationOrder(BaseModel):
    symbol: str = Field(default="BTCUSDT", min_length=3, max_length=24)
    side: str = Field(default="BUY", pattern="^(BUY|SELL)$")
    quantity: float = Field(default=0.0001, ge=0.00001, le=0.001)


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


@router.post("/{profile_id}/certify-bybit-test-order")
async def certify_bybit_test_order(
    profile_id: uuid.UUID,
    payload: BybitCertificationOrder,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_admin(user):
        raise HTTPException(403, "ADMIN role required")
    profile = _profile(db, user, profile_id)
    if profile.environment not in {"TESTNET", "DEMO"}:
        raise HTTPException(409, "Bybit Spot certification is restricted to TESTNET or DEMO")

    symbol = payload.symbol.strip().upper().replace("/", "").replace(" ", "")
    side = "Buy" if payload.side == "BUY" else "Sell"
    client = _client(profile)

    open_orders_before = (await client.spot_open_orders()).get("list", [])
    if any(str(row.get("symbol") or "").upper() == symbol for row in open_orders_before):
        raise HTTPException(409, "BYBIT_SPOT_CERTIFICATION_SYMBOL_ALREADY_HAS_OPEN_ORDER")

    wallet_before = await client.wallet()
    holdings_before = client.spot_holdings_from_wallet(wallet_before)
    base_coin = symbol[:-4] if symbol.endswith("USDT") else ""
    before_qty = next((float(x.get("quantity") or 0) for x in holdings_before if x.get("coin") == base_coin), 0.0)

    link_id = f"atlas-spot-cert-{uuid.uuid4().hex[:15]}"
    try:
        placed = await client.place_test_spot_market_order(
            symbol=symbol,
            side=side,
            qty=payload.quantity,
            order_link_id=link_id,
        )
    except Exception as exc:
        raise HTTPException(
            409,
            {
                "provider": "BYBIT",
                "product": "SPOT",
                "environment": profile.environment,
                "purpose": "CONTROLLED_SPOT_SIMULATION_CERTIFICATION",
                "certification_pass": False,
                "symbol": symbol,
                "side": payload.side,
                "quantity": payload.quantity,
                "provider_error": str(exc)[:500],
                "next_action": "Do not bypass provider restrictions. Keep automatic Bybit execution blocked until Spot certification succeeds.",
            },
        ) from exc

    await asyncio.sleep(1.0)
    history = (await client.spot_order_history(20)).get("list", [])
    order = next(
        (
            row for row in history
            if str(row.get("orderLinkId") or "") == link_id
            or str(row.get("orderId") or "") == str(placed.get("orderId") or "")
        ),
        None,
    )
    wallet_after = await client.wallet()
    holdings_after = client.spot_holdings_from_wallet(wallet_after)
    after_qty = next((float(x.get("quantity") or 0) for x in holdings_after if x.get("coin") == base_coin), 0.0)
    balance_changed = after_qty > before_qty if side == "Buy" else after_qty < before_qty
    order_filled = bool(order) and str(order.get("orderStatus") or "").lower() in {"filled", "partiallyfilled"}
    certification_pass = bool(order_filled and balance_changed)

    return {
        "provider": "BYBIT",
        "product": "SPOT",
        "environment": profile.environment,
        "purpose": "CONTROLLED_SPOT_SIMULATION_CERTIFICATION",
        "certification_pass": certification_pass,
        "symbol": symbol,
        "side": payload.side,
        "quantity": payload.quantity,
        "order_link_id": link_id,
        "placed": placed,
        "order": order,
        "base_coin": base_coin,
        "base_quantity_before": before_qty,
        "base_quantity_after": after_qty,
        "balance_changed": balance_changed,
        "execution_status": "CERTIFICATION_PROBE_PASSED" if certification_pass else "BLOCKED_PENDING_CERTIFICATION",
        "next_action": "Keep automatic Bybit execution blocked. Verify the Spot fill and add a controlled Spot close/reversal certification before enabling automation.",
    }
