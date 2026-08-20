from __future__ import annotations

from statistics import mean, pstdev


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return mean(values[-period:])


def ema_series(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    out = [values[0]]
    for value in values[1:]:
        out.append(alpha * value + (1 - alpha) * out[-1])
    return out


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return ema_series(values, period)[-1]


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    changes = [b - a for a, b in zip(values[-period - 1:-1], values[-period:])]
    gains = sum(max(x, 0) for x in changes) / period
    losses = sum(max(-x, 0) for x in changes) / period
    if losses == 0:
        return 100.0
    rs = gains / losses
    return 100 - (100 / (1 + rs))


def macd(values: list[float]) -> dict[str, float | None]:
    if len(values) < 26:
        return {"macd": None, "signal": None, "histogram": None}
    fast = ema_series(values, 12)
    slow = ema_series(values, 26)
    line = [fast[i] - slow[i] for i in range(len(values))]
    signal_series = ema_series(line, 9)
    return {"macd": line[-1], "signal": signal_series[-1], "histogram": line[-1] - signal_series[-1]}


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    if len(closes) <= period:
        return None
    trs: list[float] = []
    for i in range(1, len(closes)):
        trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    return mean(trs[-period:])


def bollinger(values: list[float], period: int = 20, deviations: float = 2.0) -> dict[str, float | None]:
    if len(values) < period:
        return {"upper": None, "middle": None, "lower": None}
    window = values[-period:]
    middle = mean(window)
    sd = pstdev(window)
    return {"upper": middle + deviations * sd, "middle": middle, "lower": middle - deviations * sd}


def market_structure(highs: list[float], lows: list[float]) -> str:
    if len(highs) < 6:
        return "UNDEFINED"
    recent_h = highs[-3:]
    prior_h = highs[-6:-3]
    recent_l = lows[-3:]
    prior_l = lows[-6:-3]
    if max(recent_h) > max(prior_h) and min(recent_l) > min(prior_l):
        return "BULLISH"
    if max(recent_h) < max(prior_h) and min(recent_l) < min(prior_l):
        return "BEARISH"
    return "RANGE"


def support_resistance(highs: list[float], lows: list[float], window: int = 20) -> dict[str, float]:
    return {"support": min(lows[-window:]), "resistance": max(highs[-window:])}


def analyze_candles(candles: list[dict]) -> dict:
    closes = [float(c["close"]) for c in candles]
    highs = [float(c["high"]) for c in candles]
    lows = [float(c["low"]) for c in candles]
    if len(closes) < 30:
        raise ValueError("at least 30 candles are required")
    e20 = ema(closes, 20)
    e50 = ema(closes, 50)
    current_rsi = rsi(closes)
    m = macd(closes)
    current_atr = atr(highs, lows, closes)
    bb = bollinger(closes)
    structure = market_structure(highs, lows)
    levels = support_resistance(highs, lows)
    trend = "BULLISH" if e20 and e50 and e20 > e50 else "BEARISH" if e20 and e50 and e20 < e50 else "NEUTRAL"
    volatility_pct = (current_atr / closes[-1] * 100) if current_atr else 0.0
    volatility = "HIGH" if volatility_pct >= 2 else "LOW" if volatility_pct <= 0.5 else "NORMAL"
    score = 50
    score += 15 if trend == "BULLISH" else -15 if trend == "BEARISH" else 0
    score += 10 if structure == "BULLISH" else -10 if structure == "BEARISH" else 0
    score += 10 if current_rsi is not None and current_rsi > 55 else -10 if current_rsi is not None and current_rsi < 45 else 0
    score += 10 if m["histogram"] is not None and m["histogram"] > 0 else -10 if m["histogram"] is not None and m["histogram"] < 0 else 0
    score = max(0, min(100, score))
    bias = "LONG" if score >= 65 else "SHORT" if score <= 35 else "NEUTRAL"
    return {
        "last_close": closes[-1], "ema20": e20, "ema50": e50, "sma20": sma(closes, 20), "rsi14": current_rsi,
        "macd": m, "atr14": current_atr, "bollinger": bb, "structure": structure,
        "support": levels["support"], "resistance": levels["resistance"], "trend": trend,
        "volatility": volatility, "volatility_pct": volatility_pct, "score": score, "bias": bias,
    }
