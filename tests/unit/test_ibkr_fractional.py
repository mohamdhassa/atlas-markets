from app.services.ibkr_fractional import (
    ibkr_fractional_policy_payload,
    ibkr_preflight_rejection_reason,
    ibkr_quantities_match,
    ibkr_quantity_is_fractional,
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
    policy = ibkr_fractional_policy_payload(fractional_enabled=True)
    assert policy["quantity_mode"] == "FRACTIONAL_SHARES"
    assert policy["share_step"] == 0.0001
    assert policy["capability_check"] == "BROKER_NATIVE_WHAT_IF_EACH_ORDER"
    assert policy["runtime_flag"] == "IBKR_FRACTIONAL_API_ENABLED"


def test_fractional_quantity_detection_preserves_whole_share_orders():
    assert ibkr_quantity_is_fractional(0.0386)
    assert ibkr_quantity_is_fractional(1.5)
    assert not ibkr_quantity_is_fractional(1)
    assert not ibkr_quantity_is_fractional(2.0)


def test_ibkr_error_10243_has_precise_reason():
    rejected = {"errors": [{"code": 10243, "message": "Fractional-sized order cannot be placed via API."}]}
    assert ibkr_preflight_rejection_reason(rejected) == "IBKR_FRACTIONAL_API_UNSUPPORTED"
    assert ibkr_preflight_rejection_reason({"errors": [{"code": 201}]}) == "BROKER_PREFLIGHT_REJECTED"


def test_entry_sizing_uses_certified_step_without_rounding_up():
    from app.services.ibkr_fractional import size_ibkr_entry
    for value, whole in [(12.7, 12), (1.99999, 1), (1, 1), (0.9999, 0), (0.0386, 0)]:
        result = size_ibkr_entry(value, fractional_enabled=False)
        assert result["shares"] == whole
        assert result["shares"] <= value
        assert result["sizing_policy"] == "RISK_SIZED_WHOLE_SHARES"
        assert result["share_step"] == 1
    assert size_ibkr_entry(12.76549, fractional_enabled=True)["shares"] == 12.7654
    for value in ["nan", "inf", -1, "invalid", None]:
        assert size_ibkr_entry(value, fractional_enabled=False)["shares"] == 0


def test_disabled_fractional_policy_reports_whole_share_minimum():
    policy = ibkr_fractional_policy_payload(fractional_enabled=False)
    assert policy["quantity_mode"] == "WHOLE_SHARES"
    assert policy["minimum_shares"] == policy["share_step"] == 1
    assert policy["capability_check"] == "BROKER_NATIVE_WHAT_IF_EACH_ORDER"
