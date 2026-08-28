from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.brokers.bybit_private import BybitPrivateClient
from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.session import get_db

router = APIRouter(tags=["performance", "trade-history"])


def _f(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _accounts(db: Session, user: User):
    q = select(BrokerProfile).where(
        BrokerProfile.provider.in_(["BYBIT", "MT5", "IBKR"]),
        BrokerProfile.is_enabled.is_(True),
    )
    if user.role != "ADMIN":
        q = q.where(BrokerProfile.user_id == user.id)
    return list(db.scalars(q).all())


def _creds(profile):
    if not profile.credential_blob_encrypted:
        raise RuntimeError(f"{profile.provider} bridge configuration missing")
    return json.loads(decrypt_secret(profile.credential_blob_encrypted))


def _mt5(profile):
    c = _creds(profile)
    return Mt5BridgeClient(c.get("bridge_url") or "http://host.docker.internal:8765", c.get("bridge_token"), get_settings().market_data_timeout_seconds)


def _ibkr(profile):
    c = _creds(profile)
    return IbkrBridgeClient(c.get("bridge_url") or "http://host.docker.internal:8766", c.get("bridge_token"), get_settings().market_data_timeout_seconds)


def _bybit(profile):
    s = get_settings()
    base = s.bybit_public_base_url if profile.environment == "LIVE" else s.bybit_demo_base_url if profile.environment == "DEMO" else s.bybit_testnet_base_url
    return BybitPrivateClient(decrypt_secret(profile.api_key_encrypted or ""), decrypt_secret(profile.api_secret_encrypted or ""), base, s.market_data_timeout_seconds)


def _mt5_market(symbol: str):
    s = str(symbol or "").upper().replace("/", "")
    if s.startswith(("XAU", "XAG", "XPT", "XPD")):
        return "METAL"
    if any(x in s for x in ("USOIL", "UKOIL", "WTI", "BRENT", "XTI", "XBR", "NATGAS", "NGAS")):
        return "COMMODITY"
    return "FX"


def _aggregate_mt5(profile, deals):
    groups = defaultdict(list)
    for d in deals:
        if not d.get("symbol"):
            continue
        key = str(d.get("position_id") or d.get("position") or d.get("order") or d.get("ticket") or "")
        if not key:
            continue
        groups[key].append(d)
    rows = []
    for position_id, items in groups.items():
        items.sort(key=lambda x: int(x.get("time_msc") or int(x.get("time", 0)) * 1000))
        exits = [x for x in items if int(x.get("entry", 0)) in (1, 2, 3)]
        if not exits:
            continue
        first, last = items[0], items[-1]
        symbol = str(first.get("symbol") or last.get("symbol") or "").upper()
        commission = sum(_f(x.get("commission")) for x in items)
        swap = sum(_f(x.get("swap")) for x in items)
        fee = sum(_f(x.get("fee")) for x in items)
        gross = sum(_f(x.get("profit")) for x in items)
        net = gross + commission + swap + fee
        open_items = [x for x in items if int(x.get("entry", 0)) == 0]
        opener = open_items[0] if open_items else first
        closer = exits[-1]
        rows.append({
            "profile_id": str(profile.id), "account": profile.account_label, "provider": "MT5",
            "environment": profile.environment, "market": _mt5_market(symbol), "symbol": symbol,
            "position_id": position_id, "side": "BUY" if int(opener.get("type", 0)) == 0 else "SELL",
            "quantity": max((_f(x.get("volume")) for x in items), default=0),
            "entry_price": _f(opener.get("price")), "exit_price": _f(closer.get("price")),
            "gross_pnl": round(gross, 8), "commission": round(commission, 8), "swap": round(swap, 8),
            "fee": round(fee, 8), "realized_pnl": round(net, 8), "pnl_available": True,
            "opened_at": int(opener.get("time_msc") or int(opener.get("time", 0)) * 1000),
            "closed_at": int(closer.get("time_msc") or int(closer.get("time", 0)) * 1000),
            "status": "CLOSED",
        })
    return rows


@router.get("/performance/unified")
async def unified_performance(days: int = Query(default=30, ge=1, le=366), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trades, errors, accounts = [], [], []
    for p in _accounts(db, user):
        if not p.credentials_configured:
            continue
        try:
            if p.provider == "MT5":
                c = _mt5(p); a = await c.account(); hist = await c.history_deals(days)
                trades.extend(_aggregate_mt5(p, hist.get("list", [])))
                equity, available = _f(a.get("equity")), _f(a.get("margin_free"))
            elif p.provider == "BYBIT":
                c = _bybit(p); w = await c.wallet(); hist = await c.closed_pnl(100); a = (w.get("list") or [{}])[0]
                equity, available = _f(a.get("totalEquity")), _f(a.get("totalAvailableBalance"))
                for x in hist.get("list", []):
                    trades.append({"profile_id": str(p.id), "account": p.account_label, "provider": "BYBIT", "environment": p.environment, "market": "CRYPTO", "symbol": x.get("symbol"), "position_id": x.get("orderId") or x.get("execId"), "side": x.get("side"), "quantity": _f(x.get("qty")), "entry_price": _f(x.get("avgEntryPrice")), "exit_price": _f(x.get("avgExitPrice")), "gross_pnl": _f(x.get("closedPnl")), "commission": 0, "swap": 0, "fee": 0, "realized_pnl": _f(x.get("closedPnl")), "pnl_available": True, "opened_at": int(x.get("createdTime") or 0), "closed_at": int(x.get("updatedTime") or x.get("createdTime") or 0), "status": "CLOSED"})
            else:
                c = _ibkr(p); a = await c.account(); hist = await c.executions(days)
                equity, available = _f(a.get("equity")), _f(a.get("available"))
                for x in hist.get("list", []):
                    trades.append({"profile_id": str(p.id), "account": p.account_label, "provider": "IBKR", "environment": p.environment, "market": "STOCK", "symbol": str(x.get("symbol") or "").upper(), "position_id": x.get("exec_id") or x.get("order_id"), "side": x.get("side"), "quantity": _f(x.get("quantity")), "entry_price": None, "exit_price": _f(x.get("price")), "gross_pnl": None, "commission": None, "swap": None, "fee": None, "realized_pnl": None, "pnl_available": False, "opened_at": 0, "closed_at": 0, "status": "EXECUTION_RECORDED"})
            accounts.append({"profile_id": str(p.id), "account": p.account_label, "provider": p.provider, "environment": p.environment, "equity": equity, "available": available})
        except Exception as exc:
            errors.append({"profile_id": str(p.id), "account": p.account_label, "provider": p.provider, "error": str(exc)[:300]})
    trades.sort(key=lambda x: x.get("closed_at") or 0, reverse=True)
    qualified = [x for x in trades if x.get("pnl_available")]
    realized = sum(_f(x.get("realized_pnl")) for x in qualified)
    wins = sum(1 for x in qualified if _f(x.get("realized_pnl")) > 0)
    daily = defaultdict(float)
    for x in qualified:
        if x.get("closed_at"):
            day = datetime.fromtimestamp(x["closed_at"] / 1000, tz=timezone.utc).date().isoformat()
            daily[day] += _f(x.get("realized_pnl"))
    return {"days": days, "summary": {"equity": round(sum(x["equity"] for x in accounts), 2), "realized_pnl": round(realized, 2), "closed_trades": len(qualified), "executions": len(trades), "wins": wins, "losses": sum(1 for x in qualified if _f(x.get("realized_pnl")) < 0), "win_rate": round(wins / len(qualified) * 100, 2) if qualified else 0}, "accounts": accounts, "daily": [{"date": d, "realized_pnl": round(v, 2)} for d, v in sorted(daily.items())], "trades": trades[:500], "errors": errors, "notes": {"MT5": "Closed positions are aggregated by position_id; realized P&L includes profit, commission, swap and fee.", "IBKR": "Executions are shown, but realized P&L remains unavailable until broker commission/P&L pairing is implemented.", "BYBIT": "Execution may remain provider-blocked until Bybit certification succeeds."}}
