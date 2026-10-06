import asyncio
from types import SimpleNamespace as NS

import pytest

from app.services import safe_automation as execution
from app.services import ibkr_position_manager as manager
from app.services.ibkr_fractional import ibkr_fill_is_complete


@pytest.mark.parametrize('status,expected,complete', [
    ({'status':'Filled','filled':95,'remaining':0},95,True),
    ({'status':'Submitted','filled':.1234,'remaining':0},.1234,True),
    ({'status':'Filled','filled':0,'remaining':0},95,False),
    ({'status':'Filled','filled':94,'remaining':0},95,False),
    ({'status':'Filled','filled':96,'remaining':0},95,False),
    ({'status':'Filled','filled':95,'remaining':1},95,False),
    ({'status':'Filled','filled':95,'remaining':-1},95,False),
    ({'status':'Filled'},95,False),
    ({'filled':float('inf'),'remaining':0},95,False),
    ({'filled':95,'remaining':float('nan')},95,False),
    ({'filled':95,'remaining':0},float('nan'),False),
    ({'filled':'invalid','remaining':0},95,False),
])
def test_fill_requires_exact_finite_quantities(status, expected, complete):
    assert ibkr_fill_is_complete(status, expected) is complete


@pytest.mark.parametrize('verifier', [execution._verify_ibkr_fill, manager._verify_fill])
def test_verification_timeout_preserves_unresolved_order(verifier):
    class Broker:
        calls = 0
        async def order_status(self, order_id):
            assert order_id == 128
            self.calls += 1
            raise TimeoutError('private broker URL must not appear in the result')
    broker = Broker()
    result, evidence = asyncio.run(verifier(broker, 128, 95))
    assert result in ('SUBMITTED', False)
    assert evidence == {'verification_error':'TimeoutError'}
    assert broker.calls == 1  # No submission retry or repeated reads after failure.


@pytest.mark.parametrize('verifier', [execution._verify_ibkr_fill, manager._verify_fill])
def test_partial_terminal_fill_is_not_complete(verifier, monkeypatch):
    async def no_delay(*args): pass
    monkeypatch.setattr(asyncio, 'sleep', no_delay)
    class Broker:
        async def order_status(self, order_id):
            return {'status':{'status':'Filled','filled':94,'remaining':0}}
    result, evidence = asyncio.run(verifier(Broker(), 128, 95))
    assert result in ('SUBMITTED', False)
    assert evidence['status']['filled'] == 94


def test_accepted_entry_retains_broker_id_when_fill_read_fails(monkeypatch):
    profile = NS(id=1, provider='IBKR', environment='PAPER', is_enabled=True,
                 is_active=True, credentials_configured=True, last_connection_status='CONNECTED')
    class DB:
        def scalar(self, query): return NS(profile_id=1)
        def get(self, model, key): return profile
    class Broker:
        submissions = 0
        async def health(self): return {'connected':True,'simulation':True}
        async def positions(self): return {'list':[]}
        async def orders(self): return {'list':[]}
        async def order_check(self, payload): return {'ok':True,'what_if':True,'simulation':True}
        async def place_order(self, payload):
            self.submissions += 1
            return {'accepted':True,'order_id':128,'simulation':True}
        async def order_status(self, order_id): raise TimeoutError('unavailable')
    broker = Broker()
    monkeypatch.setattr(execution, 'IbkrBridgeClient', lambda *args: broker)
    monkeypatch.setattr(execution, '_secret', lambda *args: {'account_id':'DU_TEST'})
    monkeypatch.setattr(execution, 'get_settings', lambda: NS(ibkr_fractional_api_enabled=False,market_data_timeout_seconds=1))
    result = asyncio.run(execution._execute_ibkr(DB(), user_id=1,
                        item={'market':'STOCK','symbol':'MSFT','request':{'side':'BUY','shares':95}}))
    assert result['status'] == 'SUBMITTED'
    assert result['reason'] == 'BROKER_FILL_NOT_CONFIRMED'
    assert result['broker_result']['order_id'] == 128
    assert result['broker_result']['final_status'] == {'verification_error':'TimeoutError'}
    assert broker.submissions == 1


def test_later_scan_failure_does_not_rollback_recorded_submission(monkeypatch):
    state = NS(enabled=True,killed=False,auto_execute_paper=True,interval_seconds=300)
    committed = []
    class DB:
        pending = []
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def scalars(self, query): return NS(all=lambda:[NS(user_id=1,profile_id=1),NS(user_id=2,profile_id=2)])
        def add(self, row):
            self.scan = row
            row.id = 'scan'
            row.signals_count = row.approved_count = row.executed_count = 0
        def refresh(self, row): pass
        def commit(self): committed.extend(self.pending); self.pending.clear()
        def rollback(self): self.pending.clear()
        def get(self, model, key): return self.scan
    db = DB()
    async def preflight(db, *, user_id):
        if user_id == 2: raise RuntimeError('later provider error')
        return {'items':[{'market':'STOCK','symbol':'MSFT','provider':'IBKR','preflight':'PASS'}]}
    async def submit(*args, **kwargs):
        return {'status':'SUBMITTED','broker_result':{'order_id':128},'reason':'BROKER_FILL_NOT_CONFIRMED'}
    monkeypatch.setattr(execution,'SessionLocal',lambda:db)
    monkeypatch.setattr(execution,'get_or_create_state',lambda db:state)
    monkeypatch.setattr(execution,'autotrade_preflight',preflight)
    monkeypatch.setattr(execution,'_execute_ibkr',submit)
    monkeypatch.setattr(execution,'_persist_action',lambda db,scan,user_id,item,result:db.pending.append(result))
    result = asyncio.run(execution.run_safe_scan())
    assert result['status'] == 'FAILED'
    assert len(committed) == 1
    assert committed[0]['broker_result']['order_id'] == 128
