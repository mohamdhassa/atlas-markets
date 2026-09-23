from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brokers.bybit_private import BybitPrivateClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.broker import BrokerProfile
from app.db.models.bybit_inventory import BybitManagedInventory

BYBIT_SIMULATION_ENVIRONMENTS = {"TESTNET", "DEMO"}
BYBIT_FILL_VERIFY_ATTEMPTS = 6
BYBIT_FILL_VERIFY_DELAY_SECONDS = 1.0
BYBIT_FILLED_STATUSES = {"FILLED", "PARTIALLYFILLED"}


def _canonical_symbol(value: str) -> str:
    return str(value or "").strip().upper().replace("/", "").replace(" ", "")


def _bybit_client(profile: BrokerProfile) -> BybitPrivateClient:
    settings = get_settings()
    environment = str(profile.environment or "").upper()
    if environment == "TESTNET":
        base_url = settings.bybit_testnet_base_url
    elif environment == "DEMO":
        base_url = settings.bybit_demo_base_url
    else:
        raise RuntimeError("BYBIT_SIMULATION_ENVIRONMENT_REQUIRED")
    if not profile.api_key_encrypted or not profile.api_secret_encrypted:
        raise RuntimeError("BYBIT_CREDENTIALS_MISSING")
    return BybitPrivateClient(
        decrypt_secret(profile.api_key_encrypted),
        decrypt_secret(profile.api_secret_encrypted),
        base_url,
        settings.market_data_timeout_seconds,
    )


def managed_inventory(db: Session, profile_id: uuid.UUID, symbol: str) -> BybitManagedInventory | None:
    return db.scalar(
        select(BybitManagedInventory).where(
            BybitManagedInventory.broker_profile_id == profile_id,
            BybitManagedInventory.symbol == _canonical_symbol(symbol),
        )
    )


def apply_managed_fill(inventory: BybitManagedInventory, *, side: str, quantity: float, price: float | None) -> None:
    side = str(side or "").upper()
    quantity = float(quantity or 0)
    if side not in {"BUY", "SELL"} or quantity <= 0:
        raise ValueError("INVALID_MANAGED_FILL")

    current = float(inventory.managed_quantity or 0)
    if side == "BUY":
        old_cost = current * float(inventory.average_entry_price or 0)
        new_quantity = current + quantity
        fill_price = float(price or 0)
        inventory.managed_quantity = new_quantity
        inventory.cumulative_bought_quantity = float(inventory.cumulative_bought_quantity or 0) + quantity
        if fill_price > 0:
            inventory.average_entry_price = (old_cost + quantity * fill_price) / new_quantity
    else:
        if quantity > current + 1e-12:
            raise ValueError("SELL_EXCEEDS_ATLAS_MANAGED_INVENTORY")
        inventory.managed_quantity = max(0.0, current - quantity)
        inventory.cumulative_sold_quantity = float(inventory.cumulative_sold_quantity or 0) + quantity
        if inventory.managed_quantity <= 1e-12:
            inventory.managed_quantity = 0.0
            inventory.average_entry_price = None


def _matching_history_row(history: list[dict], order_link_id: str) -> dict | None:
    for row in history:
        if str(row.get("orderLinkId") or "") != order_link_id:
            continue
        if str(row.get("orderStatus") or "").upper() in BYBIT_FILLED_STATUSES:
            return row
    return None


async def _verify_spot_fill(client: BybitPrivateClient, order_link_id: str) -> dict | None:
    for attempt in range(BYBIT_FILL_VERIFY_ATTEMPTS):
        if attempt:
            await asyncio.sleep(BYBIT_FILL_VERIFY_DELAY_SECONDS)
        history = (await client.spot_order_history(100)).get("list") or []
        row = _matching_history_row(history, order_link_id)
        if row is not None:
            return row
    return None


def _fill_quantity(row: dict, fallback: float) -> float:
    for key in ("cumExecQty", "execQty", "qty"):
        try:
            value = float(row.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    return float(fallback)


def _fill_price(row: dict) -> float | None:
    for key in ("avgPrice", "price"):
        try:
            value = float(row.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    return None


def _base_coin(symbol: str) -> str:
    symbol = _canonical_symbol(symbol)
    for quote in ("USDT", "USDC", "USD"):
        if symbol.endswith(quote) and len(symbol) > len(quote):
            return symbol[:-len(quote)]
    raise ValueError(f"UNSUPPORTED_SPOT_QUOTE:{symbol}")


def _wallet_coin_quantity(wallet: dict, coin: str) -> float:
    rows = wallet.get("list") or []
    coins = (rows[0].get("coin") or []) if rows else []
    for row in coins:
        if str(row.get("coin") or "").upper() == str(coin or "").upper():
            try:
                return max(0.0, float(row.get("walletBalance") or 0))
            except (TypeError, ValueError):
                return 0.0
    return 0.0


async def execute_managed_spot_order(
    db: Session,
    *,
    profile: BrokerProfile,
    user_id: uuid.UUID,
    symbol: str,
    side: str,
    quantity: float,
) -> dict:
    symbol = _canonical_symbol(symbol)
    side = str(side or "").upper()
    quantity = float(quantity or 0)
    environment = str(profile.environment or "").upper()

    base = {
        "provider": "BYBIT",
        "environment": environment,
        "product": "SPOT",
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "sizing_policy": "ATLAS_MANAGED_SPOT_INVENTORY",
    }

    if environment not in BYBIT_SIMULATION_ENVIRONMENTS:
        return {**base, "status": "BLOCK", "reason": "BYBIT_TESTNET_OR_DEMO_REQUIRED"}
    if not profile.execution_certified or not profile.execution_certification_buy_passed or not profile.execution_certification_sell_passed:
        return {**base, "status": "BLOCK", "reason": "BYBIT_SPOT_CERTIFICATION_REQUIRED"}
    if not (profile.is_enabled and profile.is_active and profile.credentials_configured and profile.last_connection_status == "CONNECTED"):
        return {**base, "status": "BLOCK", "reason": "ROUTE_NOT_READY"}
    if side not in {"BUY", "SELL"} or quantity <= 0:
        return {**base, "status": "BLOCK", "reason": "INVALID_ORDER_PROPOSAL"}

    inventory = managed_inventory(db, profile.id, symbol)
    managed_before = float(inventory.managed_quantity or 0) if inventory else 0.0
    if side == "BUY" and managed_before > 1e-12:
        return {**base, "status": "BLOCK", "reason": "ATLAS_MANAGED_POSITION_ALREADY_OPEN", "managed_quantity": managed_before}
    if side == "SELL" and (inventory is None or managed_before <= 1e-12):
        return {**base, "status": "BLOCK", "reason": "NO_ATLAS_MANAGED_INVENTORY", "managed_quantity": managed_before}
    if side == "SELL" and quantity > managed_before + 1e-12:
        return {**base, "status": "BLOCK", "reason": "SELL_EXCEEDS_ATLAS_MANAGED_INVENTORY", "managed_quantity": managed_before}

    client = _bybit_client(profile)
    reconciliation = None
    if side == "SELL":
        wallet = await client.wallet()
        broker_quantity = _wallet_coin_quantity(wallet, _base_coin(symbol))
        if broker_quantity <= 1e-12:
            inventory.managed_quantity = 0.0
            inventory.average_entry_price = None
            db.flush()
            return {
                **base,
                "status": "BLOCK",
                "reason": "BROKER_SPOT_BALANCE_EMPTY_RECONCILED",
                "managed_quantity_before": managed_before,
                "managed_quantity_after": 0.0,
                "broker_quantity": broker_quantity,
            }
        if broker_quantity + 1e-12 < managed_before:
            inventory.managed_quantity = broker_quantity
            managed_before = broker_quantity
            db.flush()
            reconciliation = "ATLAS_MANAGED_INVENTORY_RECONCILED_TO_BROKER_BALANCE"
        quantity = min(quantity, managed_before, broker_quantity)
        base["quantity"] = quantity
        if quantity <= 1e-12:
            return {
                **base,
                "status": "BLOCK",
                "reason": "NO_SELLABLE_ATLAS_MANAGED_INVENTORY",
                "managed_quantity": managed_before,
                "broker_quantity": broker_quantity,
            }

    order_link_id = f"atlas-auto-{uuid.uuid4().hex[:20]}"
    broker_result = await client.place_test_spot_market_order(
        symbol=symbol,
        side="Buy" if side == "BUY" else "Sell",
        qty=quantity,
        order_link_id=order_link_id,
    )
    fill = await _verify_spot_fill(client, order_link_id)
    if fill is None:
        return {
            **base,
            "status": "SUBMITTED",
            "reason": "BROKER_FILL_NOT_CONFIRMED",
            "order_link_id": order_link_id,
            "broker_result": broker_result,
            "managed_quantity_before": managed_before,
        }

    filled_quantity = _fill_quantity(fill, quantity)
    fill_price = _fill_price(fill)
    if side == "SELL" and filled_quantity > managed_before + 1e-12:
        return {
            **base,
            "status": "BLOCK",
            "reason": "BROKER_FILL_EXCEEDS_ATLAS_MANAGED_INVENTORY",
            "order_link_id": order_link_id,
            "broker_result": broker_result,
        }

    if inventory is None:
        inventory = BybitManagedInventory(
            user_id=user_id,
            broker_profile_id=profile.id,
            symbol=symbol,
            managed_quantity=0.0,
            cumulative_bought_quantity=0.0,
            cumulative_sold_quantity=0.0,
        )
        db.add(inventory)

    apply_managed_fill(inventory, side=side, quantity=filled_quantity, price=fill_price)
    db.flush()

    return {
        **base,
        "status": "EXECUTED",
        "order_link_id": order_link_id,
        "broker_order_id": fill.get("orderId") or broker_result.get("orderId"),
        "filled_quantity": filled_quantity,
        "fill_price": fill_price,
        "managed_quantity_before": managed_before,
        "managed_quantity_after": float(inventory.managed_quantity or 0),
        "reconciliation": reconciliation,
        "broker_result": {**broker_result, "fill": fill},
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }
