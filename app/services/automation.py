from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models.automation import AutomationScan, AutomationState
from app.db.models.broker import BrokerProfile
from app.db.models.paper import PaperOrder, PaperPosition, PaperWallet
from app.db.models.signal import RiskEvent, RiskProfile, Signal
from app.db.models.strategy import StrategyProfile
from app.db.session import SessionLocal
from app.market_data.bybit import BybitPublicMarketData
from app.services.historical_intelligence import db_candles, historical_probability
from app.services.news_intelligence import apply_news_context, context_for_symbol, refresh_news
from app.services.paper_execution import build_execution_plan
from app.services.signal_risk import GeneratedSignal, evaluate_risk, generate_signal, reasons_json


def get_or_create_state(db):
    state=db.scalar(select(AutomationState).where(AutomationState.name=="default"))
    if state is None:state=AutomationState(name="default");db.add(state);db.commit();db.refresh(state)
    return state

def _risk(db):
    r=db.scalar(select(RiskProfile).where(RiskProfile.name=="Default"))
    if r is None:r=RiskProfile(name="Default");db.add(r);db.commit();db.refresh(r)
    return r

def _strategy(db):
    s=db.scalar(select(StrategyProfile).where(StrategyProfile.name=="Default"))
    if s is None:s=StrategyProfile(name="Default");db.add(s);db.commit();db.refresh(s)
    return s

def _wallet(db,profile_id):
    w=db.scalar(select(PaperWallet).where(PaperWallet.profile_id==profile_id))
    if w is None:w=PaperWallet(profile_id=profile_id);db.add(w);db.commit();db.refresh(w)
    return w

def _with_history(signal:GeneratedSignal,history:dict)->GeneratedSignal:
    if history.get("matches",0)<25 or signal.decision not in {"BUY","SELL"}:return signal
    support=float(history["up_probability"] if signal.decision=="BUY" else history["down_probability"])
    strength=round(signal.strength*0.70+support*0.30,2)
    classification="STRONG_SIGNAL" if strength>=80 else "SIGNAL" if strength>=65 else "WATCH"
    return GeneratedSignal(decision=signal.decision,classification=classification,score=signal.score,strength=strength,reasons=[*signal.reasons,f"historical_{history['matches']}_matches",f"historical_support_{support:.1f}"])

async def run_scan()->dict:
    settings=get_settings()
    with SessionLocal() as db:
        state=get_or_create_state(db);strategy=_strategy(db)
        if not state.enabled or state.killed or not strategy.enabled:
            reason="ENGINE_DISABLED" if not state.enabled else "KILL_SWITCH" if state.killed else "STRATEGY_DISABLED";return {"status":"SKIPPED","reason":reason}
        symbols=[s.strip().upper() for s in state.symbols_csv.split(",") if s.strip()]
        accounts=list(db.scalars(select(BrokerProfile).where(BrokerProfile.provider=="ATLAS_PAPER",BrokerProfile.is_enabled.is_(True))).all())
        scan=AutomationScan(status="RUNNING",symbols_count=len(symbols),accounts_count=len(accounts));db.add(scan);db.commit();db.refresh(scan)
        market=BybitPublicMarketData(settings.bybit_public_base_url,settings.market_data_timeout_seconds);risk=_risk(db)
        try:
            try:await refresh_news(db)
            except Exception:pass
            for account in accounts:
                for symbol in symbols:
                    candles=await market.get_candles(symbol=symbol,interval=strategy.timeframe,category="linear",limit=200)
                    technical=generate_signal([c.model_dump() for c in candles]);news=context_for_symbol(db,symbol,hours=24);generated=apply_news_context(technical,news)
                    history=historical_probability(db_candles(db,"CRYPTO",symbol,strategy.timeframe),horizon=6);generated=_with_history(generated,history)
                    minimum=max(risk.minimum_signal_score,strategy.minimum_signal_strength);approved,reason,details=evaluate_risk(generated,minimum_signal_score=minimum,account_enabled=account.is_enabled,allow_live_trading=False,account_environment="PAPER")
                    details["news"]={"bias":news.bias,"sentiment":news.sentiment,"article_count":news.article_count};details["historical"]=history
                    sig=Signal(profile_id=account.id,symbol=symbol,timeframe=strategy.timeframe,decision=generated.decision,classification=generated.classification,score=generated.score,reasons_json=reasons_json(generated.reasons),risk_status="APPROVED" if approved else "REJECTED")
                    db.add(sig);db.flush();db.add(RiskEvent(profile_id=account.id,signal_id=sig.id,approved=approved,reason_code=reason,details_json=json.dumps(details,separators=(",",":"))));scan.signals_count+=1
                    if approved:scan.approved_count+=1
                    if approved and state.auto_execute_paper and generated.decision in {"BUY","SELL"}:
                        open_positions=list(db.scalars(select(PaperPosition).where(PaperPosition.profile_id==account.id)).all());same_symbol=db.scalar(select(PaperPosition).where(PaperPosition.profile_id==account.id,PaperPosition.symbol==symbol))
                        if len(open_positions)<risk.max_open_positions and same_symbol is None:
                            ticker=await market.get_tickers(category="linear",symbols=(symbol,))
                            if ticker.tickers:
                                price=ticker.tickers[0].last_price;wallet=_wallet(db,account.id);equity=wallet.cash_balance+sum(p.entry_price*p.quantity for p in open_positions)
                                plan=build_execution_plan(decision=generated.decision,price=price,equity=equity,available_cash=wallet.cash_balance,risk_per_trade_pct=risk.risk_per_trade_pct,stop_atr_multiplier=strategy.stop_atr_multiplier,take_profit_rr=strategy.take_profit_rr,max_position_notional_pct=strategy.max_position_notional_pct)
                                if plan.notional<=wallet.cash_balance:
                                    wallet.cash_balance-=plan.notional;db.add(PaperOrder(profile_id=account.id,signal_id=sig.id,symbol=symbol,side=plan.side,quantity=plan.quantity,fill_price=price,notional=plan.notional,status="FILLED"));db.add(PaperPosition(profile_id=account.id,signal_id=sig.id,symbol=symbol,side=plan.side,quantity=plan.quantity,entry_price=price,mark_price=price,stop_loss=plan.stop_loss,take_profit=plan.take_profit));scan.executed_count+=1
                    db.flush()
            now=datetime.now(timezone.utc);scan.status="COMPLETED";scan.finished_at=now;state.last_scan_at=now;state.next_scan_at=now+timedelta(seconds=state.interval_seconds);db.commit();return {"status":scan.status,"signals":scan.signals_count,"approved":scan.approved_count,"executed":scan.executed_count}
        except Exception as exc:
            scan.status="FAILED";scan.error_message=str(exc)[:500];scan.finished_at=datetime.now(timezone.utc);db.commit();return {"status":"FAILED","error":scan.error_message}

async def automation_loop(stop_event:asyncio.Event):
    while not stop_event.is_set():
        try:
            with SessionLocal() as db:
                state=get_or_create_state(db);wait=max(10,state.interval_seconds);due=state.next_scan_at is None or state.next_scan_at<=datetime.now(timezone.utc);enabled=state.enabled and not state.killed
            if enabled and due:await run_scan()
            try:await asyncio.wait_for(stop_event.wait(),timeout=min(wait,30))
            except asyncio.TimeoutError:pass
        except Exception:
            try:await asyncio.wait_for(stop_event.wait(),timeout=15)
            except asyncio.TimeoutError:pass
