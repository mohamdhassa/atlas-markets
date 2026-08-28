from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.automation import AutomationScan
from app.db.models.broker import BrokerProfile
from app.db.models.symbol_strategy import SymbolStrategy
from app.db.session import SessionLocal
from app.services.automation import get_or_create_state
from app.services.autotrade_preflight import autotrade_preflight

CERTIFIED_AUTOMATION_ROUTES = {('MT5', 'DEMO'), ('IBKR', 'PAPER')}
IBKR_CERTIFIED_MAX_SHARES_PER_ORDER = 1


def automation_certification_blocker(provider: str | None, environment: str | None) -> str | None:
    provider = str(provider or '').upper(); environment = str(environment or '').upper()
    if (provider, environment) in CERTIFIED_AUTOMATION_ROUTES: return None
    if provider == 'BYBIT': return 'PROVIDER_EXECUTION_NOT_CERTIFIED'
    if provider == 'IBKR': return 'IBKR_PAPER_ONLY_CERTIFIED'
    return 'AUTOMATION_ROUTE_NOT_CERTIFIED'


def _secret(profile: BrokerProfile) -> dict:
    if not profile.credential_blob_encrypted: raise RuntimeError(f'{profile.provider} bridge configuration missing')
    return json.loads(decrypt_secret(profile.credential_blob_encrypted))


def _canonical_symbol(value: str | None) -> str: return str(value or '').strip().upper().replace('/', '').replace(' ', '')


async def _execute_mt5(db, *, user_id, item: dict) -> dict:
    market = str(item.get('market') or '').upper(); symbol = _canonical_symbol(item.get('symbol'))
    cfg = db.scalar(select(SymbolStrategy).where(SymbolStrategy.user_id == user_id, SymbolStrategy.market == market, SymbolStrategy.symbol == symbol, SymbolStrategy.enabled.is_(True), SymbolStrategy.mode == 'AUTO_TRADE'))
    if cfg is None: return {'market':market,'symbol':symbol,'provider':'MT5','status':'SKIP','reason':'AUTO_TRADE_NOT_ENABLED'}
    profile = db.get(BrokerProfile, cfg.profile_id)
    if profile is None: return {'market':market,'symbol':symbol,'provider':'MT5','status':'BLOCK','reason':'PROFILE_NOT_FOUND'}
    blocker = automation_certification_blocker(profile.provider, profile.environment)
    if blocker: return {'market':market,'symbol':symbol,'provider':profile.provider,'status':'BLOCK','reason':blocker}
    if not (profile.is_enabled and profile.is_active and profile.credentials_configured and profile.last_connection_status == 'CONNECTED'): return {'market':market,'symbol':symbol,'provider':profile.provider,'status':'BLOCK','reason':'ROUTE_NOT_READY'}
    proposed=item.get('request') or {}; volume=float(proposed.get('volume') or 0); stop_loss=proposed.get('stop_loss'); take_profit=proposed.get('take_profit'); side=str(proposed.get('side') or '').upper()
    if side not in {'BUY','SELL'} or volume <= 0: return {'market':market,'symbol':symbol,'provider':'MT5','status':'BLOCK','reason':'INVALID_ORDER_PROPOSAL'}
    if stop_loss is None or take_profit is None: return {'market':market,'symbol':symbol,'provider':'MT5','status':'BLOCK','reason':'PROTECTION_REQUIRED'}
    creds=_secret(profile); broker=Mt5BridgeClient(creds.get('bridge_url') or 'http://host.docker.internal:8765',creds.get('bridge_token'),get_settings().market_data_timeout_seconds)
    health=await broker.health(); terminal=health.get('terminal') or {}; server=str(health.get('server') or '')
    if 'demo' not in server.lower(): return {'market':market,'symbol':symbol,'provider':'MT5','status':'BLOCK','reason':'MT5_DEMO_SERVER_REQUIRED'}
    if terminal and not terminal.get('trade_allowed',False): return {'market':market,'symbol':symbol,'provider':'MT5','status':'BLOCK','reason':'MT5_ALGO_TRADING_DISABLED'}
    positions=(await broker.positions()).get('list',[])
    if any(_canonical_symbol(x.get('symbol'))==symbol and float(x.get('volume') or 0)!=0 for x in positions): return {'market':market,'symbol':symbol,'provider':'MT5','status':'BLOCK','reason':'SYMBOL_ALREADY_HAS_POSITION'}
    orders=(await broker.orders()).get('list',[])
    if any(_canonical_symbol(x.get('symbol'))==symbol for x in orders): return {'market':market,'symbol':symbol,'provider':'MT5','status':'BLOCK','reason':'SYMBOL_ALREADY_HAS_OPEN_ORDER'}
    check=await broker.order_check({'symbol':symbol,'side':side,'volume':volume,'stop_loss':stop_loss,'take_profit':take_profit,'comment':'ATLAS AUTO PREFLIGHT'})
    if int((check.get('result') or {}).get('retcode',-1)) not in {0,10009}: return {'market':market,'symbol':symbol,'provider':'MT5','status':'BLOCK','reason':'BROKER_PREFLIGHT_REJECTED','broker_check':check}
    result=await broker.place_demo_order(symbol=symbol,side=side,volume=volume,stop_loss=float(stop_loss),take_profit=float(take_profit),comment='ATLAS AUTO DEMO')
    return {'market':market,'symbol':symbol,'provider':'MT5','environment':'DEMO','status':'EXECUTED','side':side,'volume':volume,'stop_loss':stop_loss,'take_profit':take_profit,'broker_result':result}


async def _execute_ibkr(db, *, user_id, item: dict) -> dict:
    market=str(item.get('market') or '').upper(); symbol=_canonical_symbol(item.get('symbol'))
    cfg=db.scalar(select(SymbolStrategy).where(SymbolStrategy.user_id==user_id,SymbolStrategy.market==market,SymbolStrategy.symbol==symbol,SymbolStrategy.enabled.is_(True),SymbolStrategy.mode=='AUTO_TRADE'))
    if cfg is None: return {'market':market,'symbol':symbol,'provider':'IBKR','status':'SKIP','reason':'AUTO_TRADE_NOT_ENABLED'}
    profile=db.get(BrokerProfile,cfg.profile_id)
    if profile is None: return {'market':market,'symbol':symbol,'provider':'IBKR','status':'BLOCK','reason':'PROFILE_NOT_FOUND'}
    blocker=automation_certification_blocker(profile.provider,profile.environment)
    if blocker: return {'market':market,'symbol':symbol,'provider':'IBKR','status':'BLOCK','reason':blocker}
    if not (profile.is_enabled and profile.is_active and profile.credentials_configured and profile.last_connection_status=='CONNECTED'): return {'market':market,'symbol':symbol,'provider':'IBKR','status':'BLOCK','reason':'ROUTE_NOT_READY'}
    proposed=item.get('request') or {}; side=str(proposed.get('side') or '').upper(); requested=int(proposed.get('shares') or 0)
    if side not in {'BUY','SELL'} or requested <= 0: return {'market':market,'symbol':symbol,'provider':'IBKR','status':'BLOCK','reason':'INVALID_ORDER_PROPOSAL'}
    # Certification intentionally starts at one share regardless of strategy sizing. Increase only after a separate sizing review.
    shares=min(requested,IBKR_CERTIFIED_MAX_SHARES_PER_ORDER)
    creds=_secret(profile); broker=IbkrBridgeClient(creds.get('bridge_url') or 'http://host.docker.internal:8766',creds.get('bridge_token'),get_settings().market_data_timeout_seconds)
    health=await broker.health()
    if not health.get('connected') or not health.get('simulation'): return {'market':market,'symbol':symbol,'provider':'IBKR','status':'BLOCK','reason':'IBKR_PAPER_BRIDGE_REQUIRED'}
    payload={'symbol':symbol,'side':side,'quantity':shares,'order_type':'MKT','sec_type':'STK','exchange':'SMART','currency':'USD','account_id':creds.get('account_id')}
    check=await broker.order_check(payload)
    if not (check.get('ok') and check.get('what_if') and check.get('simulation')): return {'market':market,'symbol':symbol,'provider':'IBKR','status':'BLOCK','reason':'BROKER_WHATIF_REJECTED','broker_check':check}
    result=await broker.place_order(payload)
    if not result.get('accepted'): return {'market':market,'symbol':symbol,'provider':'IBKR','status':'BLOCK','reason':'BROKER_ORDER_REJECTED','broker_result':result}
    return {'market':market,'symbol':symbol,'provider':'IBKR','environment':'PAPER','status':'EXECUTED','side':side,'shares':shares,'strategy_requested_shares':requested,'sizing_policy':'CERTIFIED_MAX_1_SHARE','broker_check':check,'broker_result':result}


async def run_safe_scan() -> dict:
    now=datetime.now(timezone.utc)
    with SessionLocal() as db:
        state=get_or_create_state(db)
        if not state.enabled:return {'status':'SKIPPED','reason':'ENGINE_DISABLED'}
        if state.killed:return {'status':'SKIPPED','reason':'KILL_SWITCH'}
        if not state.auto_execute_paper:return {'status':'SKIPPED','reason':'SIMULATION_EXECUTION_DISABLED'}
        auto_configs=list(db.scalars(select(SymbolStrategy).where(SymbolStrategy.enabled.is_(True),SymbolStrategy.mode=='AUTO_TRADE')).all()); user_ids=sorted({cfg.user_id for cfg in auto_configs},key=str)
        if not user_ids:
            state.last_scan_at=now;state.next_scan_at=now+timedelta(seconds=state.interval_seconds);db.commit();return {'status':'SKIPPED','reason':'NO_AUTO_TRADE_SYMBOLS'}
        scan=AutomationScan(status='RUNNING',symbols_count=len(auto_configs),accounts_count=len({cfg.profile_id for cfg in auto_configs}));db.add(scan);db.commit();db.refresh(scan);results=[]
        try:
            for user_id in user_ids:
                preflight=await autotrade_preflight(db,user_id=user_id)
                for item in preflight.get('items',[]):
                    if item.get('preflight')!='PASS':continue
                    scan.signals_count+=1;scan.approved_count+=1;provider=str(item.get('provider') or '').upper()
                    if provider=='MT5': result=await _execute_mt5(db,user_id=user_id,item=item)
                    elif provider=='IBKR': result=await _execute_ibkr(db,user_id=user_id,item=item)
                    else: result={'market':item.get('market'),'symbol':item.get('symbol'),'provider':provider,'status':'BLOCK','reason':automation_certification_blocker(provider,None)}
                    results.append(result)
                    if result.get('status')=='EXECUTED':scan.executed_count+=1
            finished=datetime.now(timezone.utc);scan.status='COMPLETED';scan.finished_at=finished;state.last_scan_at=finished;state.next_scan_at=finished+timedelta(seconds=state.interval_seconds);db.commit()
            return {'status':'COMPLETED','purpose':'CERTIFIED_AUTOMATIC_SIMULATION_EXECUTION','execution_enabled':True,'certified_routes':[{'provider':'MT5','environment':'DEMO'},{'provider':'IBKR','environment':'PAPER','max_shares_per_order':IBKR_CERTIFIED_MAX_SHARES_PER_ORDER}],'blocked_routes':{'BYBIT':'PROVIDER_EXECUTION_NOT_CERTIFIED'},'signals':scan.signals_count,'approved':scan.approved_count,'executed':scan.executed_count,'results':results}
        except Exception as exc:
            scan.status='FAILED';scan.error_message=str(exc)[:500];scan.finished_at=datetime.now(timezone.utc);db.commit();return {'status':'FAILED','error':scan.error_message,'results':results}


async def safe_automation_loop(stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            with SessionLocal() as db:
                state=get_or_create_state(db);wait=max(30,state.interval_seconds);due=state.next_scan_at is None or state.next_scan_at<=datetime.now(timezone.utc);enabled=state.enabled and not state.killed and state.auto_execute_paper
            if enabled and due:await run_safe_scan()
            try:await asyncio.wait_for(stop_event.wait(),timeout=min(wait,30))
            except asyncio.TimeoutError:pass
        except Exception:
            try:await asyncio.wait_for(stop_event.wait(),timeout=15)
            except asyncio.TimeoutError:pass
