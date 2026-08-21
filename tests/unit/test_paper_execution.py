import pytest
from app.services.paper_execution import build_execution_plan, exit_trigger, position_pnl

def test_buy_plan_uses_risk_and_two_to_one_reward():
    p=build_execution_plan(decision="BUY",price=100.0,equity=100000.0,available_cash=100000.0,risk_per_trade_pct=1.0,atr=2.0)
    assert p.side=="BUY";assert p.notional<=20000;assert p.stop_loss==97.0;assert p.take_profit==106.0;assert p.risk_amount==1000.0

def test_short_pnl_is_positive_when_price_falls():
    assert position_pnl(side="SELL",quantity=2,entry_price=100,mark_price=90)==20

def test_stop_and_take_profit_triggers():
    assert exit_trigger(side="BUY",mark_price=95,stop_loss=96,take_profit=108)=="STOP_LOSS"
    assert exit_trigger(side="SELL",mark_price=90,stop_loss=105,take_profit=92)=="TAKE_PROFIT"
    assert exit_trigger(side="BUY",mark_price=100,stop_loss=95,take_profit=110) is None

def test_non_directional_signal_cannot_execute():
    with pytest.raises(ValueError): build_execution_plan(decision="HOLD",price=100,equity=100000,available_cash=100000,risk_per_trade_pct=1)
