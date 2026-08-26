from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.services.provider_routing import normalize_market, normalize_symbol, route_candidates, select_execution_route


STARTER_UNIVERSE: dict[str, tuple[str, ...]] = {
    'STOCK': ('AAPL', 'MSFT', 'NVDA', 'AMZN', 'META', 'TSLA'),
    'ETF': ('SPY', 'QQQ', 'IWM'),
    'FX': ('EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'USDCHF'),
    'METAL': ('XAUUSD', 'XAGUSD'),
    'COMMODITY': ('XTIUSD',),
    'CRYPTO': ('BTCUSDT', 'ETHUSDT', 'SOLUSDT'),
}


@dataclass(frozen=True)
class UniverseItem:
    market: str
    symbol: str
    configured: bool
    strategy_mode: str | None
    strategy_enabled: bool | None
    profile_id: str | None
    provider: str | None
    environment: str | None
    executable_route: bool
    route_candidates: int


def starter_symbols(markets: Iterable[str] | None = None) -> list[tuple[str, str]]:
    wanted = [normalize_market(m) for m in markets] if markets else list(STARTER_UNIVERSE)
    rows: list[tuple[str, str]] = []
    for market in wanted:
        for symbol in STARTER_UNIVERSE.get(market, ()):
            rows.append((market, normalize_symbol(market, symbol)))
    return rows


def build_universe(profiles: Iterable[object], strategies: Iterable[object], markets: Iterable[str] | None = None) -> list[UniverseItem]:
    profiles = list(profiles)
    strategies = list(strategies)
    wanted = {normalize_market(m) for m in markets} if markets else set(STARTER_UNIVERSE)

    configured: dict[tuple[str, str], object] = {}
    for row in strategies:
        market = normalize_market(str(getattr(row, 'market', '') or ''))
        if market not in wanted:
            continue
        symbol = normalize_symbol(market, str(getattr(row, 'symbol', '') or ''))
        configured[(market, symbol)] = row

    keys = set(starter_symbols(wanted)) | set(configured)
    result: list[UniverseItem] = []
    for market, symbol in sorted(keys):
        strategy = configured.get((market, symbol))
        candidates = route_candidates(market, profiles)
        selected = select_execution_route(market, profiles)
        profile_id = str(getattr(strategy, 'profile_id')) if strategy is not None else (selected.profile_id if selected else None)
        provider = selected.provider if selected else None
        environment = selected.environment if selected else None
        if strategy is not None:
            matched = next((c for c in candidates if c.profile_id == profile_id), None)
            if matched is not None:
                provider, environment = matched.provider, matched.environment
        result.append(UniverseItem(
            market=market,
            symbol=symbol,
            configured=strategy is not None,
            strategy_mode=str(getattr(strategy, 'mode', '') or '') or None if strategy is not None else None,
            strategy_enabled=bool(getattr(strategy, 'enabled', False)) if strategy is not None else None,
            profile_id=profile_id,
            provider=provider,
            environment=environment,
            executable_route=bool(selected and selected.executable),
            route_candidates=len(candidates),
        ))
    return result
