from __future__ import annotations

import json
from dataclasses import dataclass

from app.analysis.technical import analyze_candles


@dataclass(frozen=True)
class GeneratedSignal:
    decision: str
    classification: str
    score: float
    strength: float
    reasons: list[str]


def generate_signal(candles: list[dict]) -> GeneratedSignal:
    analysis = analyze_candles(candles)
    score = float(analysis.get("score", 50.0))
    bias = str(analysis.get("bias", "NEUTRAL")).upper()
    decision = bias if bias in {"LONG", "SHORT"} else "HOLD"
    strength = score if decision == "LONG" else 100.0 - score if decision == "SHORT" else 50.0

    if decision == "HOLD":
        classification = "NO_SIGNAL"
    elif strength >= 80:
        classification = "STRONG_SIGNAL"
    elif strength >= 65:
        classification = "SIGNAL"
    else:
        classification = "WATCH"

    reasons: list[str] = []
    trend = analysis.get("trend")
    volatility = analysis.get("volatility")
    structure = analysis.get("structure")
    rsi = analysis.get("rsi14")
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
        strength=strength,
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
    if signal.strength < minimum_signal_score:
        return False, "SIGNAL_SCORE_BELOW_MINIMUM", {
            "score": signal.score,
            "strength": signal.strength,
            "minimum_signal_score": minimum_signal_score,
        }
    if environment == "LIVE" and not allow_live_trading:
        return False, "LIVE_TRADING_DISABLED", {"environment": environment}

    return True, "APPROVED_FOR_SIMULATION", {
        "score": signal.score,
        "strength": signal.strength,
        "minimum_signal_score": minimum_signal_score,
        "environment": environment,
    }


def reasons_json(reasons: list[str]) -> str:
    return json.dumps(reasons, separators=(",", ":"))
