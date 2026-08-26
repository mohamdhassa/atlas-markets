from __future__ import annotations

from sqlalchemy import select

from app.db.models.symbol_strategy import SymbolStrategy
from app.services.instrument_universe import STARTER_UNIVERSE, starter_symbols
from app.services.instrument_validation import validate_instrument
from app.services.provider_routing import normalize_market, select_execution_route

SAFE_SEED_MODES = {'WATCH', 'SIGNALS'}


def normalize_seed_mode(mode: str) -> str:
    value = str(mode or '').upper()
    if value not in SAFE_SEED_MODES:
        raise ValueError('validated bulk seed only allows WATCH or SIGNALS')
    return value


async def seed_validated_universe(db, *, user_id, profiles: list[object], markets: list[str] | None = None, mode: str = 'SIGNALS') -> dict:
    mode = normalize_seed_mode(mode)
    wanted = [normalize_market(x) for x in markets] if markets else list(STARTER_UNIVERSE)
    existing = {(x.market, x.symbol) for x in db.scalars(select(SymbolStrategy).where(SymbolStrategy.user_id == user_id)).all()}
    created: list[dict] = []
    skipped: list[dict] = []

    for market, symbol in starter_symbols(wanted):
        if (market, symbol) in existing:
            skipped.append({'market': market, 'symbol': symbol, 'reason': 'ALREADY_CONFIGURED'})
            continue
        route = select_execution_route(market, profiles)
        if route is None:
            skipped.append({'market': market, 'symbol': symbol, 'reason': 'NO_EXECUTABLE_ROUTE'})
            continue
        profile = next((p for p in profiles if str(p.id) == route.profile_id), None)
        if profile is None:
            skipped.append({'market': market, 'symbol': symbol, 'reason': 'ROUTE_PROFILE_MISSING'})
            continue
        item = type('SeedItem', (), {'market': market, 'symbol': symbol})()
        validation = await validate_instrument(profile, item)
        if not validation.supported:
            skipped.append({'market': market, 'symbol': symbol, 'reason': validation.reason})
            continue
        row = SymbolStrategy(user_id=user_id, profile_id=profile.id, market=market, symbol=symbol, mode=mode, enabled=True)
        db.add(row)
        created.append({'market': market, 'symbol': symbol, 'profile_id': str(profile.id), 'provider': profile.provider, 'mode': mode, 'validation': validation.details})
        existing.add((market, symbol))

    db.commit()
    return {'mode': mode, 'created_count': len(created), 'skipped_count': len(skipped), 'created': created, 'skipped': skipped}
