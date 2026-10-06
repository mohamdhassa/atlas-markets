from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation, ROUND_DOWN


IBKR_FRACTIONAL_SHARE_STEP = Decimal("0.0001")
IBKR_MIN_FRACTIONAL_SHARES = Decimal("0.0001")
IBKR_QUANTITY_TOLERANCE = 0.0000001
IBKR_FRACTIONAL_API_ERROR_CODE = 10243


def normalize_ibkr_shares(value: object) -> float:
    """Return a positive IBKR stock quantity rounded down to 4 decimals.

    Rounding down prevents an order from exceeding the risk-sized notional.
    IBKR's broker-native What-If remains the final capability check.
    """
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return 0.0
    if not quantity.is_finite() or quantity <= 0:
        return 0.0
    normalized = quantity.quantize(IBKR_FRACTIONAL_SHARE_STEP, rounding=ROUND_DOWN)
    if normalized < IBKR_MIN_FRACTIONAL_SHARES:
        return 0.0
    return float(normalized)


def ibkr_quantities_match(left: object, right: object) -> bool:
    try:
        left_value = float(left)
        right_value = float(right)
    except (TypeError, ValueError):
        return False
    return (
        math.isfinite(left_value)
        and math.isfinite(right_value)
        and abs(left_value - right_value) <= IBKR_QUANTITY_TOLERANCE
    )


def ibkr_quantity_is_fractional(value: object) -> bool:
    try:
        quantity = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(quantity) and quantity > 0 and not math.isclose(
        quantity, round(quantity), abs_tol=IBKR_QUANTITY_TOLERANCE
    )


def ibkr_preflight_rejection_reason(result: dict) -> str:
    """Return a stable ATLAS reason for known broker-native failures."""
    for error in result.get("errors") or []:
        try:
            code = int(error.get("code"))
        except (AttributeError, TypeError, ValueError):
            continue
        if code == IBKR_FRACTIONAL_API_ERROR_CODE:
            return "IBKR_FRACTIONAL_API_UNSUPPORTED"
    return "BROKER_PREFLIGHT_REJECTED"


def size_ibkr_entry(value: object, *, fractional_enabled: bool) -> dict:
    """Round an entry down to the certified step; never increase risk-sized shares."""
    quantity = normalize_ibkr_shares(value)
    if not fractional_enabled:
        quantity = float(Decimal(str(quantity)).to_integral_value(rounding=ROUND_DOWN))
    policy = ibkr_fractional_policy_payload(fractional_enabled=fractional_enabled)
    return {"shares": quantity, "quantity": quantity,
            "quantity_mode": policy["quantity_mode"], "share_step": policy["share_step"],
            "sizing_policy": "RISK_SIZED_" + policy["quantity_mode"]}


def ibkr_fractional_policy_payload(*, fractional_enabled: bool | None = None) -> dict:
    if fractional_enabled is None:
        from app.core.config import get_settings
        fractional_enabled = get_settings().ibkr_fractional_api_enabled
    return {
        "quantity_mode": "FRACTIONAL_SHARES" if fractional_enabled else "WHOLE_SHARES",
        "minimum_shares": float(IBKR_MIN_FRACTIONAL_SHARES) if fractional_enabled else 1.0,
        "share_step": float(IBKR_FRACTIONAL_SHARE_STEP) if fractional_enabled else 1.0,
        "rounding": "DOWN_TO_PRESERVE_RISK_LIMIT",
        "capability_check": "BROKER_NATIVE_WHAT_IF_EACH_ORDER",
        "runtime_flag": "IBKR_FRACTIONAL_API_ENABLED",
    }


def ibkr_fill_is_complete(status: dict, expected_quantity: object) -> bool:
    """Require exact finite fill quantity and zero remaining broker quantity."""
    try:
        expected = float(expected_quantity)
        filled = float(status.get("filled"))
        remaining = float(status.get("remaining"))
    except (TypeError, ValueError):
        return False
    return (
        math.isfinite(expected) and expected > 0
        and math.isfinite(filled) and filled > 0
        and math.isfinite(remaining) and remaining >= 0
        and ibkr_quantities_match(filled, expected)
        and ibkr_quantities_match(remaining, 0)
    )
