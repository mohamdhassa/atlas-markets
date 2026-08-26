from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


MARKETS = {'CRYPTO', 'FX', 'STOCK', 'ETF', 'METAL', 'COMMODITY'}
PROVIDER_MARKETS = {
    'BYBIT': {'CRYPTO'},
    'MT5': {'FX', 'METAL', 'COMMODITY'},
    'IBKR': {'STOCK', 'ETF'},
    'TWELVE_DATA': set(),
}


def normalize_market(value: str) -> str:
    market = (value or '').strip().upper()
    if market not in MARKETS:
        raise ValueError(f'unsupported market: {market or value!r}')
    return market


def normalize_symbol(market: str, symbol: str) -> str:
    market = normalize_market(market)
    value = (symbol or '').upper().replace(' ', '')
    if not value:
        raise ValueError('symbol is required')
    return value.replace('/', '') if market in {'FX', 'CRYPTO', 'METAL', 'COMMODITY'} else value


def providers_for_market(market: str) -> tuple[str, ...]:
    market = normalize_market(market)
    return tuple(provider for provider, markets in PROVIDER_MARKETS.items() if market in markets)


def provider_supports_market(provider: str, market: str) -> bool:
    return normalize_market(market) in PROVIDER_MARKETS.get((provider or '').upper(), set())


@dataclass(frozen=True)
class RouteCandidate:
    profile_id: str
    provider: str
    label: str
    environment: str
    connected: bool
    enabled: bool
    active: bool
    credentials_configured: bool

    @property
    def executable(self) -> bool:
        return self.connected and self.enabled and self.active and self.credentials_configured


def route_candidates(market: str, profiles: Iterable[object]) -> list[RouteCandidate]:
    market = normalize_market(market)
    rows: list[RouteCandidate] = []
    for profile in profiles:
        provider = str(getattr(profile, 'provider', '') or '').upper()
        if not provider_supports_market(provider, market):
            continue
        rows.append(RouteCandidate(
            profile_id=str(getattr(profile, 'id')),
            provider=provider,
            label=str(getattr(profile, 'account_label', '') or provider),
            environment=str(getattr(profile, 'environment', '') or ''),
            connected=str(getattr(profile, 'last_connection_status', '') or '').upper() == 'CONNECTED',
            enabled=bool(getattr(profile, 'is_enabled', False)),
            active=bool(getattr(profile, 'is_active', False)),
            credentials_configured=bool(getattr(profile, 'credentials_configured', False)),
        ))
    rows.sort(key=lambda row: (not row.executable, row.provider, row.label, row.profile_id))
    return rows


def select_execution_route(market: str, profiles: Iterable[object]) -> RouteCandidate | None:
    return next((row for row in route_candidates(market, profiles) if row.executable), None)
