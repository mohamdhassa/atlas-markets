from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean, pstdev


@dataclass(frozen=True)
class StrategyRoute:
    regime: str
    strategy: str
    confidence: float
    eligible: tuple[str, ...]
    reasons: tuple[str, ...]
    executable: bool = False
    mode: str = "SHADOW"


def _series(candles: list[dict], key: str) -> list[float]:
    return [float(row[key]) for row in candles]


def darvas_box(candles: list[dict], *, lookback: int = 20, breakout_buffer_pct: float = 0.1) -> dict:
    """Describe the completed box before the latest candle; never submits a trade."""
    if len(candles) < lookback + 1:
        return {"valid": False, "reason": "INSUFFICIENT_DATA", "breakout": "NONE"}
    box = candles[-(lookback + 1) : -1]
    latest = candles[-1]
    top = max(_series(box, "high"))
    bottom = min(_series(box, "low"))
    midpoint = (top + bottom) / 2.0
    width_pct = ((top - bottom) / midpoint * 100.0) if midpoint else 0.0
    close = float(latest["close"])
    upper_trigger = top * (1.0 + max(0.0, breakout_buffer_pct) / 100.0)
    lower_trigger = bottom * (1.0 - max(0.0, breakout_buffer_pct) / 100.0)
    volumes = [float(row.get("volume") or 0.0) for row in box]
    average_volume = mean(volumes) if volumes else 0.0
    latest_volume = float(latest.get("volume") or 0.0)
    volume_ratio = latest_volume / average_volume if average_volume else 0.0
    breakout = "UP" if close > upper_trigger else "DOWN" if close < lower_trigger else "NONE"
    return {
        "valid": width_pct <= 12.0 and top > bottom,
        "reason": "BOX_DETECTED" if width_pct <= 12.0 and top > bottom else "BOX_TOO_WIDE",
        "top": round(top, 8),
        "bottom": round(bottom, 8),
        "width_pct": round(width_pct, 4),
        "breakout": breakout,
        "volume_ratio": round(volume_ratio, 4),
        "volume_confirmed": volume_ratio >= 1.2,
        "lookback": lookback,
    }


def route_strategy(
    candles: list[dict],
    *,
    news_score: float | None = None,
    minimum_confidence: float = 60.0,
) -> dict:
    """Route current market structure to an eligible strategy in shadow mode."""
    if len(candles) < 31:
        route = StrategyRoute("INSUFFICIENT_DATA", "NO_TRADE", 0.0, (), ("needs_31_candles",))
        return {**asdict(route), "box": darvas_box(candles)}

    closes = _series(candles[-60:], "close")
    returns = [(closes[i] / closes[i - 1] - 1.0) * 100.0 for i in range(1, len(closes)) if closes[i - 1]]
    volatility = pstdev(returns) if len(returns) > 1 else 0.0
    fast = mean(closes[-10:])
    slow = mean(closes[-30:])
    trend = ((fast / slow) - 1.0) * 100.0 if slow else 0.0
    box = darvas_box(candles)
    reasons: list[str] = []

    if volatility >= 1.8:
        regime, eligible = "HIGH_VOLATILITY", ("news_breakout", "volatility")
        strategy, confidence = "NO_TRADE", 48.0
        reasons.append("high_volatility_requires_extra_confirmation")
    elif abs(trend) >= max(0.45, volatility * 0.9):
        regime, eligible = ("TRENDING_UP" if trend > 0 else "TRENDING_DOWN"), ("trend", "momentum", "pullback")
        strategy, confidence = "trend", min(90.0, 62.0 + abs(trend) * 6.0)
        reasons.append("moving_average_trend")
    elif box.get("valid") and box.get("breakout") in {"UP", "DOWN"} and box.get("volume_confirmed"):
        regime, eligible = "BOX_BREAKOUT", ("darvas_box", "breakout")
        strategy, confidence = "darvas_box", min(92.0, 66.0 + (float(box["volume_ratio"]) - 1.2) * 12.0)
        reasons.extend(("price_closed_outside_box", "breakout_volume_confirmed"))
    elif volatility <= 0.25:
        regime, eligible = "LOW_VOLATILITY", ("darvas_box",)
        strategy, confidence = "NO_TRADE", 45.0
        reasons.append("box_not_broken")
    else:
        regime, eligible = "RANGING", ("mean_reversion", "darvas_box")
        strategy, confidence = "mean_reversion", min(78.0, 61.0 + max(0.0, 0.8 - volatility) * 10.0)
        reasons.append("range_bound_price_action")

    if news_score is not None and abs(float(news_score)) >= 0.75:
        strategy, confidence = "NO_TRADE", min(confidence, 40.0)
        reasons.append("extreme_news_uncertainty")
    if confidence < minimum_confidence:
        strategy = "NO_TRADE"
        reasons.append("router_confidence_below_threshold")

    route = StrategyRoute(regime, strategy, round(confidence, 2), eligible, tuple(reasons))
    return {
        **asdict(route),
        "metrics": {"trend_pct": round(trend, 4), "volatility_pct": round(volatility, 4)},
        "box": box,
        "safety": "Routing is advisory and cannot submit or authorize an order.",
    }
