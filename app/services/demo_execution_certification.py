from __future__ import annotations

import json
from sqlalchemy import select

from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.broker import BrokerProfile
from app.db.models.symbol_strategy import SymbolStrategy
from app.services.autotrade_preflight import autotrade_preflight


def _secret(profile) -> dict:
    if not profile.credential_blob_encrypted:
        raise RuntimeError('MT5 bridge configuration missing')
    return json.loads(decrypt_secret(profile.credential_blob_encrypted))


def _select_certifiable(items: list[dict], *, market: str, symbol: str) -> dict:
    market = market.upper().strip()
    symbol = symbol.upper().strip().replace('/', '').replace(' ', '')
    matches = [x for x in items if x.get('market') == market and str(x.get('symbol') or '').upper() == symbol]
    if not matches:
        raise RuntimeError('SYMBOL_NOT_IN_PREFLIGHT')
    row = matches[0]
    if row.get('preflight') != 'PASS':
        raise RuntimeError(f"PREFLIGHT_NOT_PASS:{row.get('reason') or row.get('preflight')}")
    if row.get('provider') != 'MT5':
        raise RuntimeError('CERTIFICATION_STAGE_MT5_ONLY')
    return row


async def certify_single_mt5_demo_order(db, *, user_id, market: str, symbol: str) -> dict:
    """Submit exactly one MT5 demo order after a fresh readiness + broker preflight cycle.

    This is a certification-only path. It refuses non-MT5 routes and any account whose
    configured environment is LIVE. The MT5 bridge independently enforces demo-only execution.
    """
    preflight = await autotrade_preflight(db, user_id=user_id)
    row = _select_certifiable(preflight['items'], market=market, symbol=symbol)

    cfg = db.scalar(select(SymbolStrategy).where(
        SymbolStrategy.user_id == user_id,
        SymbolStrategy.market == market.upper().strip(),
        SymbolStrategy.symbol == symbol.upper().strip().replace('/', '').replace(' ', ''),
        SymbolStrategy.enabled.is_(True),
    ))
    if cfg is None:
        raise RuntimeError('STRATEGY_NOT_FOUND')
    profile = db.get(BrokerProfile, cfg.profile_id)
    if profile is None or profile.user_id != user_id:
        raise RuntimeError('PROFILE_NOT_FOUND')
    if profile.provider != 'MT5':
        raise RuntimeError('CERTIFICATION_STAGE_MT5_ONLY')
    if profile.environment == 'LIVE':
        raise RuntimeError('LIVE_EXECUTION_FORBIDDEN_IN_CERTIFICATION')

    request = row.get('request') or {}
    volume = float(request.get('volume') or 0)
    if volume <= 0:
        raise RuntimeError('INVALID_MT5_VOLUME')

    c = _secret(profile)
    broker = Mt5BridgeClient(
        c.get('bridge_url') or 'http://host.docker.internal:8765',
        c.get('bridge_token'),
        get_settings().market_data_timeout_seconds,
    )
    result = await broker.place_demo_order(
        symbol=symbol,
        side=request.get('side'),
        volume=volume,
        stop_loss=request.get('stop_loss'),
        take_profit=request.get('take_profit'),
        comment='ATLAS CERTIFY',
    )
    return {
        'purpose': 'SINGLE_MT5_DEMO_EXECUTION_CERTIFICATION',
        'execution_count': 1,
        'market': market.upper().strip(),
        'symbol': symbol.upper().strip().replace('/', '').replace(' ', ''),
        'provider': 'MT5',
        'environment': profile.environment,
        'request': request,
        'broker_result': result,
    }
