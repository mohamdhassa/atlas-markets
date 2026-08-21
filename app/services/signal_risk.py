from __future__ import annotations

import json
from dataclasses import dataclass
from app.analysis.strategy_intelligence import scenario_from_candles

@dataclass(frozen=True)
class GeneratedSignal:
    decision:str
    classification:str
    score:float
    strength:float
    reasons:list[str]

def generate_signal(candles:list[dict])->GeneratedSignal:
    scenario=scenario_from_candles(candles,timeframe="5m",market="CRYPTO")
    action=str(scenario.get("action","WAIT")).upper();decision="BUY" if action=="BUY" else "SELL" if action=="SELL" else "HOLD"
    bull=float(scenario.get("bullish_probability",50.0));bear=float(scenario.get("bearish_probability",50.0));score=bull
    strength=bull if decision=="BUY" else bear if decision=="SELL" else max(bull,bear)
    classification="NO_SIGNAL" if decision=="HOLD" else "STRONG_SIGNAL" if strength>=80 else "SIGNAL" if strength>=65 else "WATCH"
    reasons=list(scenario.get("reasons") or [])
    trend=str(scenario.get("trend","NEUTRAL")).lower()
    trend_reason=f"trend_{trend}"
    if trend_reason not in reasons:
        reasons.insert(0,trend_reason)
    return GeneratedSignal(decision=decision,classification=classification,score=score,strength=strength,reasons=reasons)

def evaluate_risk(signal:GeneratedSignal,*,minimum_signal_score:float,account_enabled:bool,allow_live_trading:bool,account_environment:str)->tuple[bool,str,dict]:
    environment=account_environment.upper()
    if not account_enabled:return False,"ACCOUNT_DISABLED",{"account_enabled":False}
    if signal.decision=="HOLD":return False,"NO_DIRECTION",{"decision":signal.decision}
    if signal.strength<minimum_signal_score:return False,"SIGNAL_SCORE_BELOW_MINIMUM",{"score":signal.score,"strength":signal.strength,"minimum_signal_score":minimum_signal_score}
    if environment=="LIVE" and not allow_live_trading:return False,"LIVE_TRADING_DISABLED",{"environment":environment}
    return True,"APPROVED_FOR_SIMULATION",{"score":signal.score,"strength":signal.strength,"minimum_signal_score":minimum_signal_score,"environment":environment}

def reasons_json(reasons:list[str])->str:return json.dumps(reasons,separators=(",",":"))
