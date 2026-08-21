from app.services.signal_risk import evaluate_risk, generate_signal

def candles(start:float=100.0,step:float=0.8,count:int=80)->list[dict]:
    rows=[];price=start
    for i in range(count):
        open_price=price;close=price+step;rows.append({"open":open_price,"high":max(open_price,close)+0.4,"low":min(open_price,close)-0.4,"close":close,"volume":1000+i});price=close
    return rows

def test_generate_buy_signal_from_uptrend():
    signal=generate_signal(candles(step=0.8));assert signal.decision=="BUY";assert signal.score>=65;assert signal.strength>=65;assert signal.classification in {"SIGNAL","STRONG_SIGNAL"};assert any(r.startswith("trend_") for r in signal.reasons)

def test_generate_sell_signal_from_downtrend():
    signal=generate_signal(candles(start=200.0,step=-0.8));assert signal.decision=="SELL";assert signal.score<=35;assert signal.strength>=65

def test_risk_rejects_disabled_account():
    signal=generate_signal(candles(step=0.8));approved,reason,_=evaluate_risk(signal,minimum_signal_score=65,account_enabled=False,allow_live_trading=False,account_environment="DEMO");assert approved is False;assert reason=="ACCOUNT_DISABLED"

def test_risk_rejects_live_when_server_disallows_live():
    signal=generate_signal(candles(step=0.8));approved,reason,_=evaluate_risk(signal,minimum_signal_score=65,account_enabled=True,allow_live_trading=False,account_environment="LIVE");assert approved is False;assert reason=="LIVE_TRADING_DISABLED"

def test_risk_approves_demo_for_simulation():
    signal=generate_signal(candles(step=0.8));approved,reason,details=evaluate_risk(signal,minimum_signal_score=65,account_enabled=True,allow_live_trading=False,account_environment="DEMO");assert approved is True;assert reason=="APPROVED_FOR_SIMULATION";assert details["environment"]=="DEMO"
