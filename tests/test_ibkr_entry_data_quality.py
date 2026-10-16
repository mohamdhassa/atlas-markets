import asyncio
import copy
import time
from types import SimpleNamespace as NS

import pytest

from app.services import trading_candles as data
from app.services import autotrade_readiness as readiness
from app.services import safe_automation as execution
import tools.ibkr_bridge as bridge

NOW=1_790_000_000_000


def quote(**changes):
    return dict(source='SNAPSHOT',market_data_type=1,received_at_ms=NOW,bid_received_at_ms=NOW,last_received_at_ms=NOW,bid=100,last=100,**changes)


def test_rth_duration_covers_200_intraday_bars_without_unbounded_requests():
    assert bridge.duration('5m',201)=='7 D'
    assert bridge.duration('3m',201)=='6 D'
    assert bridge.duration('3m',1000)=='7 D'
    assert bridge.duration('1m',1000)=='1 D'  # Safe cap; insufficient history blocks.


def test_quote_callbacks_preserve_actual_mode_delayed_ticks_and_arrival_time(monkeypatch):
    monkeypatch.setattr(bridge.time,'time',lambda:NOW/1000)
    state=bridge.State()
    state.marketDataType(1,3)
    state.tickPrice(1,68,100,None)
    state.tickString(1,88,str((NOW-900_000)//1000))
    assert state.quotes[1]==dict(market_data_type=3,last=100,received_at_ms=NOW,last_received_at_ms=NOW,
                                 delayed_ticks=True,last_trade_at_ms=NOW-900_000)
    state.tickPrice(1,4,-1,None)
    state.tickPrice(1,4,float('nan'),None)
    assert state.quotes[1]['last']==100
    state.marketDataType(2,1);state.tickPrice(2,1,99,None);state.tickPrice(2,2,101,None)
    assert data.ibkr_entry_quote_quality({'source':'SNAPSHOT',**state.quotes[2]},now_ms=NOW)['reason'] is None


@pytest.mark.parametrize('changes,reason',[
    ({'market_data_type':None},'REALTIME'),({'market_data_type':2},'REALTIME'),
    ({'market_data_type':3},'REALTIME'),({'market_data_type':4},'REALTIME'),
    ({'delayed_ticks':True},'REALTIME'),({'source':'HISTORICAL_FALLBACK'},'REALTIME'),
    ({'bid_received_at_ms':None},'QUOTE_STALE'),({'bid_received_at_ms':NOW-30_001},'QUOTE_STALE'),
    ({'bid_received_at_ms':NOW+1},'QUOTE_STALE'),({'bid':None,'last_trade_at_ms':NOW-900_000},'LAST_TRADE_STALE'),
    ({'last':float('inf'),'bid':None},'PRICE_INVALID'),
    ({'bid':None},'LAST_TRADE_TIME_REQUIRED'),
])
def test_quote_failures_cannot_approve_entry(changes,reason):
    q=quote();q.update(changes)
    assert reason in data.ibkr_entry_quote_quality(q,now_ms=NOW)['reason']


def test_arrival_is_explicitly_distinguished_from_source_timestamp():
    evidence=data.ibkr_entry_quote_quality(quote(),now_ms=NOW)
    assert evidence['reason'] is None
    assert evidence['source_timestamp_available'] is False
    assert evidence['last_trade_age_ms'] is None


@pytest.mark.parametrize('count,age,reason',[(140,0,'INSUFFICIENT'),(200,900_000,'STALE'),(200,-1,'STALE'),(200,390_000,None)])
def test_entry_coverage_and_age_are_both_required(count,age,reason):
    rows=[{'timestamp_ms':NOW-age-300_000}]*count
    result=data.entry_candle_quality(rows,'5m',now_ms=NOW)
    assert (reason in result['reason']) if reason else result['reason'] is None


def test_readiness_records_insufficient_history_before_signal(monkeypatch):
    from unit.test_ibkr_whole_share_sizing import route
    DB,Broker,_=route.__wrapped__(monkeypatch)
    original=Broker.candles
    async def short(self,*args,**kwargs):
        payload=await original(self,*args,**kwargs);payload['list']=payload['list'][-140:];return payload
    monkeypatch.setattr(Broker,'candles',short)
    monkeypatch.setattr(readiness,'generate_signal',lambda *args,**kwargs:pytest.fail('signal on short history'))
    row=asyncio.run(readiness.autotrade_readiness(DB(),user_id=1))['items'][0]
    assert row['readiness']=='BLOCK'
    assert row['market_data_quality']['candles']['count']==140


@pytest.mark.parametrize('mode',[None,2,3,4])
def test_execution_rechecks_quote_before_whatif_or_submission(monkeypatch,mode):
    from unit.test_ibkr_whole_share_sizing import route
    DB,Broker,_=route.__wrapped__(monkeypatch)
    async def health(self):return {'connected':True,'simulation':True}
    async def orders(self):return {'list':[]}
    async def delayed(self,*args,**kwargs):
        q=quote();q.update(market_data_type=mode,received_at_ms=int(time.time()*1000));return q
    monkeypatch.setattr(Broker,'health',health,raising=False)
    monkeypatch.setattr(Broker,'orders',orders,raising=False)
    monkeypatch.setattr(Broker,'quote',delayed)
    result=asyncio.run(execution._execute_ibkr(DB(),user_id=1,item={
        'market':'STOCK','symbol':'TSLA','request':{'side':'BUY','shares':2}}))
    assert result['reason']=='IBKR_ENTRY_REALTIME_QUOTE_REQUIRED'
    assert Broker.checks==[]


def test_bid_does_not_refresh_an_old_ask_for_buy_entry():
    q=quote();q.update(ask=101,ask_received_at_ms=NOW-40_000)
    assert data.ibkr_entry_quote_quality(q,side='BUY',now_ms=NOW)['reason']=='IBKR_ENTRY_QUOTE_STALE'
    assert data.ibkr_entry_quote_quality(q,side='SELL',now_ms=NOW)['reason'] is None


def test_execution_rejects_lagged_candles_before_quote_and_order(monkeypatch):
    from unit.test_ibkr_whole_share_sizing import route
    DB,Broker,_=route.__wrapped__(monkeypatch)
    async def health(self):return {'connected':True,'simulation':True}
    async def orders(self):return {'list':[]}
    original=Broker.candles
    async def lagged(self,*args,**kwargs):
        payload=await original(self,*args,**kwargs)
        for row in payload['list']:row['timestamp_ms']-=900_000
        return payload
    async def forbidden(*args,**kwargs):pytest.fail('quote/order must not be requested')
    monkeypatch.setattr(Broker,'health',health,raising=False)
    monkeypatch.setattr(Broker,'orders',orders,raising=False)
    monkeypatch.setattr(Broker,'candles',lagged)
    monkeypatch.setattr(Broker,'quote',forbidden)
    result=asyncio.run(execution._execute_ibkr(DB(),user_id=1,item={
        'market':'STOCK','symbol':'TSLA','request':{'side':'BUY','shares':2}}))
    assert result['reason']=='ENTRY_CANDLES_STALE'
    assert Broker.checks==[]


@pytest.mark.parametrize('mode,status',[(1,'LIVE'),(2,'FROZEN'),(3,'DELAYED'),(4,'DELAYED_FROZEN'),(None,'UNKNOWN')])
def test_quote_endpoint_exposes_mode_and_retains_chart_price(monkeypatch,mode,status):
    monkeypatch.setattr(bridge,'auth',lambda *args:None)
    monkeypatch.setattr(bridge,'read_ready',lambda *args:None)
    monkeypatch.setattr(bridge,'rid',lambda:98761)
    monkeypatch.setattr(bridge,'prepare',lambda *args:None)
    monkeypatch.setattr(bridge,'wait',lambda *args:None)
    def request(req,*args):
        if mode is not None:bridge.ib.marketDataType(req,mode)
        bridge.ib.tickPrice(req,4,100,None)
    monkeypatch.setattr(bridge.ib,'reqMktData',request)
    result=bridge.quote('TSLA')
    assert result['source']=='SNAPSHOT' and result['last']==100
    assert result['data_status']==status
    assert 'last_received_at_ms' in result


def test_historical_quote_remains_displayable_but_entry_ineligible(monkeypatch):
    monkeypatch.setattr(bridge,'auth',lambda *args:None)
    monkeypatch.setattr(bridge,'read_ready',lambda *args:None)
    monkeypatch.setattr(bridge,'rid',lambda:98762)
    monkeypatch.setattr(bridge,'prepare',lambda *args:None)
    monkeypatch.setattr(bridge,'wait',lambda *args:None)
    monkeypatch.setattr(bridge.ib,'reqMktData',lambda *args:None)
    def historical(req,*args):bridge.ib.bars[req]=[{'close':100,'time':'20261016  13:30:00'}]
    monkeypatch.setattr(bridge.ib,'reqHistoricalData',historical)
    monkeypatch.setattr(bridge.ib,'cancelHistoricalData',lambda *args:None)
    result=bridge.quote('TSLA')
    assert result['last']==100 and result['data_status']=='HISTORICAL'
    assert data.ibkr_entry_quote_quality(result)['reason']=='IBKR_ENTRY_REALTIME_QUOTE_REQUIRED'
