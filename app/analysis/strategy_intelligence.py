from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from app.analysis.technical import analyze_candles


@dataclass(frozen=True)
class CandlePattern:
    name: str
    direction: str
    confidence: float


def _body(c: dict) -> float:
    return abs(float(c["close"]) - float(c["open"]))


def _range(c: dict) -> float:
    return max(float(c["high"]) - float(c["low"]), 1e-12)


def detect_candlestick_patterns(candles: list[dict]) -> list[CandlePattern]:
    if len(candles) < 3:
        return []
    prev, cur = candles[-2], candles[-1]
    po, pc = float(prev["open"]), float(prev["close"])
    o, h, l, c = map(float, (cur["open"], cur["high"], cur["low"], cur["close"]))
    patterns: list[CandlePattern] = []
    body = abs(c - o); rng = max(h - l, 1e-12)
    upper = h - max(o, c); lower = min(o, c) - l
    if body / rng <= 0.12:
        patterns.append(CandlePattern("DOJI", "NEUTRAL", 55.0))
    if lower >= body * 2 and upper <= body and c >= o:
        patterns.append(CandlePattern("HAMMER", "BULLISH", 68.0))
    if upper >= body * 2 and lower <= body and c <= o:
        patterns.append(CandlePattern("SHOOTING_STAR", "BEARISH", 68.0))
    if pc < po and c > o and o <= pc and c >= po:
        patterns.append(CandlePattern("BULLISH_ENGULFING", "BULLISH", 74.0))
    if pc > po and c < o and o >= pc and c <= po:
        patterns.append(CandlePattern("BEARISH_ENGULFING", "BEARISH", 74.0))
    return patterns


def swing_structure(candles: list[dict], lookback: int = 12) -> dict:
    if len(candles) < lookback:
        return {"state": "UNDEFINED", "higher_highs": 0, "higher_lows": 0, "lower_highs": 0, "lower_lows": 0}
    chunk = candles[-lookback:]
    highs = [float(x["high"]) for x in chunk]
    lows = [float(x["low"]) for x in chunk]
    half = lookback // 2
    prior_h, recent_h = highs[:half], highs[half:]
    prior_l, recent_l = lows[:half], lows[half:]
    hh = int(max(recent_h) > max(prior_h)); hl = int(min(recent_l) > min(prior_l))
    lh = int(max(recent_h) < max(prior_h)); ll = int(min(recent_l) < min(prior_l))
    state = "BULLISH" if hh and hl else "BEARISH" if lh and ll else "RANGE"
    return {"state": state, "higher_highs": hh, "higher_lows": hl, "lower_highs": lh, "lower_lows": ll}


def detect_breakout(candles: list[dict], window: int = 20) -> dict:
    if len(candles) <= window:
        return {"state": "NONE", "level": None}
    prev = candles[-window-1:-1]
    last = candles[-1]
    resistance = max(float(x["high"]) for x in prev)
    support = min(float(x["low"]) for x in prev)
    close = float(last["close"])
    if close > resistance:
        return {"state": "BULLISH_BREAKOUT", "level": resistance}
    if close < support:
        return {"state": "BEARISH_BREAKOUT", "level": support}
    return {"state": "NONE", "level": None}


def scenario_from_candles(candles: list[dict], *, timeframe: str = "5m", market: str = "CRYPTO") -> dict:
    tech = analyze_candles(candles)
    patterns = detect_candlestick_patterns(candles)
    structure = swing_structure(candles)
    breakout = detect_breakout(candles)
    last = float(candles[-1]["close"])
    atr = float(tech.get("atr14") or max(last * 0.005, 1e-8))
    support = float(tech["support"]); resistance = float(tech["resistance"])

    bull = 0.0; bear = 0.0; reasons: list[str] = []
    if tech["trend"] == "BULLISH": bull += 22; reasons.append("ema_trend_bullish")
    elif tech["trend"] == "BEARISH": bear += 22; reasons.append("ema_trend_bearish")
    if structure["state"] == "BULLISH": bull += 22; reasons.append("higher_highs_higher_lows")
    elif structure["state"] == "BEARISH": bear += 22; reasons.append("lower_highs_lower_lows")
    if breakout["state"] == "BULLISH_BREAKOUT": bull += 18; reasons.append("resistance_breakout")
    elif breakout["state"] == "BEARISH_BREAKOUT": bear += 18; reasons.append("support_breakdown")
    for p in patterns:
        if p.direction == "BULLISH": bull += (p.confidence - 50) * 0.45; reasons.append(p.name.lower())
        elif p.direction == "BEARISH": bear += (p.confidence - 50) * 0.45; reasons.append(p.name.lower())
        else: reasons.append(p.name.lower())
    rsi = tech.get("rsi14")
    if isinstance(rsi, (int, float)):
        if 52 <= rsi <= 68: bull += 10; reasons.append("rsi_bullish_confirmation")
        elif 32 <= rsi <= 48: bear += 10; reasons.append("rsi_bearish_confirmation")
        elif rsi >= 75: bear += 5; reasons.append("rsi_overbought_risk")
        elif rsi <= 25: bull += 5; reasons.append("rsi_oversold_reversal_risk")
    hist = (tech.get("macd") or {}).get("histogram")
    if isinstance(hist, (int, float)):
        if hist > 0: bull += 8
        elif hist < 0: bear += 8

    total = max(bull + bear, 1.0)
    bull_prob = round(50 + ((bull - bear) / total) * 40, 1)
    bull_prob = max(10.0, min(90.0, bull_prob)); bear_prob = round(100 - bull_prob, 1)
    direction = "BUY" if bull_prob >= 62 else "SELL" if bear_prob >= 62 else "WAIT"
    confidence = max(bull_prob, bear_prob) if direction != "WAIT" else round(100 - abs(bull_prob - 50) * 2, 1)

    if direction == "BUY":
        entry_low = max(support, last - 0.35 * atr); entry_high = last + 0.10 * atr
        invalidation = min(support, last - 1.25 * atr); stop = invalidation
        target1 = last + 1.5 * (last - stop); target2 = last + 2.5 * (last - stop)
    elif direction == "SELL":
        entry_low = last - 0.10 * atr; entry_high = min(resistance, last + 0.35 * atr)
        invalidation = max(resistance, last + 1.25 * atr); stop = invalidation
        target1 = last - 1.5 * (stop - last); target2 = last - 2.5 * (stop - last)
    else:
        entry_low = support; entry_high = resistance; invalidation = None; stop = None; target1 = None; target2 = None

    return {
        "market": market.upper(), "timeframe": timeframe, "last_price": last,
        "action": direction, "confidence": confidence,
        "bullish_probability": bull_prob, "bearish_probability": bear_prob,
        "trend": tech["trend"], "structure": structure, "breakout": breakout,
        "candlestick_patterns": [p.__dict__ for p in patterns],
        "support": support, "resistance": resistance, "atr": atr,
        "entry_zone": {"low": entry_low, "high": entry_high},
        "invalidation": invalidation, "stop_loss": stop,
        "targets": [x for x in (target1, target2) if x is not None],
        "reasons": reasons,
        "methodology": {
            "framework": "Murphy-style trend/levels/confirmation",
            "price_action": "Brooks-style bar and market-structure interpretation",
            "candles": "Nison-style candlestick confirmation",
            "patterns": "Bulkowski-style pattern statistics foundation",
            "note": "Conceptual implementation; not a reproduction of copyrighted text or proprietary tables."
        },
    }
