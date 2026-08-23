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
LOGIN=os.getenv('ATLAS_MT5_LOGIN','').strip()
PASSWORD=os.getenv('ATLAS_MT5_PASSWORD','')
SERVER=os.getenv('ATLAS_MT5_SERVER','FusionMarkets-Demo').strip()
TERMINAL_PATH=os.getenv('ATLAS_MT5_TERMINAL_PATH','').strip()

def auth(x_atlas_bridge_token:str|None):
    if TOKEN and x_atlas_bridge_token!=TOKEN:raise HTTPException(401,'invalid bridge token')

def require_terminal():
    kwargs={}
    if LOGIN:
        try: kwargs['login']=int(LOGIN)
        except ValueError: raise HTTPException(503,'ATLAS_MT5_LOGIN must be the numeric MT5 login')
    if PASSWORD: kwargs['password']=PASSWORD
    if SERVER: kwargs['server']=SERVER
    ok=mt5.initialize(TERMINAL_PATH,**kwargs) if TERMINAL_PATH else mt5.initialize(**kwargs)
    if not ok:raise HTTPException(503,f'MT5 initialize failed: {mt5.last_error()}')
    info=mt5.account_info()
    if info is None:raise HTTPException(503,f'MT5 account unavailable: {mt5.last_error()}')
    if LOGIN and int(getattr(info,'login',0))!=int(LOGIN):raise HTTPException(503,f'MT5 connected to wrong login {getattr(info,"login",None)}; expected {LOGIN}')
    return info

def obj(v):return v._asdict() if hasattr(v,'_asdict') else v

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

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--host',default='0.0.0.0');p.add_argument('--port',type=int,default=8765);args=p.parse_args();uvicorn.run(app,host=args.host,port=args.port)
