from app.analysis.strategy_router import darvas_box, route_strategy
from app.api.routes_analysis import router


def _candles(closes, *, base_volume=1000.0, final_volume=None):
    rows = []
    for index, close in enumerate(closes):
        volume = final_volume if index == len(closes) - 1 and final_volume is not None else base_volume
        rows.append({"open": close, "high": close + 0.4, "low": close - 0.4, "close": close, "volume": volume})
    return rows


def test_darvas_box_uses_completed_bars_and_confirms_volume_breakout():
    rows = _candles([100.0] * 35 + [103.0], final_volume=1800.0)
    box = darvas_box(rows)
    assert box["valid"] is True
    assert box["breakout"] == "UP"
    assert box["volume_confirmed"] is True


def test_router_selects_darvas_only_for_confirmed_box_breakout():
    rows = _candles([100.0] * 35 + [103.0], final_volume=1800.0)
    result = route_strategy(rows)
    assert result["regime"] == "BOX_BREAKOUT"
    assert result["strategy"] == "darvas_box"
    assert result["executable"] is False
    assert result["mode"] == "SHADOW"


def test_router_prefers_trend_strategy_in_sustained_trend():
    result = route_strategy(_candles([100 + index * 0.4 for index in range(60)]))
    assert result["regime"] == "TRENDING_UP"
    assert result["strategy"] == "trend"


def test_router_chooses_no_trade_during_extreme_news_uncertainty():
    result = route_strategy(_candles([100 + index * 0.4 for index in range(60)]), news_score=-0.9)
    assert result["strategy"] == "NO_TRADE"
    assert "extreme_news_uncertainty" in result["reasons"]


def test_unconfirmed_box_does_not_trigger_darvas_entry():
    result = route_strategy(_candles([100.0] * 36))
    assert result["strategy"] == "NO_TRADE"
    assert result["box"]["breakout"] == "NONE"


def test_router_endpoint_is_registered_and_shadow_only():
    routes = {(route.path, frozenset(route.methods or [])) for route in router.routes}
    assert ("/analysis/strategy-router/from-candles", frozenset({"POST"})) in routes
    result = route_strategy(_candles([100.0] * 35 + [103.0], final_volume=1800.0))
    assert result["executable"] is False
    assert "cannot submit" in result["safety"]
