"""Recover broker-confirmed fills from durable ATLAS audits; never estimate net P&L."""
import json
import math


def saved_fill(action, profile, account_id=None):
    if (action.provider != "IBKR" or action.status not in {"EXECUTED", "EXIT_EXECUTED"}
            or action.broker_profile_id != profile.id or action.user_id != profile.user_id
            or action.environment != profile.environment or not action.broker_order_id):
        return None
    try:
        raw = json.loads(action.raw_json or "{}")
        broker = raw.get("result", {}).get("broker_result", {})
        response = broker.get("final_status", {})
        status = response.get("status", {})
        quantity = float(status.get("filled", 0))
        price = float(status.get("avg_fill_price", 0))
        expected = float(action.quantity or 0)
        order_id = str(action.broker_order_id)
        if (str(response.get("order_id")) != order_id
                or str(status.get("order_id")) != order_id
                or str(status.get("status", "")).upper() != "FILLED"
                or not all(math.isfinite(v) and v > 0 for v in (quantity, price, expected))
                or not math.isclose(quantity, expected, rel_tol=0, abs_tol=1e-8)
                or float(status.get("remaining", -1)) != 0
                or action.side not in {"BUY", "SELL"}):
            return None
        if broker.get("account_id") not in (None, "", account_id):
            return None
        return {
            "profile_id": str(profile.id), "account": profile.account_label,
            "provider": "IBKR", "market": action.market or "STOCK",
            "symbol": action.symbol, "side": action.side, "quantity": quantity,
            "execution_price": price, "broker_order_id": order_id,
            "time": int(action.created_at.timestamp() * 1000),
            "time_source": "ATLAS_ACTION_RECORDED_AT",
            "execution_source": "PERSISTED_BROKER_FILL_STATUS",
            "commission": None, "pnl": None, "pnl_available": False,
            "closed_trade": action.status == "EXIT_EXECUTED",
            "pnl_status": "BROKER_PNL_PENDING",
        }
    except (ValueError, TypeError, AttributeError, KeyError):
        return None


def merge_saved_fills(rows, actions, profile, account_id=None):
    """Live execution IDs win; never add an order aggregate beside its live fills."""
    existing = {str(row.get("broker_order_id")) for row in rows
                if str(row.get("profile_id")) == str(profile.id)}
    for action in actions:
        saved = saved_fill(action, profile, account_id)
        if saved is None:
            continue
        if saved["broker_order_id"] in existing:
            if saved["closed_trade"]:
                for row in rows:
                    if (str(row.get("profile_id")) == str(profile.id)
                            and str(row.get("broker_order_id")) == saved["broker_order_id"]):
                        row["closed_trade"] = True
            continue
        rows.append(saved)
        existing.add(saved["broker_order_id"])
    return rows
