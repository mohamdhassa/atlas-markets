from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AssetProfile:
    symbol: str
    market: str
    asset_class: str
    strategy_families: tuple[str, ...]
    default_timeframes: tuple[str, ...]


ASSET_UNIVERSE: tuple[AssetProfile, ...] = (
    AssetProfile("EURUSD", "FX", "FOREX", ("trend", "breakout", "mean_reversion", "session_momentum"), ("4h", "1h", "15m", "5m")),
    AssetProfile("GBPUSD", "FX", "FOREX", ("trend", "breakout", "mean_reversion", "session_momentum"), ("4h", "1h", "15m", "5m")),
    AssetProfile("USDJPY", "FX", "FOREX", ("trend", "breakout", "mean_reversion", "session_momentum"), ("4h", "1h", "15m", "5m")),
    AssetProfile("USDCHF", "FX", "FOREX", ("trend", "breakout", "mean_reversion", "session_momentum"), ("4h", "1h", "15m", "5m")),
    AssetProfile("AUDUSD", "FX", "FOREX", ("trend", "breakout", "mean_reversion", "session_momentum"), ("4h", "1h", "15m", "5m")),
    AssetProfile("USDCAD", "FX", "FOREX", ("trend", "breakout", "mean_reversion", "session_momentum"), ("4h", "1h", "15m", "5m")),
    AssetProfile("XAUUSD", "METALS", "GOLD", ("trend", "momentum", "breakout", "mean_reversion"), ("4h", "1h", "15m", "5m")),
    AssetProfile("XAGUSD", "METALS", "SILVER", ("trend", "momentum", "breakout", "mean_reversion"), ("4h", "1h", "15m", "5m")),
    AssetProfile("WTI", "COMMODITIES", "OIL", ("trend", "momentum", "breakout", "volatility"), ("4h", "1h", "15m", "5m")),
    AssetProfile("BRENT", "COMMODITIES", "OIL", ("trend", "momentum", "breakout", "volatility"), ("4h", "1h", "15m", "5m")),
    AssetProfile("BTCUSDT", "CRYPTO", "CRYPTO", ("trend", "momentum", "breakout", "mean_reversion"), ("4h", "1h", "15m", "5m")),
    AssetProfile("ETHUSDT", "CRYPTO", "CRYPTO", ("trend", "momentum", "breakout", "mean_reversion"), ("4h", "1h", "15m", "5m")),
    AssetProfile("SOLUSDT", "CRYPTO", "CRYPTO", ("trend", "momentum", "breakout", "mean_reversion"), ("4h", "1h", "15m", "5m")),
    AssetProfile("XRPUSDT", "CRYPTO", "CRYPTO", ("trend", "momentum", "breakout", "mean_reversion"), ("4h", "1h", "15m", "5m")),
    AssetProfile("BNBUSDT", "CRYPTO", "CRYPTO", ("trend", "momentum", "breakout", "mean_reversion"), ("4h", "1h", "15m", "5m")),
    AssetProfile("SPY", "EQUITY", "ETF", ("trend", "momentum", "breakout", "mean_reversion"), ("1d", "4h", "1h", "15m", "5m")),
    AssetProfile("QQQ", "EQUITY", "ETF", ("trend", "momentum", "breakout", "mean_reversion"), ("1d", "4h", "1h", "15m", "5m")),
)

EQUITY_SEED_SYMBOLS = (
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD", "AVGO",
    "JPM", "XOM", "CVX", "COP", "SLB", "NEM", "GOLD",
)


def profile_for(symbol: str) -> AssetProfile | None:
    normalized = symbol.upper().replace("/", "")
    return next((profile for profile in ASSET_UNIVERSE if profile.symbol == normalized), None)


def universe_summary() -> dict:
    groups: dict[str, list[str]] = {}
    for profile in ASSET_UNIVERSE:
        groups.setdefault(profile.market, []).append(profile.symbol)
    groups["EQUITY_SEED"] = list(EQUITY_SEED_SYMBOLS)
    return groups


def universe_profiles() -> list[dict]:
    return [asdict(profile) for profile in ASSET_UNIVERSE]
