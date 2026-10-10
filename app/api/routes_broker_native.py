from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,Query,HTTPException
from pydantic import BaseModel, Field
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user, require_admin
from app.brokers.bybit_private import BybitPrivateClient
from app.brokers.mt5_bridge import Mt5BridgeClient
from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.models.bybit_inventory import BybitManagedInventory
from app.db.models.automation import AutomationAction
from app.db.models.ibkr_statement import IbkrStatementEvidence
from app.db.models.symbol_strategy import SymbolStrategy
from app.db.session import get_db
from app.services.provider_reads import isolated_provider_read
from app.services.ibkr_ledger_history import merge_saved_fills
from app.services.trade_news_context import attach_trade_news

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
 _creds(p);s=get_settings();url=(s.mt5_bridge_url or '').strip()
 if not url:raise RuntimeError('MT5 execution node is pending and has not been configured on the ATLAS server')
 return Mt5BridgeClient(url,(s.mt5_bridge_token or '').strip() or None,s.market_data_timeout_seconds)
def _ibkr(p):
 c=_creds(p);return IbkrBridgeClient(c.get('bridge_url') or 'http://host.docker.internal:8766',c.get('bridge_token'),get_settings().market_data_timeout_seconds)
def _f(v):
 try:return float(v or 0)
 except:return 0.0

def _execution_time_ms(row):
 for key in ('time','executed_at','execution_time','timestamp','datetime'):
  value=row.get(key)
  if value in (None,''):continue
  if isinstance(value,(int,float)):
   number=int(value);return number*1000 if number and number<10_000_000_000 else number
  text=str(value).strip()
  if text.isdigit():
   number=int(text);return number*1000 if number and number<10_000_000_000 else number
  try:return int(datetime.fromisoformat(text.replace('Z','+00:00')).timestamp()*1000)
  except ValueError:continue
 return 0
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

def _side(value):
 return 'BUY' if str(value or '').upper() in {'BUY','BOT','LONG'} else 'SELL' if str(value or '').upper() in {'SELL','SLD','SHORT'} else str(value or '').upper()

def _iso_ms(value):
 return datetime.fromtimestamp(value/1000,tz=timezone.utc).isoformat() if value else None

def _pair_execution_lots(rows):
 """Add entry/duration context without replacing broker-reported P&L."""
 inventory=defaultdict(lambda:{'BUY':[],'SELL':[]})
 for row in sorted(rows,key=lambda x:x.get('time') or 0):
  key=(str(row.get('profile_id')),str(row.get('symbol') or '').upper())
  side=_side(row.get('side')); qty=_f(row.get('quantity')); price=_f(row.get('execution_price'))
  if side not in {'BUY','SELL'} or qty<=0 or price<=0:continue
  opposite='SELL' if side=='BUY' else 'BUY'
  if not row.get('pnl_available') and not row.get('closed_trade'):
   inventory[key][side].append([qty,price,int(row.get('time') or 0)])
   continue
  remaining=qty;cost=0.0;matched=0.0;opened=[]
  while remaining>1e-12 and inventory[key][opposite]:
   lot=inventory[key][opposite][0];take=min(remaining,lot[0]);cost+=take*lot[1];matched+=take;opened.append(lot[2]);lot[0]-=take;remaining-=take
   if lot[0]<=1e-12:inventory[key][opposite].pop(0)
  if matched>0:
   row['entry_price']=cost/matched;row['invested_amount']=cost;row['opened_at']=min(opened) if opened else 0
  elif row.get('entry_price'):
   row['invested_amount']=qty*_f(row.get('entry_price'))
  row['closed_at']=int(row.get('time') or 0)
  row['duration_seconds']=max(0,(row['closed_at']-row.get('opened_at',0))//1000) if row.get('opened_at') else None
  pnl=_f(row.get('pnl')) if row.get('pnl_available') else None
  row['return_pct']=round(pnl/row['invested_amount']*100,4) if pnl is not None and row.get('invested_amount') else None
  row['opened_at_iso']=_iso_ms(row.get('opened_at'));row['closed_at_iso']=_iso_ms(row.get('closed_at'))
 return rows

def _trade_context(db,user,rows):
 profile_ids={r.get('profile_id') for r in rows if r.get('profile_id')};symbols={str(r.get('symbol') or '').upper() for r in rows}
 strategies=list(db.scalars(select(SymbolStrategy).where(SymbolStrategy.profile_id.in_(profile_ids))).all()) if profile_ids else []
 strategy_map={(str(x.profile_id),str(x.symbol).upper()):x for x in strategies}
 aq=select(AutomationAction).where(AutomationAction.broker_profile_id.in_(profile_ids)) if profile_ids else None
 if aq is not None and user.role!='ADMIN':aq=aq.where(AutomationAction.user_id==user.id)
 actions=list(db.scalars(aq.order_by(AutomationAction.created_at.desc())).all()) if aq is not None else []
 by_order={(str(x.broker_profile_id),str(x.broker_order_id)):x for x in actions if x.broker_order_id}
 by_symbol=defaultdict(list)
 for x in actions:by_symbol[(str(x.broker_profile_id),str(x.symbol).upper())].append(x)
 for row in rows:
  key=(str(row.get('profile_id')),str(row.get('symbol') or '').upper());action=by_order.get((key[0],str(row.get('broker_order_id') or '')))
  if action is None:
   candidates=by_symbol.get(key,[]);stamp=int(row.get('time') or 0)
   action=min(candidates,key=lambda x:abs(int(x.created_at.timestamp()*1000)-stamp)) if candidates and stamp else None
  strategy=strategy_map.get(key);exact=bool(action and row.get('broker_order_id') and str(action.broker_order_id)==str(row.get('broker_order_id')))
  row['attribution']='ATLAS_EXACT_ORDER' if exact else 'BROKER_REPORTED'
  row['strategy']={'id':str(strategy.id),'mode':strategy.mode,'timeframe':strategy.timeframe,'risk_per_trade_pct':strategy.risk_per_trade_pct,'minimum_signal_strength':strategy.minimum_signal_strength} if strategy else None
  row['decision']={'side':action.side,'status':action.status,'reason':action.reason,'sizing_policy':action.sizing_policy,'created_at':action.created_at.isoformat()} if action else None

 return attach_trade_news(db, rows)

@router.get('/portfolio')
@isolated_provider_read
async def portfolio(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 out=[];positions=[];errors=[]
 for p in _accounts(db,user):
  if not p.credentials_configured:continue
  try:
   symmap=_symbol_market_map(db,p.id)
   if p.provider=='BYBIT':
    c=_bybit(p);w=await c.wallet();a=(w.get('list') or [{}])[0];equity=_f(a.get('totalEquity'));available=_f(a.get('totalAvailableBalance'))
    # ATLAS executes Bybit Spot. Show ATLAS-managed Spot inventory here instead of derivatives positions.
    managed=list(db.scalars(select(BybitManagedInventory).where(BybitManagedInventory.broker_profile_id==p.id,BybitManagedInventory.user_id==p.user_id,BybitManagedInventory.managed_quantity>0)).all())
    plist=managed
    for x in managed:
     positions.append({'profile_id':str(p.id),'account':p.account_label,'provider':'BYBIT','market':'CRYPTO','symbol':x.symbol,'side':'LONG','quantity':_f(x.managed_quantity),'entry_price':_f(x.average_entry_price),'mark_price':None,'unrealized_pnl':None,'leverage':None,'position_source':'ATLAS_MANAGED_SPOT'})
    unrealized=0
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
   out.append({'id':str(p.id),'label':p.account_label,'provider':p.provider,'market':_account_market(p.provider),'environment':p.environment,'active':p.is_active,'status':'CONNECTED','data_status':'FRESH','observed_at':datetime.now(timezone.utc).isoformat(),'equity':equity,'available':available,'positions':len(plist),'unrealized_pnl':round(unrealized,2)})
  except Exception as exc:
   errors.append({'profile_id':str(p.id),'account':p.account_label,'provider':p.provider,'error':str(exc)[:240]})
   if p.provider=='IBKR':
    out.append({'id':str(p.id),'label':p.account_label,'provider':p.provider,'market':_account_market(p.provider),'environment':p.environment,'active':p.is_active,'status':'UNAVAILABLE','data_status':'STALE','observed_at':p.last_sync_at.isoformat() if p.last_sync_at else None,'equity':p.equity_usd,'available':None,'positions':None,'unrealized_pnl':None})
 fresh=[x for x in out if x.get('data_status')=='FRESH']
 return {'accounts':out,'positions':positions,'errors':errors,'totals':{'partial':bool(errors),'equity':round(sum(x['equity'] for x in fresh),2),'available':round(sum(x['available'] for x in fresh),2),'unrealized_pnl':round(sum(x['unrealized_pnl'] for x in fresh),2),'open_positions':len(positions)}}

@router.get('/broker-orders')
@isolated_provider_read
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
@isolated_provider_read
async def broker_performance(days:int=Query(default=30,ge=1,le=366),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 account_rows=[];trade_rows=[];errors=[]
 for p in _accounts(db,user):
  if not p.credentials_configured:continue
  try:
   symmap=_symbol_market_map(db,p.id)
   if p.provider=='BYBIT':
    c=_bybit(p);wallet=await c.wallet();hist=await c.closed_pnl(100);a=(wallet.get('list') or [{}])[0];equity=_f(a.get('totalEquity'));available=_f(a.get('totalAvailableBalance'));account_market='CRYPTO'
    for x in hist.get('list',[]):trade_rows.append({'profile_id':str(p.id),'account':p.account_label,'market':'CRYPTO','provider':'BYBIT','symbol':x.get('symbol'),'pnl':_f(x.get('closedPnl')),'pnl_available':True,'time':int(x.get('updatedTime') or x.get('createdTime') or 0),'side':x.get('side')})
    # Bybit Spot Testnet closed-PnL history does not represent ATLAS Spot fills reliably.
    # Persisted EXECUTED automation actions are the authoritative ATLAS execution audit trail.
    existing_ids={str(x.get('broker_order_id') or '') for x in trade_rows if x.get('provider')=='BYBIT' and str(x.get('profile_id'))==str(p.id)}
    actions=list(db.scalars(select(AutomationAction).where(AutomationAction.broker_profile_id==p.id,AutomationAction.user_id==p.user_id,AutomationAction.provider=='BYBIT',AutomationAction.status=='EXECUTED').order_by(AutomationAction.created_at.desc())).all())
    bybit_report_rows=[]
    for x in actions:
     oid=str(x.broker_order_id or '')
     if oid and oid in existing_ids:continue
     fills=[]
     if oid:
      try:fills=(await c.spot_executions(order_id=oid,limit=100)).get('list') or []
      except Exception:fills=[]
     exec_qty=sum(_f(f.get('execQty')) for f in fills)
     exec_value=sum(_f(f.get('execValue')) for f in fills)
     exec_fee=sum(_f(f.get('execFee')) for f in fills)
     price=(exec_value/exec_qty) if exec_qty>0 and exec_value>0 else None
     row={'profile_id':str(p.id),'account':p.account_label,'market':x.market or 'CRYPTO','provider':'BYBIT','symbol':x.symbol,'pnl':0,'pnl_available':False,'time':int(x.created_at.timestamp()*1000) if x.created_at else 0,'side':x.side,'execution_price':price,'quantity':exec_qty or _f(x.quantity),'notional':exec_value or None,'commission':exec_fee if fills else None,'commission_currency':(fills[0].get('feeCurrency') if fills else None),'broker_order_id':oid or None,'execution_id':(fills[0].get('execId') if len(fills)==1 else None),'execution_source':'BYBIT_SPOT_EXECUTION' if fills else 'ATLAS_AUTOMATION_ACTION'}
     bybit_report_rows.append(row)
     if oid:existing_ids.add(oid)
    # Match ATLAS-managed Spot sells to preceding buys for reporting P&L only.
    inventory=defaultdict(list)
    for row in sorted(bybit_report_rows,key=lambda z:z.get('time') or 0):
     side=str(row.get('side') or '').upper();qty=_f(row.get('quantity'));price=row.get('execution_price')
     if not price or qty<=0:continue
     key=str(row.get('symbol') or '').upper()
     if side=='BUY':inventory[key].append([qty,_f(price),int(row.get('time') or 0)])
     elif side=='SELL':
      remaining=qty;cost=0.0;matched=0.0
      while remaining>1e-12 and inventory[key]:
       lot=inventory[key][0];take=min(remaining,lot[0]);cost+=take*lot[1];matched+=take;row.setdefault('opened_at',lot[2]);lot[0]-=take;remaining-=take
       if lot[0]<=1e-12:inventory[key].pop(0)
      if matched>0 and remaining<=1e-12:
       row['pnl']=round(qty*_f(price)-cost,8);row['pnl_available']=True;row['entry_price']=cost/matched if matched else None;row['invested_amount']=cost
    trade_rows.extend(bybit_report_rows)
   elif p.provider=='MT5':
    c=_mt5(p);a=await c.account();hist=await c.history_deals(days);equity=_f(a.get('equity'));available=_f(a.get('margin_free'));account_market='FX+METAL+COMMODITY'
    for x in hist.get('list',[]):
     if not x.get('symbol') or int(x.get('entry',0))==0:continue
     symbol=str(x.get('symbol')).upper();market=symmap.get(symbol,_mt5_market(symbol));trade_rows.append({'profile_id':str(p.id),'account':p.account_label,'market':market,'provider':'MT5','symbol':symbol,'pnl':_f(x.get('profit'))+_f(x.get('commission'))+_f(x.get('swap')),'pnl_available':True,'time':int(x.get('time_msc') or int(x.get('time',0))*1000),'side':'BUY' if int(x.get('type',0))==0 else 'SELL'})
   else:
    c=_ibkr(p);a=await c.account();hist=await c.executions(days);equity=_f(a.get('equity'));available=_f(a.get('available'));account_market='STOCK+ETF'
    for x in hist.get('list',[]):
     symbol=str(x.get('symbol') or '').upper();market=symmap.get(symbol,'STOCK');pnl_available=bool(x.get('pnl_available')) and x.get('realized_pnl') is not None;trade_rows.append({'profile_id':str(p.id),'account':p.account_label,'market':market,'provider':'IBKR','symbol':symbol,'pnl':_f(x.get('realized_pnl')) if pnl_available else 0,'pnl_available':pnl_available,'time':_execution_time_ms(x),'side':x.get('side'),'execution_price':_f(x.get('price')),'quantity':_f(x.get('quantity')),'commission':_f(x.get('commission')) if x.get('commission') is not None else None,'broker_order_id':x.get('order_id'),'execution_id':x.get('execution_id') or x.get('exec_id')})
   account_rows.append({'profile_id':str(p.id),'account':p.account_label,'provider':p.provider,'market':account_market,'environment':p.environment,'broker_equity':equity,'equity':equity,'available':available,'starting_capital':_f(p.simulation_capital_override_usd) if p.simulation_capital_override_usd is not None else None})
  except Exception as exc:errors.append({'profile_id':str(p.id),'account':p.account_label,'provider':p.provider,'error':str(exc)[:240]})
 for p in _accounts(db,user):
  if p.provider!='IBKR' or not p.credentials_configured:continue
  actions=list(db.scalars(select(AutomationAction).where(AutomationAction.broker_profile_id==p.id,AutomationAction.user_id==p.user_id,AutomationAction.provider=='IBKR',AutomationAction.environment==p.environment,AutomationAction.status.in_(['EXECUTED','EXIT_EXECUTED'])).order_by(AutomationAction.created_at)).all())
  try:account_id=_creds(p).get('account_id')
  except Exception:continue
  statement_rows=list(db.scalars(select(IbkrStatementEvidence).where(
   IbkrStatementEvidence.broker_profile_id==p.id,IbkrStatementEvidence.user_id==p.user_id)).all())
  statements={}
  for evidence in statement_rows:
   if not isinstance(evidence,IbkrStatementEvidence):continue
   try:statements[str(evidence.action_id)]=json.loads(evidence.evidence_json)
   except (ValueError,TypeError):continue
  merge_saved_fills(trade_rows,actions,p,account_id,statements)
 _pair_execution_lots(trade_rows)
 _trade_context(db,user,trade_rows)
 for row in trade_rows:
  stamp=int(row.get('time') or 0)
  row['executed_at']=datetime.fromtimestamp(stamp/1000,tz=timezone.utc).isoformat() if stamp else None
 by_account=defaultdict(list);by_market=defaultdict(list);by_symbol=defaultdict(list)
 for r in trade_rows:by_account[r['profile_id']].append(r);by_market[r['market']].append(r);by_symbol[f"{r['market']}:{r['symbol']}"].append(r)
 accounts=[]
 for a in account_rows:
  stats=_stats(by_account[a['profile_id']]);start=a.get('starting_capital');realized=stats['realized_pnl']
  accounts.append({**a,**stats,'strategy_value':round(start+realized,2) if start is not None else None,'net_gain':realized,'return_pct':round(realized/start*100,2) if start else None})
 markets=[]
 for market in MARKETS:
  rows=by_market[market];markets.append({'market':market,'equity':round(sum(a['equity'] for a in account_rows if market in a['market'].split('+')),2),**_stats(rows),'connected_accounts':sum(1 for a in account_rows if market in a['market'].split('+'))})
 symbols=[{'market':k.split(':',1)[0],'symbol':k.split(':',1)[1],**_stats(v)} for k,v in sorted(by_symbol.items())];series=defaultdict(float)
 for r in trade_rows:
  if r.get('pnl_available') and r.get('time'):
   d=datetime.fromtimestamp(r['time']/1000,tz=timezone.utc).date().isoformat();series[d]+=_f(r['pnl'])
 starting=sum(a.get('starting_capital') or 0 for a in accounts);overall_stats=_stats(trade_rows)
 return {'days':days,'overall':{'broker_equity':round(sum(a['equity'] for a in account_rows),2),'equity':round(sum(a['equity'] for a in account_rows),2),'starting_capital':round(starting,2),'strategy_value':round(starting+overall_stats['realized_pnl'],2),**overall_stats},'markets':markets,'accounts':accounts,'symbols':symbols,'daily':[{'date':d,'realized_pnl':round(v,2)} for d,v in sorted(series.items())],'trades':sorted(trade_rows,key=lambda x:x.get('time') or 0,reverse=True)[:200],'errors':errors,'notes':{'IBKR':'Broker-reported P&L is authoritative. Entry, duration, strategy and news context are attached only when matching evidence exists.','attribution':'ATLAS_EXACT_ORDER requires an exact persisted broker order match; other rows remain BROKER_REPORTED.','news':'News is contextual when stored for the same symbol within 24 hours before execution; it is not claimed as causal.'}}

@router.get('/execution-readiness')
async def execution_readiness(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 accounts=_accounts(db,user);by=lambda p:[a for a in accounts if a.provider==p and a.last_connection_status=='CONNECTED'];mt5=by('MT5');ibkr=by('IBKR');bybit=by('BYBIT')
 return {'CRYPTO':{'market_data':True,'broker':bool(bybit),'simulation_execution':any(a.environment in {'DEMO','TESTNET'} for a in bybit)},'FX':{'market_data':bool(mt5),'broker':bool(mt5),'simulation_execution':any(a.environment=='DEMO' for a in mt5)},'STOCK':{'market_data':bool(ibkr),'broker':bool(ibkr),'simulation_execution':any(a.environment=='PAPER' for a in ibkr)},'ETF':{'market_data':bool(ibkr),'broker':bool(ibkr),'simulation_execution':any(a.environment=='PAPER' for a in ibkr)},'METAL':{'market_data':bool(mt5),'broker':bool(mt5),'simulation_execution':any(a.environment=='DEMO' for a in mt5)},'COMMODITY':{'market_data':bool(mt5),'broker':bool(mt5),'simulation_execution':any(a.environment=='DEMO' for a in mt5)}}


class IbkrStatementImport(BaseModel):
 profile_id: UUID
 xml: str = Field(min_length=1, max_length=5_000_000)
 timezone: str = Field(min_length=1, max_length=64)
 mapping: dict[UUID, list[str]] = Field(default_factory=dict, max_length=1000)
 apply: bool = False


@router.post('/performance/ibkr-statement/import')
def import_ibkr_statement(payload: IbkrStatementImport, user: User = Depends(require_admin), db: Session = Depends(get_db)):
 from app.services.ibkr_statement_import import reconcile_statement
 profile = db.get(BrokerProfile, payload.profile_id, with_for_update=payload.apply)
 if profile is None or profile.provider != 'IBKR' or profile.environment != 'PAPER':
  raise HTTPException(404, 'IBKR Paper profile not found')
 try:
  account_id = _creds(profile).get('account_id')
 except Exception:
  raise HTTPException(422, 'Profile account configuration unavailable') from None
 try:
  result = reconcile_statement(db, profile, account_id, payload.xml, payload.timezone,
                               payload.mapping, user.id, apply=payload.apply)
  if payload.apply: db.commit()
  return result
 except ValueError as exc:
  db.rollback()
  raise HTTPException(422, str(exc)) from None
