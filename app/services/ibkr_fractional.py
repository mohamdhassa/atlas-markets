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


def ibkr_fractional_policy_payload() -> dict:
    return {
        "quantity_mode": "FRACTIONAL_SHARES",
        "minimum_shares": float(IBKR_MIN_FRACTIONAL_SHARES),
        "share_step": float(IBKR_FRACTIONAL_SHARE_STEP),
        "rounding": "DOWN_TO_PRESERVE_RISK_LIMIT",
        "capability_check": "BROKER_NATIVE_WHAT_IF_EACH_ORDER",
        "runtime_flag": "IBKR_FRACTIONAL_API_ENABLED",
    }
