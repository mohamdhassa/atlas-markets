import asyncio
import time
from types import SimpleNamespace as NS

import pytest
from app.core.config import Settings
from app.services import autotrade_readiness as readiness
from app.services import safe_automation as execution
from app.services import trading_candles as candles
from app.services import ibkr_paper_data as paper

NOW = 1790000000000


@pytest.mark.parametrize('enabled,environment,live,expected', [
    (False,'PAPER',False,False), (True,'PAPER',False,True),
    (True,'LIVE',False,False), (True,'DEMO',False,False),
    (True,'PAPER',True,False),
])
def test_mode_requires_explicit_flag_paper_environment_and_live_disabled(enabled,environment,live,expected):
    settings = NS(ibkr_paper_delayed_data_enabled=enabled, allow_live_trading=live)
    result = asyncio.run(paper.delayed_paper_mode(settings,environment,None,
                         health={'connected':True,'simulation':True}))
    assert result is expected


@pytest.mark.parametrize('health', [
    {'connected':False,'simulation':True}, {'connected':True,'simulation':False},
    {'connected':True}, {'connected':True,'simulation':1},
])
def test_mode_refuses_unverified_paper_bridge(health):
    with pytest.raises(ValueError,match='IBKR_PAPER_BRIDGE_REQUIRED'):
        asyncio.run(paper.delayed_paper_mode(NS(ibkr_paper_delayed_data_enabled=True),
                                            'PAPER',None,health=health))


def rows(age=900000,count=200,price=100):
    return [dict(timestamp_ms=NOW-age-300000,close=price)] * count


@pytest.mark.parametrize('age,passed', [(900000,True),(1590000,True),
                                       (1590001,False),(-1,False),(86400000,False)])
def test_delayed_window_is_bounded_not_disabled(age,passed):
    result = candles.entry_candle_quality(rows(age),'5m',now_ms=NOW,paper_delayed=True)
    assert (result['reason'] is None) is passed
    assert result['maximum_age_ms']==1590000
    assert result['policy']==paper.POLICY
    if age==900000:
        assert candles.entry_candle_quality(rows(age),'5m',now_ms=NOW)['reason']=='ENTRY_CANDLES_STALE'


def test_missing_history_still_blocks_and_reference_never_claims_live_quote():
    with pytest.raises(ValueError,match='HISTORY_INSUFFICIENT'):
        paper.delayed_reference(rows(count=199),'5m',now_ms=NOW)
    quote,evidence=paper.delayed_reference(rows(),'5m',now_ms=NOW)
    assert quote['last']==100
    assert quote['reference_bar_end_ms']==NOW-900000
    assert evidence['age_ms']==900000 and evidence['real_time'] is False
    assert evidence['data_status']=='DELAYED_SIMULATION'
    assert candles.ibkr_entry_quote_quality(quote,now_ms=NOW)['reason']=='IBKR_ENTRY_REALTIME_QUOTE_REQUIRED'


@pytest.mark.parametrize('price',[0,-1,float('nan'),float('inf')])
def test_invalid_reference_price_rejected(price):
    with pytest.raises(ValueError,match='PRICE_INVALID'):
        paper.delayed_reference(rows(price=price),'5m',now_ms=NOW)


def setup(monkeypatch, lag=900000):
    from unit.test_ibkr_whole_share_sizing import route
    DB,Broker,settings=route.__wrapped__(monkeypatch)
    settings.ibkr_paper_delayed_data_enabled=True
    settings.allow_live_trading=False
    original=Broker.candles
    async def lagged(self,*args,**kwargs):
        payload=await original(self,*args,**kwargs)
        for row in payload['list']:row['timestamp_ms']-=lag
        return payload
    async def health(self):return {'connected':True,'simulation':True}
    async def orders(self):return {'list':[]}
    async def no_snapshot(*args,**kwargs):pytest.fail('Paper delayed mode should use completed reference, not snapshot')
    monkeypatch.setattr(Broker,'candles',lagged)
    monkeypatch.setattr(Broker,'health',health,raising=False)
    monkeypatch.setattr(Broker,'orders',orders,raising=False)
    monkeypatch.setattr(Broker,'quote',no_snapshot)
    return DB,Broker,settings


def test_readiness_uses_paper_reference_and_retains_strategy_and_size_guards(monkeypatch):
    DB,Broker,_=setup(monkeypatch)
    row=asyncio.run(readiness.autotrade_readiness(DB(),user_id=1))['items'][0]
    assert row['readiness']=='PASS',row
    quality=row['market_data_quality']
    assert quality['candles']['policy']==paper.POLICY
    assert quality['quote']['data_status']=='DELAYED_SIMULATION'
    assert row['strategy_route']['strategy']=='trend'
    assert row['proposed_order']['shares']>=1
    assert row['proposed_order']['price']==100


def test_execution_rechecks_delayed_reference_before_whatif_and_keeps_authorization(monkeypatch):
    DB,Broker,_=setup(monkeypatch)
    async def place(self,payload,**kwargs):
        assert kwargs['before_submit']() is None
        return {'accepted':True,'order_id':99}
    async def verify(*args):return 'FILLED',{'status':'Filled'}
    monkeypatch.setattr(Broker,'place_order',place,raising=False)
    monkeypatch.setattr(execution,'_entry_authorization_blocker',lambda *args:None)
    monkeypatch.setattr(execution,'_verify_ibkr_fill',verify)
    result=asyncio.run(execution._execute_ibkr(DB(),user_id=1,item={
        'market':'STOCK','symbol':'TSLA','request':{'side':'BUY','shares':2}}))
    assert result['status']=='EXECUTED'
    assert len(Broker.checks)==1 and Broker.checks[0]['quantity']==2
    assert result['market_data_quality']['quote']['real_time'] is False


def test_execution_rejects_older_data_without_whatif_or_order(monkeypatch):
    DB,Broker,_=setup(monkeypatch,lag=3600000)
    result=asyncio.run(execution._execute_ibkr(DB(),user_id=1,item={
        'market':'STOCK','symbol':'TSLA','request':{'side':'BUY','shares':2}}))
    assert result['reason']=='ENTRY_CANDLES_STALE'
    assert Broker.checks==[]


def test_kill_during_delayed_preflight_still_blocks_submission(monkeypatch):
    DB,Broker,_=setup(monkeypatch)
    async def forbidden(*args,**kwargs):pytest.fail('submit after kill')
    monkeypatch.setattr(Broker,'place_order',forbidden,raising=False)
    monkeypatch.setattr(execution,'_entry_authorization_blocker',lambda *args:'KILL_SWITCH')
    result=asyncio.run(execution._execute_ibkr(DB(),user_id=1,item={
        'market':'STOCK','symbol':'TSLA','request':{'side':'BUY','shares':2}}))
    assert result['reason']=='KILL_SWITCH'


def test_flag_defaults_off():
    assert Settings(_env_file=None).ibkr_paper_delayed_data_enabled is False


def test_delayed_mode_does_not_bypass_router(monkeypatch):
    DB,_,_=setup(monkeypatch)
    monkeypatch.setattr(readiness,'route_strategy',lambda *args:{'strategy':'NO_TRADE','regime':'LOW_VOLATILITY'})
    row=asyncio.run(readiness.autotrade_readiness(DB(),user_id=1))['items'][0]
    assert row['readiness']=='BLOCK'
    assert 'STRATEGY_ROUTER_NO_TRADE' in row['blockers']


def test_delayed_mode_cannot_add_to_existing_symbol(monkeypatch):
    DB,Broker,_=setup(monkeypatch)
    async def positions(self):return {'list':[{'symbol':'TSLA','quantity':1}]}
    monkeypatch.setattr(Broker,'positions',positions)
    result=asyncio.run(execution._execute_ibkr(DB(),user_id=1,item={
        'market':'STOCK','symbol':'TSLA','request':{'side':'BUY','shares':2}}))
    assert result['reason']=='SYMBOL_ALREADY_HAS_POSITION'
    assert Broker.checks==[]


def test_opted_in_ibkr_sizing_uses_completed_atr_and_records_basis(monkeypatch):
    DB,Broker,settings=setup(monkeypatch)
    settings.ibkr_paper_atr_sizing_enabled=True
    row=asyncio.run(readiness.autotrade_readiness(DB(),user_id=1))['items'][0]
    assert row['readiness']=='PASS',row
    proof=row['strategy_snapshot']['protection_sizing']
    assert proof['basis']=='COMPLETED_CANDLE_ATR' and proof['atr_value']==2
    assert row['proposed_order']['stop_loss']==98
    assert row['proposed_order']['take_profit']==104
    assert row['proposed_order']['shares']==int(row['proposed_order']['shares'])
