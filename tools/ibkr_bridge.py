from __future__ import annotations
import argparse,os,threading,time,math
from functools import wraps
from datetime import datetime,timedelta,timezone
from fastapi import FastAPI,HTTPException,Header
from pydantic import BaseModel
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
import uvicorn

class State(EWrapper,EClient):
 def __init__(self):
  self.account_requests={}
  self.connection_epoch=0;self.request_epochs={};self.server_connected=None;self.server_changed_at=None;self.read_failures={};self.read_retry_at={};self.read_state_lock=threading.Lock()
  EClient.__init__(self,self);self.next_id=None;self.accounts=[];self.values={};self.positions=[];self.open_orders=[];self.executions=[];self.commissions={};self.errors=[];self.quotes={};self.bars={};self.contracts={};self.order_statuses={};self.whatif_results={};self._events={}
 def _event(self,k):return self._events.setdefault(k,threading.Event())
 def nextValidId(self,orderId):
  self.next_id=orderId
  if self.server_connected is None:self.server_connected=True
  self._event('connected').set()
 def managedAccounts(self,accountsList):self.accounts=[x for x in accountsList.split(',') if x]
 def accountSummary(self,reqId,account,tag,value,currency):
  values=self.account_requests.get(reqId)
  if values is not None:values[(account,tag)]=(value,currency)
 def accountSummaryEnd(self,reqId):
  if reqId in self.account_requests:self._event(f'acct:{reqId}').set()
 def position(self,account,contract,pos,avgCost):self.positions.append({'account':account,'symbol':contract.symbol,'sec_type':contract.secType,'exchange':contract.exchange,'currency':contract.currency,'quantity':float(pos),'avg_cost':float(avgCost)})
 def positionEnd(self):self._event('positions').set()
 def openOrder(self,orderId,contract,order,orderState):
  self.open_orders.append({'order_id':orderId,'symbol':contract.symbol,'sec_type':contract.secType,'side':order.action,'type':order.orderType,'quantity':float(order.totalQuantity),'limit_price':float(order.lmtPrice or 0),'aux_price':float(order.auxPrice or 0),'status':orderState.status})
  if getattr(order,'whatIf',False):
   def f(name):
    try:
     v=getattr(orderState,name,None);return float(v) if v not in {None,''} else None
    except:return None
   self.whatif_results[int(orderId)]={'status':getattr(orderState,'status',''),'init_margin_before':f('initMarginBefore'),'init_margin_change':f('initMarginChange'),'init_margin_after':f('initMarginAfter'),'maint_margin_before':f('maintMarginBefore'),'maint_margin_change':f('maintMarginChange'),'maint_margin_after':f('maintMarginAfter'),'equity_with_loan_before':f('equityWithLoanBefore'),'equity_with_loan_change':f('equityWithLoanChange'),'equity_with_loan_after':f('equityWithLoanAfter'),'commission':f('commission'),'min_commission':f('minCommission'),'max_commission':f('maxCommission'),'commission_currency':getattr(orderState,'commissionCurrency',''),'warning':getattr(orderState,'warningText','') or ''};self._event(f'whatif:{int(orderId)}').set()
 def openOrderEnd(self):self._event('orders').set()
 def orderStatus(self,orderId,status,filled,remaining,avgFillPrice,permId,parentId,lastFillPrice,clientId,whyHeld,mktCapPrice):
  self.order_statuses[int(orderId)]={'order_id':int(orderId),'status':status,'filled':float(filled),'remaining':float(remaining),'avg_fill_price':float(avgFillPrice or 0),'last_fill_price':float(lastFillPrice or 0),'perm_id':int(permId or 0),'client_id':int(clientId or 0),'why_held':whyHeld or ''};self._event(f'order-status:{int(orderId)}').set()
 def execDetails(self,reqId,contract,execution):self.executions.append({'execution_id':execution.execId,'order_id':execution.orderId,'account':execution.acctNumber,'symbol':contract.symbol,'sec_type':contract.secType,'side':execution.side,'quantity':float(execution.shares),'price':float(execution.price),'time':execution.time})
 def execDetailsEnd(self,reqId):self._event(f'exec:{reqId}').set()
 def commissionReport(self,report):
  realized=float(report.realizedPNL);realized=None if not math.isfinite(realized) or abs(realized)>1e100 else realized
  self.commissions[str(report.execId)]={'commission':float(report.commission or 0),'commission_currency':report.currency,'realized_pnl':realized}
 def tickPrice(self,reqId,tickType,price,attrib):
  q=self.quotes.setdefault(reqId,{})
  if tickType in {1,66}:q['bid']=float(price)
  elif tickType in {2,67}:q['ask']=float(price)
  elif tickType in {4,68}:q['last']=float(price)
  if q.get('last') or (q.get('bid') and q.get('ask')):self._event(f'quote:{reqId}').set()
 def tickSnapshotEnd(self,reqId):self._event(f'quote:{reqId}').set()
 def historicalData(self,reqId,bar):self.bars.setdefault(reqId,[]).append({'time':bar.date,'open':float(bar.open),'high':float(bar.high),'low':float(bar.low),'close':float(bar.close),'volume':float(bar.volume or 0)})
 def historicalDataEnd(self,reqId,start,end):self._event(f'bars:{reqId}').set()
 def contractDetails(self,reqId,details):
  c=details.contract;self.contracts.setdefault(reqId,[]).append({'con_id':c.conId,'symbol':c.symbol,'local_symbol':c.localSymbol,'sec_type':c.secType,'exchange':c.exchange,'primary_exchange':c.primaryExchange,'currency':c.currency,'long_name':details.longName,'min_tick':details.minTick})
 def contractDetailsEnd(self,reqId):self._event(f'contract:{reqId}').set()
 def error(self,reqId,errorCode,errorString,advancedOrderRejectJson=''):
  row={'id':reqId,'code':errorCode,'message':errorString}
  if advancedOrderRejectJson:row['advanced_reject']=advancedOrderRejectJson
  self.errors.append(row)
  self.errors=self.errors[-200:]
  if errorCode in {1100,2110,1101,1102}:
   self.server_connected=errorCode in {1101,1102}
   self.server_changed_at=datetime.now(timezone.utc).isoformat()
   global account_cache_at
   account_cache_at=0.0
   if self.server_connected:
    with self.read_state_lock:self.read_failures.clear();self.read_retry_at.clear()
   else:
    self.connection_epoch+=1
    for event in tuple(self._events.values()):event.set()
   print('IBKR_SERVER_RESTORED' if self.server_connected else 'IBKR_SERVER_UNAVAILABLE',flush=True)
  if reqId in self.account_requests:self._event(f'acct:{reqId}').set()
  if reqId>=0:
   self._event(f'order-status:{reqId}').set()
   if errorCode not in {2104,2106,2158,2186}:self._event(f'quote:{reqId}').set();self._event(f'bars:{reqId}').set();self._event(f'contract:{reqId}').set()

app=FastAPI(title='ATLAS IBKR Bridge');ib=State();cfg={}
account_lock=threading.Lock();account_cache=None;account_cache_at=0.0
def auth(x_atlas_bridge_token:str|None):
 token=cfg.get('token')
 if token and x_atlas_bridge_token!=token:raise HTTPException(401,'invalid bridge token')
def server_ready():return ib.isConnected() and ib.server_connected is not False
def require_server():
 if not server_ready():raise HTTPException(503,'IBKR_SERVER_UNAVAILABLE' if ib.isConnected() else 'IBKR_SOCKET_DISCONNECTED')
def read_ready(operation):
 require_server()
 with ib.read_state_lock:remaining=max(0,ib.read_retry_at.get(operation,0)-time.monotonic())
 if remaining:raise HTTPException(503,'IBKR_READ_RECOVERY_COOLDOWN',headers={'Retry-After':str(max(1,math.ceil(remaining)))})
def read_failed(operation):
 with ib.read_state_lock:
  attempts=min(5,ib.read_failures.get(operation,0)+1);ib.read_failures[operation]=attempts
  ib.read_retry_at[operation]=time.monotonic()+min(120,10*2**(attempts-1))
def read_succeeded(operation):
 with ib.read_state_lock:ib.read_failures.pop(operation,None);ib.read_retry_at.pop(operation,None)
read_locks={'positions':threading.Lock(),'orders':threading.Lock()}
def serial_read(operation):
 def decorate(fn):
  @wraps(fn)
  def wrapped(x_atlas_bridge_token=None):
   auth(x_atlas_bridge_token);read_ready(operation)
   if not read_locks[operation].acquire(blocking=False):raise HTTPException(503,'IBKR_READ_ALREADY_IN_PROGRESS')
   try:return fn(x_atlas_bridge_token)
   finally:read_locks[operation].release()
  return wrapped
 return decorate
def prepare(key):ib.request_epochs[key]=ib.connection_epoch;ib._event(key).clear()
def wait(key,seconds=10):
 e=ib._event(key)
 try:
  if not e.wait(seconds):
   read_failed(key.split(':')[0]);raise HTTPException(504,f'IBKR timeout waiting for {key}')
  require_server()
  if ib.request_epochs.get(key,ib.connection_epoch)!=ib.connection_epoch:raise HTTPException(503,'IBKR_READ_INTERRUPTED_BY_DISCONNECT')
  read_succeeded(key.split(':')[0])
 finally:ib.request_epochs.pop(key,None)
def rid():return int(time.time()*1000000)%2000000000
def contract(symbol,sec_type='STK',exchange='SMART',currency='USD'):
 c=Contract();c.symbol=symbol.upper();c.secType=sec_type;c.exchange=exchange;c.currency=currency;return c
def bar_size(tf):return {'1m':'1 min','5m':'5 mins','15m':'15 mins','30m':'30 mins','1h':'1 hour','4h':'4 hours','1d':'1 day'}.get(tf,'5 mins')
def duration(tf,limit):
 if tf=='1d':return f'{max(1,min(limit,365))} D'
 minutes={'1m':1,'5m':5,'15m':15,'30m':30,'1h':60,'4h':240}.get(tf,5)*max(limit,10)
 return f'{max(1,min(365,(minutes//1440)+2))} D'
def _connect_once():
 global account_cache,account_cache_at
 account_cache=None;account_cache_at=0.0
 ib._event('connected').clear();ib.next_id=None;ib.errors=[];ib.server_connected=None
 with ib.read_state_lock:ib.read_failures.clear();ib.read_retry_at.clear()
 try:
  if ib.isConnected():ib.disconnect();time.sleep(.25)
  ib.connect(cfg['host'],cfg['port'],clientId=cfg['client_id'])
  threading.Thread(target=ib.run,daemon=True).start()
  return ib._event('connected').wait(8)
 except Exception as exc:
  ib.errors.append({'id':-1,'code':'CONNECT_EXCEPTION','message':repr(exc)});return False
@app.on_event('startup')
def startup():
 for attempt in range(1,4):
  if _connect_once():
   ib.reqMarketDataType(3)
   print(f"ATLAS IBKR bridge connected to {cfg['host']}:{cfg['port']} client_id={cfg['client_id']} accounts={ib.accounts} market_data=DELAYED")
   return
  detail='; '.join(f"{e.get('code')}: {e.get('message')}" for e in ib.errors[-6:]) or 'No IBKR error callback was received. Check that TWS/IB Gateway is running, Enable ActiveX and Socket Clients is ON, socket port matches, and restart TWS after changing API settings.'
  print(f"IBKR connection attempt {attempt}/3 failed: {detail}")
  try:ib.disconnect()
  except Exception:pass
  time.sleep(1.5)
 raise RuntimeError(f"IBKR TWS/IB Gateway connection failed at {cfg['host']}:{cfg['port']} client_id={cfg['client_id']}. {detail}")
@app.on_event('shutdown')
def shutdown():ib.disconnect()
@app.get('/health')
def health(x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);return {'status':'ok' if server_ready() else 'degraded','connected':server_ready(),'socket_connected':ib.isConnected(),'server_connected':ib.server_connected,'server_changed_at':ib.server_changed_at,'accounts':ib.accounts,'host':cfg['host'],'port':cfg['port'],'client_id':cfg['client_id'],'simulation':cfg['simulation'],'errors':ib.errors[-12:]}
@app.get('/account')
def account(x_atlas_bridge_token:str|None=Header(default=None)):
 global account_cache,account_cache_at
 auth(x_atlas_bridge_token)
 read_ready('acct')
 if account_cache is not None and time.monotonic()-account_cache_at<2:return dict(account_cache)
 # Never queue more broker subscriptions while an earlier summary is pending.
 if not account_lock.acquire(blocking=False):raise HTTPException(503,'IBKR account summary already in progress; retry shortly')
 r=rid();key=f'acct:{r}';ib.account_requests[r]={};prepare(key)
 try:
  ib.reqAccountSummary(r,'All','NetLiquidation,TotalCashValue,AvailableFunds,BuyingPower');wait(key)
  if any(e.get('id')==r for e in ib.errors):raise HTTPException(502,'IBKR account summary rejected')
  acct=cfg.get('account_id') or (ib.accounts[0] if ib.accounts else '')
  values=ib.account_requests[r]
  tags={'equity':'NetLiquidation','cash':'TotalCashValue','available':'AvailableFunds','buying_power':'BuyingPower'}
  if any((acct,tag) not in values for tag in tags.values()):raise HTTPException(502,'IBKR account summary incomplete')
  result={'account_id':acct,'simulation':cfg['simulation'],'data_status':'FRESH','observed_at':datetime.now(timezone.utc).isoformat(),**{name:float(values[(acct,tag)][0]) for name,tag in tags.items()}}
  account_cache=dict(result);account_cache_at=time.monotonic();return result
 finally:
  try:ib.cancelAccountSummary(r)
  finally:
   ib.account_requests.pop(r,None);ib._events.pop(key,None);ib.request_epochs.pop(key,None);account_lock.release()
@app.get('/positions')
@serial_read('positions')
def positions(x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);read_ready('positions');ib.positions=[];prepare('positions');ib.reqPositions()
 try:wait('positions');return {'list':list(ib.positions)}
 finally:ib.cancelPositions()
@app.get('/orders')
@serial_read('orders')
def orders(x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);read_ready('orders');ib.open_orders=[];prepare('orders');ib.reqOpenOrders();wait('orders');return {'list':ib.open_orders}
@app.get('/orders/{order_id}/status')
def order_status(order_id:int,x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);status=ib.order_statuses.get(int(order_id));errs=[e for e in ib.errors if int(e.get('id') or -1)==int(order_id)]
 return {'order_id':int(order_id),'status':status,'errors':errs[-8:]}
@app.get('/executions')
def executions(days:int=30,x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);read_ready('exec');from ibapi.execution import ExecutionFilter
 r=rid();key=f'exec:{r}';ib.executions=[];ib.commissions={};f=ExecutionFilter();f.time=(datetime.now()-timedelta(days=max(1,min(days,30)))).strftime('%Y%m%d 00:00:00');prepare(key);ib.reqExecutions(r,f);wait(key);time.sleep(.35)
 rows=[]
 for x in ib.executions:
  c=ib.commissions.get(str(x['execution_id']),{});rows.append({**x,**c,'pnl_available':c.get('realized_pnl') is not None})
 return {'list':rows}
@app.get('/contract')
def contract_info(symbol:str,sec_type:str='STK',exchange:str='SMART',currency:str='USD',x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);read_ready('contract');r=rid();key=f'contract:{r}';ib.contracts[r]=[];prepare(key);ib.reqContractDetails(r,contract(symbol,sec_type,exchange,currency));wait(key,12);rows=ib.contracts.pop(r,[])
 if not rows:raise HTTPException(404,f'No IBKR contract found for {symbol}')
 exact=next((x for x in rows if x.get('symbol','').upper()==symbol.upper() and x.get('sec_type')==sec_type),rows[0]);return exact
@app.get('/quote')
def quote(symbol:str,sec_type:str='STK',exchange:str='SMART',currency:str='USD',x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);read_ready('quote');read_ready('bars')
 r=rid();key=f'quote:{r}';ib.quotes[r]={};prepare(key)
 ib.reqMktData(r,contract(symbol,sec_type,exchange,currency),'',True,False,[])
 try:
  wait(key,6)
 except HTTPException:
  require_server()
 q=ib.quotes.pop(r,{})
 # Snapshot requests can legitimately end without a usable last/bid/ask on
 # delayed IBKR data. Avoid cancelMktData for snapshot=True: IBKR ends the
 # request itself and cancelling afterwards can emit error 300.
 if not q.get('last') and q.get('bid') and q.get('ask'):
  q['last']=(q['bid']+q['ask'])/2
 if q.get('last') or q.get('bid') or q.get('ask'):
  return {'symbol':symbol.upper(),'sec_type':sec_type,'currency':currency,'source':'SNAPSHOT',**q}
 # Safe fallback: use the most recent completed historical trade bar. This is
 # market-data retrieval only; it does not change any execution/risk gate.
 hr=rid();hkey=f'bars:{hr}';ib.bars[hr]=[];prepare(hkey)
 ib.reqHistoricalData(hr,contract(symbol,sec_type,exchange,currency),'','2 D','5 mins','TRADES',1,1,False,[])
 try:
  wait(hkey,15)
 finally:
  try:ib.cancelHistoricalData(hr)
  except Exception:pass
 rows=ib.bars.pop(hr,[])
 if not rows:
  raise HTTPException(502,f'No IBKR quote or historical fallback returned for {symbol}')
 last=float(rows[-1]['close'])
 return {'symbol':symbol.upper(),'sec_type':sec_type,'currency':currency,'last':last,'source':'HISTORICAL_FALLBACK','bar_time':rows[-1].get('time')}
@app.get('/candles')
def candles(symbol:str,timeframe:str='5m',limit:int=200,sec_type:str='STK',exchange:str='SMART',currency:str='USD',x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);read_ready('bars');limit=max(10,min(limit,1000));r=rid();key=f'bars:{r}';ib.bars[r]=[];prepare(key);ib.reqHistoricalData(r,contract(symbol,sec_type,exchange,currency),'',duration(timeframe,limit),bar_size(timeframe),'TRADES',1,1,False,[]);
 try:wait(key,15);rows=ib.bars.pop(r,[])
 finally:
  ib.cancelHistoricalData(r);ib.bars.pop(r,None);ib._events.pop(key,None);ib.request_epochs.pop(key,None)
 if not rows:raise HTTPException(502,f'No IBKR candles returned for {symbol}')
 return {'symbol':symbol.upper(),'timeframe':timeframe,'list':rows[-limit:]}
class OrderPayload(BaseModel):
 symbol:str;side:str;quantity:float;order_type:str='MKT';limit_price:float|None=None;sec_type:str='STK';exchange:str='SMART';currency:str='USD';account_id:str|None=None
@app.post('/order-check')
def order_check(p:OrderPayload,x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);require_server()
 if not cfg['simulation']:raise HTTPException(403,'ATLAS IBKR bridge refuses Live Money execution')
 if p.quantity<=0:raise HTTPException(400,'quantity must be positive')
 if p.side.upper() not in {'BUY','SELL'}:raise HTTPException(400,'side must be BUY or SELL')
 if p.order_type.upper() not in {'MKT','LMT'}:raise HTTPException(400,'order_type must be MKT or LMT')
 oid=ib.next_id
 if oid is None:raise HTTPException(503,'IBKR next order id unavailable')
 ib.whatif_results.pop(int(oid),None);ib.errors=[e for e in ib.errors if int(e.get('id') or -1)!=int(oid)];prepare(f'whatif:{int(oid)}')
 o=Order();o.action=p.side.upper();o.totalQuantity=p.quantity;o.orderType=p.order_type.upper();o.transmit=True;o.whatIf=True;o.account=p.account_id or cfg.get('account_id') or '';o.tif='DAY'
 if hasattr(o,'eTradeOnly'):o.eTradeOnly=False
 if hasattr(o,'firmQuoteOnly'):o.firmQuoteOnly=False
 if o.orderType=='LMT':o.lmtPrice=float(p.limit_price or 0)
 ib.placeOrder(oid,contract(p.symbol,p.sec_type,p.exchange,p.currency),o);ib.next_id+=1
 ib._event(f'whatif:{int(oid)}').wait(8)
 require_server()
 if ib.request_epochs.get(f'whatif:{int(oid)}',ib.connection_epoch)!=ib.connection_epoch:raise HTTPException(503,'IBKR_READ_INTERRUPTED_BY_DISCONNECT')
 result=ib.whatif_results.pop(int(oid),None);errs=[e for e in ib.errors if int(e.get('id') or -1)==int(oid)]
 if result is None:return {'ok':False,'what_if':True,'simulation':True,'account_id':p.account_id or cfg.get('account_id'),'symbol':p.symbol.upper(),'side':p.side.upper(),'quantity':p.quantity,'order_type':p.order_type.upper(),'errors':errs[-8:],'reason':'NO_WHAT_IF_RESPONSE'}
 margin={k:result.get(k) for k in ('init_margin_before','init_margin_change','init_margin_after','maint_margin_before','maint_margin_change','maint_margin_after','equity_with_loan_before','equity_with_loan_change','equity_with_loan_after')}
 return {'ok':not bool(errs),'what_if':True,'simulation':True,'account_id':p.account_id or cfg.get('account_id'),'symbol':p.symbol.upper(),'side':p.side.upper(),'quantity':p.quantity,'order_type':p.order_type.upper(),'margin':margin,'commission':{'estimate':result.get('commission'),'min':result.get('min_commission'),'max':result.get('max_commission'),'currency':result.get('commission_currency')},'warning':result.get('warning'),'errors':errs[-8:]}
@app.post('/orders')
def place(p:OrderPayload,x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);require_server()
 if not cfg['simulation']:raise HTTPException(403,'ATLAS IBKR bridge refuses Live Money execution')
 if p.quantity<=0:raise HTTPException(400,'quantity must be positive')
 if p.side.upper() not in {'BUY','SELL'}:raise HTTPException(400,'side must be BUY or SELL')
 if p.order_type.upper() not in {'MKT','LMT'}:raise HTTPException(400,'order_type must be MKT or LMT')
 oid=ib.next_id
 if oid is None:raise HTTPException(503,'IBKR next order id unavailable')
 o=Order();o.action=p.side.upper();o.totalQuantity=p.quantity;o.orderType=p.order_type.upper();o.transmit=True;o.account=p.account_id or cfg.get('account_id') or '';o.tif='DAY'
 if hasattr(o,'eTradeOnly'):o.eTradeOnly=False
 if hasattr(o,'firmQuoteOnly'):o.firmQuoteOnly=False
 if o.orderType=='LMT':o.lmtPrice=float(p.limit_price or 0)
 ib.placeOrder(oid,contract(p.symbol,p.sec_type,p.exchange,p.currency),o);ib.next_id+=1
 return {'accepted':True,'simulation':True,'order_id':oid,'account_id':p.account_id or cfg.get('account_id'),'symbol':p.symbol.upper(),'side':p.side.upper(),'quantity':p.quantity,'order_type':p.order_type.upper()}
@app.delete('/orders/{order_id}')
def cancel(order_id:int,x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);require_server()
 if not cfg['simulation']:raise HTTPException(403,'ATLAS IBKR bridge refuses Live Money execution')
 ib.cancelOrder(order_id);return {'cancel_requested':True,'order_id':order_id,'simulation':True}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--host',default=os.getenv('ATLAS_IBKR_HOST','127.0.0.1'));p.add_argument('--port',type=int,default=int(os.getenv('ATLAS_IBKR_PORT','7497')));p.add_argument('--client-id',type=int,default=int(os.getenv('ATLAS_IBKR_CLIENT_ID','27')));p.add_argument('--account-id',default=os.getenv('ATLAS_IBKR_ACCOUNT_ID',''));p.add_argument('--bridge-port',type=int,default=int(os.getenv('ATLAS_IBKR_BRIDGE_PORT','8766')));a=p.parse_args();cfg.update(host=a.host,port=a.port,client_id=a.client_id,account_id=a.account_id,token=os.getenv('ATLAS_IBKR_BRIDGE_TOKEN'),simulation=a.port in {7497,4002});uvicorn.run(app,host='0.0.0.0',port=a.bridge_port)
