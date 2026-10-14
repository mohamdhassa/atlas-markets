import copy
from types import SimpleNamespace as NS

import pytest
from fastapi import HTTPException

from app.services import trading_candles as integrity
from app.services import autotrade_readiness as readiness
import tools.ibkr_bridge as bridge

START = 1_700_000_000_000


def bars(n=201):
    return [dict(timestamp_ms=START+i*300_000, interval='5m', open=100,
                 high=101,low=99,close=100,volume=10) for i in range(n)]


def test_forming_bar_excluded_exact_close_included_and_inputs_unchanged():
    rows=bars();before=copy.deepcopy(rows)
    result=integrity.completed_trading_candles(rows,'5m',now_ms=START+200*300_000)
    assert len(result)==200 and result[-1]['timestamp_ms']==rows[-2]['timestamp_ms']
    result=integrity.completed_trading_candles(rows,'5m',now_ms=START+201*300_000)
    assert len(result)==200 and result[0]['timestamp_ms']==rows[1]['timestamp_ms']
    assert rows==before


@pytest.mark.parametrize('change,reason', [
    ('missing','TIMESTAMP_REQUIRED'),('duplicate','ORDER_INVALID'),
    ('reverse','ORDER_INVALID'),('interval','INTERVAL_MISMATCH'),
    ('end','END_INVALID'),('nan','OHLC_INVALID'),('low','OHLC_INVALID')])
def test_invalid_trading_inputs_fail_closed(change,reason):
    rows=bars(31)
    if change=='missing':rows[-1].pop('timestamp_ms')
    elif change=='duplicate':rows[-1]['timestamp_ms']=rows[-2]['timestamp_ms']
    elif change=='reverse':rows.reverse()
    elif change=='interval':rows[-1]['interval']='3m'
    elif change=='end':rows[-1]['bar_end_ms']=rows[-1]['timestamp_ms']+1
    elif change=='nan':rows[-1]['close']=float('nan')
    elif change=='low':rows[-1]['low']=105
    with pytest.raises(ValueError,match=reason):
        integrity.completed_trading_candles(rows,'5m',now_ms=START+31*300_000)


def test_insufficient_complete_bars_and_unsupported_interval_block():
    with pytest.raises(ValueError,match='INSUFFICIENT'):
        integrity.completed_trading_candles(bars(30),'5m',now_ms=START+29*300_000)
    with pytest.raises(ValueError,match='INTERVAL_UNSUPPORTED'):
        integrity.completed_trading_candles(bars(),'7m')


def test_ibkr_metadata_required_old_or_mislabeled_bridge_cannot_pass(monkeypatch):
    monkeypatch.setattr(integrity.time,'time',lambda:(START+201*300_000)/1000)
    for payload in ({'list':bars()},{'actual_timeframe':'3m','list':bars()}):
        with pytest.raises(ValueError,match='TIMEFRAME_UNVERIFIED'):
            integrity.completed_ibkr_candles(payload,'5m')
    assert len(integrity.completed_ibkr_candles({'actual_timeframe':'5m','list':bars()},'5m'))==200


def test_real_3m_size_and_duration_no_silent_unknown_fallback():
    assert bridge.bar_size('3m')=='3 mins'
    assert bridge.duration('3m',600)=='3 D'
    for fn,args in ((bridge.bar_size,('7m',)),(bridge.duration,('7m',200))):
        with pytest.raises(HTTPException) as exc:fn(*args)
        assert exc.value.status_code==400


def test_epoch_timestamp_is_utc_and_chart_time_stays_readable():
    row=bridge.timestamped_candle({'time':'1791984600','close':100},'3m')
    assert row['timestamp_ms']==1791984600000
    assert row['bar_end_ms']-row['timestamp_ms']==180_000
    assert row['interval']=='3m' and row['time']=='20261014  13:30:00'
    with pytest.raises(HTTPException):bridge.timestamped_candle({'time':'20261014  13:30:00'},'3m')


@pytest.mark.parametrize('day,hours',[('20260308',23),('20261101',25),('20261014',24)])
def test_daily_calendar_end_handles_new_york_dst(day,hours):
    row=bridge.timestamped_candle({'time':day},'1d')
    assert row['bar_end_ms']-row['timestamp_ms']==hours*3_600_000
    rows=[dict(timestamp_ms=row['timestamp_ms']-i*86_400_000,open=100,high=101,low=99,
               close=100,interval='1d') for i in reversed(range(1,31))]+[{**row,'open':100,'high':101,'low':99,'close':100}]
    assert len(integrity.completed_trading_candles(rows,'1d',now_ms=row['bar_end_ms']-1))==30
    assert len(integrity.completed_trading_candles(rows,'1d',now_ms=row['bar_end_ms']))==31


def test_bridge_request_uses_actual_interval_epoch_format_and_preserves_forming_chart_bar(monkeypatch):
    calls=[]
    monkeypatch.setattr(bridge,'auth',lambda *args:None)
    monkeypatch.setattr(bridge,'read_ready',lambda *args:None)
    monkeypatch.setattr(bridge,'rid',lambda:98765)
    monkeypatch.setattr(bridge,'prepare',lambda *args:None)
    def request(*args):
        calls.append(args)
        bridge.ib.bars[98765]=[dict(time='1791984600',open=100,high=101,low=99,close=100,volume=1)]
    monkeypatch.setattr(bridge.ib,'reqHistoricalData',request)
    monkeypatch.setattr(bridge.ib,'cancelHistoricalData',lambda *args:None)
    monkeypatch.setattr(bridge,'wait',lambda *args:None)
    payload=bridge.candles('TSLA','3m',201)
    assert calls[0][4]=='3 mins' and calls[0][7]==2
    assert payload['actual_timeframe']=='3m'
    assert len(payload['list'])==1  # Chart feed is not filtered by trading completion.


def test_readiness_blocks_unverified_candles_before_signal_or_broker_order(monkeypatch):
    import asyncio
    from test_ibkr_whole_share_sizing import route
    # Reuse the established readiness fixture directly with this monkeypatch.
    DB,Broker,_=route.__wrapped__(monkeypatch)
    async def wrong(*args,**kwargs):return {'actual_timeframe':'3m','list':bars()}
    monkeypatch.setattr(Broker,'candles',wrong)
    def forbidden(*args,**kwargs):raise AssertionError('signal must not run')
    monkeypatch.setattr(readiness,'generate_signal',forbidden)
    report=asyncio.run(readiness.autotrade_readiness(DB(),user_id=1))
    assert report['items'][0]['readiness']=='BLOCK'
    assert 'TIMEFRAME_UNVERIFIED' in report['items'][0]['reason']
    assert Broker.checks==[]


def test_readiness_signal_and_router_receive_only_completed_window(monkeypatch):
    import asyncio
    from test_ibkr_whole_share_sizing import route
    DB,Broker,_=route.__wrapped__(monkeypatch)
    raw=bars()
    async def candles(*args,**kwargs):return {'actual_timeframe':'5m','list':raw}
    monkeypatch.setattr(Broker,'candles',candles)
    monkeypatch.setattr(integrity.time,'time',lambda:(START+200*300_000)/1000)
    captured=[]
    def generate(rows,**kwargs):
        captured.append(rows)
        return NS(decision='BUY',classification='BUY',strength=90)
    def router(rows):
        captured.append(rows)
        return {'strategy':'trend','regime':'TRENDING_UP'}
    monkeypatch.setattr(readiness,'generate_signal',generate)
    monkeypatch.setattr(readiness,'route_strategy',router)
    row=asyncio.run(readiness.autotrade_readiness(DB(),user_id=1))['items'][0]
    assert len(captured)==2 and captured[0]==captured[1]==raw[:-1]
    assert row['candle_integrity']['count']==200
    assert row['candle_integrity']['last_end_ms']==START+200*300_000


def test_bybit_readiness_blocks_missing_timestamp_before_signal(monkeypatch):
    import asyncio
    from test_ibkr_whole_share_sizing import route
    DB,_,_=route.__wrapped__(monkeypatch)
    db=DB();profile=db.get(None,None)
    profile.provider='BYBIT';profile.environment='TESTNET'
    class Market:
        async def get_candles(self,**kwargs):
            assert kwargs['category']=='spot' and kwargs['limit']==201
            return [NS(model_dump=lambda:dict(open=100,high=101,low=99,close=100))]
    monkeypatch.setattr(readiness,'BybitPublicMarketData',lambda *args:Market())
    def forbidden(*args,**kwargs):raise AssertionError('signal must not run')
    monkeypatch.setattr(readiness,'generate_signal',forbidden)
    row=asyncio.run(readiness.autotrade_readiness(db,user_id=1))['items'][0]
    assert row['readiness']=='BLOCK' and 'TIMESTAMP_REQUIRED' in row['reason']
