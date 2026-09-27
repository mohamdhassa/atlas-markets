from __future__ import annotations
import asyncio,json,math
from datetime import datetime,timedelta,timezone
from sqlalchemy import select
from app.brokers.bybit_private import BybitPrivateClient
from app.brokers.mt5_bridge import Mt5BridgeClient
from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.automation import AutomationScan,AutomationState
from app.db.models.broker import BrokerProfile
from app.db.models.signal import RiskEvent,RiskProfile,Signal
from app.db.models.strategy import StrategyProfile
from app.db.models.symbol_strategy import SymbolStrategy
from app.db.session import SessionLocal
from app.market_data.bybit import BybitPublicMarketData
from app.services.historical_intelligence import db_candles,historical_probability
from app.services.news_intelligence import apply_news_context,context_for_symbol,refresh_news
from app.services.paper_execution import build_execution_plan
from app.services.signal_risk import GeneratedSignal,evaluate_risk,generate_signal,reasons_json

def get_or_create_state(db):
 s=db.scalar(select(AutomationState).where(AutomationState.name=='default'))
 if s is None:s=AutomationState(name='default');db.add(s);db.commit();db.refresh(s)
 return s
def _risk(db):
 r=db.scalar(select(RiskProfile).where(RiskProfile.name=='Default'))
 if r is None:r=RiskProfile(name='Default');db.add(r);db.commit();db.refresh(r)
 return r
def _strategy(db):
 s=db.scalar(select(StrategyProfile).where(StrategyProfile.name=='Default'))
 if s is None:s=StrategyProfile(name='Default');db.add(s);db.commit();db.refresh(s)
 return s
def _canonical_symbol(symbol):return str(symbol or '').strip().upper().replace('/','').replace(' ','')
def _open_symbols(rows,quantity_key=None):
 out=set()
 for row in rows or []:
  if quantity_key is not None and float(row.get(quantity_key) or 0)==0:continue
  symbol=_canonical_symbol(row.get('symbol'))
  if symbol:out.add(symbol)
 return out
def _has_exposure(open_symbols,symbol):return _canonical_symbol(symbol) in open_symbols
def _with_history(signal:GeneratedSignal,history:dict)->GeneratedSignal:
 if history.get('matches',0)<25 or signal.decision not in {'BUY','SELL'}:return signal
 support=float(history['up_probability'] if signal.decision=='BUY' else history['down_probability']);strength=round(signal.strength*.70+support*.30,2);classification='STRONG_SIGNAL' if strength>=80 else 'SIGNAL' if strength>=65 else 'WATCH'
 return GeneratedSignal(decision=signal.decision,classification=classification,score=signal.score,strength=strength,reasons=[*signal.reasons,f"historical_{history['matches']}_matches",f'historical_support_{support:.1f}'])
def _bybit_simulation_client(a,settings):
 if a.environment not in {'DEMO','TESTNET'}:raise RuntimeError('automation refuses Bybit Live Money execution')
 if not a.api_key_encrypted or not a.api_secret_encrypted:raise RuntimeError('Bybit Simulation credentials are not configured')
 base=settings.bybit_demo_base_url if a.environment=='DEMO' else settings.bybit_testnet_base_url
 return BybitPrivateClient(decrypt_secret(a.api_key_encrypted),decrypt_secret(a.api_secret_encrypted),base,settings.market_data_timeout_seconds)
def _bridge_creds(a):
 if not a.credential_blob_encrypted:raise RuntimeError(f'{a.provider} Simulation bridge configuration is missing')
 return json.loads(decrypt_secret(a.credential_blob_encrypted))
def _mt5_simulation_client(a,settings):
 if a.environment!='DEMO':raise RuntimeError('automation refuses MT5 Live Money execution')
 c=_bridge_creds(a);return Mt5BridgeClient(c.get('bridge_url') or 'http://host.docker.internal:8765',c.get('bridge_token'),settings.market_data_timeout_seconds)
def _ibkr_simulation_client(a,settings):
 if a.environment!='PAPER':raise RuntimeError('automation refuses IBKR Live Money execution')
 c=_bridge_creds(a);return IbkrBridgeClient(c.get('bridge_url') or 'http://host.docker.internal:8766',c.get('bridge_token'),settings.market_data_timeout_seconds)
def _wallet_numbers(wallet):
 a=(wallet.get('list') or [{}])[0];equity=float(a.get('totalEquity') or a.get('totalWalletBalance') or 0);available=float(a.get('totalAvailableBalance') or a.get('totalWalletBalance') or equity);return equity,available
def _configs(db,account,state):
 rows=list(db.scalars(select(SymbolStrategy).where(SymbolStrategy.profile_id==account.id,SymbolStrategy.enabled.is_(True))).all())
 if rows:return rows
 if account.provider=='BYBIT':return [type('LegacyConfig',(),{'symbol':s.strip().upper(),'market':'CRYPTO','mode':'SIGNALS','timeframe':None,'minimum_signal_strength':None,'risk_per_trade_pct':None,'stop_atr_multiplier':None,'take_profit_rr':None,'max_position_notional_pct':None})() for s in state.symbols_csv.split(',') if s.strip()]
 return []
def _params(cfg,default,risk):
 return (cfg.timeframe or default.timeframe,max(risk.minimum_signal_score,cfg.minimum_signal_strength if cfg.minimum_signal_strength is not None else default.minimum_signal_strength),min(risk.risk_per_trade_pct,cfg.risk_per_trade_pct if cfg.risk_per_trade_pct is not None else risk.risk_per_trade_pct),cfg.stop_atr_multiplier if cfg.stop_atr_multiplier is not None else default.stop_atr_multiplier,cfg.take_profit_rr if cfg.take_profit_rr is not None else default.take_profit_rr,cfg.max_position_notional_pct if cfg.max_position_notional_pct is not None else default.max_position_notional_pct)
def _round_volume(raw,info):
 mn=float(info.get('volume_min') or 0.01);mx=float(info.get('volume_max') or raw);step=float(info.get('volume_step') or mn);v=max(mn,min(mx,raw));v=math.floor(v/step)*step;return round(max(mn,v),8)
def _record(db,scan,account,cfg,generated,approved,reason,details,timeframe):
 sig=Signal(profile_id=account.id,symbol=cfg.symbol,timeframe=timeframe,decision=generated.decision,classification=generated.classification,score=generated.score,reasons_json=reasons_json(generated.reasons),risk_status='APPROVED' if approved else 'REJECTED');db.add(sig);db.flush();db.add(RiskEvent(profile_id=account.id,signal_id=sig.id,approved=approved,reason_code=reason,details_json=json.dumps(details,separators=(',',':'))));scan.signals_count+=1;scan.approved_count+=1 if approved else 0;return sig
async def run_scan()->dict:
 settings=get_settings()
 with SessionLocal() as db:
  state=get_or_create_state(db);default=_strategy(db)
  if not state.enabled or state.killed or not default.enabled:return {'status':'SKIPPED','reason':'ENGINE_DISABLED' if not state.enabled else 'KILL_SWITCH' if state.killed else 'STRATEGY_DISABLED'}
  accounts=list(db.scalars(select(BrokerProfile).where(BrokerProfile.provider.in_(['BYBIT','MT5','IBKR']),BrokerProfile.environment.in_(['DEMO','TESTNET','PAPER']),BrokerProfile.is_enabled.is_(True),BrokerProfile.is_active.is_(True),BrokerProfile.credentials_configured.is_(True),BrokerProfile.last_connection_status=='CONNECTED')).all())
  if not accounts:return {'status':'SKIPPED','reason':'NO_CONNECTED_EXTERNAL_SIMULATION_ACCOUNT'}
  all_configs={a.id:_configs(db,a,state) for a in accounts};scan=AutomationScan(status='RUNNING',symbols_count=sum(len(x) for x in all_configs.values()),accounts_count=len(accounts));db.add(scan);db.commit();db.refresh(scan);crypto_market=BybitPublicMarketData(settings.bybit_public_base_url,settings.market_data_timeout_seconds);risk=_risk(db)
  try:
   try:await refresh_news(db)
   except Exception:pass
   for account in accounts:
    if account.provider=='BYBIT':
     broker=_bybit_simulation_client(account,settings);wallet=await broker.wallet();broker_positions=await broker.positions();equity,available=_wallet_numbers(wallet);position_rows=[p for p in broker_positions.get('list',[]) if float(p.get('size') or 0)!=0];open_symbols=_open_symbols(position_rows);account.equity_usd=equity;account.available_balance_usd=available;account.open_positions_count=len(position_rows)
     for cfg in all_configs[account.id]:
      if cfg.market!='CRYPTO':continue
      symbol=cfg.symbol;timeframe,minimum,risk_pct,stop,rr,max_pos=_params(cfg,default,risk);candles=await crypto_market.get_candles(symbol=symbol,interval=timeframe,category='linear',limit=200);technical=generate_signal([c.model_dump() for c in candles]);news=context_for_symbol(db,symbol,hours=24);generated=_with_history(apply_news_context(technical,news),historical_probability(db_candles(db,'CRYPTO',symbol,timeframe),horizon=6))
      if cfg.mode=='WATCH':continue
      approved,reason,details=evaluate_risk(generated,minimum_signal_score=minimum,account_enabled=account.is_enabled,allow_live_trading=False,account_environment=account.environment);details.update({'execution_environment':'SIMULATION','provider_environment':account.environment,'broker':'BYBIT','strategy_mode':cfg.mode,'market':'CRYPTO'});sig=_record(db,scan,account,cfg,generated,approved,reason,details,timeframe)
      if cfg.mode=='AUTO_TRADE' and approved and state.auto_execute_paper and generated.decision in {'BUY','SELL'} and len(open_symbols)<risk.max_open_positions and not _has_exposure(open_symbols,symbol):
       ticker=await crypto_market.get_tickers(category='linear',symbols=(symbol,))
       if ticker.tickers:
        price=ticker.tickers[0].last_price;plan=build_execution_plan(decision=generated.decision,price=price,equity=equity,available_cash=available,risk_per_trade_pct=risk_pct,stop_atr_multiplier=stop,take_profit_rr=rr,max_position_notional_pct=max_pos)
        if plan.notional<=available:await broker.place_demo_market_order(symbol=symbol,side='Buy' if plan.side.upper()=='BUY' else 'Sell',qty=plan.quantity,stop_loss=plan.stop_loss,take_profit=plan.take_profit,order_link_id=f'atlas-{str(sig.id)[:30]}');scan.executed_count+=1;open_symbols.add(_canonical_symbol(symbol));available=max(0,available-plan.notional)
    elif account.provider=='MT5':
     broker=_mt5_simulation_client(account,settings);acct=await broker.account();health=await broker.health();equity=float(acct.get('equity') or 0);available=float(acct.get('margin_free') or equity);pos=await broker.positions();position_rows=pos.get('list',[]);open_symbols=_open_symbols(position_rows);account.equity_usd=equity;account.available_balance_usd=available;account.open_positions_count=len(position_rows)
     terminal=health.get('terminal') or {}
     if terminal and not terminal.get('trade_allowed',False):continue
     for cfg in all_configs[account.id]:
      if cfg.market not in {'FX','METAL','COMMODITY'}:continue
      symbol=cfg.symbol;timeframe,minimum,risk_pct,stop,rr,max_pos=_params(cfg,default,risk);raw=(await broker.candles(symbol,timeframe,200)).get('list',[]);technical=generate_signal(raw);news=context_for_symbol(db,symbol,hours=24);generated=_with_history(apply_news_context(technical,news),historical_probability(db_candles(db,cfg.market,symbol,timeframe),horizon=6))
      if cfg.mode=='WATCH':continue
      approved,reason,details=evaluate_risk(generated,minimum_signal_score=minimum,account_enabled=account.is_enabled,allow_live_trading=False,account_environment=account.environment);details.update({'execution_environment':'SIMULATION','provider_environment':account.environment,'broker':'MT5_FUSION','strategy_mode':cfg.mode,'market':cfg.market,'market_data_provider':'MT5_FUSION'});sig=_record(db,scan,account,cfg,generated,approved,reason,details,timeframe)
      if cfg.mode=='AUTO_TRADE' and approved and state.auto_execute_paper and generated.decision in {'BUY','SELL'} and len(open_symbols)<risk.max_open_positions and not _has_exposure(open_symbols,symbol):
       info=await broker.symbol(symbol);price=float(info.get('ask') if generated.decision=='BUY' else info.get('bid'));plan=build_execution_plan(decision=generated.decision,price=price,equity=equity,available_cash=available,risk_per_trade_pct=risk_pct,stop_atr_multiplier=stop,take_profit_rr=rr,max_position_notional_pct=max_pos);contract=float(info.get('trade_contract_size') or 100000);volume=_round_volume(plan.quantity/contract,info);await broker.order_check({'symbol':symbol,'side':generated.decision,'volume':volume,'stop_loss':plan.stop_loss,'take_profit':plan.take_profit,'comment':'ATLAS SIMULATION'});await broker.place_demo_order(symbol=symbol,side=generated.decision,volume=volume,stop_loss=plan.stop_loss,take_profit=plan.take_profit,comment='ATLAS SIMULATION');scan.executed_count+=1;open_symbols.add(_canonical_symbol(symbol))
    elif account.provider=='IBKR':
     broker=_ibkr_simulation_client(account,settings);health=await broker.health();acct=await broker.account();equity=float(acct.get('equity') or 0);available=float(acct.get('available') or acct.get('cash') or equity);pos=await broker.positions();position_rows=[x for x in pos.get('list',[]) if float(x.get('quantity') or 0)!=0];open_symbols=_open_symbols(position_rows,'quantity');account.equity_usd=equity;account.available_balance_usd=available;account.open_positions_count=len(position_rows)
     if not health.get('connected') or not health.get('simulation'):continue
     for cfg in all_configs[account.id]:
      if cfg.market not in {'STOCK','ETF'}:continue
      symbol=cfg.symbol;timeframe,minimum,risk_pct,stop,rr,max_pos=_params(cfg,default,risk);raw=(await broker.candles(symbol,timeframe,200,sec_type='STK')).get('list',[]);technical=generate_signal(raw);news=context_for_symbol(db,symbol,hours=24);generated=_with_history(apply_news_context(technical,news),historical_probability(db_candles(db,cfg.market,symbol,timeframe),horizon=6))
      if cfg.mode=='WATCH':continue
      approved,reason,details=evaluate_risk(generated,minimum_signal_score=minimum,account_enabled=account.is_enabled,allow_live_trading=False,account_environment=account.environment);details.update({'execution_environment':'SIMULATION','provider_environment':'PAPER','broker':'IBKR','strategy_mode':cfg.mode,'market':cfg.market,'market_data_provider':'IBKR'});sig=_record(db,scan,account,cfg,generated,approved,reason,details,timeframe)
      if cfg.mode=='AUTO_TRADE' and approved and state.auto_execute_paper and generated.decision in {'BUY','SELL'} and len(open_symbols)<risk.max_open_positions and not _has_exposure(open_symbols,symbol):
       quote=await broker.quote(symbol,sec_type='STK');price=float(quote.get('ask') if generated.decision=='BUY' else quote.get('bid') or quote.get('last'));plan=build_execution_plan(decision=generated.decision,price=price,equity=equity,available_cash=available,risk_per_trade_pct=risk_pct,stop_atr_multiplier=stop,take_profit_rr=rr,max_position_notional_pct=max_pos);shares=math.floor(plan.quantity)
       if shares>=1 and shares*price<=available:
        payload={'symbol':symbol,'side':generated.decision,'quantity':shares,'order_type':'MKT','sec_type':'STK','exchange':'SMART','currency':'USD','account_id':acct.get('account_id')};await broker.order_check(payload);await broker.place_order(payload);scan.executed_count+=1;open_symbols.add(_canonical_symbol(symbol));available=max(0,available-shares*price)
    db.flush()
   now=datetime.now(timezone.utc);scan.status='COMPLETED';scan.finished_at=now;state.last_scan_at=now;state.next_scan_at=now+timedelta(seconds=state.interval_seconds);db.commit();return {'status':scan.status,'signals':scan.signals_count,'approved':scan.approved_count,'executed':scan.executed_count,'execution':'EXTERNAL_BROKER_SIMULATION','brokers':['BYBIT','MT5_FUSION','IBKR'],'strategy_scope':'PER_ACCOUNT_SYMBOL'}
  except Exception as exc:scan.status='FAILED';scan.error_message=str(exc)[:500];scan.finished_at=datetime.now(timezone.utc);db.commit();return {'status':'FAILED','error':scan.error_message}
async def automation_loop(stop_event:asyncio.Event):
 while not stop_event.is_set():
  try:
   with SessionLocal() as db:state=get_or_create_state(db);wait=max(10,state.interval_seconds);due=state.next_scan_at is None or state.next_scan_at<=datetime.now(timezone.utc);enabled=state.enabled and not state.killed
   if enabled and due:await run_scan()
   try:await asyncio.wait_for(stop_event.wait(),timeout=min(wait,30))
   except asyncio.TimeoutError:pass
  except Exception:
   try:await asyncio.wait_for(stop_event.wait(),timeout=15)
   except asyncio.TimeoutError:pass
