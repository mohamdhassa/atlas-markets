from __future__ import annotations

import json
from dataclasses import dataclass

from app.analysis.technical import analyze_candles


@dataclass(frozen=True)
class GeneratedSignal:
    decision: str
    classification: str
    score: float
    reasons: list[str]


def generate_signal(candles: list[dict]) -> GeneratedSignal:
    analysis = analyze_candles(candles)
    score = float(analysis.get("signal_score", 0.0))
    bias = str(analysis.get("bias", "NEUTRAL")).upper()

    if bias == "BULLISH":
        decision = "LONG"
    elif bias == "BEARISH":
        decision = "SHORT"
    else:
        decision = "HOLD"

    abs_score = abs(score)
    if abs_score >= 80:
        classification = "STRONG_SIGNAL"
    elif abs_score >= 65:
        classification = "SIGNAL"
    elif abs_score >= 45:
        classification = "WATCH"
    else:
        classification = "NO_SIGNAL"

    reasons: list[str] = []
    trend = analysis.get("trend_regime")
    volatility = analysis.get("volatility_regime")
    structure = analysis.get("market_structure")
    rsi = analysis.get("rsi")
    macd = analysis.get("macd") or {}

    if trend:
        reasons.append(f"trend_{str(trend).lower()}")
    if volatility:
        reasons.append(f"volatility_{str(volatility).lower()}")
    if structure:
        reasons.append(f"structure_{str(structure).lower()}")
    if isinstance(rsi, (int, float)):
        if rsi >= 70:
            reasons.append("rsi_overbought")
        elif rsi <= 30:
            reasons.append("rsi_oversold")
        else:
            reasons.append("rsi_neutral")
    histogram = macd.get("histogram") if isinstance(macd, dict) else None
    if isinstance(histogram, (int, float)):
        reasons.append("macd_positive" if histogram > 0 else "macd_negative" if histogram < 0 else "macd_flat")

    return GeneratedSignal(
        decision=decision,
        classification=classification,
        score=score,
        reasons=reasons,
    )


def evaluate_risk(
    signal: GeneratedSignal,
    *,
    minimum_signal_score: float,
    account_enabled: bool,
    allow_live_trading: bool,
    account_environment: str,
) -> tuple[bool, str, dict]:
    environment = account_environment.upper()

    if not account_enabled:
        return False, "ACCOUNT_DISABLED", {"account_enabled": False}
    if signal.decision == "HOLD":
        return False, "NO_DIRECTION", {"decision": signal.decision}
    if abs(signal.score) < minimum_signal_score:
        return False, "SIGNAL_SCORE_BELOW_MINIMUM", {
            "score": signal.score,
            "minimum_signal_score": minimum_signal_score,
        }
    if environment == "LIVE" and not allow_live_trading:
        return False, "LIVE_TRADING_DISABLED", {"environment": environment}

    return True, "APPROVED_FOR_SIMULATION", {
        "score": signal.score,
        "minimum_signal_score": minimum_signal_score,
        "environment": environment,
    }


def reasons_json(reasons: list[str]) -> str:
    return json.dumps(reasons, separators=(",", ":"))
