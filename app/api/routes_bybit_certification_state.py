from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.routes_accounts import _authorized_profile, _bybit_client
from app.db.models.auth import User
from app.db.session import get_db

router = APIRouter(prefix="/accounts", tags=["accounts"])


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
        active_derivative_positions = [
            row for row in derivative_positions if float(row.get("size") or 0) != 0
        ]
        certified = bool(profile.execution_certified)
        return {
            "provider": "BYBIT",
            "environment": profile.environment,
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
            "automatic_execution_enabled": False,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"BYBIT spot state failed: {str(exc)[:240]}") from exc
