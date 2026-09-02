from __future__ import annotations
import argparse,os
from datetime import datetime,timezone,timedelta
from fastapi import FastAPI,Header,HTTPException,Query
from pydantic import BaseModel,Field
import uvicorn
try:
    import MetaTrader5 as mt5
except ImportError as exc:
    raise SystemExit('Install Windows dependencies first: py -m pip install MetaTrader5 fastapi uvicorn') from exc

app=FastAPI(title='ATLAS MT5 Bridge')
TOKEN=os.getenv('ATLAS_MT5_BRIDGE_TOKEN','')
LOGIN=os.getenv('ATLAS_MT5_LOGIN','').strip()
PASSWORD=os.getenv('ATLAS_MT5_PASSWORD','')
SERVER=os.getenv('ATLAS_MT5_SERVER','').strip()
TERMINAL_PATH=os.getenv('ATLAS_MT5_TERMINAL_PATH','').strip()

class OrderRequest(BaseModel):
    symbol:str=Field(min_length=3,max_length=32)
    side:str=Field(pattern='^(BUY|SELL)$')
    volume:float=Field(gt=0)
    stop_loss:float|None=None
    take_profit:float|None=None
    deviation:int=Field(default=20,ge=0,le=500)
    comment:str=Field(default='ATLAS DEMO',max_length=31)
class CloseRequest(BaseModel):
    deviation:int=Field(default=20,ge=0,le=500)
    comment:str=Field(default='ATLAS CLOSE',max_length=31)

def auth(x_atlas_bridge_token:str|None):
    if TOKEN and x_atlas_bridge_token!=TOKEN:raise HTTPException(401,'invalid bridge token')
def require_terminal():
    kwargs={}
    if LOGIN:
        try:kwargs['login']=int(LOGIN)
        except ValueError:raise HTTPException(503,'ATLAS_MT5_LOGIN must be the numeric MT5 login')
    if PASSWORD:kwargs['password']=PASSWORD
    if SERVER:kwargs['server']=SERVER
    ok=mt5.initialize(TERMINAL_PATH,**kwargs) if TERMINAL_PATH else mt5.initialize(**kwargs)
    if not ok:raise HTTPException(503,f'MT5 initialize failed: {mt5.last_error()}')
    info=mt5.account_info()
    if info is None:raise HTTPException(503,f'MT5 account unavailable: {mt5.last_error()}')
    if LOGIN and int(getattr(info,'login',0))!=int(LOGIN):raise HTTPException(503,f'MT5 connected to wrong login {getattr(info,"login",None)}; expected {LOGIN}')
    return info
def require_demo(account):
    server=str(getattr(account,'server',''))
    if 'demo' not in server.lower():raise HTTPException(403,f'ATLAS bridge execution is demo-only; connected server is {server or "unknown"}')
    terminal=mt5.terminal_info()
    if terminal and not getattr(terminal,'trade_allowed',False):raise HTTPException(409,'MT5 Algo Trading is disabled in the terminal')
def obj(v):return v._asdict() if hasattr(v,'_asdict') else v
def symbol_info(symbol:str):
    s=symbol.strip().upper();info=mt5.symbol_info(s)
    if info is None:raise HTTPException(404,f'MT5 symbol {s} not found')
    if not info.visible and not mt5.symbol_select(s,True):raise HTTPException(409,f'MT5 symbol {s} cannot be selected')
    tick=mt5.symbol_info_tick(s)
    if tick is None:raise HTTPException(503,f'No current tick for {s}')
    d=obj(info);d['bid']=float(tick.bid);d['ask']=float(tick.ask);d['time_msc']=getattr(tick,'time_msc',None);return d
def timeframe_value(tf:str):
    key=tf.strip().lower();mapping={'1m':mt5.TIMEFRAME_M1,'5m':mt5.TIMEFRAME_M5,'15m':mt5.TIMEFRAME_M15,'30m':mt5.TIMEFRAME_M30,'1h':mt5.TIMEFRAME_H1,'4h':mt5.TIMEFRAME_H4,'1d':mt5.TIMEFRAME_D1}
    if key not in mapping:raise HTTPException(422,'timeframe must be 1m, 5m, 15m, 30m, 1h, 4h or 1d')
    return mapping[key]
def candle_rows(symbol:str,timeframe:str,limit:int):
    s=symbol.strip().upper();symbol_info(s);rates=mt5.copy_rates_from_pos(s,timeframe_value(timeframe),0,max(2,min(int(limit),500)))
    if rates is None:raise HTTPException(503,f'MT5 candles unavailable for {s}: {mt5.last_error()}')
    return [{'timestamp':datetime.fromtimestamp(int(x['time']),timezone.utc).isoformat(),'open':float(x['open']),'high':float(x['high']),'low':float(x['low']),'close':float(x['close']),'volume':float(x['tick_volume'])} for x in rates]
def build_request(payload:OrderRequest,position:int|None=None):
    s=payload.symbol.strip().upper();info=mt5.symbol_info(s)
    if info is None:raise HTTPException(404,f'MT5 symbol {s} not found')
    if not info.visible:mt5.symbol_select(s,True)
    tick=mt5.symbol_info_tick(s)
    if tick is None:raise HTTPException(503,f'No current tick for {s}')
    side=payload.side.upper();price=float(tick.ask if side=='BUY' else tick.bid)
    req={'action':mt5.TRADE_ACTION_DEAL,'symbol':s,'volume':float(payload.volume),'type':mt5.ORDER_TYPE_BUY if side=='BUY' else mt5.ORDER_TYPE_SELL,'price':price,'deviation':payload.deviation,'magic':250825,'comment':payload.comment,'type_time':mt5.ORDER_TIME_GTC,'type_filling':mt5.ORDER_FILLING_IOC}
    if payload.stop_loss is not None:req['sl']=float(payload.stop_loss)
    if payload.take_profit is not None:req['tp']=float(payload.take_profit)
    if position is not None:req['position']=int(position)
    return req

@app.get('/health')
def health(x_atlas_bridge_token:str|None=Header(default=None)):
    auth(x_atlas_bridge_token);account=require_terminal();info=mt5.terminal_info();return {'status':'ok','connected':bool(info and getattr(info,'connected',False)),'login':getattr(account,'login',None),'server':getattr(account,'server',None),'terminal':obj(info) if info else None}
@app.get('/account')
def account(x_atlas_bridge_token:str|None=Header(default=None)):
    auth(x_atlas_bridge_token);return obj(require_terminal())
@app.get('/positions')
def positions(x_atlas_bridge_token:str|None=Header(default=None)):
    auth(x_atlas_bridge_token);require_terminal();return {'list':[obj(x) for x in (mt5.positions_get() or [])]}
@app.get('/orders')
def orders(x_atlas_bridge_token:str|None=Header(default=None)):
    auth(x_atlas_bridge_token);require_terminal();return {'list':[obj(x) for x in (mt5.orders_get() or [])]}
@app.get('/symbols/search')
def search_symbols(q:str=Query(min_length=1,max_length=32),limit:int=Query(50,ge=1,le=200),x_atlas_bridge_token:str|None=Header(default=None)):
    auth(x_atlas_bridge_token);require_terminal();needle=q.strip().upper();rows=[]
    for info in mt5.symbols_get() or []:
        name=str(getattr(info,'name','') or '').upper();path=str(getattr(info,'path','') or '').upper();desc=str(getattr(info,'description','') or '').upper()
        if needle in name or needle in path or needle in desc:
            rows.append({'name':getattr(info,'name',None),'path':getattr(info,'path',None),'description':getattr(info,'description',None),'visible':bool(getattr(info,'visible',False)),'trade_mode':getattr(info,'trade_mode',None),'digits':getattr(info,'digits',None),'volume_min':getattr(info,'volume_min',None),'volume_step':getattr(info,'volume_step',None)})
            if len(rows)>=limit:break
    return {'query':needle,'list':rows}
@app.get('/symbol/{symbol}')
def get_symbol(symbol:str,x_atlas_bridge_token:str|None=Header(default=None)):
    auth(x_atlas_bridge_token);require_terminal();return symbol_info(symbol)
@app.get('/candles/{symbol}')
def get_candles(symbol:str,timeframe:str=Query('5m'),limit:int=Query(200,ge=2,le=500),x_atlas_bridge_token:str|None=Header(default=None)):
    auth(x_atlas_bridge_token);require_terminal();return {'symbol':symbol.strip().upper(),'timeframe':timeframe,'provider':'MT5_FUSION','list':candle_rows(symbol,timeframe,limit)}
@app.get('/history/deals')
def history_deals(days:int=30,x_atlas_bridge_token:str|None=Header(default=None)):
    auth(x_atlas_bridge_token);require_terminal();days=max(1,min(int(days),366));end=datetime.now(timezone.utc);start=end-timedelta(days=days);rows=mt5.history_deals_get(start,end) or [];return {'from':start.isoformat(),'to':end.isoformat(),'list':[obj(x) for x in rows]}
@app.post('/order/check')
def order_check(payload:OrderRequest,x_atlas_bridge_token:str|None=Header(default=None)):
    auth(x_atlas_bridge_token);account=require_terminal();require_demo(account);req=build_request(payload);r=mt5.order_check(req)
    if r is None:raise HTTPException(502,f'MT5 order_check failed: {mt5.last_error()}')
    return {'request':req,'result':obj(r)}
@app.post('/order')
def place_order(payload:OrderRequest,x_atlas_bridge_token:str|None=Header(default=None)):
    auth(x_atlas_bridge_token);account=require_terminal();require_demo(account);req=build_request(payload);check=mt5.order_check(req)
    if check is None:raise HTTPException(502,f'MT5 order_check failed: {mt5.last_error()}')
    if int(getattr(check,'retcode',-1)) not in {0,getattr(mt5,'TRADE_RETCODE_DONE',10009)}:raise HTTPException(409,f'MT5 order rejected by preflight: {obj(check)}')
    r=mt5.order_send(req)
    if r is None:raise HTTPException(502,f'MT5 order_send failed: {mt5.last_error()}')
    if int(getattr(r,'retcode',-1)) not in {getattr(mt5,'TRADE_RETCODE_DONE',10009),getattr(mt5,'TRADE_RETCODE_PLACED',10008)}:raise HTTPException(409,f'MT5 order failed: {obj(r)}')
    return {'request':req,'result':obj(r)}
@app.post('/positions/{ticket}/close')
def close_position(ticket:int,payload:CloseRequest,x_atlas_bridge_token:str|None=Header(default=None)):
    auth(x_atlas_bridge_token);account=require_terminal();require_demo(account);rows=mt5.positions_get(ticket=ticket) or []
    if not rows:raise HTTPException(404,'MT5 position not found')
    p=rows[0];side='SELL' if int(p.type)==int(mt5.POSITION_TYPE_BUY) else 'BUY';req=OrderRequest(symbol=p.symbol,side=side,volume=float(p.volume),deviation=payload.deviation,comment=payload.comment);r=mt5.order_send(build_request(req,position=ticket))
    if r is None:raise HTTPException(502,f'MT5 close failed: {mt5.last_error()}')
    if int(getattr(r,'retcode',-1)) not in {getattr(mt5,'TRADE_RETCODE_DONE',10009),getattr(mt5,'TRADE_RETCODE_PLACED',10008)}:raise HTTPException(409,f'MT5 close failed: {obj(r)}')
    return {'result':obj(r)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--host',default='0.0.0.0');p.add_argument('--port',type=int,default=8765);args=p.parse_args();uvicorn.run(app,host=args.host,port=args.port)
