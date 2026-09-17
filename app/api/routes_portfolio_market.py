from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.session import get_db
from app.market_data.bybit import BybitPublicMarketData
import json

router = APIRouter(prefix="/portfolio-market", tags=["portfolio"])


def _profile(db: Session, user: User, profile_id: str) -> BrokerProfile:
    q = select(BrokerProfile).where(BrokerProfile.id == profile_id, BrokerProfile.is_enabled.is_(True))
    if user.role != "ADMIN":
        q = q.where(BrokerProfile.user_id == user.id)
    p = db.scalar(q)
    if not p:
        raise HTTPException(status_code=404, detail="portfolio account not found")
    return p


@router.get("/{profile_id}/{symbol}/candles")
async def portfolio_candles(
    profile_id: str,
    symbol: str,
    timeframe: str = Query("5m"),
    limit: int = Query(120, ge=20, le=300),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p = _profile(db, user, profile_id)
    symbol = symbol.strip().upper().replace("/", "").replace(" ", "")
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol required")
    try:
        if p.provider == "IBKR":
            if not p.credential_blob_encrypted:
                raise RuntimeError("IBKR bridge configuration missing")
            cfg = json.loads(decrypt_secret(p.credential_blob_encrypted))
            client = IbkrBridgeClient(
                cfg.get("bridge_url") or "http://host.docker.internal:8766",
                cfg.get("bridge_token"),
                get_settings().market_data_timeout_seconds,
            )
            raw = await client.candles(symbol, timeframe=timeframe, limit=limit)
            rows = raw.get("list", []) if isinstance(raw, dict) else []
        elif p.provider == "BYBIT":
            s = get_settings()
            client = BybitPublicMarketData(s.bybit_public_base_url, s.market_data_timeout_seconds)
            rows = [x.model_dump() for x in await client.get_candles(symbol=symbol, interval=timeframe, category="linear", limit=limit)]
        else:
            raise HTTPException(status_code=422, detail=f"live chart feed not available for {p.provider}")
        return {"profile_id": str(p.id), "provider": p.provider, "symbol": symbol, "timeframe": timeframe, "candles": rows}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)[:240]) from exc
