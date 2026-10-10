import json
from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
from app.services.ibkr_ledger_history import saved_fill, merge_saved_fills
from app.api.routes_broker_native import _pair_execution_lots, _stats


def profile():
    return SimpleNamespace(id='p', user_id='u', environment='PAPER', account_label='Paper')


def action(order=10, side='BUY', closed=False, hour=10):
    return SimpleNamespace(provider='IBKR', status='EXIT_EXECUTED' if closed else 'EXECUTED',
        broker_profile_id='p', user_id='u', environment='PAPER', broker_order_id=str(order),
        quantity=2, side=side, market='STOCK', symbol='MSFT',
        created_at=datetime(2026,10,9,hour,tzinfo=timezone.utc),
        raw_json=json.dumps({'result':{'broker_result':{'order_id':order,'account_id':'DU_TEST',
            'final_status':{'order_id':order,'status':{'order_id':order,'status':'Filled',
            'filled':2,'remaining':0,'avg_fill_price':100 if not closed else 105}}}},
            'preflight':{'broker_check':{'commission':{'estimate':1}}}}))


def test_saved_closes_survive_empty_bridge_and_never_invent_net_pnl():
    rows=merge_saved_fills([], [action(), action(11,'SELL',True,11)], profile(), 'DU_TEST')
    _pair_execution_lots(rows)
    close=rows[1]
    assert close['closed_trade'] and close['entry_price']==100
    assert close['duration_seconds']==3600 and close['invested_amount']==200
    assert close['pnl'] is None and close['commission'] is None
    assert not close['pnl_available'] and close['return_pct'] is None
    assert _stats(rows)['realized_pnl']==0 and _stats(rows)['pnl_trades']==0


def test_short_close_context_is_paired():
    rows=merge_saved_fills([], [action(side='SELL'),action(11,'BUY',True,11)],profile(),'DU_TEST')
    _pair_execution_lots(rows)
    assert rows[1]['entry_price']==100 and rows[1]['closed_trade']


@pytest.mark.parametrize('field,value', [('user_id','other'),('broker_profile_id','other'),
    ('environment','LIVE'),('provider','BYBIT'),('status','SUBMITTED')])
def test_wrong_scope_and_unfilled_actions_are_excluded(field,value):
    row=action();setattr(row,field,value)
    assert saved_fill(row,profile(),'DU_TEST') is None


@pytest.mark.parametrize('field,value', [('status','Submitted'),('filled',1),('remaining',1),
    ('avg_fill_price',0),('avg_fill_price',float('nan')),('order_id',99)])
def test_incomplete_or_invalid_fill_evidence_is_excluded(field,value):
    row=action();raw=json.loads(row.raw_json)
    raw['result']['broker_result']['final_status']['status'][field]=value
    row.raw_json=json.dumps(raw)
    assert saved_fill(row,profile(),'DU_TEST') is None


def test_wrong_broker_account_is_excluded():
    assert saved_fill(action(),profile(),'OTHER') is None


def test_live_fills_win_and_duplicate_actions_do_not_duplicate_rows():
    live={'profile_id':'p','broker_order_id':11,'pnl_available':True,'pnl':8,'commission':2}
    rows=merge_saved_fills([live], [action(11,'SELL',True),action(11,'SELL',True)],profile(),'DU_TEST')
    assert rows==[live] and live['closed_trade'] and live['pnl']==8


def test_other_profiles_same_order_id_do_not_suppress_saved_history():
    rows=merge_saved_fills([{'profile_id':'other','broker_order_id':10}], [action()],profile(),'DU_TEST')
    assert len(rows)==2


def test_frontend_displays_pending_closed_rows_without_showing_open_entries():
    from pathlib import Path
    text=Path('app/static/live-pages.js').read_text()
    assert '.filter(x=>x.pnl_available||x.closed_trade)' in text
    assert "x.pnl_available?moneyLive(x.pnl):'P&amp;L pending'" in text

@pytest.mark.parametrize('history_fails',[False,True])
def test_report_recovers_history_even_if_bridge_is_empty_or_unavailable(monkeypatch,history_fails):
    import asyncio
    import app.api.routes_broker_native as route
    p=profile();p.provider='IBKR';p.credentials_configured=True
    class Broker:
        async def account(self):return {'equity':1000,'available':500}
        async def executions(self,days):
            if history_fails:raise RuntimeError('bridge unavailable')
            return {'list':[]}
    class DB:
        def scalars(self,query):
            return SimpleNamespace(all=lambda:[action(),action(11,'SELL',True,11)])
    monkeypatch.setattr(route,'_accounts',lambda db,user:[p])
    monkeypatch.setattr(route,'_symbol_market_map',lambda db,pid:{})
    monkeypatch.setattr(route,'_creds',lambda p:{'account_id':'DU_TEST'})
    monkeypatch.setattr(route,'_ibkr',lambda p:Broker())
    monkeypatch.setattr(route,'_trade_context',lambda db,user,rows:rows)
    p.simulation_capital_override_usd=None
    result=asyncio.run(route.broker_performance.__wrapped__(days=30,user=SimpleNamespace(role='ADMIN'),db=DB()))
    closed=[row for row in result['trades'] if row.get('closed_trade')]
    assert len(closed)==1 and closed[0]['entry_price']==100
    assert closed[0]['pnl'] is None
    assert result['overall']['pnl_trades']==0
    assert bool(result['errors'])==history_fails
