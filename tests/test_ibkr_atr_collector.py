from types import SimpleNamespace
import asyncio
import json
import pytest
from app.scripts import collect_ibkr_atr_research as collector


def setup(monkeypatch, environment='PAPER', connected=True):
    class Session:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,*args):return SimpleNamespace(provider='IBKR',environment=environment)
    class Broker:
        async def health(self):return dict(connected=connected,simulation=True)
        async def candles(self,symbol,timeframe,limit,**kwargs):
            assert limit==1000
            return dict(actual_timeframe=timeframe,list=[dict(timestamp_ms=1700000000000+i*300000,open=100,high=101,low=99,close=100,volume=10) for i in range(205)])
    monkeypatch.setattr(collector,'SessionLocal',Session)
    monkeypatch.setattr(collector,'_secret',lambda profile:{})
    monkeypatch.setattr(collector,'IbkrBridgeClient',lambda *args:Broker())
    monkeypatch.setattr(collector,'SYMBOLS',('SPY',))


def test_read_only_export_and_no_overwrite(monkeypatch,tmp_path):
    setup(monkeypatch)
    args=SimpleNamespace(profile_id=None,output=tmp_path/'data',timeframe='5m')
    asyncio.run(collector.collect(args))
    result=json.loads((args.output/'SPY-5m.json').read_text())
    assert result['provider']=='IBKR' and result['regular_hours'] is True
    assert 'account_id' not in result
    with pytest.raises(FileExistsError):asyncio.run(collector.collect(args))


@pytest.mark.parametrize('environment,connected',[('LIVE',True),('PAPER',False)])
def test_refuses_live_or_disconnected_export(monkeypatch,tmp_path,environment,connected):
    setup(monkeypatch,environment,connected)
    args=SimpleNamespace(profile_id=None,output=tmp_path/'data',timeframe='5m')
    with pytest.raises(ValueError):asyncio.run(collector.collect(args))
    assert not args.output.exists()
