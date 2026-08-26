from __future__ import annotations

import json
from sqlalchemy import select

from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.broker import BrokerProfile
from app.db.models.symbol_strategy import SymbolStrategy
from app.market_data.bybit import BybitPublicMarketData
from app.services.signal_risk import generate_signal

SAFE_SCAN_MODES = {'WATCH', 'SIGNALS'}


def scan_mode_allowed(mode: str, include_watch: bool = False) -> bool:
    value = str(mode or '').upper()
    return value == 'SIGNALS' or (include_watch and value == 'WATCH')


def _bridge_cfg(profile) -> dict:
    if not profile.credential_blob_encrypted:
        raise RuntimeError(f'{profile.provider} bridge configuration missing')
    return json.loads(decrypt_secret(profile.credential_blob_encrypted))


async def scan_user_universe(db, *, user_id, include_watch: bool = False) -> dict:
    settings = get_settings()
    strategies = list(db.scalars(select(SymbolStrategy).where(SymbolStrategy.user_id == user_id, SymbolStrategy.enabled.is_(True))).all())
    strategies = [x for x in strategies if scan_mode_allowed(x.mode, include_watch)]
    profiles = {p.id: p for p in db.scalars(select(BrokerProfile).where(BrokerProfile.user_id == user_id)).all()}
    bybit_market = BybitPublicMarketData(settings.bybit_public_base_url, settings.market_data_timeout_seconds)
    rows: list[dict] = []

    for cfg in sorted(strategies, key=lambda x: (x.market, x.symbol)):
        profile = profiles.get(cfg.profile_id)
        if profile is None:
            rows.append({'market': cfg.market, 'symbol': cfg.symbol, 'status': 'SKIPPED', 'reason': 'PROFILE_MISSING'})
            continue
        if not (profile.is_enabled and profile.is_active and profile.credentials_configured and profile.last_connection_status == 'CONNECTED'):
            rows.append({'market': cfg.market, 'symbol': cfg.symbol, 'provider': profile.provider, 'status': 'SKIPPED', 'reason': 'ROUTE_NOT_READY'})
            continue
        timeframe = cfg.timeframe or '5m'
        try:
            if profile.provider == 'BYBIT':
                candles = await bybit_market.get_candles(symbol=cfg.symbol, interval=timeframe, category='linear', limit=200)
                raw = [c.model_dump() for c in candles]
            elif profile.provider == 'MT5':
                c = _bridge_cfg(profile)
                broker = Mt5BridgeClient(c.get('bridge_url') or 'http://host.docker.internal:8765', c.get('bridge_token'), settings.market_data_timeout_seconds)
                raw = (await broker.candles(cfg.symbol, timeframe, 200)).get('list', [])
            elif profile.provider == 'IBKR':
                c = _bridge_cfg(profile)
                broker = IbkrBridgeClient(c.get('bridge_url') or 'http://host.docker.internal:8766', c.get('bridge_token'), settings.market_data_timeout_seconds)
                raw = (await broker.candles(cfg.symbol, timeframe, 200, sec_type='STK')).get('list', [])
            else:
                rows.append({'market': cfg.market, 'symbol': cfg.symbol, 'provider': profile.provider, 'status': 'SKIPPED', 'reason': 'UNSUPPORTED_PROVIDER'})
                continue
            generated = generate_signal(raw)
            rows.append({'market': cfg.market, 'symbol': cfg.symbol, 'provider': profile.provider, 'environment': profile.environment, 'mode': cfg.mode, 'timeframe': timeframe, 'status': 'SCANNED', 'decision': generated.decision, 'classification': generated.classification, 'score': generated.score, 'strength': generated.strength, 'reasons': generated.reasons})
        except Exception as exc:
            rows.append({'market': cfg.market, 'symbol': cfg.symbol, 'provider': profile.provider, 'status': 'FAILED', 'reason': f'{type(exc).__name__}: {str(exc) or repr(exc)}'})

    return {
        'execution_enabled': False,
        'purpose': 'MULTI_INSTRUMENT_SIGNAL_PREVIEW',
        'configured_scanned': len(strategies),
        'scanned_count': sum(1 for x in rows if x.get('status') == 'SCANNED'),
        'failed_count': sum(1 for x in rows if x.get('status') == 'FAILED'),
        'skipped_count': sum(1 for x in rows if x.get('status') == 'SKIPPED'),
        'items': rows,
    }
