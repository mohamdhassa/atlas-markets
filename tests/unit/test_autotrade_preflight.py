from app.services.autotrade_preflight import _mt5_check_ok
from types import SimpleNamespace

from app.services.autotrade_readiness import _ibkr_connection_verdict, _router_blocker


def test_mt5_preflight_accepts_success_retcode_zero():
    assert _mt5_check_ok({'result': {'retcode': 0}}) is True


def test_mt5_preflight_accepts_done_retcode():
    assert _mt5_check_ok({'result': {'retcode': 10009}}) is True


def test_mt5_preflight_rejects_missing_or_failed_retcode():
    assert _mt5_check_ok({'result': {'retcode': 10030}}) is False
    assert _mt5_check_ok({'result': {}}) is False


def test_router_no_trade_blocks_simulation_order():
    assert _router_blocker({"strategy": "NO_TRADE", "regime": "LOW_VOLATILITY"}, "BUY") == "STRATEGY_ROUTER_NO_TRADE"


def test_router_requires_signal_to_agree_with_trend():
    route = {"strategy": "trend", "regime": "TRENDING_UP"}
    assert _router_blocker(route, "SELL") == "STRATEGY_ROUTER_DIRECTION_CONFLICT"
    assert _router_blocker(route, "BUY") is None


def test_darvas_breakout_direction_gates_order():
    route = {"strategy": "darvas_box", "regime": "BOX_BREAKOUT", "box": {"breakout": "UP"}}
    assert _router_blocker(route, "SELL") == "STRATEGY_ROUTER_DIRECTION_CONFLICT"
    assert _router_blocker(route, "BUY") is None


def test_ibkr_stale_profile_can_only_recover_after_account_verification():
    profile = SimpleNamespace(environment="PAPER", external_account_ref="DU123")
    credentials = {"account_id": "DU123"}
    assert _ibkr_connection_verdict(profile, credentials, {"connected": True, "simulation": True}, {"account_id": "DU123", "simulation": True}) == (True, "CONNECTED")
    assert _ibkr_connection_verdict(profile, credentials, {"connected": True, "simulation": True}, {"account_id": "DU999", "simulation": True}) == (False, "IBKR_ACCOUNT_MISMATCH")
    assert _ibkr_connection_verdict(profile, credentials, {"connected": True, "simulation": False}, {"account_id": "DU123", "simulation": False}) == (False, "IBKR_PAPER_SESSION_REQUIRED")
    assert _ibkr_connection_verdict(profile, credentials, {"connected": False}, {}) == (False, "IBKR_BRIDGE_DISCONNECTED")
