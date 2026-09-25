from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt
from statistics import mean, pstdev

from app.analysis.strategy_intelligence import scenario_from_candles


@dataclass(frozen=True)
class ShadowDecision:
    action: str
    confidence: float
    regime: str
    confirmations: int
    contradictions: int
    threshold: float
    reasons: list[str]
    executable: bool = False
    mode: str = "SHADOW"


SYMBOL_CALIBRATION = {
    "SPY": {"threshold": 68.0, "min_confirmations": 2},
    "QQQ": {"threshold": 69.0, "min_confirmations": 2},
    "AAPL": {"threshold": 70.0, "min_confirmations": 2},
    "MSFT": {"threshold": 70.0, "min_confirmations": 2},
    "NVDA": {"threshold": 73.0, "min_confirmations": 3},
    "TSLA": {"threshold": 75.0, "min_confirmations": 3},
}


def _closes(candles: list[dict]) -> list[float]:
    return [float(row["close"]) for row in candles]


def detect_regime(candles: list[dict]) -> dict:
    if len(candles) < 30:
        return {"name": "INSUFFICIENT_DATA", "volatility_pct": 0.0, "trend_pct": 0.0}
    closes = _closes(candles[-60:])
    returns = [(closes[i] / closes[i - 1] - 1.0) * 100 for i in range(1, len(closes)) if closes[i - 1]]
    volatility = pstdev(returns) if len(returns) > 1 else 0.0
    fast = mean(closes[-10:])
    slow = mean(closes[-30:])
    trend = ((fast / slow) - 1.0) * 100 if slow else 0.0
    if volatility >= 1.8:
        name = "HIGH_VOLATILITY"
    elif abs(trend) >= max(0.45, volatility * 0.9):
        name = "TRENDING_UP" if trend > 0 else "TRENDING_DOWN"
    elif volatility <= 0.25:
        name = "LOW_VOLATILITY"
    else:
        name = "RANGING"
    return {"name": name, "volatility_pct": round(volatility, 4), "trend_pct": round(trend, 4)}


def _direction(value: object) -> str:
    value = str(value or "").upper()
    return "BUY" if value in {"BUY", "LONG", "BULLISH", "TRENDING_UP"} else "SELL" if value in {"SELL", "SHORT", "BEARISH", "TRENDING_DOWN"} else "HOLD"


def evaluate_shadow_strategy(
    candles: list[dict],
    *,
    symbol: str,
    market: str,
    timeframe: str,
    higher_timeframes: list[dict] | None = None,
    news_score: float | None = None,
    vision_observation: dict | None = None,
) -> dict:
    if len(candles) < 30:
        raise ValueError("at least 30 normalized OHLC candles are required")
    symbol = symbol.upper().replace("/", "")
    scenario = scenario_from_candles(candles, timeframe=timeframe, market=market)
    regime = detect_regime(candles)
    calibration = SYMBOL_CALIBRATION.get(symbol, {"threshold": 70.0, "min_confirmations": 2})
    base_action = _direction(scenario.get("action"))
    base_confidence = float(scenario.get("confidence") or 0.0)
    confirmations = 1 if base_action in {"BUY", "SELL"} else 0
    contradictions = 0
    reasons = [f"base_{base_action.lower()}", f"regime_{regime['name'].lower()}"]

    regime_direction = _direction(regime["name"])
    if base_action in {"BUY", "SELL"} and regime_direction == base_action:
        confirmations += 1
        base_confidence += 4.0
        reasons.append("regime_confirmation")
    elif regime_direction in {"BUY", "SELL"} and base_action in {"BUY", "SELL"}:
        contradictions += 1
        base_confidence -= 7.0
        reasons.append("regime_contradiction")

    for row in higher_timeframes or []:
        direction = _direction(row.get("action") or row.get("bias") or row.get("trend"))
        if direction == base_action and direction != "HOLD":
            confirmations += 1
            base_confidence += 3.0
            reasons.append(f"higher_timeframe_{direction.lower()}")
        elif direction in {"BUY", "SELL"} and base_action in {"BUY", "SELL"}:
            contradictions += 1
            base_confidence -= 4.0
            reasons.append("higher_timeframe_contradiction")

    if news_score is not None and base_action in {"BUY", "SELL"}:
        news_score = max(-1.0, min(1.0, float(news_score)))
        agreement = news_score > 0.15 if base_action == "BUY" else news_score < -0.15
        disagreement = news_score < -0.15 if base_action == "BUY" else news_score > 0.15
        if agreement:
            confirmations += 1
            base_confidence += min(abs(news_score) * 5.0, 5.0)
            reasons.append("news_confirmation")
        elif disagreement:
            contradictions += 1
            base_confidence -= min(abs(news_score) * 7.0, 7.0)
            reasons.append("news_contradiction")

    # Vision is advisory only. It can add one bounded vote and can never create a trade.
    if vision_observation and base_action in {"BUY", "SELL"}:
        vision_direction = _direction(vision_observation.get("direction"))
        vision_confidence = max(0.0, min(100.0, float(vision_observation.get("confidence") or 0.0)))
        if vision_confidence >= 65 and vision_direction == base_action:
            confirmations += 1
            base_confidence += min((vision_confidence - 60.0) * 0.1, 4.0)
            reasons.append("vision_confirmation")
        elif vision_confidence >= 65 and vision_direction in {"BUY", "SELL"}:
            contradictions += 1
            base_confidence -= min((vision_confidence - 60.0) * 0.15, 6.0)
            reasons.append("vision_contradiction")

    confidence = max(0.0, min(100.0, base_confidence))
    blocked = (
        base_action == "HOLD"
        or confidence < calibration["threshold"]
        or confirmations < calibration["min_confirmations"]
        or contradictions >= confirmations
        or regime["name"] in {"INSUFFICIENT_DATA", "LOW_VOLATILITY"}
    )
    action = "HOLD" if blocked else base_action
    if blocked:
        reasons.append("shadow_gate_blocked")
    decision = ShadowDecision(
        action=action,
        confidence=round(confidence, 2),
        regime=regime["name"],
        confirmations=confirmations,
        contradictions=contradictions,
        threshold=float(calibration["threshold"]),
        reasons=reasons,
    )
    return {
        **asdict(decision),
        "symbol": symbol,
        "market": market.upper(),
        "timeframe": timeframe,
        "base_scenario": scenario,
        "regime_details": regime,
        "calibration": calibration,
        "safety": "Shadow decisions are observational and cannot submit orders.",
    }


def _metrics(outcomes: list[float]) -> dict:
    if not outcomes:
        return {"trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "net_return_pct": 0.0, "avg_return_pct": 0.0, "profit_factor": None, "max_drawdown_pct": 0.0, "sharpe_like": None}
    wins = [x for x in outcomes if x > 0]
    losses = [x for x in outcomes if x <= 0]
    equity = peak = 1.0
    max_drawdown = 0.0
    for value in outcomes:
        equity *= 1.0 + value / 100.0
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, ((peak - equity) / peak) * 100 if peak else 0.0)
    deviation = pstdev(outcomes) if len(outcomes) > 1 else 0.0
    return {
        "trades": len(outcomes),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(outcomes) * 100, 2),
        "net_return_pct": round((equity - 1.0) * 100, 4),
        "avg_return_pct": round(mean(outcomes), 4),
        "profit_factor": round(sum(wins) / abs(sum(losses)), 3) if losses and sum(losses) else None,
        "max_drawdown_pct": round(max_drawdown, 4),
        "sharpe_like": round(mean(outcomes) / deviation * sqrt(len(outcomes)), 3) if deviation else None,
    }


def walk_forward_shadow_backtest(
    candles: list[dict],
    *,
    symbol: str,
    market: str,
    timeframe: str,
    horizon: int = 6,
    warmup: int = 80,
    cost_bps: float = 8.0,
    split_ratio: float = 0.7,
) -> dict:
    if len(candles) < warmup + horizon + 1:
        raise ValueError("insufficient candles for walk-forward shadow backtest")
    split_index = max(warmup + 1, min(len(candles) - horizon, int(len(candles) * split_ratio)))
    training: list[float] = []
    validation: list[float] = []
    for index in range(warmup, len(candles) - horizon):
        decision = evaluate_shadow_strategy(candles[: index + 1], symbol=symbol, market=market, timeframe=timeframe)
        action = decision["action"]
        if action not in {"BUY", "SELL"}:
            continue
        entry = float(candles[index]["close"])
        future = float(candles[index + horizon]["close"])
        raw = ((future / entry) - 1.0) * 100 if entry else 0.0
        signed = raw if action == "BUY" else -raw
        outcome = signed - (max(0.0, cost_bps) / 100.0)
        (training if index < split_index else validation).append(outcome)
    return {
        "mode": "SHADOW",
        "executable": False,
        "symbol": symbol.upper().replace("/", ""),
        "market": market.upper(),
        "timeframe": timeframe,
        "sample_count": len(candles),
        "horizon_bars": horizon,
        "cost_bps_per_round_trip": cost_bps,
        "split_index": split_index,
        "training": _metrics(training),
        "validation": _metrics(validation),
        "promotion": {
            "eligible": False,
            "reason": "OBSERVATION_REQUIRED",
            "requirements": ["30+ validation trades", "positive validation expectancy", "profit factor >= 1.2", "max drawdown <= 10%", "30 days forward paper observation"],
        },
    }
