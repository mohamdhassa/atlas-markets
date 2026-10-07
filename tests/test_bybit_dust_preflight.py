import asyncio
from types import SimpleNamespace as NS

import pytest

from app.services import autotrade_preflight as module


@pytest.mark.parametrize('side,dust,blocked', [
    ('SELL',['XRPUSDT'],True),
    ('SELL',[' xrp/usdt '],True),
    ('SELL',['ETHUSDT'],False),
    ('SELL',[],False),
    ('BUY',['XRPUSDT'],False),
])
def test_confirmed_sell_dust_blocks_before_broker_preflight(monkeypatch, side, dust, blocked):
    slots = {'count':0, 'quantity_dust_symbols':dust, 'unverified_symbols':[]}
    row = {'market':'CRYPTO','symbol':'XRPUSDT','provider':'BYBIT','environment':'TESTNET',
           'readiness':'PASS','managed_position_slots':slots,
           'proposed_order':{'side':side,'quantity':.0001}}
    profile = NS(id=1,provider='BYBIT',environment='TESTNET',execution_certified=True,
                 execution_certification_buy_passed=True,execution_certification_sell_passed=True)
    class DB:
        calls = 0
        def scalars(self, query):
            self.calls += 1
            rows = [NS(market='CRYPTO',symbol='XRPUSDT',profile_id=1)] if self.calls == 1 else [profile]
            return NS(all=lambda:rows)
    async def readiness(*args,**kwargs): return {'items':[row]}
    calls = []
    class Broker:
        async def spot_open_orders(self): calls.append('orders'); return {'list':[]}
    monkeypatch.setattr(module,'autotrade_readiness',readiness)
    monkeypatch.setattr(module,'_bybit_client',lambda *args:Broker())
    result = asyncio.run(module.autotrade_preflight(DB(),user_id=1))['items'][0]
    assert result['managed_position_slots'] == slots
    assert result['request']['side'] == side
    if blocked:
        assert result['preflight'] == 'BLOCK'
        assert result['reason'] == 'BYBIT_MANAGED_QUANTITY_DUST'
        assert calls == []
    else:
        assert result['preflight'] == 'PASS'
        assert calls == ['orders']
