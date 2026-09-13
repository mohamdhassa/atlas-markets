from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.routes_accounts import _authorized_profile, _bybit_client
from app.db.models.auth import User
from app.db.models.bybit_inventory import BybitManagedInventory
from app.db.session import get_db

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _certification_evidence(history: list[dict]) -> dict:
    matched = []
    buy = False
    sell = False
    for row in history:
        link_id = str(row.get("orderLinkId") or "")
        status = str(row.get("orderStatus") or "").lower()
        side = str(row.get("side") or "").upper()
        if not link_id.startswith("atlas-spot-cert-"):
            continue
        if status not in {"filled", "partiallyfilled"}:
            continue
        if side == "BUY":
            buy = True
        elif side == "SELL":
            sell = True
        else:
            continue
        matched.append({
            "order_link_id": link_id,
            "order_id": row.get("orderId"),
            "side": side,
            "status": row.get("orderStatus"),
            "symbol": row.get("symbol"),
        })
    return {"buy": buy, "sell": sell, "matched": matched}


def _managed_inventory_payload(db: Session, profile_id: uuid.UUID) -> list[dict]:
    rows = list(db.scalars(
        select(BybitManagedInventory)
        .where(BybitManagedInventory.broker_profile_id == profile_id)
        .order_by(BybitManagedInventory.symbol)
    ).all())
    return [
        {
            "symbol": row.symbol,
            "managed_quantity": float(row.managed_quantity or 0),
            "average_entry_price": row.average_entry_price,
            "cumulative_bought_quantity": float(row.cumulative_bought_quantity or 0),
            "cumulative_sold_quantity": float(row.cumulative_sold_quantity or 0),
            "updated_at": row.updated_at,
        }
        for row in rows
    ]


@router.get("/{profile_id}/bybit-spot-state")
async def bybit_spot_state_persistent(
    profile_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _authorized_profile(db, user, profile_id)
    if profile.provider != "BYBIT":
        raise HTTPException(400, "Bybit profile required")
    try:
        client = _bybit_client(profile)
        wallet = await client.wallet()
        holdings = client.spot_holdings_from_wallet(wallet)
        spot_orders = (await client.spot_open_orders()).get("list") or []
        derivative_positions = (await client.positions()).get("list") or []
        active_derivative_positions = [row for row in derivative_positions if float(row.get("size") or 0) != 0]
        certified = bool(profile.execution_certified)
        simulation_environment = str(profile.environment or "").upper() in {"TESTNET", "DEMO"}
        route_ready = bool(
            certified
            and simulation_environment
            and profile.is_enabled
            and profile.is_active
            and profile.credentials_configured
            and profile.last_connection_status == "CONNECTED"
        )
        managed_inventory = _managed_inventory_payload(db, profile.id)
        return {
            "provider": "BYBIT",
            "environment": profile.environment,
            "product": "SPOT",
            "profile_id": str(profile.id),
            "holdings": holdings,
            "spot_holdings_count": len(holdings),
            "spot_open_orders": spot_orders,
            "spot_open_orders_count": len(spot_orders),
            "derivative_positions_count": len(active_derivative_positions),
            "buy_certified": bool(profile.execution_certification_buy_passed),
            "sell_certified": bool(profile.execution_certification_sell_passed),
            "execution_certified": certified,
            "execution_certified_at": profile.execution_certified_at,
            "execution_status": "CERTIFIED" if certified else "BLOCKED_PENDING_CERTIFICATION",
            "managed_inventory": managed_inventory,
            "managed_inventory_count": sum(1 for row in managed_inventory if row["managed_quantity"] > 1e-12),
            "route_ready": route_ready,
            "automatic_execution_enabled": route_ready,
            "live_money_armed": False,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"BYBIT spot state failed: {str(exc)[:240]}") from exc


@router.post("/{profile_id}/reconcile-bybit-spot-certification")
async def reconcile_bybit_spot_certification(
    profile_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != "ADMIN":
        raise HTTPException(403, "ADMIN role required")
    profile = _authorized_profile(db, user, profile_id)
    if profile.provider != "BYBIT":
        raise HTTPException(400, "Bybit profile required")
    if profile.environment not in {"TESTNET", "DEMO"}:
        raise HTTPException(409, "Bybit certification reconciliation is restricted to TESTNET or DEMO")
    try:
        client = _bybit_client(profile)
        history = (await client.spot_order_history(100)).get("list") or []
        evidence = _certification_evidence(history)
        if not evidence["matched"]:
            raise HTTPException(409, "No filled ATLAS Spot certification orders were found in Bybit history")

        profile.execution_certification_buy_passed = bool(evidence["buy"])
        profile.execution_certification_sell_passed = bool(evidence["sell"])
        profile.execution_certified = bool(evidence["buy"] and evidence["sell"])
        profile.execution_certified_at = datetime.now(timezone.utc) if profile.execution_certified else None
        db.commit()
        db.refresh(profile)

        return {
            "provider": "BYBIT",
            "environment": profile.environment,
            "profile_id": str(profile.id),
            "buy_certified": bool(profile.execution_certification_buy_passed),
            "sell_certified": bool(profile.execution_certification_sell_passed),
            "execution_certified": bool(profile.execution_certified),
            "execution_certified_at": profile.execution_certified_at,
            "execution_status": "CERTIFIED" if profile.execution_certified else "BLOCKED_PENDING_CERTIFICATION",
            "matched_certification_orders": evidence["matched"],
            "automatic_execution_enabled": False,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"BYBIT certification reconciliation failed: {str(exc)[:240]}") from exc
