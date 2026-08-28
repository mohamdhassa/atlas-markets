from __future__ import annotations

from collections import defaultdict
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.routes_phase35 import unified_performance
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.models.symbol_strategy import SymbolStrategy
from app.db.session import get_db

router = APIRouter(tags=['strategies', 'performance'])


def _f(v):
    try:return float(v or 0)
    except (TypeError,ValueError):return 0.0


@router.get('/strategies/performance')
async def strategy_performance(days:int=Query(default=30,ge=1,le=366),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    q=select(SymbolStrategy).order_by(SymbolStrategy.market,SymbolStrategy.symbol)
    if user.role!='ADMIN':q=q.where(SymbolStrategy.user_id==user.id)
    strategies=list(db.scalars(q).all())
    profiles={str(p.id):p for p in db.scalars(select(BrokerProfile)).all()}
    perf=await unified_performance(days=days,user=user,db=db)
    buckets=defaultdict(list)
    for t in perf.get('trades',[]):
        if t.get('pnl_available'):
            buckets[(str(t.get('profile_id')),str(t.get('market') or '').upper(),str(t.get('symbol') or '').upper())].append(t)
    rows=[]
    for s in strategies:
        trades=buckets.get((str(s.profile_id),str(s.market).upper(),str(s.symbol).upper()),[])
        pnl=sum(_f(t.get('realized_pnl')) for t in trades);wins=sum(1 for t in trades if _f(t.get('realized_pnl'))>0);losses=sum(1 for t in trades if _f(t.get('realized_pnl'))<0)
        p=profiles.get(str(s.profile_id));count=len(trades);wr=(wins/count*100) if count else 0
        if count<3:health='INSUFFICIENT_DATA'
        elif pnl<0 and wr<35:health='POOR'
        elif pnl<0:health='WATCH'
        else:health='HEALTHY'
        rows.append({'strategy_id':str(s.id),'profile_id':str(s.profile_id),'account':p.account_label if p else 'Unknown','provider':p.provider if p else None,'environment':p.environment if p else None,'market':s.market,'symbol':s.symbol,'mode':s.mode,'enabled':s.enabled,'timeframe':s.timeframe,'minimum_signal_strength':s.minimum_signal_strength,'risk_per_trade_pct':s.risk_per_trade_pct,'stop_atr_multiplier':s.stop_atr_multiplier,'take_profit_rr':s.take_profit_rr,'max_position_notional_pct':s.max_position_notional_pct,'closed_trades':count,'wins':wins,'losses':losses,'win_rate':round(wr,2),'realized_pnl':round(pnl,2),'health':health})
    rows.sort(key=lambda x:(x['health']!='POOR',x['realized_pnl']))
    evaluated=[x for x in rows if x['closed_trades']]
    return {'days':days,'summary':{'configured':len(rows),'auto_trade':sum(1 for x in rows if x['mode']=='AUTO_TRADE' and x['enabled']),'evaluated':len(evaluated),'poor':sum(1 for x in evaluated if x['health']=='POOR'),'watch':sum(1 for x in evaluated if x['health']=='WATCH'),'healthy':sum(1 for x in evaluated if x['health']=='HEALTHY')},'strategies':rows,'methodology':{'attribution':'Closed trades are matched to configured strategy by profile_id + market + symbol.','poor':'At least 3 closed trades, negative realized P&L and win rate below 35%.','watch':'At least 3 closed trades with negative realized P&L but win rate at least 35%.','safety':'Performance labels are advisory only. ATLAS does not automatically promote, disable or increase risk.'}}
