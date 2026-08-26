from __future__ import annotations

import json
from dataclasses import dataclass

from app.brokers.bybit_private import BybitPrivateClient
from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.services.instrument_universe import UniverseItem


@dataclass(frozen=True)
class ValidationResult:
    market: str
    symbol: str
    provider: str | None
    profile_id: str | None
    supported: bool
    reason: str
    details: dict


def _bridge_cfg(profile) -> dict:
    if not getattr(profile, 'credential_blob_encrypted', None):
        raise RuntimeError('bridge configuration missing')
    return json.loads(decrypt_secret(profile.credential_blob_encrypted))


async def validate_instrument(profile, item: UniverseItem) -> ValidationResult:
    provider = str(getattr(profile, 'provider', '') or '').upper()
    settings = get_settings()
    try:
        if provider == 'MT5':
            cfg = _bridge_cfg(profile)
            client = Mt5BridgeClient(cfg.get('bridge_url') or 'http://host.docker.internal:8765', cfg.get('bridge_token'), settings.market_data_timeout_seconds)
            data = await client.symbol(item.symbol)
            bid = float(data.get('bid') or 0)
            ask = float(data.get('ask') or 0)
            if not data or not bool(data.get('visible', True)):
                return ValidationResult(item.market, item.symbol, provider, str(profile.id), False, 'MT5_SYMBOL_NOT_VISIBLE', data or {})
            return ValidationResult(item.market, item.symbol, provider, str(profile.id), True, 'SUPPORTED', {'bid': bid, 'ask': ask, 'digits': data.get('digits'), 'volume_min': data.get('volume_min'), 'volume_step': data.get('volume_step')})

        if provider == 'IBKR':
            cfg = _bridge_cfg(profile)
            client = IbkrBridgeClient(cfg.get('bridge_url') or 'http://host.docker.internal:8766', cfg.get('bridge_token'), settings.market_data_timeout_seconds)
            data = await client.contract(item.symbol, sec_type='STK', exchange='SMART', currency='USD')
            return ValidationResult(item.market, item.symbol, provider, str(profile.id), True, 'SUPPORTED', {'con_id': data.get('con_id'), 'primary_exchange': data.get('primary_exchange'), 'long_name': data.get('long_name'), 'min_tick': data.get('min_tick')})

        if provider == 'BYBIT':
            if not getattr(profile, 'api_key_encrypted', None) or not getattr(profile, 'api_secret_encrypted', None):
                raise RuntimeError('Bybit credentials missing')
            env = str(getattr(profile, 'environment', '') or '').upper()
            base = settings.bybit_demo_base_url if env == 'DEMO' else settings.bybit_testnet_base_url if env == 'TESTNET' else settings.bybit_public_base_url
            client = BybitPrivateClient(decrypt_secret(profile.api_key_encrypted), decrypt_secret(profile.api_secret_encrypted), base, settings.market_data_timeout_seconds)
            data = await client.get('/v5/market/instruments-info', {'category': 'linear', 'symbol': item.symbol})
            rows = data.get('list') or []
            if not rows:
                return ValidationResult(item.market, item.symbol, provider, str(profile.id), False, 'BYBIT_SYMBOL_NOT_FOUND', {})
            row = rows[0]
            lot = row.get('lotSizeFilter') or {}
            return ValidationResult(item.market, item.symbol, provider, str(profile.id), True, 'SUPPORTED', {'status': row.get('status'), 'base_coin': row.get('baseCoin'), 'quote_coin': row.get('quoteCoin'), 'min_order_qty': lot.get('minOrderQty'), 'qty_step': lot.get('qtyStep'), 'min_notional': lot.get('minNotionalValue')})

        return ValidationResult(item.market, item.symbol, provider or None, str(getattr(profile, 'id', '') or '') or None, False, 'UNSUPPORTED_PROVIDER', {})
    except Exception as exc:
        return ValidationResult(item.market, item.symbol, provider or None, str(getattr(profile, 'id', '') or '') or None, False, f'{type(exc).__name__}: {str(exc) or repr(exc)}', {})
