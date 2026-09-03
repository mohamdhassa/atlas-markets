from __future__ import annotations

import json
import math
from sqlalchemy import select

from app.brokers.bybit_private import BybitPrivateClient
from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.broker import BrokerProfile
from app.db.models.signal import RiskProfile
from app.db.models.strategy import StrategyProfile
from app.db.models.symbol_strategy import SymbolStrategy
from app.market_data.bybit import BybitPublicMarketData
from app.services.paper_execution import build_execution_plan
from app.services.signal_risk import evaluate_risk, generate_signal

READINESS_MAX_GROSS_EXPOSURE_PCT = 50.0
READINESS_MAX_NEW_POSITIONS_PER_ACCOUNT = 5
IBKR_CERTIFIED_MAX_SHARES_PER_ORDER = 1


def _secret(profile) -> dict:
    if not profile.credential_blob_encrypted: raise RuntimeError(f'{profile.provider} bridge configuration missing')
    return json.loads(decrypt_secret(profile.credential_blob_encrypted))

def _risk(db):
    row=db.scalar(select(RiskProfile).where(RiskProfile.name=='Default')); return row or RiskProfile(name='Default')
def _strategy(db):
    row=db.scalar(select(StrategyProfile).where(StrategyProfile.name=='Default')); return row or StrategyProfile(name='Default')
def _params(cfg,default,risk):
    minimum=max(risk.minimum_signal_score,cfg.minimum_signal_strength if cfg.minimum_signal_strength is not None else default.minimum_signal_strength)
    risk_pct=min(risk.risk_per_trade_pct,cfg.risk_per_trade_pct if cfg.risk_per_trade_pct is not None else risk.risk_per_trade_pct)
    stop=cfg.stop_atr_multiplier if cfg.stop_atr_multiplier is not None else default.stop_atr_multiplier
    rr=cfg.take_profit_rr if cfg.take_profit_rr is not None else default.take_profit_rr
    max_pos=cfg.max_position_notional_pct if cfg.max_position_notional_pct is not None else default.max_position_notional_pct
    return cfg.timeframe or default.timeframe,minimum,risk_pct,stop,rr,max_pos

def _round_volume(raw,info):
    mn=float(info.get('volume_min') or .01);mx=float(info.get('volume_max') or raw);step=float(info.get('volume_step') or mn);value=max(mn,min(mx,raw));value=math.floor(value/step)*step;return round(max(mn,value),8)
def _ibkr_quote_price(quote,decision):
    for field in (('ask','last','bid') if decision=='BUY' else ('bid','last','ask')):
        try: price=float(quote.get(field) or 0)
        except (TypeError,ValueError): continue
        if math.isfinite(price) and price>0:return price
    return 0.0
def _provider_execution_blockers(profile): return ['PROVIDER_EXECUTION_NOT_CERTIFIED'] if profile.provider=='BYBIT' else []
def _portfolio_guard(*,equity,existing_positions,existing_gross_notional,reserved_new_notional,reserved_new_positions,proposed_notional):
    if equity<=0:return ['PORTFOLIO_EQUITY_UNAVAILABLE']
    blockers=[];max_gross=equity*(READINESS_MAX_GROSS_EXPOSURE_PCT/100);projected=max(0,existing_gross_notional)+max(0,reserved_new_notional)+max(0,proposed_notional)
    if projected>max_gross+1e-8:blockers.append('PORTFOLIO_GROSS_EXPOSURE_LIMIT')
    if existing_positions+reserved_new_positions+1>READINESS_MAX_NEW_POSITIONS_PER_ACCOUNT:blockers.append('PORTFOLIO_POSITION_LIMIT')
    return blockers
def _position_notional(position):
    for key in ('market_value','marketValue','notional','position_value','positionValue'):
        try:value=abs(float(position.get(key) or 0))
        except (TypeError,ValueError):value=0
        if value>0:return value
    qty=abs(float(position.get('quantity') or position.get('volume') or position.get('size') or 0))
    for key in ('market_price','marketPrice','price','markPrice','current_price','currentPrice'):
        try:price=abs(float(position.get(key) or 0))
        except (TypeError,ValueError):price=0
        if price>0:return qty*price
    return 0.0

async def autotrade_readiness(db,*,user_id)->dict:
    settings=get_settings();risk=_risk(db);default=_strategy(db);configs=list(db.scalars(select(SymbolStrategy).where(SymbolStrategy.user_id==user_id,SymbolStrategy.enabled.is_(True))).all());profiles={p.id:p for p in db.scalars(select(BrokerProfile).where(BrokerProfile.user_id==user_id)).all()};market=BybitPublicMarketData(settings.bybit_public_base_url,settings.market_data_timeout_seconds);rows=[];portfolio_reservations={}
    for cfg in sorted(configs,key=lambda x:(x.market,x.symbol)):
        profile=profiles.get(cfg.profile_id);base={'market':cfg.market,'symbol':cfg.symbol,'mode':cfg.mode,'execution':'DRY_RUN'}
        if not profile:rows.append({**base,'readiness':'BLOCK','reason':'PROFILE_MISSING'});continue
        base.update(provider=profile.provider,environment=profile.environment)
        if not(profile.is_enabled and profile.is_active and profile.credentials_configured and profile.last_connection_status=='CONNECTED'):rows.append({**base,'readiness':'BLOCK','reason':'ROUTE_NOT_READY'});continue
        try:
            timeframe,minimum,risk_pct,stop,rr,max_pos=_params(cfg,default,risk);existing_qty=existing_positions=0;existing_gross=equity=available=price=0.0;sizing={}
            signal_market=str(cfg.market or 'CRYPTO').upper()
            if profile.provider=='BYBIT':
                candles=await market.get_candles(symbol=cfg.symbol,interval=timeframe,category='linear',limit=200);generated=generate_signal([x.model_dump() for x in candles],timeframe=timeframe,market=signal_market);base_url=settings.bybit_demo_base_url if profile.environment=='DEMO' else settings.bybit_testnet_base_url;broker=BybitPrivateClient(decrypt_secret(profile.api_key_encrypted),decrypt_secret(profile.api_secret_encrypted),base_url,settings.market_data_timeout_seconds);wallet=await broker.wallet();positions=await broker.positions();account=(wallet.get('list') or [{}])[0];equity=float(account.get('totalEquity') or account.get('totalWalletBalance') or 0);available=float(account.get('totalAvailableBalance') or account.get('totalWalletBalance') or equity);active=[p for p in positions.get('list',[]) if float(p.get('size') or 0)!=0];existing_positions=len(active);existing_gross=sum(_position_notional(p) for p in active);existing_qty=sum(float(p.get('size') or 0) for p in active if str(p.get('symbol') or '').upper()==cfg.symbol.upper());ticker=await market.get_tickers(category='linear',symbols=(cfg.symbol,));price=float(ticker.tickers[0].last_price) if ticker.tickers else 0
            elif profile.provider=='MT5':
                c=_secret(profile);broker=Mt5BridgeClient(c.get('bridge_url') or 'http://host.docker.internal:8765',c.get('bridge_token'),settings.market_data_timeout_seconds);generated=generate_signal((await broker.candles(cfg.symbol,timeframe,200)).get('list',[]),timeframe=timeframe,market=signal_market);acct=await broker.account();positions=(await broker.positions()).get('list',[]);equity=float(acct.get('equity') or 0);available=float(acct.get('margin_free') or equity);existing_positions=len(positions);existing_gross=sum(_position_notional(p) for p in positions);existing_qty=sum(float(p.get('volume') or p.get('quantity') or 0) for p in positions if str(p.get('symbol') or '').upper()==cfg.symbol.upper());info=await broker.symbol(cfg.symbol);price=float(info.get('ask') if generated.decision=='BUY' else info.get('bid') or 0);sizing['contract_size']=float(info.get('trade_contract_size') or 100000);sizing['symbol_info']=info
            elif profile.provider=='IBKR':
                c=_secret(profile);broker=IbkrBridgeClient(c.get('bridge_url') or 'http://host.docker.internal:8766',c.get('bridge_token'),settings.market_data_timeout_seconds);generated=generate_signal((await broker.candles(cfg.symbol,timeframe,200,sec_type='STK')).get('list',[]),timeframe=timeframe,market=signal_market);acct=await broker.account();positions=[p for p in (await broker.positions()).get('list',[]) if float(p.get('quantity') or 0)!=0];equity=float(acct.get('equity') or 0);available=float(acct.get('available') or acct.get('cash') or equity);existing_positions=len(positions);existing_gross=sum(_position_notional(p) for p in positions);existing_qty=sum(float(p.get('quantity') or 0) for p in positions if str(p.get('symbol') or '').upper()==cfg.symbol.upper());price=_ibkr_quote_price(await broker.quote(cfg.symbol,sec_type='STK'),generated.decision)
            else:rows.append({**base,'readiness':'BLOCK','reason':'UNSUPPORTED_PROVIDER'});continue
            approved,reason,details=evaluate_risk(generated,minimum_signal_score=minimum,account_enabled=profile.is_enabled,allow_live_trading=False,account_environment=profile.environment);blockers=_provider_execution_blockers(profile)
            if not approved:blockers.append(reason)
            if existing_positions>=risk.max_open_positions:blockers.append('MAX_OPEN_POSITIONS_REACHED')
            if existing_qty!=0:blockers.append('SYMBOL_ALREADY_HAS_POSITION')
            proposed=None;reservation=portfolio_reservations.setdefault(str(profile.id),{'notional':0.0,'positions':0});portfolio={'existing_gross_notional':round(existing_gross,8),'reserved_new_notional':round(float(reservation['notional']),8),'gross_exposure_limit_pct':READINESS_MAX_GROSS_EXPOSURE_PCT,'new_position_limit':READINESS_MAX_NEW_POSITIONS_PER_ACCOUNT}
            if approved and price>0:
                plan=build_execution_plan(decision=generated.decision,price=price,equity=equity,available_cash=available,risk_per_trade_pct=risk_pct,stop_atr_multiplier=stop,take_profit_rr=rr,max_position_notional_pct=max_pos);effective_notional=plan.notional;proposed={'side':plan.side,'price':price,'notional':plan.notional,'quantity':plan.quantity,'stop_loss':plan.stop_loss,'take_profit':plan.take_profit}
                if profile.provider=='MT5':proposed['volume']=_round_volume(plan.quantity/sizing['contract_size'],sizing['symbol_info'])
                if profile.provider=='IBKR':
                    strategy_shares=max(0,math.floor(plan.quantity));certified_shares=min(strategy_shares,IBKR_CERTIFIED_MAX_SHARES_PER_ORDER);effective_notional=certified_shares*price;proposed.update({'strategy_requested_shares':strategy_shares,'shares':certified_shares,'quantity':certified_shares,'notional':effective_notional,'sizing_policy':'CERTIFIED_MAX_1_SHARE','certified_max_shares':IBKR_CERTIFIED_MAX_SHARES_PER_ORDER})
                if effective_notional>available:blockers.append('INSUFFICIENT_AVAILABLE_BALANCE')
                blockers.extend(_portfolio_guard(equity=equity,existing_positions=existing_positions,existing_gross_notional=existing_gross,reserved_new_notional=float(reservation['notional']),reserved_new_positions=int(reservation['positions']),proposed_notional=effective_notional))
                if not blockers:reservation['notional']=float(reservation['notional'])+effective_notional;reservation['positions']=int(reservation['positions'])+1
                portfolio['projected_gross_notional']=round(existing_gross+float(reservation['notional'])+(0 if not blockers else effective_notional),8)
            signal_ready=approved and price>0;rows.append({**base,'timeframe':timeframe,'decision':generated.decision,'classification':generated.classification,'strength':generated.strength,'signal_reason':reason,'risk_details':details,'account':{'equity':equity,'available':available,'open_positions':existing_positions},'portfolio':portfolio,'existing_symbol_quantity':existing_qty,'proposed_order':proposed,'signal_ready':signal_ready,'execution_ready':not blockers,'readiness':'PASS' if not blockers else 'BLOCK','blockers':blockers})
        except Exception as exc:rows.append({**base,'readiness':'BLOCK','reason':f'{type(exc).__name__}: {str(exc) or repr(exc)}'})
    return {'execution_enabled':False,'purpose':'AUTO_TRADE_READINESS_DRY_RUN','portfolio_policy':{'max_gross_exposure_pct':READINESS_MAX_GROSS_EXPOSURE_PCT,'max_new_positions_per_account':READINESS_MAX_NEW_POSITIONS_PER_ACCOUNT,'ibkr_paper_max_shares_per_order':IBKR_CERTIFIED_MAX_SHARES_PER_ORDER},'configured_count':len(configs),'pass_count':sum(x.get('readiness')=='PASS' for x in rows),'block_count':sum(x.get('readiness')=='BLOCK' for x in rows),'items':rows}
