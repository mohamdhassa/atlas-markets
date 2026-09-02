from __future__ import annotations

import json
from datetime import datetime, timezone
from sqlalchemy import select

from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.automation import AutomationAction
from app.db.models.broker import BrokerProfile
from app.db.models.symbol_strategy import SymbolStrategy


def _canonical(value):
    return str(value or '').strip().upper().replace('/', '').replace(' ', '')


def _secret(profile):
    if not profile.credential_blob_encrypted:
        raise RuntimeError(f'{profile.provider} bridge configuration missing')
    return json.loads(decrypt_secret(profile.credential_blob_encrypted))


def _ibkr_owned_symbols(db, user_id, profile_id):
    rows = db.scalars(select(AutomationAction).where(
        AutomationAction.user_id == user_id,
        AutomationAction.broker_profile_id == profile_id,
        AutomationAction.provider == 'IBKR',
        AutomationAction.status == 'EXECUTED',
    )).all()
    return {_canonical(x.symbol) for x in rows if x.symbol}


def _strategy_map(db, user_id):
    rows = db.scalars(select(SymbolStrategy).where(SymbolStrategy.user_id == user_id)).all()
    return {(_canonical(x.symbol), str(x.market or '').upper()): x for x in rows}


async def inspect_position_lifecycle(db, *, user_id):
    """Read-only lifecycle inspection. Never places or closes an order."""
    settings = get_settings()
    profiles = db.scalars(select(BrokerProfile).where(BrokerProfile.user_id == user_id)).all()
    strategies = _strategy_map(db, user_id)
    items = []
    errors = []

    for profile in profiles:
        provider = str(profile.provider or '').upper()
        environment = str(profile.environment or '').upper()
        if provider not in {'MT5', 'IBKR'}:
            continue
        if not (profile.is_enabled and profile.is_active and profile.credentials_configured and profile.last_connection_status == 'CONNECTED'):
            continue
        try:
            creds = _secret(profile)
            if provider == 'MT5':
                broker = Mt5BridgeClient(creds.get('bridge_url') or 'http://host.docker.internal:8765', creds.get('bridge_token'), settings.market_data_timeout_seconds)
                positions = (await broker.positions()).get('list', [])
                for p in positions:
                    symbol = _canonical(p.get('symbol'))
                    comment = str(p.get('comment') or '')
                    owned = comment.upper().startswith('ATLAS')
                    market = next((m for (s, m) in strategies if s == symbol), None)
                    cfg = strategies.get((symbol, market)) if market else None
                    sl = float(p.get('sl') or 0)
                    tp = float(p.get('tp') or 0)
                    opened = p.get('time')
                    age_seconds = None
                    if opened:
                        try: age_seconds = max(0, int(datetime.now(timezone.utc).timestamp()) - int(opened))
                        except (TypeError, ValueError): pass
                    reasons = []
                    if not owned: reasons.append('OWNERSHIP_NOT_VERIFIED')
                    if cfg is None: reasons.append('STRATEGY_NOT_CONFIGURED')
                    if sl <= 0: reasons.append('STOP_LOSS_MISSING')
                    if tp <= 0: reasons.append('TAKE_PROFIT_MISSING')
                    items.append({'provider':'MT5','environment':environment,'profile_id':str(profile.id),'market':market,'symbol':symbol,'position_id':str(p.get('ticket') or ''),'side':'BUY' if int(p.get('type') or 0)==0 else 'SELL','quantity':float(p.get('volume') or 0),'entry_price':float(p.get('price_open') or 0),'mark_price':float(p.get('price_current') or 0),'unrealized_pnl':float(p.get('profit') or 0),'stop_loss':sl or None,'take_profit':tp or None,'age_seconds':age_seconds,'atlas_owned':owned,'strategy_mode':getattr(cfg,'mode',None),'lifecycle_status':'MANAGED' if owned and cfg and sl>0 and tp>0 else 'REVIEW','reasons':reasons,'action':'HOLD','execution_enabled':False})
            else:
                broker = IbkrBridgeClient(creds.get('bridge_url') or 'http://host.docker.internal:8766', creds.get('bridge_token'), settings.market_data_timeout_seconds)
                positions = (await broker.positions()).get('list', [])
                owned_symbols = _ibkr_owned_symbols(db, user_id, profile.id)
                for p in positions:
                    qty = float(p.get('quantity') or 0)
                    if qty == 0: continue
                    symbol = _canonical(p.get('symbol'))
                    owned = symbol in owned_symbols
                    market = next((m for (s, m) in strategies if s == symbol), None)
                    cfg = strategies.get((symbol, market)) if market else None
                    reasons = []
                    if not owned: reasons.append('OWNERSHIP_NOT_VERIFIED')
                    if cfg is None: reasons.append('STRATEGY_NOT_CONFIGURED')
                    reasons.append('BROKER_NATIVE_PROTECTION_NOT_VERIFIED')
                    items.append({'provider':'IBKR','environment':environment,'profile_id':str(profile.id),'market':market,'symbol':symbol,'position_id':None,'side':'LONG' if qty>0 else 'SHORT','quantity':abs(qty),'entry_price':float(p.get('avg_cost') or 0),'mark_price':None,'unrealized_pnl':None,'stop_loss':None,'take_profit':None,'age_seconds':None,'atlas_owned':owned,'strategy_mode':getattr(cfg,'mode',None),'lifecycle_status':'REVIEW','reasons':reasons,'action':'HOLD','execution_enabled':False})
        except Exception as exc:
            errors.append({'provider':provider,'profile_id':str(profile.id),'error':f'{type(exc).__name__}: {str(exc) or repr(exc)}'})

    return {'status':'COMPLETED','purpose':'POSITION_LIFECYCLE_MONITOR_NO_EXECUTION','execution_enabled':False,'position_count':len(items),'atlas_owned_count':sum(bool(x['atlas_owned']) for x in items),'managed_count':sum(x['lifecycle_status']=='MANAGED' for x in items),'review_count':sum(x['lifecycle_status']=='REVIEW' for x in items),'items':items,'errors':errors}
