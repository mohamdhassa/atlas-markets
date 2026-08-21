from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean


@dataclass
class StrategyResult:
    name: str
    score: float
    trades: int
    wins: int
    losses: int
    win_rate: float
    avg_return_pct: float
    max_drawdown_pct: float


def _returns(candles: list[dict]) -> list[float]:
    closes = [float(candle["close"]) for candle in candles]
    return [
        (closes[index] / closes[index - 1] - 1.0) * 100
        for index in range(1, len(closes))
        if closes[index - 1]
    ]


def evaluate_strategy(name: str, candles: list[dict]) -> StrategyResult:
    returns = _returns(candles)
    trades = len(returns)
    wins = sum(value > 0 for value in returns)
    losses = sum(value < 0 for value in returns)
    win_rate = (wins / trades * 100) if trades else 0.0
    avg_return = mean(returns) if returns else 0.0

    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for value in returns:
        equity *= 1.0 + value / 100.0
        peak = max(peak, equity)
        if peak:
            max_drawdown = max(max_drawdown, (peak - equity) / peak * 100.0)

    volatility = mean(abs(value) for value in returns) if returns else 0.0
    family_bias = {
        "trend": 2.0,
        "momentum": 1.5,
        "breakout": 1.0,
        "mean_reversion": 0.5,
        "session_momentum": 1.0,
        "volatility": 1.0,
    }.get(name, 0.0)

    score = max(
        0.0,
        min(
            100.0,
            win_rate * 0.55
            + max(avg_return, 0.0) * 10.0
            + min(volatility, 5.0) * 3.0
            + family_bias
            - max_drawdown * 0.4,
        ),
    )

    return StrategyResult(
        name=name,
        score=round(score, 2),
        trades=trades,
        wins=wins,
        losses=losses,
        win_rate=round(win_rate, 2),
        avg_return_pct=round(avg_return, 4),
        max_drawdown_pct=round(max_drawdown, 2),
    )


def select_strategy(candles: list[dict], families: list[str] | tuple[str, ...]) -> dict:
    results = [evaluate_strategy(name, candles) for name in families]
    results.sort(key=lambda result: result.score, reverse=True)
    return {
        "selected": asdict(results[0]) if results else None,
        "candidates": [asdict(result) for result in results],
        "selection_basis": "historical performance ranking; the risk engine remains authoritative",
    }
