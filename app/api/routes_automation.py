from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.db.models.auth import User
from app.db.models.automation import AutomationScan
from app.db.session import get_db
from app.services.automation import get_or_create_state
from app.services.safe_automation import IBKR_CERTIFIED_MAX_SHARES_PER_ORDER, run_safe_scan

router=APIRouter(prefix="/automation",tags=["automation"])

class AutomationUpdate(BaseModel):
    enabled: bool
    simulation_execution: bool|None=None
    auto_execute_paper: bool|None=None
    interval_seconds: int=Field(300,ge=30,le=86400)
    symbols: list[str]=Field(default_factory=lambda:["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT"])


def _state_payload(s):
    return {"enabled":s.enabled,"killed":s.killed,"simulation_execution":s.auto_execute_paper,"interval_seconds":s.interval_seconds,"symbols":[x for x in s.symbols_csv.split(",") if x],"last_scan_at":s.last_scan_at,"next_scan_at":s.next_scan_at,"execution_policy":"CERTIFIED_ROUTES_ONLY","certified_routes":[{"provider":"MT5","environment":"DEMO"},{"provider":"IBKR","environment":"PAPER","max_shares_per_order":IBKR_CERTIFIED_MAX_SHARES_PER_ORDER}],"blocked_routes":{"BYBIT":"PROVIDER_EXECUTION_NOT_CERTIFIED"}}

@router.get("/state")
def state(_:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return _state_payload(get_or_create_state(db))

@router.put("/state")
def update(payload:AutomationUpdate,_:User=Depends(require_admin),db:Session=Depends(get_db)):
    s=get_or_create_state(db);s.enabled=payload.enabled
    requested=payload.simulation_execution if payload.simulation_execution is not None else payload.auto_execute_paper
    if requested is not None:s.auto_execute_paper=requested
    s.interval_seconds=payload.interval_seconds;s.symbols_csv=",".join(dict.fromkeys(x.strip().upper() for x in payload.symbols if x.strip()));db.commit();db.refresh(s);return _state_payload(s)

@router.post("/kill")
def kill(_:User=Depends(require_admin),db:Session=Depends(get_db)):
    s=get_or_create_state(db);s.killed=True;s.enabled=False;db.commit();db.refresh(s);return _state_payload(s)

@router.post("/restart")
def restart(_:User=Depends(require_admin),db:Session=Depends(get_db)):
    s=get_or_create_state(db);s.killed=False;s.enabled=True;s.next_scan_at=None;db.commit();db.refresh(s);return _state_payload(s)

@router.post("/scan-now")
async def scan_now(_:User=Depends(require_admin)):
    return await run_safe_scan()

@router.get("/scans")
def scans(limit:int=50,_:User=Depends(get_current_user),db:Session=Depends(get_db)):
    rows=list(db.scalars(select(AutomationScan).order_by(AutomationScan.started_at.desc()).limit(min(max(limit,1),200))).all())
    return [{"id":r.id,"status":r.status,"symbols_count":r.symbols_count,"accounts_count":r.accounts_count,"signals_count":r.signals_count,"approved_count":r.approved_count,"executed_count":r.executed_count,"error_message":r.error_message,"started_at":r.started_at,"finished_at":r.finished_at} for r in rows]
