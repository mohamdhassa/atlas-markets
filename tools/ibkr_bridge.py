from __future__ import annotations
import argparse,os,threading,time
from datetime import datetime,timedelta,timezone
from fastapi import FastAPI,HTTPException,Header
from pydantic import BaseModel
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
import uvicorn

class State(EWrapper,EClient):
 def __init__(self):EClient.__init__(self,self);self.next_id=None;self.accounts=[];self.values={};self.positions=[];self.open_orders=[];self.executions=[];self.errors=[];self._events={}
 def _event(self,k):return self._events.setdefault(k,threading.Event())
 def nextValidId(self,orderId):self.next_id=orderId;self._event('connected').set()
 def managedAccounts(self,accountsList):self.accounts=[x for x in accountsList.split(',') if x]
 def accountSummary(self,reqId,account,tag,value,currency):self.values[(account,tag)]=(value,currency)
 def accountSummaryEnd(self,reqId):self._event(f'acct:{reqId}').set()
 def position(self,account,contract,pos,avgCost):self.positions.append({'account':account,'symbol':contract.symbol,'sec_type':contract.secType,'exchange':contract.exchange,'currency':contract.currency,'quantity':float(pos),'avg_cost':float(avgCost)})
 def positionEnd(self):self._event('positions').set()
 def openOrder(self,orderId,contract,order,orderState):self.open_orders.append({'order_id':orderId,'symbol':contract.symbol,'sec_type':contract.secType,'side':order.action,'type':order.orderType,'quantity':float(order.totalQuantity),'limit_price':float(order.lmtPrice or 0),'status':orderState.status})
 def openOrderEnd(self):self._event('orders').set()
 def execDetails(self,reqId,contract,execution):self.executions.append({'execution_id':execution.execId,'order_id':execution.orderId,'account':execution.acctNumber,'symbol':contract.symbol,'sec_type':contract.secType,'side':execution.side,'quantity':float(execution.shares),'price':float(execution.price),'time':execution.time})
 def execDetailsEnd(self,reqId):self._event(f'exec:{reqId}').set()
 def error(self,reqId,errorCode,errorString,advancedOrderRejectJson=''):self.errors.append({'id':reqId,'code':errorCode,'message':errorString})

app=FastAPI(title='ATLAS IBKR Bridge');ib=State();cfg={}
def auth(x_atlas_bridge_token:str|None):
 token=cfg.get('token');
 if token and x_atlas_bridge_token!=token:raise HTTPException(401,'invalid bridge token')
def wait(key,seconds=8):
 e=ib._event(key);e.clear()
 if not e.wait(seconds):raise HTTPException(504,f'IBKR timeout waiting for {key}')
def contract(symbol,sec_type='STK',exchange='SMART',currency='USD'):
 c=Contract();c.symbol=symbol.upper();c.secType=sec_type;c.exchange=exchange;c.currency=currency;return c
@app.on_event('startup')
def startup():
 ib.connect(cfg['host'],cfg['port'],clientId=cfg['client_id']);threading.Thread(target=ib.run,daemon=True).start()
 if not ib._event('connected').wait(10):raise RuntimeError('IBKR TWS/IB Gateway connection failed')
@app.on_event('shutdown')
def shutdown():ib.disconnect()
@app.get('/health')
def health(x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);return {'status':'ok','connected':ib.isConnected(),'accounts':ib.accounts,'host':cfg['host'],'port':cfg['port'],'client_id':cfg['client_id'],'simulation':cfg['simulation'],'errors':ib.errors[-5:]}
@app.get('/account')
def account(x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token);rid=int(time.time()*1000)%2000000000;ib.reqAccountSummary(rid,'All','NetLiquidation,TotalCashValue,AvailableFunds,BuyingPower');wait(f'acct:{rid}');ib.cancelAccountSummary(rid);acct=cfg.get('account_id') or (ib.accounts[0] if ib.accounts else '')
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
 rid=int(time.time()*1000)%2000000000;ib.executions=[];f=ExecutionFilter();f.time=(datetime.now()-timedelta(days=max(1,min(days,30)))).strftime('%Y%m%d 00:00:00');ib.reqExecutions(rid,f);wait(f'exec:{rid}');return {'list':ib.executions}
class OrderPayload(BaseModel):
 symbol:str;side:str;quantity:float;order_type:str='MKT';limit_price:float|None=None;sec_type:str='STK';exchange:str='SMART';currency:str='USD';account_id:str|None=None
@app.post('/order-check')
def order_check(p:OrderPayload,x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token)
 if not cfg['simulation']:raise HTTPException(403,'ATLAS IBKR bridge refuses Live Money execution')
 if p.quantity<=0:raise HTTPException(400,'quantity must be positive')
 if p.side.upper() not in {'BUY','SELL'}:raise HTTPException(400,'side must be BUY or SELL')
 return {'ok':True,'simulation':True,'account_id':p.account_id or cfg.get('account_id'),'symbol':p.symbol.upper(),'side':p.side.upper(),'quantity':p.quantity}
@app.post('/orders')
def place(p:OrderPayload,x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token)
 if not cfg['simulation']:raise HTTPException(403,'ATLAS IBKR bridge refuses Live Money execution')
 oid=ib.next_id
 if oid is None:raise HTTPException(503,'IBKR next order id unavailable')
 o=Order();o.action=p.side.upper();o.totalQuantity=p.quantity;o.orderType=p.order_type.upper();o.transmit=True;o.account=p.account_id or cfg.get('account_id') or ''
 if o.orderType=='LMT':o.lmtPrice=float(p.limit_price or 0)
 ib.placeOrder(oid,contract(p.symbol,p.sec_type,p.exchange,p.currency),o);ib.next_id+=1;return {'accepted':True,'order_id':oid,'simulation':True}
@app.post('/orders/{order_id}/cancel')
def cancel(order_id:int,x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token)
 if not cfg['simulation']:raise HTTPException(403,'ATLAS IBKR bridge refuses Live Money execution')
 ib.cancelOrder(order_id,'');return {'cancel_requested':True,'order_id':order_id}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--host',default=os.getenv('ATLAS_IBKR_HOST','127.0.0.1'));p.add_argument('--port',type=int,default=int(os.getenv('ATLAS_IBKR_PORT','7497')));p.add_argument('--client-id',type=int,default=int(os.getenv('ATLAS_IBKR_CLIENT_ID','27')));p.add_argument('--account-id',default=os.getenv('ATLAS_IBKR_ACCOUNT_ID',''));p.add_argument('--bridge-port',type=int,default=int(os.getenv('ATLAS_IBKR_BRIDGE_PORT','8766')));a=p.parse_args();cfg.update(host=a.host,port=a.port,client_id=a.client_id,account_id=a.account_id,token=os.getenv('ATLAS_IBKR_BRIDGE_TOKEN'),simulation=a.port in {7497,4002});uvicorn.run(app,host='0.0.0.0',port=a.bridge_port)
