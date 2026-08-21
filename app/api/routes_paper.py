from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.models.paper import PaperOrder, PaperPosition, PaperWallet
from app.db.models.signal import RiskProfile, Signal
from app.db.session import get_db
from app.market_data.bybit import BybitPublicMarketData
from app.services.paper_execution import build_execution_plan, exit_trigger, position_pnl

router=APIRouter(prefix="/paper",tags=["paper"])

def _account(db,user,profile_id):
    p=db.get(BrokerProfile,profile_id)
    if p is None: raise HTTPException(404,"account not found")
    if user.role!="ADMIN" and p.user_id!=user.id: raise HTTPException(403,"account access denied")
    if p.provider!="ATLAS_PAPER": raise HTTPException(400,"account is not an ATLAS PAPER profile")
    return p

def _wallet(db,profile_id):
    w=db.scalar(select(PaperWallet).where(PaperWallet.profile_id==profile_id))
    if w is None: w=PaperWallet(profile_id=profile_id);db.add(w);db.commit();db.refresh(w)
    return w

async def _price(symbol):
    s=get_settings(); market=BybitPublicMarketData(s.bybit_public_base_url,s.market_data_timeout_seconds)
    snap=await market.get_tickers(category="linear",symbols=(symbol,))
    if not snap.tickers: raise HTTPException(502,"market price unavailable")
    return snap.tickers[0].last_price

@router.get("/{profile_id}/summary")
def summary(profile_id:uuid.UUID,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    _account(db,user,profile_id);w=_wallet(db,profile_id);ps=list(db.scalars(select(PaperPosition).where(PaperPosition.profile_id==profile_id)).all());os=list(db.scalars(select(PaperOrder).where(PaperOrder.profile_id==profile_id).order_by(PaperOrder.created_at.desc()).limit(100)).all())
    unreal=sum(position_pnl(side=p.side,quantity=p.quantity,entry_price=p.entry_price,mark_price=p.mark_price) for p in ps)
    return {"profile_id":profile_id,"starting_balance":w.starting_balance,"cash_balance":w.cash_balance,"equity":w.cash_balance+sum(p.mark_price*p.quantity for p in ps),"realized_pnl":w.realized_pnl,"unrealized_pnl":unreal,"positions":[{"id":p.id,"signal_id":p.signal_id,"symbol":p.symbol,"side":p.side,"quantity":p.quantity,"entry_price":p.entry_price,"mark_price":p.mark_price,"unrealized_pnl":position_pnl(side=p.side,quantity=p.quantity,entry_price=p.entry_price,mark_price=p.mark_price),"stop_loss":p.stop_loss,"take_profit":p.take_profit,"opened_at":p.opened_at} for p in ps],"orders":[{"id":o.id,"signal_id":o.signal_id,"symbol":o.symbol,"side":o.side,"quantity":o.quantity,"fill_price":o.fill_price,"notional":o.notional,"status":o.status,"exit_reason":o.exit_reason,"realized_pnl":o.realized_pnl,"created_at":o.created_at} for o in os]}

@router.post("/{profile_id}/execute/{signal_id}")
async def execute(profile_id:uuid.UUID,signal_id:uuid.UUID,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    account=_account(db,user,profile_id); signal=db.get(Signal,signal_id)
    if signal is None or signal.profile_id!=account.id: raise HTTPException(404,"signal not found")
    if signal.risk_status!="APPROVED": raise HTTPException(409,"signal is not risk approved")
    if signal.decision not in {"BUY","SELL"}: raise HTTPException(409,"signal has no executable direction")
    if db.scalar(select(PaperOrder).where(PaperOrder.signal_id==signal.id)) is not None: raise HTTPException(409,"signal already executed")
    risk=db.scalar(select(RiskProfile).where(RiskProfile.name=="Default")); positions=list(db.scalars(select(PaperPosition).where(PaperPosition.profile_id==profile_id)).all())
    if risk and len(positions)>=risk.max_open_positions: raise HTTPException(409,"maximum open positions reached")
    w=_wallet(db,profile_id);price=await _price(signal.symbol);equity=w.cash_balance+sum(p.mark_price*p.quantity for p in positions)
    plan=build_execution_plan(decision=signal.decision,price=price,equity=equity,available_cash=w.cash_balance,risk_per_trade_pct=(risk.risk_per_trade_pct if risk else 1.0))
    if plan.notional>w.cash_balance: raise HTTPException(409,"insufficient paper cash")
    w.cash_balance-=plan.notional
    order=PaperOrder(profile_id=profile_id,signal_id=signal.id,symbol=signal.symbol,side=plan.side,quantity=plan.quantity,fill_price=price,notional=plan.notional,status="FILLED")
    pos=PaperPosition(profile_id=profile_id,signal_id=signal.id,symbol=signal.symbol,side=plan.side,quantity=plan.quantity,entry_price=price,mark_price=price,stop_loss=plan.stop_loss,take_profit=plan.take_profit)
    db.add_all([order,pos]);db.commit();db.refresh(pos)
    return {"status":"FILLED","position_id":pos.id,"symbol":pos.symbol,"side":pos.side,"quantity":pos.quantity,"fill_price":price,"stop_loss":pos.stop_loss,"take_profit":pos.take_profit,"risk_amount":plan.risk_amount}

@router.post("/{profile_id}/refresh")
async def refresh(profile_id:uuid.UUID,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    _account(db,user,profile_id);w=_wallet(db,profile_id);ps=list(db.scalars(select(PaperPosition).where(PaperPosition.profile_id==profile_id)).all());closed=[]
    for p in ps:
        price=await _price(p.symbol);p.mark_price=price;trigger=exit_trigger(side=p.side,mark_price=price,stop_loss=p.stop_loss,take_profit=p.take_profit)
        if trigger:
            pnl=position_pnl(side=p.side,quantity=p.quantity,entry_price=p.entry_price,mark_price=price);w.cash_balance+=p.quantity*price;w.realized_pnl+=pnl
            db.add(PaperOrder(profile_id=profile_id,signal_id=p.signal_id,symbol=p.symbol,side="SELL" if p.side=="BUY" else "BUY",quantity=p.quantity,fill_price=price,notional=p.quantity*price,status="FILLED",exit_reason=trigger,realized_pnl=pnl));closed.append({"symbol":p.symbol,"reason":trigger,"pnl":pnl});db.delete(p)
    db.commit();return {"status":"REFRESHED","closed":closed}

@router.post("/{profile_id}/positions/{position_id}/close")
async def close(profile_id:uuid.UUID,position_id:uuid.UUID,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    _account(db,user,profile_id);p=db.get(PaperPosition,position_id)
    if p is None or p.profile_id!=profile_id: raise HTTPException(404,"position not found")
    w=_wallet(db,profile_id);price=await _price(p.symbol);pnl=position_pnl(side=p.side,quantity=p.quantity,entry_price=p.entry_price,mark_price=price);w.cash_balance+=p.quantity*price;w.realized_pnl+=pnl
    db.add(PaperOrder(profile_id=profile_id,signal_id=p.signal_id,symbol=p.symbol,side="SELL" if p.side=="BUY" else "BUY",quantity=p.quantity,fill_price=price,notional=p.quantity*price,status="FILLED",exit_reason="MANUAL",realized_pnl=pnl));db.delete(p);db.commit();return {"status":"CLOSED","symbol":p.symbol,"exit_price":price,"realized_pnl":pnl}
