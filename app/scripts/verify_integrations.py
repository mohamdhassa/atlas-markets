from __future__ import annotations
import asyncio,json
from sqlalchemy import select
from app.brokers.bybit_private import BybitPrivateClient
from app.brokers.mt5_bridge import Mt5BridgeClient
from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.broker import BrokerProfile
from app.db.session import SessionLocal
from app.market_data.fx import TwelveDataFxMarketData

def f(v):
 try:return float(v or 0)
 except:return 0.0
async def detect_bybit(p):
 s=get_settings();key=decrypt_secret(p.api_key_encrypted or '');secret=decrypt_secret(p.api_secret_encrypted or '');errors={}
 for env,url in [('TESTNET',s.bybit_testnet_base_url),('DEMO',s.bybit_demo_base_url),('LIVE',s.bybit_public_base_url)]:
  try:return env,BybitPrivateClient(key,secret,url,s.market_data_timeout_seconds),await BybitPrivateClient(key,secret,url,s.market_data_timeout_seconds).wallet()
  except Exception as exc:errors[env]=str(exc)
 raise RuntimeError('credentials failed in all Bybit environments: '+json.dumps(errors))
async def certify_bybit(p):
 env,c,w=await detect_bybit(p);pos=await c.positions();orders=await c.open_orders();history=await c.order_history(20);closed=await c.closed_pnl(20);a=(w.get('list') or [{}])[0];plist=[x for x in pos.get('list',[]) if f(x.get('size'))]
 p.environment=env;p.equity_usd=f(a.get('totalEquity'));p.wallet_balance_usd=f(a.get('totalWalletBalance'));p.available_balance_usd=f(a.get('totalAvailableBalance'));p.open_positions_count=len(plist);p.open_orders_count=len(orders.get('list',[]));p.last_connection_status='CONNECTED'
 return f"BYBIT {env}: CONNECTED | equity={p.equity_usd:.2f} positions={p.open_positions_count} open_orders={p.open_orders_count} history={len(history.get('list',[]))} closed={len(closed.get('list',[]))}"
def bridge_creds(p):
 if not p.credential_blob_encrypted:raise RuntimeError('bridge configuration missing')
 return json.loads(decrypt_secret(p.credential_blob_encrypted))
async def certify_mt5(p):
 c0=bridge_creds(p);c=Mt5BridgeClient(c0.get('bridge_url') or 'http://host.docker.internal:8765',c0.get('bridge_token'),get_settings().market_data_timeout_seconds);health=await c.health();account=await c.account()
 if not health.get('connected'):raise RuntimeError('bridge reachable but terminal disconnected')
 expected=str(c0.get('login') or '').strip();actual=str(account.get('login') or '').strip()
 if expected and actual and expected!=actual:raise RuntimeError(f'account mismatch expected {expected}, got {actual}')
 pos=await c.positions();orders=await c.orders();history=await c.history_deals(30);fx=await c.candles('EURUSD','5m',20);market_checks=[f"FX=EURUSD:{len(fx.get('list',[]))}"]
 for label,candidates in [('METAL',['XAUUSD','GOLD']),('COMMODITY',['USOIL','WTI','XTIUSD','UKOIL','BRENT'])]:
  ok=None
  for symbol in candidates:
   try:
    data=await c.symbol(symbol)
    if data:ok=symbol;break
   except Exception:pass
  market_checks.append(f'{label}={ok or "NOT_FOUND_ON_ACCOUNT"}')
 p.equity_usd=f(account.get('equity'));p.wallet_balance_usd=f(account.get('balance'));p.available_balance_usd=f(account.get('margin_free'));p.open_positions_count=len(pos.get('list',[]));p.open_orders_count=len(orders.get('list',[]));p.last_connection_status='CONNECTED'
 terminal=health.get('terminal') or {};trade='ON' if terminal.get('trade_allowed') else 'OFF'
 return f"MT5 {p.environment}: CONNECTED | login={actual} equity={p.equity_usd:.2f} positions={p.open_positions_count} orders={p.open_orders_count} deals={len(history.get('list',[]))} algo={trade} | {' '.join(market_checks)}"
async def certify_ibkr(p):
 c0=bridge_creds(p);c=IbkrBridgeClient(c0.get('bridge_url') or 'http://host.docker.internal:8766',c0.get('bridge_token'),get_settings().market_data_timeout_seconds);health=await c.health();account=await c.account()
 if not health.get('connected'):raise RuntimeError('bridge reachable but TWS/IB Gateway disconnected')
 expected=str(c0.get('account_id') or '').strip();actual=str(account.get('account_id') or '').strip()
 if expected and actual!=expected:raise RuntimeError(f'account mismatch expected {expected}, got {actual}')
 if p.environment=='PAPER' and not account.get('simulation'):raise RuntimeError('profile is Simulation but IBKR session is Live Money')
 pos=await c.positions();orders=await c.orders();execs=await c.executions(30);p.equity_usd=f(account.get('equity'));p.wallet_balance_usd=f(account.get('cash'));p.available_balance_usd=f(account.get('available'));p.open_positions_count=len([x for x in pos.get('list',[]) if f(x.get('quantity'))]);p.open_orders_count=len(orders.get('list',[]));p.last_connection_status='CONNECTED'
 return f"IBKR {p.environment}: CONNECTED | account={actual} equity={p.equity_usd:.2f} positions={p.open_positions_count} orders={p.open_orders_count} executions={len(execs.get('list',[]))} simulation={bool(account.get('simulation'))}"
async def verify():
 db=SessionLocal();out=[]
 try:
  profiles=list(db.scalars(select(BrokerProfile).where(BrokerProfile.provider.in_(['BYBIT','TWELVE_DATA','MT5','IBKR']),BrokerProfile.is_enabled.is_(True))).all())
  for p in profiles:
   try:
    if p.provider=='BYBIT':msg=await certify_bybit(p)
    elif p.provider=='MT5':msg=await certify_mt5(p)
    elif p.provider=='IBKR':msg=await certify_ibkr(p)
    else:
     s=get_settings();key=decrypt_secret(p.api_key_encrypted or '');await TwelveDataFxMarketData(s.fx_market_data_base_url,key,s.market_data_timeout_seconds).get_quote('EURUSD');p.last_connection_status='CONNECTED';msg='TWELVE_DATA: CONNECTED (market data only)'
    out.append('PASS | '+msg)
   except Exception as exc:
    if p.provider=='TWELVE_DATA' and '429' in str(exc):out.append('WARN | TWELVE_DATA: RATE LIMITED (secondary market data; broker-native data remains available)')
    else:p.last_connection_status='FAILED';out.append(f'FAIL | {p.provider} {p.account_label}: {exc}')
  db.commit()
 finally:db.close()
 print('\n'.join(out) if out else 'No enabled external provider profiles found')
if __name__=='__main__':asyncio.run(verify())
