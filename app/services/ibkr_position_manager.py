from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from sqlalchemy import select

from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.automation import AutomationAction, AutomationScan
from app.db.models.broker import BrokerProfile
from app.db.models.strategy import StrategyProfile
from app.db.models.symbol_strategy import SymbolStrategy
from app.db.session import SessionLocal
from app.services.automation import get_or_create_state
from app.services.signal_risk import generate_signal


def _canonical(value):return str(value or '').strip().upper().replace('/','').replace(' ','')
def _short(value,limit):
    if value is None:return None
    text=str(value);return text if len(text)<=limit else text[:max(0,limit-3)]+'...'
def _secret(profile):
    if not profile.credential_blob_encrypted:raise RuntimeError('IBKR bridge configuration missing')
    return json.loads(decrypt_secret(profile.credential_blob_encrypted))
def _default_strategy(db):return db.scalar(select(StrategyProfile).where(StrategyProfile.name=='Default')) or StrategyProfile(name='Default')
def _minimum_strength(cfg,default):return float((cfg.minimum_signal_strength if cfg.minimum_signal_strength is not None else default.minimum_signal_strength) or 65.0)
def _timeframe(cfg,default):return str((cfg.timeframe if cfg.timeframe else default.timeframe) or '5m')
def _opposite(position_side,decision):return (position_side=='LONG' and decision=='SELL') or (position_side=='SHORT' and decision=='BUY')

def _execution_matches_action(action, execution, account_id):
    """Return True only when broker execution evidence exactly proves an ATLAS entry fill."""
    try:
        if int(execution.get('order_id'))!=int(action.broker_order_id):return False
    except (TypeError,ValueError):return False
    if _canonical(execution.get('symbol'))!=_canonical(action.symbol):return False
    expected_side='BOT' if str(action.side or '').upper()=='BUY' else 'SLD' if str(action.side or '').upper()=='SELL' else None
    if expected_side is None or str(execution.get('side') or '').upper()!=expected_side:return False
    if account_id and str(execution.get('account') or '')!=str(account_id):return False
    return True

def _reconciliation_evidence(action, executions, account_id):
    matches=[x for x in executions if _execution_matches_action(action,x,account_id)]
    expected=float(action.quantity or 0)
    filled=sum(float(x.get('quantity') or 0) for x in matches)
    if expected<=0 or abs(filled-expected)>=1e-9:return None
    return {'order_id':str(action.broker_order_id),'symbol':_canonical(action.symbol),'side':str(action.side or '').upper(),'quantity':expected,'execution_ids':[str(x.get('execution_id') or '') for x in matches if x.get('execution_id')]}

def _submitted_entries(db,profile):
    return list(db.scalars(select(AutomationAction).where(
        AutomationAction.user_id==profile.user_id,
        AutomationAction.broker_profile_id==profile.id,
        AutomationAction.provider=='IBKR',
        AutomationAction.environment=='PAPER',
        AutomationAction.status=='SUBMITTED',
        AutomationAction.reason=='BROKER_FILL_NOT_CONFIRMED',
        AutomationAction.broker_order_id.is_not(None),
    )).all())

def _mark_reconciled(action,source,evidence):
    action.status='EXECUTED'
    action.reason='BROKER_EXECUTION_RECONCILED' if source=='IBKR_EXECUTIONS' else 'BROKER_POSITION_RECONCILED'
    try:raw=json.loads(action.raw_json or '{}')
    except (TypeError,ValueError,json.JSONDecodeError):raw={}
    raw['reconciliation']={'source':source,'verified_at':datetime.now(timezone.utc).isoformat(),**evidence}
    action.raw_json=json.dumps(raw,default=str)

def _reconcile_submitted_entries(db,profile,executions,account_id):
    """Promote delayed IBKR Paper fills only when execution history proves exact ownership."""
    reconciled=[]
    for action in _submitted_entries(db,profile):
        evidence=_reconciliation_evidence(action,executions,account_id)
        if evidence is None:continue
        _mark_reconciled(action,'IBKR_EXECUTIONS',evidence)
        reconciled.append(action)
    if reconciled:db.flush()
    return reconciled

def _position_fallback_evidence(action,position,account_id):
    """Return strict current-position evidence for one unresolved Paper entry.

    This is intentionally weaker than execution history and is used only when the
    broker no longer exposes completed executions after a Gateway restart.
    """
    if account_id and str(position.get('account') or '')!=str(account_id):return None
    if _canonical(position.get('symbol'))!=_canonical(action.symbol):return None
    expected=float(action.quantity or 0);live=float(position.get('quantity') or 0)
    side=str(action.side or '').upper()
    if expected<=0:return None
    if side=='BUY' and live<=0:return None
    if side=='SELL' and live>=0:return None
    if abs(live)+1e-9<expected:return None
    return {'order_id':str(action.broker_order_id),'account':str(position.get('account') or account_id or ''),'symbol':_canonical(action.symbol),'side':side,'quantity':expected,'live_position_quantity':live,'live_avg_cost':position.get('avg_cost')}

def _reconcile_submitted_entries_from_positions(db,profile,positions,account_id):
    """Fallback reconciliation only for an unambiguous unresolved entry/live position pair."""
    rows=_submitted_entries(db,profile)
    by_symbol={}
    for action in rows:by_symbol.setdefault(_canonical(action.symbol),[]).append(action)
    pos_by_symbol={}
    for position in positions:
        if account_id and str(position.get('account') or '')!=str(account_id):continue
        if abs(float(position.get('quantity') or 0))<=1e-9:continue
        pos_by_symbol.setdefault(_canonical(position.get('symbol')),[]).append(position)
    reconciled=[]
    for symbol,actions in by_symbol.items():
        broker_positions=pos_by_symbol.get(symbol,[])
        if len(actions)!=1 or len(broker_positions)!=1:continue
        action=actions[0];position=broker_positions[0]
        evidence=_position_fallback_evidence(action,position,account_id)
        if evidence is None:continue
        _mark_reconciled(action,'IBKR_CURRENT_POSITION_FALLBACK',evidence)
        reconciled.append(action)
    if reconciled:db.flush()
    return reconciled

def _latest_entry(db,user_id,profile_id,symbol):
    rows=list(db.scalars(select(AutomationAction).where(
        AutomationAction.user_id==user_id,
        AutomationAction.broker_profile_id==profile_id,
        AutomationAction.provider=='IBKR',
        AutomationAction.symbol==symbol,
        AutomationAction.status.in_(['EXECUTED','EXIT_EXECUTED']),
    ).order_by(AutomationAction.created_at.desc())).all())
    if not rows:return None
    latest=rows[0]
    if latest.status!='EXECUTED' or not latest.broker_order_id:return None
    return latest

def _entry_fill_verified(entry, broker_entry, position_side, quantity):
    """Verify an entry from current broker state, with a restart-safe persisted fallback.

    IB Gateway can forget completed order status after a session restart. In that case,
    accept ATLAS's persisted EXECUTED record only when the live position still exactly
    matches the persisted entry direction and quantity. A broker-reported non-filled
    state never falls back to persistence.
    """
    state=str((broker_entry or {}).get('status') or '').upper()
    if state=='FILLED':return True,'BROKER_FILLED'
    if state:return False,'BROKER_NOT_FILLED'
    expected_side='LONG' if entry.side=='BUY' else 'SHORT' if entry.side=='SELL' else None
    persisted_qty=float(entry.quantity or 0)
    if entry.status=='EXECUTED' and expected_side==position_side and persisted_qty>0 and abs(persisted_qty-float(quantity))<1e-9:
        return True,'PERSISTED_EXECUTED_LIVE_POSITION_MATCH'
    return False,'ENTRY_FILL_NOT_VERIFIED'
def _persist(db,scan,user_id,profile,item,result):
    broker_result=result.get('broker_result') or {};order_id=broker_result.get('order_id')
    db.add(AutomationAction(scan_id=scan.id,user_id=user_id,broker_profile_id=profile.id,provider='IBKR',environment='PAPER',market=_short(item.get('market'),24),symbol=_short(item.get('symbol'),32),side=_short(result.get('close_side'),8),status=_short(result.get('status') or 'UNKNOWN',24),reason=_short(result.get('reason'),128),quantity=float(item.get('quantity') or 0),sizing_policy='POSITION_LIFECYCLE_EXIT',broker_order_id=_short(order_id,128),broker_position_id=None,raw_json=json.dumps({'position':item,'result':result},default=str)))

async def _verify_fill(broker,order_id,quantity):
    latest=None
    for attempt in range(6):
        if attempt:await asyncio.sleep(1)
        latest=await broker.order_status(int(order_id));status=latest.get('status') or {};state=str(status.get('status') or '').upper();filled=float(status.get('filled') or 0);remaining=float(status.get('remaining') or 0)
        if filled>=quantity or (state=='FILLED' and remaining<=0):return True,latest
        if state in {'CANCELLED','CANCELED','INACTIVE','API CANCELLED','APICANCELLED'}:return False,latest
    return False,latest

async def run_ibkr_position_manager():
    """Close only current, provably ATLAS-owned IBKR Paper positions on strong opposite signals."""
    with SessionLocal() as db:
        state=get_or_create_state(db)
        if not state.enabled:return {'status':'SKIPPED','reason':'ENGINE_DISABLED'}
        if state.killed:return {'status':'SKIPPED','reason':'KILL_SWITCH'}
        if not state.auto_execute_paper:return {'status':'SKIPPED','reason':'SIMULATION_EXECUTION_DISABLED'}
        profiles=list(db.scalars(select(BrokerProfile).where(BrokerProfile.provider=='IBKR',BrokerProfile.environment=='PAPER',BrokerProfile.is_enabled.is_(True),BrokerProfile.is_active.is_(True),BrokerProfile.last_connection_status=='CONNECTED')).all())
        if not profiles:return {'status':'SKIPPED','reason':'NO_IBKR_PAPER_PROFILES'}
        scan=AutomationScan(status='RUNNING',symbols_count=0,accounts_count=len(profiles));db.add(scan);db.commit();db.refresh(scan);results=[];default=_default_strategy(db)
        try:
            for profile in profiles:
                creds=_secret(profile);broker=IbkrBridgeClient(creds.get('bridge_url') or 'http://host.docker.internal:8766',creds.get('bridge_token'),get_settings().market_data_timeout_seconds);health=await broker.health()
                if not health.get('connected') or not health.get('simulation'):continue
                executions=(await broker.executions(30)).get('list',[])
                _reconcile_submitted_entries(db,profile,executions,creds.get('account_id'))
                positions=(await broker.positions()).get('list',[])
                _reconcile_submitted_entries_from_positions(db,profile,positions,creds.get('account_id'))
                for p in positions:
                    qty=float(p.get('quantity') or 0)
                    if qty==0:continue
                    scan.symbols_count+=1;symbol=_canonical(p.get('symbol'));position_side='LONG' if qty>0 else 'SHORT';entry=_latest_entry(db,profile.user_id,profile.id,symbol)
                    cfg=db.scalar(select(SymbolStrategy).where(SymbolStrategy.user_id==profile.user_id,SymbolStrategy.profile_id==profile.id,SymbolStrategy.symbol==symbol,SymbolStrategy.enabled.is_(True),SymbolStrategy.mode=='AUTO_TRADE'))
                    market=str(cfg.market or '').upper() if cfg else None
                    item={'profile_id':str(profile.id),'market':market,'symbol':symbol,'position_side':position_side,'quantity':abs(qty),'entry_order_id':entry.broker_order_id if entry else None}
                    blockers=[]
                    if entry is None:blockers.append('OWNERSHIP_NOT_VERIFIED')
                    elif (entry.side=='BUY' and position_side!='LONG') or (entry.side=='SELL' and position_side!='SHORT'):blockers.append('POSITION_DIRECTION_MISMATCH')
                    if cfg is None:blockers.append('AUTO_TRADE_NOT_ENABLED')
                    if blockers:
                        result={'status':'EXIT_BLOCKED','reason':'|'.join(blockers)};results.append({**item,**result});_persist(db,scan,profile.user_id,profile,item,result);continue
                    entry_status=await broker.order_status(int(entry.broker_order_id))
                    broker_entry=entry_status.get('status') or {}
                    fill_verified,fill_source=_entry_fill_verified(entry,broker_entry,position_side,abs(qty))
                    item['entry_fill_source']=fill_source
                    if not fill_verified:
                        result={'status':'EXIT_BLOCKED','reason':'ENTRY_FILL_NOT_VERIFIED'};results.append({**item,**result});_persist(db,scan,profile.user_id,profile,item,result);continue
                    timeframe=_timeframe(cfg,default);minimum=_minimum_strength(cfg,default);candles=(await broker.candles(symbol,timeframe,200,sec_type='STK')).get('list',[]);signal=generate_signal(candles,timeframe=timeframe,market=market or 'STOCK');should_exit=_opposite(position_side,str(signal.decision).upper()) and float(signal.strength)>=minimum
                    item.update({'signal_decision':signal.decision,'signal_strength':signal.strength,'minimum_signal_strength':minimum})
                    if not should_exit:
                        result={'status':'HOLD','reason':'NO_EXIT_SIGNAL'};results.append({**item,**result});continue
                    scan.signals_count+=1;scan.approved_count+=1;close_side='SELL' if position_side=='LONG' else 'BUY';close_result=await broker.close_position(symbol=symbol,quantity=abs(qty),position_side=position_side,account_id=creds.get('account_id'));order_id=close_result.get('order_id')
                    result={'status':'EXIT_SUBMITTED','reason':'STRONG_OPPOSITE_SIGNAL','close_side':close_side,'broker_result':close_result}
                    if order_id is not None:
                        filled,final_status=await _verify_fill(broker,order_id,abs(qty));close_result['final_status']=final_status
                        if filled:result['status']='EXIT_EXECUTED';scan.executed_count+=1
                    results.append({**item,**result});_persist(db,scan,profile.user_id,profile,item,result)
            scan.status='COMPLETED';scan.finished_at=datetime.now(timezone.utc);db.commit();return {'status':'COMPLETED','purpose':'IBKR_PAPER_POSITION_LIFECYCLE_EXECUTION','execution_enabled':True,'evaluated':scan.symbols_count,'exit_signals':scan.signals_count,'exit_executed':scan.executed_count,'results':results}
        except Exception as exc:
            db.rollback();persisted=db.get(AutomationScan,scan.id)
            if persisted is not None:persisted.status='FAILED';persisted.error_message=_short(exc,500);persisted.finished_at=datetime.now(timezone.utc);db.commit()
            return {'status':'FAILED','error':_short(exc,500),'results':results}

async def ibkr_position_manager_loop(stop_event):
    while not stop_event.is_set():
        try:
            with SessionLocal() as db:state=get_or_create_state(db);wait=max(30,int(state.interval_seconds or 300));enabled=state.enabled and not state.killed and state.auto_execute_paper
            if enabled:await run_ibkr_position_manager()
            try:await asyncio.wait_for(stop_event.wait(),timeout=wait)
            except asyncio.TimeoutError:pass
        except Exception:
            try:await asyncio.wait_for(stop_event.wait(),timeout=30)
            except asyncio.TimeoutError:pass
