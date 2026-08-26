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


def _mt5_search_terms(symbol: str) -> list[str]:
    s = str(symbol or '').upper().replace('/', '').replace(' ', '')
    terms = [s]
    if len(s) >= 3:
        terms.append(s[:3])
    aliases = {
        'XAGUSD': ['SILVER'],
        'XAUUSD': ['GOLD'],
        'XTIUSD': ['WTI', 'OIL'],
    }
    terms.extend(aliases.get(s, []))
    result: list[str] = []
    for term in terms:
        if term and term not in result:
            result.append(term)
    return result


async def _resolve_mt5_symbol(client: Mt5BridgeClient, requested: str) -> tuple[str, dict] | None:
    requested = str(requested or '').upper().replace('/', '').replace(' ', '')
    candidates: dict[str, dict] = {}
    for term in _mt5_search_terms(requested):
        try:
            rows = (await client.search_symbols(term, 100)).get('list') or []
        except Exception:
            continue
        for row in rows:
            name = str(row.get('name') or '').upper()
            if name:
                candidates[name] = row
    if not candidates:
        return None

    def score(entry: tuple[str, dict]) -> tuple[int, int, str]:
        name, row = entry
        description = str(row.get('description') or '').upper()
        value = 0
        if name == requested:
            value += 100
        if name.startswith(requested):
            value += 80
        if requested in name:
            value += 60
        if requested.startswith('XAG') and ('XAG' in name or 'SILVER' in description or 'SILVER' in name):
            value += 50
        if requested.startswith('XAU') and ('XAU' in name or 'GOLD' in description or 'GOLD' in name):
            value += 50
        if requested == 'XTIUSD' and ('WTI' in name or 'OIL' in description or 'OIL' in name):
            value += 50
        if bool(row.get('visible')):
            value += 5
        return (-value, len(name), name)

    for name, _ in sorted(candidates.items(), key=score):
        try:
            return name, await client.symbol(name)
        except Exception:
            continue
    return None


async def validate_instrument(profile, item: UniverseItem) -> ValidationResult:
    provider = str(getattr(profile, 'provider', '') or '').upper()
    settings = get_settings()
    try:
        if provider == 'MT5':
            cfg = _bridge_cfg(profile)
            client = Mt5BridgeClient(cfg.get('bridge_url') or 'http://host.docker.internal:8765', cfg.get('bridge_token'), settings.market_data_timeout_seconds)
            broker_symbol = item.symbol
            try:
                data = await client.symbol(item.symbol)
            except Exception:
                resolved = await _resolve_mt5_symbol(client, item.symbol)
                if not resolved:
                    return ValidationResult(item.market, item.symbol, provider, str(profile.id), False, 'MT5_SYMBOL_NOT_FOUND', {})
                broker_symbol, data = resolved
            bid = float(data.get('bid') or 0)
            ask = float(data.get('ask') or 0)
            if not data or not bool(data.get('visible', True)):
                return ValidationResult(item.market, item.symbol, provider, str(profile.id), False, 'MT5_SYMBOL_NOT_VISIBLE', data or {})
            details = {'bid': bid, 'ask': ask, 'digits': data.get('digits'), 'volume_min': data.get('volume_min'), 'volume_step': data.get('volume_step'), 'broker_symbol': broker_symbol}
            if broker_symbol.upper() != item.symbol.upper():
                details['requested_symbol'] = item.symbol
                details['alias_resolved'] = True
            return ValidationResult(item.market, item.symbol, provider, str(profile.id), True, 'SUPPORTED', details)

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
