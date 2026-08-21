from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaperExecutionPlan:
    side: str
    quantity: float
    notional: float
    stop_loss: float
    take_profit: float
    risk_amount: float


def build_execution_plan(*, decision: str, price: float, equity: float, available_cash: float, risk_per_trade_pct: float, atr: float | None = None) -> PaperExecutionPlan:
    if decision not in {"BUY", "SELL"}:
        raise ValueError("only BUY or SELL signals can be executed")
    if price <= 0 or equity <= 0 or available_cash <= 0:
        raise ValueError("price, equity and available cash must be positive")
    risk_amount = equity * (risk_per_trade_pct / 100.0)
    stop_distance = max((atr or price * 0.01) * 1.5, price * 0.005)
    quantity_by_risk = risk_amount / stop_distance
    max_notional = available_cash * 0.20
    quantity = min(quantity_by_risk, max_notional / price)
    if quantity <= 0:
        raise ValueError("calculated position size is zero")
    if decision == "BUY":
        stop_loss = price - stop_distance
        take_profit = price + (stop_distance * 2.0)
    else:
        stop_loss = price + stop_distance
        take_profit = price - (stop_distance * 2.0)
    return PaperExecutionPlan(decision, round(quantity, 8), round(quantity * price, 8), round(stop_loss, 8), round(take_profit, 8), round(risk_amount, 8))


def position_pnl(*, side: str, quantity: float, entry_price: float, mark_price: float) -> float:
    direction = 1.0 if side == "BUY" else -1.0
    return (mark_price - entry_price) * quantity * direction


def exit_trigger(*, side: str, mark_price: float, stop_loss: float | None, take_profit: float | None) -> str | None:
    if side == "BUY":
        if stop_loss is not None and mark_price <= stop_loss: return "STOP_LOSS"
        if take_profit is not None and mark_price >= take_profit: return "TAKE_PROFIT"
    else:
        if stop_loss is not None and mark_price >= stop_loss: return "STOP_LOSS"
        if take_profit is not None and mark_price <= take_profit: return "TAKE_PROFIT"
    return None
