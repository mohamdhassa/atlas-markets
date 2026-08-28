from __future__ import annotations

import json
from sqlalchemy import select

from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.broker import BrokerProfile
from app.db.models.symbol_strategy import SymbolStrategy


def _secret(profile) -> dict:
    if not profile.credential_blob_encrypted:
        raise RuntimeError('MT5 bridge configuration missing')
    return json.loads(decrypt_secret(profile.credential_blob_encrypted))


async def inspect_mt5_position(db, *, user_id, market: str, symbol: str) -> dict:
    market = market.upper().strip()
    symbol = symbol.upper().strip().replace('/', '').replace(' ', '')

    cfg = db.scalar(select(SymbolStrategy).where(
        SymbolStrategy.user_id == user_id,
        SymbolStrategy.market == market,
        SymbolStrategy.symbol == symbol,
        SymbolStrategy.enabled.is_(True),
    ))
    if cfg is None:
        raise RuntimeError('STRATEGY_NOT_FOUND')

    profile = db.get(BrokerProfile, cfg.profile_id)
    if profile is None or profile.user_id != user_id:
        raise RuntimeError('PROFILE_NOT_FOUND')
    if profile.provider != 'MT5':
        raise RuntimeError('MT5_POSITION_INSPECTION_ONLY')

    c = _secret(profile)
    broker = Mt5BridgeClient(
        c.get('bridge_url') or 'http://host.docker.internal:8765',
        c.get('bridge_token'),
        get_settings().market_data_timeout_seconds,
    )
    raw = await broker.positions()
    rows = raw.get('list', []) if isinstance(raw, dict) else []
    matches = [x for x in rows if str(x.get('symbol') or '').upper() == symbol and float(x.get('volume') or 0) != 0]
    if not matches:
        raise RuntimeError('POSITION_NOT_FOUND')
    if len(matches) > 1:
        raise RuntimeError('MULTIPLE_POSITIONS_FOUND')

    x = matches[0]
    return {
        'provider': 'MT5',
        'environment': profile.environment,
        'market': market,
        'symbol': symbol,
        'ticket': x.get('ticket'),
        'side': 'BUY' if int(x.get('type', 0)) == 0 else 'SELL',
        'volume': float(x.get('volume') or 0),
        'entry_price': float(x.get('price_open') or 0),
        'current_price': float(x.get('price_current') or 0),
        'stop_loss': float(x.get('sl') or 0) or None,
        'take_profit': float(x.get('tp') or 0) or None,
        'profit': float(x.get('profit') or 0),
    }
