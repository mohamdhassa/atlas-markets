from __future__ import annotations
import argparse,os,threading,time
from datetime import datetime,timedelta
from fastapi import FastAPI,HTTPException,Header
from pydantic import BaseModel
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
import uvicorn

class State(EWrapper,EClient):
 def __init__(self):
  EClient.__init__(self,self);self.next_id=None;self.accounts=[];self.values={};self.positions=[];self.open_orders=[];self.executions=[];self.errors=[];self.quotes={};self.bars={};self._events={}
 def _event(self,k):return self._events.setdefault(k,threading.Event())
 def nextValidId(self,orderId):self.next_id=orderId;self._event('connected').set()
 def managedAccounts(self,accountsList):self.accounts=[x for x in accountsList.split(',') if x]
 def accountSummary(self,reqId,account,tag,value,currency):self.values[(account,tag)]=(value,currency)
 def accountSummaryEnd(self,reqId):self._event(f'acct:{reqId}').set()
 def position(self,account,contract,pos,avgCost):self.positions.append({'account':account,'symbol':contract.symbol,'sec_type':contract.secType,'exchange':contract.exchange,'currency':contract.currency,'quantity':float(pos),'avg_cost':float(avgCost)})
 def positionEnd(self):self._event('positions').set()
 def openOrder(self,orderId,contract,order,orderState):self.open_orders.append({'order_id':orderId,'symbol':contract.symbol,'sec_type':contract.secType,'side':order.action,'type':order.orderType,'quantity':float(order.totalQuantity),'limit_price':float(order.lmtPrice or 0),'aux_price':float(order.auxPrice or 0),'status':orderState.status})
 def openOrderEnd(self):self._event('orders').set()
 def execDetails(self,reqId,contract,execution):self.executions.append({'execution_id':execution.execId,'order_id':execution.orderId,'account':execution.acctNumber,'symbol':contract.symbol,'sec_type':contract.secType,'side':execution.side,'quantity':float(execution.shares),'price':float(execution.price),'time':execution.time})
 def execDetailsEnd(self,reqId):self._event(f'exec:{reqId}').set()
 def tickPrice(self,reqId,tickType,price,attrib):
  q=self.quotes.setdefault(reqId,{})
  if tickType==1:q['bid']=float(price)
  elif tickType==2:q['ask']=float(price)
  elif tickType in {4,68}:q['last']=float(price)
  if q.get('last') or (q.get('bid') and q.get('ask')):self._event(f'quote:{reqId}').set()
 def tickSnapshotEnd(self,reqId):self._event(f'quote:{reqId}').set()
 def historicalData(self,reqId,bar):self.bars.setdefault(reqId,[]).append({'time':bar.date,'open':float(bar.open),'high':float(bar.high),'low':float(bar.low),'close':float(bar.close),'volume':float(bar.volume or 0)})
 def historicalDataEnd(self,reqId,start,end):self._event(f'bars:{reqId}').set()
 def error(self,reqId,errorCode,errorString,advancedOrderRejectJson=''):
  self.errors.append({'id':reqId,'code':errorCode,'message':errorString})
  if reqId>=0 and errorCode not in {2104,2106,2158}:self._event(f'quote:{reqId}').set();self._event(f'bars:{reqId}').set()

app=FastAPI(title='ATLAS IBKR Bridge');ib=State();cfg={}
def auth(x_atlas_bridge_token:str|None):
 token=cfg.get('token')
 if token and x_atlas_bridge_token!=token:raise HTTPException(401,'invalid bridge token')
def wait(key,seconds=10):
 e=ib._event(key);e.clear()
 if not e.wait(seconds):raise HTTPException(504,f'IBKR timeout waiting for {key}')
def rid():return int(time.time()*1000000)%2000000000
def contract(symbol,sec_type='STK',exchange='SMART',currency='USD'):
 c=Contract();c.symbol=symbol.upper();c.secType=sec_type;c.exchange=exchange;c.currency=currency;return c
def bar_size(tf):return {'1m':'1 min','5m':'5 mins','15m':'15 mins','30m':'30 mins','1h':'1 hour','4h':'4 hours','1d':'1 day'}.get(tf,'5 mins')
def duration(tf,limit):
 if tf=='1d':return f'{max(1,min(limit,365))} D'
 minutes={'1m':1,'5m':5,'15m':15,'30m':30,'1h':60,'4h':240}.get(tf,5)*max(limit,10)
 return f'{max(1,min(365,(minutes//1440)+2))} D'
@app.on_event('startup')
def startup():
 ib.connect(cfg['host'],cfg['port'],clientId=cfg['client_id']);threading.Thread(target=ib.run,daemon=True).start()
 if not ib._event('connected').wait(10):raise RuntimeError('IBKR TWS/IB Gateway connection failed')
@app.on_event('shutdown')
def shutdown():ib.disconnect()
@app.get('/health')
def health(x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);return {'status':'ok','connected':ib.isConnected(),'accounts':ib.accounts,'host':cfg['host'],'port':cfg['port'],'client_id':cfg['client_id'],'simulation':cfg['simulation'],'errors':ib.errors[-8:]}
@app.get('/account')
def account(x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);r=rid();ib.reqAccountSummary(r,'All','NetLiquidation,TotalCashValue,AvailableFunds,BuyingPower');wait(f'acct:{r}');ib.cancelAccountSummary(r);acct=cfg.get('account_id') or (ib.accounts[0] if ib.accounts else '')
 def val(tag):
  try:return float(ib.values.get((acct,tag),('0',''))[0])
  except:return 0.0
 return {'account_id':acct,'equity':val('NetLiquidation'),'cash':val('TotalCashValue'),'available':val('AvailableFunds'),'buying_power':val('BuyingPower'),'simulation':cfg['simulation']}
@app.get('/positions')
def positions(x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);ib.positions=[];ib.reqPositions();wait('positions');ib.cancelPositions();return {'list':ib.positions}
@app.get('/orders')
def orders(x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);ib.open_orders=[];ib.reqOpenOrders();wait('orders');return {'list':ib.open_orders}
@app.get('/executions')
def executions(days:int=30,x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);from ibapi.execution import ExecutionFilter
 r=rid();ib.executions=[];f=ExecutionFilter();f.time=(datetime.now()-timedelta(days=max(1,min(days,30)))).strftime('%Y%m%d 00:00:00');ib.reqExecutions(r,f);wait(f'exec:{r}');return {'list':ib.executions}
@app.get('/quote')
def quote(symbol:str,sec_type:str='STK',exchange:str='SMART',currency:str='USD',x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);r=rid();ib.quotes[r]={};ib.reqMktData(r,contract(symbol,sec_type,exchange,currency),'',True,False,[]);wait(f'quote:{r}');ib.cancelMktData(r);q=ib.quotes.pop(r,{})
 if not q:raise HTTPException(502,f'No IBKR quote returned for {symbol}')
 if not q.get('last') and q.get('bid') and q.get('ask'):q['last']=(q['bid']+q['ask'])/2
 return {'symbol':symbol.upper(),'sec_type':sec_type,'currency':currency,**q}
@app.get('/candles')
def candles(symbol:str,timeframe:str='5m',limit:int=200,sec_type:str='STK',exchange:str='SMART',currency:str='USD',x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);limit=max(10,min(limit,1000));r=rid();ib.bars[r]=[];ib.reqHistoricalData(r,contract(symbol,sec_type,exchange,currency),'',duration(timeframe,limit),bar_size(timeframe),'TRADES',1,1,False,[]);wait(f'bars:{r}',15);ib.cancelHistoricalData(r);rows=ib.bars.pop(r,[])
 if not rows:raise HTTPException(502,f'No IBKR candles returned for {symbol}')
 return {'symbol':symbol.upper(),'timeframe':timeframe,'list':rows[-limit:]}
class OrderPayload(BaseModel):
 symbol:str;side:str;quantity:float;order_type:str='MKT';limit_price:float|None=None;sec_type:str='STK';exchange:str='SMART';currency:str='USD';account_id:str|None=None
@app.post('/order-check')
def order_check(p:OrderPayload,x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token)
 if not cfg['simulation']:raise HTTPException(403,'ATLAS IBKR bridge refuses Live Money execution')
 if p.quantity<=0:raise HTTPException(400,'quantity must be positive')
 if p.side.upper() not in {'BUY','SELL'}:raise HTTPException(400,'side must be BUY or SELL')
 if p.order_type.upper() not in {'MKT','LMT'}:raise HTTPException(400,'order_type must be MKT or LMT')
 return {'ok':True,'simulation':True,'account_id':p.account_id or cfg.get('account_id'),'symbol':p.symbol.upper(),'side':p.side.upper(),'quantity':p.quantity,'order_type':p.order_type.upper()}
@app.post('/orders')
def place(p:OrderPayload,x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token)
 if not cfg['simulation']:raise HTTPException(403,'ATLAS IBKR bridge refuses Live Money execution')
 oid=ib.next_id
 if oid is None:raise HTTPException(503,'IBKR next order id unavailable')
 o=Order();o.action=p.side.upper();o.totalQuantity=p.quantity;o.orderType=p.order_type.upper();o.transmit=True;o.account=p.account_id or cfg.get('account_id') or ''
 if o.orderType=='LMT':o.lmtPrice=float(p.limit_price or 0)
 ib.placeOrder(oid,contract(p.symbol,p.sec_type,p.exchange,p.currency),o);ib.next_id+=1;return {'accepted':True,'order_id':oid,'simulation':True,'symbol':p.symbol.upper(),'side':p.side.upper(),'quantity':p.quantity}
@app.post('/orders/{order_id}/cancel')
def cancel(order_id:int,x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token)
 if not cfg['simulation']:raise HTTPException(403,'ATLAS IBKR bridge refuses Live Money execution')
 ib.cancelOrder(order_id,'');return {'cancel_requested':True,'order_id':order_id}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--host',default=os.getenv('ATLAS_IBKR_HOST','127.0.0.1'));p.add_argument('--port',type=int,default=int(os.getenv('ATLAS_IBKR_PORT','7497')));p.add_argument('--client-id',type=int,default=int(os.getenv('ATLAS_IBKR_CLIENT_ID','27')));p.add_argument('--account-id',default=os.getenv('ATLAS_IBKR_ACCOUNT_ID',''));p.add_argument('--bridge-port',type=int,default=int(os.getenv('ATLAS_IBKR_BRIDGE_PORT','8766')));a=p.parse_args();cfg.update(host=a.host,port=a.port,client_id=a.client_id,account_id=a.account_id,token=os.getenv('ATLAS_IBKR_BRIDGE_TOKEN'),simulation=a.port in {7497,4002});uvicorn.run(app,host='0.0.0.0',port=a.bridge_port)
