from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user, require_admin
from app.db.models.auth import User, UserRole
from app.db.models.automation import AutomationAction, AutomationScan
from app.db.models.broker import BrokerProfile
from app.db.models.symbol_strategy import SymbolStrategy
from app.db.session import get_db
from app.services.automation import get_or_create_state
from app.services.safe_automation import CERTIFIED_AUTOMATION_ROUTES, IBKR_CERTIFIED_MAX_SHARES_PER_ORDER, run_safe_scan

router=APIRouter(prefix="/automation",tags=["automation"])
class AutomationUpdate(BaseModel):
    enabled:bool
    simulation_execution:bool|None=None
    auto_execute_paper:bool|None=None
    interval_seconds:int=Field(300,ge=30,le=86400)
    symbols:list[str]=Field(default_factory=lambda:["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT"])
def _state_payload(s):return {"enabled":s.enabled,"killed":s.killed,"simulation_execution":s.auto_execute_paper,"interval_seconds":s.interval_seconds,"symbols":[x for x in s.symbols_csv.split(",") if x],"last_scan_at":s.last_scan_at,"next_scan_at":s.next_scan_at,"execution_policy":"CERTIFIED_ROUTES_ONLY","certified_routes":[{"provider":"MT5","environment":"DEMO"},{"provider":"IBKR","environment":"PAPER","max_shares_per_order":IBKR_CERTIFIED_MAX_SHARES_PER_ORDER}],"blocked_routes":{"BYBIT":"PROVIDER_EXECUTION_NOT_CERTIFIED"}}
@router.get('/state')
def state(_:User=Depends(get_current_user),db:Session=Depends(get_db)):return _state_payload(get_or_create_state(db))
@router.put('/state')
def update(payload:AutomationUpdate,_:User=Depends(require_admin),db:Session=Depends(get_db)):
    s=get_or_create_state(db);s.enabled=payload.enabled;requested=payload.simulation_execution if payload.simulation_execution is not None else payload.auto_execute_paper
    if requested is not None:s.auto_execute_paper=requested
    s.interval_seconds=payload.interval_seconds;s.symbols_csv=','.join(dict.fromkeys(x.strip().upper() for x in payload.symbols if x.strip()));db.commit();db.refresh(s);return _state_payload(s)
@router.post('/kill')
def kill(_:User=Depends(require_admin),db:Session=Depends(get_db)):
    s=get_or_create_state(db);s.killed=True;s.enabled=False;db.commit();db.refresh(s);return _state_payload(s)
@router.post('/restart')
def restart(_:User=Depends(require_admin),db:Session=Depends(get_db)):
    s=get_or_create_state(db);s.killed=False;s.enabled=True;s.next_scan_at=None;db.commit();db.refresh(s);return _state_payload(s)
@router.post('/scan-now')
async def scan_now(_:User=Depends(require_admin)):return await run_safe_scan()

@router.post('/monitor-scan')
def monitor_scan(
    provider:str|None=Query(default=None,max_length=32),
    markets:list[str]|None=Query(default=None),
    user:User=Depends(require_admin),
    db:Session=Depends(get_db),
):
    provider_filter=str(provider or '').upper() or None
    market_filter={str(x).upper() for x in (markets or []) if str(x).strip()}
    q=select(SymbolStrategy,BrokerProfile).join(BrokerProfile,BrokerProfile.id==SymbolStrategy.profile_id).where(SymbolStrategy.user_id==user.id,SymbolStrategy.enabled.is_(True))
    if provider_filter:q=q.where(BrokerProfile.provider==provider_filter)
    if market_filter:q=q.where(SymbolStrategy.market.in_(sorted(market_filter)))
    rows=list(db.execute(q.order_by(SymbolStrategy.market,SymbolStrategy.symbol)).all())
    items=[]
    for cfg,profile in rows:
        reason=None;status='PASS'
        if not profile.is_enabled:status,reason='BLOCK','ACCOUNT_DISABLED'
        elif not profile.is_active:status,reason='BLOCK','ACCOUNT_NOT_ACTIVE'
        elif not profile.credentials_configured:status,reason='BLOCK','CREDENTIALS_NOT_CONFIGURED'
        elif profile.last_connection_status!='CONNECTED':status,reason='BLOCK',f'ACCOUNT_{profile.last_connection_status or "NOT_CONNECTED"}'
        elif (str(profile.provider).upper(),str(profile.environment).upper()) not in CERTIFIED_AUTOMATION_ROUTES:
            status='BLOCK';reason='PROVIDER_EXECUTION_NOT_CERTIFIED' if str(profile.provider).upper()=='BYBIT' else 'AUTOMATION_ROUTE_NOT_CERTIFIED'
        elif cfg.mode!='AUTO_TRADE':status,reason='SKIP',f'MODE_{cfg.mode}'
        items.append({'market':cfg.market,'symbol':cfg.symbol,'provider':profile.provider,'environment':profile.environment,'mode':cfg.mode,'preflight':status,'reason':reason,'execution':'NONE'})
    return {
        'status':'COMPLETED','monitored_only':True,'execution_enabled':False,'purpose':'WORKSPACE_ROUTE_MONITOR_NO_EXECUTION',
        'scope':{'provider':provider_filter,'markets':sorted(market_filter)},
        'checked_count':sum(x['preflight'] in {'PASS','BLOCK'} for x in items),
        'pass_count':sum(x['preflight']=='PASS' for x in items),
        'block_count':sum(x['preflight']=='BLOCK' for x in items),
        'skip_count':sum(x['preflight']=='SKIP' for x in items),
        'items':items,
    }
@router.get('/scans')
def scans(limit:int=50,_:User=Depends(get_current_user),db:Session=Depends(get_db)):
    rows=list(db.scalars(select(AutomationScan).order_by(AutomationScan.started_at.desc()).limit(min(max(limit,1),200))).all());return [{"id":r.id,"status":r.status,"symbols_count":r.symbols_count,"accounts_count":r.accounts_count,"signals_count":r.signals_count,"approved_count":r.approved_count,"executed_count":r.executed_count,"error_message":r.error_message,"started_at":r.started_at,"finished_at":r.finished_at} for r in rows]
@router.get('/actions')
def actions(limit:int=100,provider:str|None=None,status:str|None=None,symbol:str|None=None,scan_id:uuid.UUID|None=None,current:User=Depends(get_current_user),db:Session=Depends(get_db)):
    q=select(AutomationAction)
    if current.role!=UserRole.ADMIN:q=q.where(AutomationAction.user_id==current.id)
    if provider:q=q.where(AutomationAction.provider==provider.upper())
    if status:q=q.where(AutomationAction.status==status.upper())
    if symbol:q=q.where(AutomationAction.symbol==symbol.upper())
    if scan_id:q=q.where(AutomationAction.scan_id==scan_id)
    rows=list(db.scalars(q.order_by(AutomationAction.created_at.desc()).limit(min(max(limit,1),500))).all())
    return [{"id":r.id,"scan_id":r.scan_id,"user_id":r.user_id,"broker_profile_id":r.broker_profile_id,"provider":r.provider,"environment":r.environment,"market":r.market,"symbol":r.symbol,"side":r.side,"status":r.status,"reason":r.reason,"quantity":r.quantity,"sizing_policy":r.sizing_policy,"broker_order_id":r.broker_order_id,"broker_position_id":r.broker_position_id,"created_at":r.created_at} for r in rows]
