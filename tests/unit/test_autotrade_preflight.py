from app.services.autotrade_preflight import _mt5_check_ok
from app.services.autotrade_readiness import _router_blocker


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
