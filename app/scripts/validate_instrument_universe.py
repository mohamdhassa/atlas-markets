from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db.models.broker import BrokerProfile
from app.db.models.symbol_strategy import SymbolStrategy
from app.db.session import SessionLocal
from app.services.instrument_universe import build_universe
from app.services.instrument_validation import validate_instrument


async def main():
    db = SessionLocal()
    try:
        profiles = list(db.scalars(select(BrokerProfile).where(
            BrokerProfile.provider.in_(['BYBIT', 'MT5', 'IBKR']),
            BrokerProfile.is_enabled.is_(True),
            BrokerProfile.is_active.is_(True),
            BrokerProfile.credentials_configured.is_(True),
            BrokerProfile.last_connection_status == 'CONNECTED',
        )).all())
        strategies = list(db.scalars(select(SymbolStrategy).where(SymbolStrategy.enabled.is_(True))).all())
        universe = build_universe(profiles, strategies)
        by_id = {str(p.id): p for p in profiles}
        supported = 0
        failed = 0
        skipped = 0
        print(f'VALIDATE | universe={len(universe)} connected_profiles={len(profiles)}')
        for item in universe:
            if not item.profile_id:
                skipped += 1
                print(f'SKIP     | {item.market:<10} {item.symbol:<12} no executable provider route')
                continue
            profile = by_id.get(item.profile_id)
            if profile is None:
                skipped += 1
                print(f'SKIP     | {item.market:<10} {item.symbol:<12} assigned profile not connected')
                continue
            result = await validate_instrument(profile, item)
            if result.supported:
                supported += 1
                print(f'PASS     | {item.market:<10} {item.symbol:<12} provider={result.provider} env={profile.environment} details={result.details}')
            else:
                failed += 1
                print(f'FAIL     | {item.market:<10} {item.symbol:<12} provider={result.provider} reason={result.reason}')
        print(f'SUMMARY  | supported={supported} failed={failed} skipped={skipped} total={len(universe)}')
        if failed:
            raise SystemExit(2)
    finally:
        db.close()


if __name__ == '__main__':
    asyncio.run(main())
