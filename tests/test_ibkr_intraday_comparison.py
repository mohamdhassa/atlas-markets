from datetime import datetime, timedelta, timezone
import pytest
from app.backtesting import ibkr_atr_comparison as base
from app.backtesting import ibkr_intraday_comparison as research


def rows():
    start = datetime(2026,10,19,13,30,tzinfo=timezone.utc)
    return [dict(timestamp_ms=int((start+timedelta(days=i//78,minutes=(i%78)*5)).timestamp()*1000),
                 open=100,high=100.1,low=99.9,close=100,volume=1000) for i in range(312)]


@pytest.mark.parametrize('side',['BUY','SELL'])
def test_scheduled_open_exit_costs_and_no_future_bar_range(side):
    data=rows()
    # Day 3: 14:55 entry, 15:45 scheduled exit.
    entry=156+65; exit_index=156+75
    data[exit_index].update(high=150,low=50)
    result=base.simulate(data,{entry:side,entry+1:side,exit_index:side},
                         measured=False,slip_bps=5,intraday=True)
    assert result['closed_trades']==1 and result['open_position'] is None
    trade=result['trades'][0]
    assert trade['reason']=='SESSION_EXIT'
    assert trade['exit_ms']==data[exit_index]['timestamp_ms']
    assert trade['pnl']<0 # Unchanged market price, adverse fills and both commissions.
    assert trade['exit_price']==pytest.approx(100*(.9995 if side=='BUY' else 1.0005))


def test_entry_cutoff_and_overnight_baseline_preserved():
    data=rows();stream={156+66:'BUY'} # Exactly 15:00.
    intraday=base.simulate(data,stream,measured=False,slip_bps=0,intraday=True)
    baseline=base.simulate(data,stream,measured=False,slip_bps=0)
    assert intraday['closed_trades']==0 and intraday['open_position'] is None
    assert baseline['open_position'] is not None


def test_missing_scheduled_bar_rejected_instead_of_overnight_carry():
    data=rows()
    research.validate_sessions(data)
    with pytest.raises(ValueError,match='SESSION_EXIT_BAR_MISSING'):
        research.validate_sessions(data[:-10])


def test_four_policies_share_signals_and_do_not_activate(monkeypatch):
    data=rows();calls=[]
    def stream(*args):
        calls.append(1)
        return {220:'BUY',300:'SELL'}
    monkeypatch.setattr(research,'signals',stream)
    report=research.compare(dict(provider='IBKR',regular_hours=True,symbol='TEST',
        timeframe='5m',collected_at_ms=data[-1]['timestamp_ms']+300000,candles=data))
    assert len(calls)==1 and len(report['cases'])==3
    assert report['verdict']=='EXPLORATORY_NOT_APPROVED_FOR_ACTIVATION'
    for case in report['cases']:
        assert len(case['results'])==4
        for label,result in case['results'].items():
            assert result['sample_status']=='LIMITED'
            if label.endswith('_intraday'):
                assert result['overnight_closed_trades']==0
                assert result['open_position'] is None


def test_gap_at_scheduled_exit_keeps_gap_stop_reason():
    data=rows();data[231].update(open=95,high=95.1,low=94.9,close=95)
    result=base.simulate(data,{220:'BUY'},measured=False,slip_bps=0,intraday=True)
    assert result['trades'][0]['reason']=='GAP_STOP'
    assert result['trades'][0]['exit_price']==95


def test_stop_before_scheduled_exit_is_honored():
    data=rows();data[221].update(low=97)
    result=base.simulate(data,{220:'BUY'},measured=False,slip_bps=0,intraday=True)
    assert result['trades'][0]['reason']=='STOP'
    assert result['trades'][0]['exit_ms']==data[221]['timestamp_ms']
