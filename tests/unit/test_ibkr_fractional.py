from app.services.ibkr_fractional import (
    ibkr_fractional_policy_payload,
    ibkr_quantities_match,
    normalize_ibkr_shares,
)


def test_fractional_quantity_rounds_down_without_exceeding_risk_budget():
    assert normalize_ibkr_shares(0.123456) == 0.1234
    assert normalize_ibkr_shares("1.99999") == 1.9999


def test_fractional_quantity_rejects_invalid_and_too_small_values():
    assert normalize_ibkr_shares(0.00009) == 0
    assert normalize_ibkr_shares(0) == 0
    assert normalize_ibkr_shares(-1) == 0
    assert normalize_ibkr_shares("not-a-number") == 0


def test_fractional_reconciliation_uses_numeric_tolerance():
    assert ibkr_quantities_match(0.10000001, 0.1)
    assert not ibkr_quantities_match(0.1002, 0.1)


def test_fractional_policy_requires_broker_native_what_if():
    policy = ibkr_fractional_policy_payload()
    assert policy["quantity_mode"] == "FRACTIONAL_SHARES"
    assert policy["share_step"] == 0.0001
    assert policy["capability_check"] == "BROKER_NATIVE_WHAT_IF_EACH_ORDER"


def test_automation_path_does_not_restore_whole_share_cap():
    safe_automation = open("app/services/safe_automation.py", encoding="utf-8").read()
    readiness = open("app/services/autotrade_readiness.py", encoding="utf-8").read()
    assert "requested = int(" not in safe_automation
    assert "math.floor(plan.quantity)" not in readiness
    assert '"sizing_policy": "RISK_SIZED_FRACTIONAL_SHARES"' in readiness
