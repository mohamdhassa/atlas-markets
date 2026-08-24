from __future__ import annotations
import json,uuid
from collections import defaultdict
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.brokers.bybit_private import BybitPrivateClient
from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.session import get_db

router=APIRouter(tags=['portfolio','performance'])

def _accounts(db:Session,user:User):
 q=select(BrokerProfile).where(BrokerProfile.provider.in_(['BYBIT','MT5']),BrokerProfile.is_enabled.is_(True));q=q if user.role=='ADMIN' else q.where(BrokerProfile.user_id==user.id);return list(db.scalars(q).all())
def _bybit(p):
 s=get_settings();base=s.bybit_public_base_url if p.environment=='LIVE' else s.bybit_demo_base_url if p.environment=='DEMO' else s.bybit_testnet_base_url
 return BybitPrivateClient(decrypt_secret(p.api_key_encrypted or ''),decrypt_secret(p.api_secret_encrypted or ''),base,s.market_data_timeout_seconds)
def _mt5(p):
 if not p.credential_blob_encrypted:raise RuntimeError('MT5 credentials missing')
 c=json.loads(decrypt_secret(p.credential_blob_encrypted));return Mt5BridgeClient(c.get('bridge_url') or 'http://host.docker.internal:8765',c.get('bridge_token'),get_settings().market_data_timeout_seconds)
def _f(v):
 try:return float(v or 0)
 except:return 0.0
def _market(provider):return 'CRYPTO' if provider=='BYBIT' else 'FX'
def _stats(rows):
 pnls=[_f(r.get('pnl')) for r in rows];wins=[x for x in pnls if x>0];loss=[x for x in pnls if x<0];gross_win=sum(wins);gross_loss=abs(sum(loss));return {'trades':len(pnls),'realized_pnl':round(sum(pnls),2),'wins':len(wins),'losses':len(loss),'win_rate':round((len(wins)/len(pnls)*100) if pnls else 0,2),'average_win':round(gross_win/len(wins),2) if wins else 0,'average_loss':round(sum(loss)/len(loss),2) if loss else 0,'profit_factor':round(gross_win/gross_loss,3) if gross_loss else (999.0 if gross_win else 0)}

@router.get('/portfolio')
async def portfolio(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 out=[];positions=[];errors=[]
 for p in _accounts(db,user):
  if not p.credentials_configured:continue
  try:
   if p.provider=='BYBIT':
    c=_bybit(p);w=await c.wallet();pos=await c.positions();a=(w.get('list') or [{}])[0];equity=_f(a.get('totalEquity'));available=_f(a.get('totalAvailableBalance'));plist=[x for x in pos.get('list',[]) if _f(x.get('size'))]
    for x in plist:positions.append({'profile_id':str(p.id),'account':p.account_label,'provider':'BYBIT','market':'CRYPTO','symbol':x.get('symbol'),'side':x.get('side'),'quantity':_f(x.get('size')),'entry_price':_f(x.get('avgPrice')),'mark_price':_f(x.get('markPrice')),'unrealized_pnl':_f(x.get('unrealisedPnl')),'leverage':x.get('leverage')})
   else:
    c=_mt5(p);a=await c.account();pos=await c.positions();equity=_f(a.get('equity'));available=_f(a.get('margin_free'));plist=pos.get('list',[])
    for x in plist:positions.append({'profile_id':str(p.id),'account':p.account_label,'provider':'MT5','market':'FX','symbol':x.get('symbol'),'side':'BUY' if int(x.get('type',0))==0 else 'SELL','quantity':_f(x.get('volume')),'entry_price':_f(x.get('price_open')),'mark_price':_f(x.get('price_current')),'unrealized_pnl':_f(x.get('profit')),'ticket':x.get('ticket')})
   out.append({'id':str(p.id),'label':p.account_label,'provider':p.provider,'market':_market(p.provider),'environment':p.environment,'active':p.is_active,'status':p.last_connection_status,'equity':equity,'available':available,'positions':len(plist),'unrealized_pnl':round(sum(_f(x.get('unrealisedPnl') if p.provider=='BYBIT' else x.get('profit')) for x in plist),2)})
  except Exception as exc:errors.append({'profile_id':str(p.id),'account':p.account_label,'error':str(exc)[:240]})
 return {'accounts':out,'positions':positions,'errors':errors,'totals':{'equity':round(sum(x['equity'] for x in out),2),'available':round(sum(x['available'] for x in out),2),'unrealized_pnl':round(sum(x['unrealized_pnl'] for x in out),2),'open_positions':len(positions)}}

@router.get('/performance/broker-native')
async def broker_performance(days:int=Query(default=30,ge=1,le=366),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 account_rows=[];trade_rows=[];errors=[]
 for p in _accounts(db,user):
  if not p.credentials_configured:continue
  market=_market(p.provider)
  try:
   if p.provider=='BYBIT':
    c=_bybit(p);wallet=await c.wallet();hist=await c.closed_pnl(100);a=(wallet.get('list') or [{}])[0];equity=_f(a.get('totalEquity'));available=_f(a.get('totalAvailableBalance'))
    for x in hist.get('list',[]):trade_rows.append({'profile_id':str(p.id),'account':p.account_label,'market':market,'provider':'BYBIT','symbol':x.get('symbol'),'pnl':_f(x.get('closedPnl')),'time':int(x.get('updatedTime') or x.get('createdTime') or 0),'side':x.get('side')})
   else:
    c=_mt5(p);a=await c.account();hist=await c.history_deals(days);equity=_f(a.get('equity'));available=_f(a.get('margin_free'))
    for x in hist.get('list',[]):
     if not x.get('symbol') or int(x.get('entry',0))==0:continue
     trade_rows.append({'profile_id':str(p.id),'account':p.account_label,'market':market,'provider':'MT5','symbol':x.get('symbol'),'pnl':_f(x.get('profit'))+_f(x.get('commission'))+_f(x.get('swap')),'time':int(x.get('time_msc') or int(x.get('time',0))*1000),'side':'BUY' if int(x.get('type',0))==0 else 'SELL'})
   account_rows.append({'profile_id':str(p.id),'account':p.account_label,'provider':p.provider,'market':market,'environment':p.environment,'equity':equity,'available':available})
  except Exception as exc:errors.append({'profile_id':str(p.id),'account':p.account_label,'error':str(exc)[:240]})
 by_account=defaultdict(list);by_market=defaultdict(list);by_symbol=defaultdict(list)
 for r in trade_rows:by_account[r['profile_id']].append(r);by_market[r['market']].append(r);by_symbol[f"{r['market']}:{r['symbol']}"].append(r)
 accounts=[]
 for a in account_rows:accounts.append({**a,**_stats(by_account[a['profile_id']])})
 markets=[]
 for market in ['CRYPTO','FX','STOCK','ETF','METAL','COMMODITY']:
  rows=by_market[market];equity=sum(a['equity'] for a in account_rows if a['market']==market);markets.append({'market':market,'equity':round(equity,2),**_stats(rows),'connected_accounts':sum(1 for a in account_rows if a['market']==market)})
 symbols=[{'market':k.split(':',1)[0],'symbol':k.split(':',1)[1],**_stats(v)} for k,v in sorted(by_symbol.items())]
 series=defaultdict(float)
 for r in trade_rows:
  if r['time']:
   d=datetime.fromtimestamp(r['time']/1000,tz=timezone.utc).date().isoformat();series[d]+=_f(r['pnl'])
 return {'days':days,'overall':{'equity':round(sum(a['equity'] for a in account_rows),2),**_stats(trade_rows)},'markets':markets,'accounts':accounts,'symbols':symbols,'daily':[{'date':d,'realized_pnl':round(v,2)} for d,v in sorted(series.items())],'trades':sorted(trade_rows,key=lambda x:x['time'],reverse=True)[:200],'errors':errors}

@router.get('/execution-readiness')
async def execution_readiness(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 accounts=_accounts(db,user);by=lambda p:[a for a in accounts if a.provider==p and a.last_connection_status=='CONNECTED']
 return {'CRYPTO':{'market_data':True,'broker':bool(by('BYBIT')),'demo_execution':any(a.environment in {'DEMO','TESTNET'} for a in by('BYBIT'))},'FX':{'market_data':True,'broker':bool(by('MT5')),'demo_execution':any(a.environment=='DEMO' for a in by('MT5'))},'STOCK':{'market_data':False,'broker':False,'demo_execution':False},'ETF':{'market_data':False,'broker':False,'demo_execution':False},'METAL':{'market_data':False,'broker':bool(by('MT5')),'demo_execution':False},'COMMODITY':{'market_data':False,'broker':bool(by('MT5')),'demo_execution':False}}
