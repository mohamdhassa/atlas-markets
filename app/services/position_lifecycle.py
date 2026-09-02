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
from app.db.models.strategy import StrategyProfile
from app.db.models.symbol_strategy import SymbolStrategy
from app.services.signal_risk import generate_signal


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


def _strategy_for_symbol(strategies, symbol):
    for (configured_symbol, market), cfg in strategies.items():
        if configured_symbol == symbol:
            return market, cfg
    return None, None


def _default_strategy(db):
    return db.scalar(select(StrategyProfile).where(StrategyProfile.name == 'Default')) or StrategyProfile(name='Default')


def _minimum_strength(cfg, default):
    value = cfg.minimum_signal_strength if cfg and cfg.minimum_signal_strength is not None else default.minimum_signal_strength
    return float(value or 65.0)


def _timeframe(cfg, default):
    return str((cfg.timeframe if cfg and cfg.timeframe else default.timeframe) or '5m')


def _opposite_signal(position_side, decision):
    side = str(position_side or '').upper()
    decision = str(decision or '').upper()
    return (side == 'BUY' and decision == 'SELL') or (side == 'SELL' and decision == 'BUY')


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
                    market, cfg = _strategy_for_symbol(strategies, symbol)
                    sl = float(p.get('sl') or 0)
                    tp = float(p.get('tp') or 0)
                    opened = p.get('time')
                    age_seconds = None
                    if opened:
                        try:
                            age_seconds = max(0, int(datetime.now(timezone.utc).timestamp()) - int(opened))
                        except (TypeError, ValueError):
                            pass
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
                    if qty == 0:
                        continue
                    symbol = _canonical(p.get('symbol'))
                    owned = symbol in owned_symbols
                    market, cfg = _strategy_for_symbol(strategies, symbol)
                    reasons = []
                    if not owned: reasons.append('OWNERSHIP_NOT_VERIFIED')
                    if cfg is None: reasons.append('STRATEGY_NOT_CONFIGURED')
                    reasons.append('BROKER_NATIVE_PROTECTION_NOT_VERIFIED')
                    items.append({'provider':'IBKR','environment':environment,'profile_id':str(profile.id),'market':market,'symbol':symbol,'position_id':None,'side':'LONG' if qty>0 else 'SHORT','quantity':abs(qty),'entry_price':float(p.get('avg_cost') or 0),'mark_price':None,'unrealized_pnl':None,'stop_loss':None,'take_profit':None,'age_seconds':None,'atlas_owned':owned,'strategy_mode':getattr(cfg,'mode',None),'lifecycle_status':'REVIEW','reasons':reasons,'action':'HOLD','execution_enabled':False})
        except Exception as exc:
            errors.append({'provider':provider,'profile_id':str(profile.id),'error':f'{type(exc).__name__}: {str(exc) or repr(exc)}'})

    return {'status':'COMPLETED','purpose':'POSITION_LIFECYCLE_MONITOR_NO_EXECUTION','execution_enabled':False,'position_count':len(items),'atlas_owned_count':sum(bool(x['atlas_owned']) for x in items),'managed_count':sum(x['lifecycle_status']=='MANAGED' for x in items),'review_count':sum(x['lifecycle_status']=='REVIEW' for x in items),'items':items,'errors':errors}


async def evaluate_mt5_exit_signals(db, *, user_id):
    """Evaluate MT5 Demo exits without executing them.

    A position is eligible only when it is demonstrably ATLAS-owned, uses an
    enabled AUTO_TRADE strategy, and has broker-native SL/TP protection. The
    only strategy-driven exit signal in v1 is a sufficiently strong opposite
    signal. Broker SL/TP remains the primary protective exit mechanism.
    """
    settings = get_settings()
    profiles = db.scalars(select(BrokerProfile).where(
        BrokerProfile.user_id == user_id,
        BrokerProfile.provider == 'MT5',
        BrokerProfile.environment == 'DEMO',
    )).all()
    strategies = _strategy_map(db, user_id)
    default = _default_strategy(db)
    items = []
    errors = []

    for profile in profiles:
        if not (profile.is_enabled and profile.is_active and profile.credentials_configured and profile.last_connection_status == 'CONNECTED'):
            continue
        try:
            creds = _secret(profile)
            broker = Mt5BridgeClient(creds.get('bridge_url') or 'http://host.docker.internal:8765', creds.get('bridge_token'), settings.market_data_timeout_seconds)
            positions = (await broker.positions()).get('list', [])
            for p in positions:
                symbol = _canonical(p.get('symbol'))
                position_side = 'BUY' if int(p.get('type') or 0) == 0 else 'SELL'
                ticket = int(p.get('ticket') or 0)
                comment = str(p.get('comment') or '')
                market, cfg = _strategy_for_symbol(strategies, symbol)
                sl = float(p.get('sl') or 0)
                tp = float(p.get('tp') or 0)
                blockers = []
                if not comment.upper().startswith('ATLAS'): blockers.append('OWNERSHIP_NOT_VERIFIED')
                if cfg is None: blockers.append('STRATEGY_NOT_CONFIGURED')
                elif not cfg.enabled or cfg.mode != 'AUTO_TRADE': blockers.append('AUTO_TRADE_NOT_ENABLED')
                if sl <= 0 or tp <= 0: blockers.append('BROKER_PROTECTION_REQUIRED')
                if ticket <= 0: blockers.append('POSITION_ID_MISSING')
                if blockers:
                    items.append({'provider':'MT5','environment':'DEMO','profile_id':str(profile.id),'market':market,'symbol':symbol,'position_id':str(ticket or ''),'position_side':position_side,'status':'BLOCK','action':'HOLD','reason':'|'.join(blockers),'execution_enabled':False})
                    continue

                timeframe = _timeframe(cfg, default)
                minimum = _minimum_strength(cfg, default)
                candles = (await broker.candles(symbol, timeframe, 200)).get('list', [])
                signal = generate_signal(candles)
                should_exit = _opposite_signal(position_side, signal.decision) and signal.strength >= minimum
                items.append({'provider':'MT5','environment':'DEMO','profile_id':str(profile.id),'market':market,'symbol':symbol,'position_id':str(ticket),'position_side':position_side,'signal_decision':signal.decision,'signal_strength':signal.strength,'minimum_signal_strength':minimum,'classification':signal.classification,'status':'PASS','action':'EXIT_SIGNAL' if should_exit else 'HOLD','reason':'STRONG_OPPOSITE_SIGNAL' if should_exit else 'NO_EXIT_SIGNAL','execution_enabled':False})
        except Exception as exc:
            errors.append({'provider':'MT5','profile_id':str(profile.id),'error':f'{type(exc).__name__}: {str(exc) or repr(exc)}'})

    return {'status':'COMPLETED','purpose':'MT5_EXIT_SIGNAL_EVALUATION_NO_EXECUTION','execution_enabled':False,'evaluated_count':len(items),'exit_signal_count':sum(x.get('action')=='EXIT_SIGNAL' for x in items),'hold_count':sum(x.get('action')=='HOLD' for x in items),'items':items,'errors':errors}
