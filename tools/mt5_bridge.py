from __future__ import annotations
import argparse,os
from fastapi import FastAPI,Header,HTTPException
import uvicorn
try:
    import MetaTrader5 as mt5
except ImportError as exc:
    raise SystemExit('Install Windows dependencies first: py -m pip install MetaTrader5 fastapi uvicorn') from exc

app=FastAPI(title='ATLAS MT5 Bridge')
TOKEN=os.getenv('ATLAS_MT5_BRIDGE_TOKEN','')

def auth(x_atlas_bridge_token:str|None):
    if TOKEN and x_atlas_bridge_token!=TOKEN:raise HTTPException(401,'invalid bridge token')

def require_terminal():
    if not mt5.initialize():raise HTTPException(503,f'MT5 initialize failed: {mt5.last_error()}')

def obj(v):return v._asdict() if hasattr(v,'_asdict') else v

@app.get('/health')
def health(x_atlas_bridge_token:str|None=Header(default=None)):
    auth(x_atlas_bridge_token);require_terminal();info=mt5.terminal_info();return {'status':'ok','connected':bool(info and getattr(info,'connected',False)),'terminal':obj(info) if info else None}
@app.get('/account')
def account(x_atlas_bridge_token:str|None=Header(default=None)):
    auth(x_atlas_bridge_token);require_terminal();a=mt5.account_info();
    if a is None:raise HTTPException(503,f'account unavailable: {mt5.last_error()}')
    return obj(a)
@app.get('/positions')
def positions(x_atlas_bridge_token:str|None=Header(default=None)):
    auth(x_atlas_bridge_token);require_terminal();return {'list':[obj(x) for x in (mt5.positions_get() or [])]}
@app.get('/orders')
def orders(x_atlas_bridge_token:str|None=Header(default=None)):
    auth(x_atlas_bridge_token);require_terminal();return {'list':[obj(x) for x in (mt5.orders_get() or [])]}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--host',default='0.0.0.0');p.add_argument('--port',type=int,default=8765);args=p.parse_args();uvicorn.run(app,host=args.host,port=args.port)
