from app.analysis.adaptive_strategy import select_strategy
from app.analysis.asset_universe import profile_for, universe_summary


def candles(count=80):
    return [
        {"open": 100 + i * 0.2, "high": 101 + i * 0.2, "low": 99 + i * 0.2, "close": 100.5 + i * 0.2, "volume": 1000}
        for i in range(count)
    ]


def test_gold_silver_and_oil_are_in_universe():
    universe = universe_summary()
    assert "XAUUSD" in universe["METALS"]
    assert "XAGUSD" in universe["METALS"]
    assert "WTI" in universe["COMMODITIES"]
    assert "BRENT" in universe["COMMODITIES"]


def test_profiles_are_asset_specific():
    assert "session_momentum" in profile_for("EURUSD").strategy_families
    assert "volatility" in profile_for("WTI").strategy_families
    assert profile_for("XAU/USD").asset_class == "GOLD"


def test_adaptive_strategy_returns_ranked_candidates():
    result = select_strategy(candles(), ("trend", "momentum", "breakout"))
    assert result["selected"]
    assert len(result["candidates"]) == 3
    assert result["candidates"][0]["score"] >= result["candidates"][-1]["score"]
