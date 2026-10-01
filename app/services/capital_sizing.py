from __future__ import annotations


SIMULATION_ENVIRONMENTS = {"PAPER", "DEMO", "TESTNET"}


def capital_sizing_inputs(
    *,
    broker_equity: float,
    broker_available: float,
    environment: str,
    simulation_capital_override_usd: float | None,
) -> tuple[float, float, str]:
    """Return the equity/cash basis used for sizing without capping live growth."""

    equity = max(0.0, float(broker_equity or 0))
    available = max(0.0, min(float(broker_available or 0), equity))
    override = float(simulation_capital_override_usd or 0)
    if str(environment or "").upper() in SIMULATION_ENVIRONMENTS and override > 0:
        equity = min(equity, override)
        available = min(available, equity)
        return equity, available, "SIMULATION_OVERRIDE"
    return equity, available, "BROKER_EQUITY"


def capital_policy_payload(*, simulation_capital_override_usd: float | None) -> dict:
    return {
        "sizing_model": "BROKER_EQUITY_WITH_OPTIONAL_SIMULATION_OVERRIDE",
        "simulation_capital_override_usd": simulation_capital_override_usd,
        "live_uses_broker_equity": True,
        "risk_controls": "RISK_PROFILE_AND_SYMBOL_STRATEGY_PERCENTAGES",
        "live_money_enabled_by_policy": False,
    }
