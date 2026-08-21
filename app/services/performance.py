from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Iterable


def _closed(rows: Iterable[dict]) -> list[dict]:
    return [r for r in rows if r.get("realized_pnl") is not None]


def _pnl_since(rows: list[dict], since: datetime) -> float:
    return sum(float(r["realized_pnl"]) for r in rows if r.get("created_at") and r["created_at"] >= since)


def performance_summary(rows: Iterable[dict], starting_balance: float) -> dict:
    trades = sorted(_closed(rows), key=lambda r: r["created_at"])
    now = datetime.now(timezone.utc)
    pnls = [float(r["realized_pnl"]) for r in trades]
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss else None
    win_rate = (len(wins) / len(pnls) * 100.0) if pnls else 0.0

    equity = starting_balance
    peak = starting_balance
    max_drawdown = 0.0
    curve = []
    for row in trades:
        equity += float(row["realized_pnl"])
        peak = max(peak, equity)
        drawdown_pct = ((peak - equity) / peak * 100.0) if peak else 0.0
        max_drawdown = max(max_drawdown, drawdown_pct)
        curve.append({"timestamp": row["created_at"], "equity": equity, "drawdown_pct": drawdown_pct})

    by_symbol = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0.0})
    for row in trades:
        item = by_symbol[str(row.get("symbol", "UNKNOWN"))]
        pnl = float(row["realized_pnl"])
        item["trades"] += 1
        item["wins"] += int(pnl > 0)
        item["pnl"] += pnl

    symbols = [
        {"symbol": symbol, "trades": item["trades"], "win_rate": (item["wins"] / item["trades"] * 100.0 if item["trades"] else 0.0), "realized_pnl": item["pnl"]}
        for symbol, item in sorted(by_symbol.items(), key=lambda kv: kv[1]["pnl"], reverse=True)
    ]

    return {
        "closed_trades": len(pnls),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_drawdown,
        "total_realized_pnl": sum(pnls),
        "daily_pnl": _pnl_since(trades, now - timedelta(days=1)),
        "weekly_pnl": _pnl_since(trades, now - timedelta(days=7)),
        "monthly_pnl": _pnl_since(trades, now - timedelta(days=30)),
        "equity_curve": curve,
        "by_symbol": symbols,
    }
