from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.brokers.bybit_private import BybitPrivateClient
from app.brokers.mt5_bridge import Mt5BridgeClient
from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.models.symbol_strategy import SymbolStrategy
from app.db.session import get_db

router=APIRouter(tags=['portfolio','performance'])
MARKETS=['CRYPTO','FX','STOCK','ETF','METAL','COMMODITY']

def _accounts(db:Session,user:User):
 q=select(BrokerProfile).where(BrokerProfile.provider.in_(['BYBIT','MT5','IBKR']),BrokerProfile.is_enabled.is_(True));q=q if user.role=='ADMIN' else q.where(BrokerProfile.user_id==user.id);return list(db.scalars(q).all())
def _creds(p):
 if not p.credential_blob_encrypted:raise RuntimeError(f'{p.provider} bridge configuration missing')
 return json.loads(decrypt_secret(p.credential_blob_encrypted))
def _bybit(p):
 s=get_settings();base=s.bybit_public_base_url if p.environment=='LIVE' else s.bybit_demo_base_url if p.environment=='DEMO' else s.bybit_testnet_base_url
 return BybitPrivateClient(decrypt_secret(p.api_key_encrypted or ''),decrypt_secret(p.api_secret_encrypted or ''),base,s.market_data_timeout_seconds)
def _mt5(p):
 c=_creds(p);return Mt5BridgeClient(c.get('bridge_url') or 'http://host.docker.internal:8765',c.get('bridge_token'),get_settings().market_data_timeout_seconds)
def _ibkr(p):
 c=_creds(p);return IbkrBridgeClient(c.get('bridge_url') or 'http://host.docker.internal:8766',c.get('bridge_token'),get_settings().market_data_timeout_seconds)
def _f(v):
 try:return float(v or 0)
 except:return 0.0
def _mt5_market(symbol):
 s=str(symbol or '').upper().replace('/','')
 if s.startswith(('XAU','XAG','XPT','XPD')):return 'METAL'
 if any(x in s for x in ('USOIL','UKOIL','WTI','BRENT','XTI','XBR','NATGAS','NGAS')):return 'COMMODITY'
 return 'FX'
def _symbol_market_map(db,profile_id):
 rows=list(db.scalars(select(SymbolStrategy).where(SymbolStrategy.profile_id==profile_id,SymbolStrategy.enabled.is_(True))).all());return {str(x.symbol).upper():x.market for x in rows}
def _account_market(provider):return 'CRYPTO' if provider=='BYBIT' else 'STOCK+ETF' if provider=='IBKR' else 'FX+METAL+COMMODITY'
def _stats(rows):
 pnl_rows=[r for r in rows if r.get('pnl_available',True)];pnls=[_f(r.get('pnl')) for r in pnl_rows];wins=[x for x in pnls if x>0];loss=[x for x in pnls if x<0];gross_win=sum(wins);gross_loss=abs(sum(loss));return {'trades':len(rows),'pnl_trades':len(pnl_rows),'realized_pnl':round(sum(pnls),2),'wins':len(wins),'losses':len(loss),'win_rate':round((len(wins)/len(pnls)*100) if pnls else 0,2),'average_win':round(gross_win/len(wins),2) if wins else 0,'average_loss':round(sum(loss)/len(loss),2) if loss else 0,'profit_factor':round(gross_win/gross_loss,3) if gross_loss else (999.0 if gross_win else 0),'pnl_complete':len(pnl_rows)==len(rows)}

@router.get('/portfolio')
async def portfolio(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 out=[];positions=[];errors=[]
 for p in _accounts(db,user):
  if not p.credentials_configured:continue
  try:
   symmap=_symbol_market_map(db,p.id)
   if p.provider=='BYBIT':
    c=_bybit(p);w=await c.wallet();pos=await c.positions();a=(w.get('list') or [{}])[0];equity=_f(a.get('totalEquity'));available=_f(a.get('totalAvailableBalance'));plist=[x for x in pos.get('list',[]) if _f(x.get('size'))]
    for x in plist:positions.append({'profile_id':str(p.id),'account':p.account_label,'provider':'BYBIT','market':'CRYPTO','symbol':x.get('symbol'),'side':x.get('side'),'quantity':_f(x.get('size')),'entry_price':_f(x.get('avgPrice')),'mark_price':_f(x.get('markPrice')),'unrealized_pnl':_f(x.get('unrealisedPnl')),'leverage':x.get('leverage')})
    unrealized=sum(_f(x.get('unrealisedPnl')) for x in plist)
   elif p.provider=='MT5':
    c=_mt5(p);a=await c.account();pos=await c.positions();equity=_f(a.get('equity'));available=_f(a.get('margin_free'));plist=pos.get('list',[])
    for x in plist:
     market=symmap.get(str(x.get('symbol') or '').upper(),_mt5_market(x.get('symbol')));positions.append({'profile_id':str(p.id),'account':p.account_label,'provider':'MT5','market':market,'symbol':x.get('symbol'),'side':'BUY' if int(x.get('type',0))==0 else 'SELL','quantity':_f(x.get('volume')),'entry_price':_f(x.get('price_open')),'mark_price':_f(x.get('price_current')),'unrealized_pnl':_f(x.get('profit')),'leverage':None,'ticket':x.get('ticket')})
    unrealized=sum(_f(x.get('profit')) for x in plist)
   else:
    c=_ibkr(p);a=await c.account();pos=await c.positions();equity=_f(a.get('equity'));available=_f(a.get('available'));plist=[x for x in pos.get('list',[]) if _f(x.get('quantity'))]
    for x in plist:
     symbol=str(x.get('symbol') or '').upper();market=symmap.get(symbol,'STOCK');positions.append({'profile_id':str(p.id),'account':p.account_label,'provider':'IBKR','market':market,'symbol':symbol,'side':'LONG' if _f(x.get('quantity'))>0 else 'SHORT','quantity':abs(_f(x.get('quantity'))),'entry_price':_f(x.get('avg_cost')),'mark_price':None,'unrealized_pnl':None,'leverage':None})
    unrealized=0
   out.append({'id':str(p.id),'label':p.account_label,'provider':p.provider,'market':_account_market(p.provider),'environment':p.environment,'active':p.is_active,'status':p.last_connection_status,'equity':equity,'available':available,'positions':len(plist),'unrealized_pnl':round(unrealized,2)})
  except Exception as exc:errors.append({'profile_id':str(p.id),'account':p.account_label,'provider':p.provider,'error':str(exc)[:240]})
 return {'accounts':out,'positions':positions,'errors':errors,'totals':{'equity':round(sum(x['equity'] for x in out),2),'available':round(sum(x['available'] for x in out),2),'unrealized_pnl':round(sum(x['unrealized_pnl'] for x in out),2),'open_positions':len(positions)}}

@router.get('/broker-orders')
async def broker_orders(limit:int=Query(default=100,ge=1,le=200),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 accounts=[];orders=[];errors=[]
 for p in _accounts(db,user):
  if not p.credentials_configured:continue
  try:
   symmap=_symbol_market_map(db,p.id)
   if p.provider=='BYBIT':
    c=_bybit(p);current=await c.open_orders();history=await c.order_history(limit);seen=set();rows=(current.get('list') or [])+(history.get('list') or [])
    for x in rows:
     oid=str(x.get('orderId') or x.get('orderLinkId') or '');key=oid or f"{x.get('symbol')}:{x.get('createdTime')}:{x.get('orderStatus')}"
     if key in seen:continue
     seen.add(key);orders.append({'profile_id':str(p.id),'account':p.account_label,'provider':'BYBIT','market':'CRYPTO','environment':p.environment,'order_id':oid,'symbol':x.get('symbol'),'side':x.get('side'),'type':x.get('orderType'),'quantity':_f(x.get('qty')),'filled_quantity':_f(x.get('cumExecQty')),'price':_f(x.get('price') or x.get('avgPrice')),'stop_loss':_f(x.get('stopLoss')) or None,'take_profit':_f(x.get('takeProfit')) or None,'status':x.get('orderStatus') or 'UNKNOWN','time':int(x.get('updatedTime') or x.get('createdTime') or 0)})
   elif p.provider=='MT5':
    c=_mt5(p);raw=await c.orders();rows=raw.get('list',[]) if isinstance(raw,dict) else []
    for x in rows:
     typ=int(x.get('type',0));symbol=str(x.get('symbol') or '').upper();orders.append({'profile_id':str(p.id),'account':p.account_label,'provider':'MT5','market':symmap.get(symbol,_mt5_market(symbol)),'environment':p.environment,'order_id':str(x.get('ticket') or ''),'symbol':symbol,'side':'BUY' if typ in {0,2,4,6} else 'SELL','type':x.get('type_description') or str(x.get('type')),'quantity':_f(x.get('volume_current') or x.get('volume_initial')),'filled_quantity':max(0,_f(x.get('volume_initial'))-_f(x.get('volume_current'))),'price':_f(x.get('price_open')),'stop_loss':_f(x.get('sl')) or None,'take_profit':_f(x.get('tp')) or None,'status':x.get('state_description') or str(x.get('state') or 'OPEN'),'time':int(x.get('time_setup_msc') or int(x.get('time_setup',0))*1000)})
   else:
    c=_ibkr(p);raw=await c.orders();rows=raw.get('list',[])
    for x in rows:
     symbol=str(x.get('symbol') or '').upper();orders.append({'profile_id':str(p.id),'account':p.account_label,'provider':'IBKR','market':symmap.get(symbol,'STOCK'),'environment':p.environment,'order_id':str(x.get('order_id') or ''),'symbol':symbol,'side':x.get('side'),'type':x.get('type'),'quantity':_f(x.get('quantity')),'filled_quantity':0,'price':_f(x.get('limit_price')) or None,'stop_loss':None,'take_profit':None,'status':x.get('status') or 'OPEN','time':0})
   accounts.append({'id':str(p.id),'label':p.account_label,'provider':p.provider,'market':_account_market(p.provider),'environment':p.environment})
  except Exception as exc:errors.append({'profile_id':str(p.id),'account':p.account_label,'provider':p.provider,'error':str(exc)[:240]})
 orders.sort(key=lambda x:x.get('time') or 0,reverse=True);return {'accounts':accounts,'orders':orders[:limit],'errors':errors,'count':min(len(orders),limit)}

@router.get('/performance/broker-native')
async def broker_performance(days:int=Query(default=30,ge=1,le=366),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 account_rows=[];trade_rows=[];errors=[]
 for p in _accounts(db,user):
  if not p.credentials_configured:continue
  try:
   symmap=_symbol_market_map(db,p.id)
   if p.provider=='BYBIT':
    c=_bybit(p);wallet=await c.wallet();hist=await c.closed_pnl(100);a=(wallet.get('list') or [{}])[0];equity=_f(a.get('totalEquity'));available=_f(a.get('totalAvailableBalance'));account_market='CRYPTO'
    for x in hist.get('list',[]):trade_rows.append({'profile_id':str(p.id),'account':p.account_label,'market':'CRYPTO','provider':'BYBIT','symbol':x.get('symbol'),'pnl':_f(x.get('closedPnl')),'pnl_available':True,'time':int(x.get('updatedTime') or x.get('createdTime') or 0),'side':x.get('side')})
   elif p.provider=='MT5':
    c=_mt5(p);a=await c.account();hist=await c.history_deals(days);equity=_f(a.get('equity'));available=_f(a.get('margin_free'));account_market='FX+METAL+COMMODITY'
    for x in hist.get('list',[]):
     if not x.get('symbol') or int(x.get('entry',0))==0:continue
     symbol=str(x.get('symbol')).upper();market=symmap.get(symbol,_mt5_market(symbol));trade_rows.append({'profile_id':str(p.id),'account':p.account_label,'market':market,'provider':'MT5','symbol':symbol,'pnl':_f(x.get('profit'))+_f(x.get('commission'))+_f(x.get('swap')),'pnl_available':True,'time':int(x.get('time_msc') or int(x.get('time',0))*1000),'side':'BUY' if int(x.get('type',0))==0 else 'SELL'})
   else:
    c=_ibkr(p);a=await c.account();hist=await c.executions(days);equity=_f(a.get('equity'));available=_f(a.get('available'));account_market='STOCK+ETF'
    for x in hist.get('list',[]):
     symbol=str(x.get('symbol') or '').upper();market=symmap.get(symbol,'STOCK');trade_rows.append({'profile_id':str(p.id),'account':p.account_label,'market':market,'provider':'IBKR','symbol':symbol,'pnl':0,'pnl_available':False,'time':0,'side':x.get('side'),'execution_price':_f(x.get('price')),'quantity':_f(x.get('quantity'))})
   account_rows.append({'profile_id':str(p.id),'account':p.account_label,'provider':p.provider,'market':account_market,'environment':p.environment,'equity':equity,'available':available})
  except Exception as exc:errors.append({'profile_id':str(p.id),'account':p.account_label,'provider':p.provider,'error':str(exc)[:240]})
 by_account=defaultdict(list);by_market=defaultdict(list);by_symbol=defaultdict(list)
 for r in trade_rows:by_account[r['profile_id']].append(r);by_market[r['market']].append(r);by_symbol[f"{r['market']}:{r['symbol']}"].append(r)
 accounts=[{**a,**_stats(by_account[a['profile_id']])} for a in account_rows]
 markets=[]
 for market in MARKETS:
  rows=by_market[market];markets.append({'market':market,'equity':round(sum(a['equity'] for a in account_rows if market in a['market'].split('+')),2),**_stats(rows),'connected_accounts':sum(1 for a in account_rows if market in a['market'].split('+'))})
 symbols=[{'market':k.split(':',1)[0],'symbol':k.split(':',1)[1],**_stats(v)} for k,v in sorted(by_symbol.items())];series=defaultdict(float)
 for r in trade_rows:
  if r.get('pnl_available') and r.get('time'):
   d=datetime.fromtimestamp(r['time']/1000,tz=timezone.utc).date().isoformat();series[d]+=_f(r['pnl'])
 return {'days':days,'overall':{'equity':round(sum(a['equity'] for a in account_rows),2),**_stats(trade_rows)},'markets':markets,'accounts':accounts,'symbols':symbols,'daily':[{'date':d,'realized_pnl':round(v,2)} for d,v in sorted(series.items())],'trades':sorted(trade_rows,key=lambda x:x.get('time') or 0,reverse=True)[:200],'errors':errors,'notes':{'IBKR':'Execution history is available; realized P&L requires commission/P&L pairing and is intentionally not fabricated.'}}

@router.get('/execution-readiness')
async def execution_readiness(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 accounts=_accounts(db,user);by=lambda p:[a for a in accounts if a.provider==p and a.last_connection_status=='CONNECTED'];mt5=by('MT5');ibkr=by('IBKR');bybit=by('BYBIT')
 return {'CRYPTO':{'market_data':True,'broker':bool(bybit),'simulation_execution':any(a.environment in {'DEMO','TESTNET'} for a in bybit)},'FX':{'market_data':bool(mt5),'broker':bool(mt5),'simulation_execution':any(a.environment=='DEMO' for a in mt5)},'STOCK':{'market_data':bool(ibkr),'broker':bool(ibkr),'simulation_execution':any(a.environment=='PAPER' for a in ibkr)},'ETF':{'market_data':bool(ibkr),'broker':bool(ibkr),'simulation_execution':any(a.environment=='PAPER' for a in ibkr)},'METAL':{'market_data':bool(mt5),'broker':bool(mt5),'simulation_execution':any(a.environment=='DEMO' for a in mt5)},'COMMODITY':{'market_data':bool(mt5),'broker':bool(mt5),'simulation_execution':any(a.environment=='DEMO' for a in mt5)}}
