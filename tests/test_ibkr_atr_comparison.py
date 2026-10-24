from datetime import datetime, timedelta, timezone
import pytest
from app.backtesting import ibkr_atr_comparison as research


def rows(count=205):
    start=datetime(2026,10,19,13,30,tzinfo=timezone.utc)
    result=[]
    for index in range(count):
        day,bar=divmod(index,78)
        stamp=int((start+timedelta(days=day,minutes=bar*5)).timestamp()*1000)
        result.append(dict(timestamp_ms=stamp,open=100,high=100.1,low=99.9,
                           close=100,volume=1000,bar_end_ms=stamp+300000))
    return result


def bundle():
    data=rows()
    return dict(provider='IBKR',regular_hours=True,timeframe='5m',symbol='TEST',
                collected_at_ms=data[-1]['timestamp_ms']+300000,candles=data)


@pytest.mark.parametrize('sign',[1,-1])
def test_rth_gap_and_both_touched_use_conservative_stop(sign):
    position=dict(sign=sign,stop=98 if sign==1 else 102,target=104 if sign==1 else 96)
    assert research.trigger(dict(open=100,high=105,low=95),position)[1]=='STOP_FIRST'
    row=dict(open=90 if sign==1 else 110,high=111,low=89)
    assert research.trigger(row,position)==(row['open'],'GAP_STOP')


@pytest.mark.parametrize('side',['BUY','SELL'])
def test_next_open_entry_cost_accounting_and_no_stacking(side):
    data=rows();data[200].update(open=101,high=101.1,low=100.9,close=101)
    data[201].update(high=110,low=90)
    result=research.simulate(data,{200:side,201:side},measured=False,slip_bps=5)
    assert result['closed_trades']==1
    trade=result['trades'][0]
    assert trade['entry_ms']==data[200]['timestamp_ms']
    assert trade['price']==pytest.approx(101*(1.0005 if side=='BUY' else .9995))
    expected=trade['sign']*trade['quantity']*(trade['exit_price']-trade['price'])
    expected-=trade['entry_fee']+max(1,trade['quantity']*.005)
    assert trade['pnl']==pytest.approx(expected)
    assert trade['planned_risk']<=2500
    assert trade['quantity']*trade['price']<=50000
    assert result['sample_status']=='LIMITED'


def test_atr_uses_prior_completed_bars_and_open_position_is_retained():
    data=rows();stream={200:'BUY'}
    a=research.simulate(data,stream,measured=True,slip_bps=0)
    data[204]['high']=999
    b=research.simulate(data,stream,measured=True,slip_bps=0)
    # Future bar can change the exit, never the entry ATR or geometry.
    first=a['open_position'] or a['trades'][0]
    second=b['open_position'] or b['trades'][0]
    assert first['atr']==second['atr']
    assert first['stop']==second['stop']
    assert a['open_position'] is not None and a['closed_trades']==0


def test_signal_windows_never_include_execution_or_future_bar(monkeypatch):
    data=rows();seen=[]
    def generated(window,**kwargs):
        seen.append(window[-1]['timestamp_ms'])
        return type('S',(),dict(decision='BUY',strength=90))()
    monkeypatch.setattr(research,'generate_signal',generated)
    monkeypatch.setattr(research,'route_strategy',lambda window:dict(strategy='trend',regime='TRENDING_UP'))
    stream=research.signals(data,'5m')
    assert stream[200]=='BUY' and seen[0]==data[199]['timestamp_ms']
    assert seen[-1]==data[-2]['timestamp_ms']


@pytest.mark.parametrize('bad',['duplicate','unfinished','gap','ohlc','non_rth'])
def test_dataset_rejects_untrustworthy_inputs(bad):
    data=bundle()
    if bad=='duplicate':data['candles'][1]['timestamp_ms']=data['candles'][0]['timestamp_ms']
    if bad=='unfinished':data['collected_at_ms']=1
    if bad=='gap':data['candles'].pop(10)
    if bad=='ohlc':data['candles'][0]['high']=99
    if bad=='non_rth':data['candles'][0]['timestamp_ms']-=3600000
    with pytest.raises(ValueError):research.validate(data)


def test_no_signal_report_is_honest_and_hashes_inputs(monkeypatch):
    monkeypatch.setattr(research,'signals',lambda *args:{})
    report=research.compare(bundle())
    assert len(report['cases'])==3 and len(report['dataset_sha256'])==64
    assert report['verdict']=='EXPLORATORY_NOT_APPROVED_FOR_ACTIVATION'
    for case in report['cases']:
        assert case['baseline']['closed_trades']==case['candidate']['closed_trades']==0
        assert case['candidate']['marked_return_pct']==0
        assert case['candidate']['profit_factor'] is None
