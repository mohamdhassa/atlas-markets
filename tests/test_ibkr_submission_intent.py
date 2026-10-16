import asyncio
import copy
import json
import uuid
from types import SimpleNamespace as NS

import pytest

from app.services import safe_automation as engine


@pytest.fixture
def route(monkeypatch):
    profile = NS(id=uuid.uuid4(), user_id=uuid.uuid4(), provider='IBKR', environment='PAPER',
                 is_enabled=True, is_active=True, credentials_configured=True,
                 last_connection_status='CONNECTED')
    cfg = NS(user_id=profile.user_id, profile_id=profile.id, enabled=True, mode='AUTO_TRADE')
    state = NS(enabled=True, killed=False, auto_execute_paper=True)
    item = {'provider':'IBKR', 'market':'STOCK', 'symbol':'TSLA',
            'request':{'side':'BUY', 'shares':128, 'stop_loss':350, 'take_profit':390}}
    scan = NS(id=uuid.uuid4())
    class DB:
        def __init__(self):
            self.rows = []
            self.saved = []
            self.locks = []
            self.commits = 0
            self.fail_commit = False
        def scalar(self, query):
            return next((r for r in self.rows if r.status in {'SUBMITTED','EXIT_SUBMITTED'}), None)
        def refresh(self, row, **kwargs):
            if kwargs.get('with_for_update'): self.locks.append(row.id)
        def add(self, row):
            row.id = uuid.uuid4()
            self.rows.append(row)
        def commit(self):
            if self.fail_commit: raise RuntimeError('database write failed')
            self.saved = [copy.deepcopy(r.raw_json) for r in self.rows]
            self.commits += 1
    monkeypatch.setattr(engine, '_profile_for_item', lambda *args:(cfg,profile))
    monkeypatch.setattr(engine, 'get_or_create_state', lambda db:state)
    return DB(), profile, cfg, state, item, scan


def run(route):
    db, profile, _, _, item, scan = route
    return asyncio.run(engine._execute_ibkr_audited(db, scan=scan, user_id=profile.user_id, item=item))


def test_intent_commits_before_submission_and_one_action_retains_final_result(route, monkeypatch):
    db, profile, _, _, item, _ = route
    async def execute(*args, **kwargs):
        assert db.commits == 1
        saved = json.loads(db.saved[0])
        assert saved['result']['status'] == 'SUBMITTED'
        assert saved['preflight'] == item
        return {'status':'EXECUTED', 'provider':'IBKR', 'broker_result':{'order_id':491}}
    monkeypatch.setattr(engine, '_execute_ibkr', execute)
    result, action = run(route)
    assert result['status'] == action.status == 'EXECUTED'
    assert action.broker_order_id == '491'
    assert len(db.rows) == 1 and db.commits == 2 and db.locks == [profile.id]
    audit = json.loads(action.raw_json)
    assert audit['submission_intent']['reason'] == 'IBKR_ENTRY_SUBMISSION_UNRESOLVED'
    assert audit['result'] == result


@pytest.mark.parametrize('failure',[TimeoutError,ConnectionError,RuntimeError])
def test_unknown_failure_stays_pending_and_next_scan_cannot_resubmit(route, monkeypatch, failure):
    db, *_ = route
    calls = []
    async def execute(*args, **kwargs):
        calls.append(1)
        raise failure('sensitive provider URL')
    monkeypatch.setattr(engine, '_execute_ibkr', execute)
    result, action = run(route)
    assert action.status == result['status'] == 'SUBMITTED'
    assert result['submission_error'] == failure.__name__
    assert 'sensitive' not in action.raw_json
    assert run(route)[0]['reason'] == 'IBKR_PENDING_SUBMISSION_RECONCILIATION_REQUIRED'
    assert len(calls) == len(db.rows) == 1


def test_worker_cancellation_retains_committed_intent(route, monkeypatch):
    db, *_ = route
    async def execute(*args, **kwargs): raise asyncio.CancelledError()
    monkeypatch.setattr(engine, '_execute_ibkr', execute)
    with pytest.raises(asyncio.CancelledError):run(route)
    assert len(db.saved) == 1 and json.loads(db.saved[0])['result']['status'] == 'SUBMITTED'
    assert run(route)[0]['reason'] == 'IBKR_PENDING_SUBMISSION_RECONCILIATION_REQUIRED'


def test_database_failure_prevents_execution(route, monkeypatch):
    db, *_ = route
    db.fail_commit = True
    async def forbidden(*args, **kwargs):pytest.fail('submit before intent commit')
    monkeypatch.setattr(engine, '_execute_ibkr', forbidden)
    with pytest.raises(RuntimeError, match='database write failed'):run(route)


@pytest.mark.parametrize('field,value,reason',[
    ('killed',True,'KILL_SWITCH'), ('enabled',False,'ENGINE_DISABLED'),
    ('auto_execute_paper',False,'SIMULATION_EXECUTION_DISABLED'),
])
def test_fresh_engine_controls_prevent_intent_and_execution(route, monkeypatch, field, value, reason):
    db, _, _, state, _, _ = route
    setattr(state,field,value)
    async def forbidden(*args, **kwargs):pytest.fail('disabled engine submitted')
    monkeypatch.setattr(engine,'_execute_ibkr',forbidden)
    assert run(route)[0]['reason'] == reason
    assert not db.rows and not db.saved


@pytest.mark.parametrize('target,field,value,reason',[
    ('cfg','enabled',False,'AUTO_TRADE_NOT_ENABLED'),
    ('cfg','mode','WATCH','AUTO_TRADE_NOT_ENABLED'),
    ('profile','is_active',False,'ROUTE_NOT_READY'),
    ('profile','environment','LIVE','IBKR_PAPER_ONLY_CERTIFIED'),
    ('profile','provider','MT5','IBKR_PROFILE_REQUIRED'),
])
def test_changed_route_is_reloaded_and_blocked(route, target, field, value, reason):
    db, profile, cfg, _, _, _ = route
    setattr(profile if target=='profile' else cfg,field,value)
    assert run(route)[0]['reason'] == reason
    assert not db.rows


def test_confirmed_pre_submission_block_releases_intent(route, monkeypatch):
    async def blocked(*args, **kwargs):return {'status':'BLOCK','reason':'IBKR_ENTRY_QUOTE_STALE'}
    monkeypatch.setattr(engine,'_execute_ibkr',blocked)
    result, action = run(route)
    assert action.status == result['status'] == 'BLOCK'
    assert run(route)[0]['reason'] == 'IBKR_ENTRY_QUOTE_STALE'
    assert len(route[0].rows) == 2


def test_authorization_is_rechecked_after_whatif_before_place(monkeypatch):
    from unit.test_ibkr_whole_share_sizing import route as shared_route
    DB, Broker, _ = shared_route.__wrapped__(monkeypatch)
    calls=[]
    async def health(self):return {'connected':True,'simulation':True}
    async def orders(self):return {'list':[]}
    async def forbidden(*args,**kwargs):pytest.fail('kill during preflight must prevent submission')
    monkeypatch.setattr(Broker,'health',health,raising=False)
    monkeypatch.setattr(Broker,'orders',orders,raising=False)
    monkeypatch.setattr(Broker,'place_order',forbidden,raising=False)
    monkeypatch.setattr(engine,'_entry_authorization_blocker',lambda *args:calls.append('check') or 'KILL_SWITCH')
    result=asyncio.run(engine._execute_ibkr(DB(),user_id=1,item={
        'market':'STOCK','symbol':'TSLA','request':{'side':'BUY','shares':2}}))
    assert result['reason']=='KILL_SWITCH' and len(Broker.checks)==1 and calls==['check']


def test_client_checks_authorization_after_its_slow_broker_reads():
    from app.brokers.ibkr_bridge import IbkrBridgeClient
    from app.services.execution_guard import PreSubmissionBlocked
    broker=IbkrBridgeClient('http://unused')
    controls={'killed':False}
    async def health():return {'connected':True,'simulation':True}
    async def positions():return {'list':[]}
    async def orders():
        controls['killed']=True
        return {'list':[]}
    async def forbidden(*args,**kwargs):pytest.fail('POST after kill')
    broker.health,broker.positions,broker.orders,broker._post=health,positions,orders,forbidden
    with pytest.raises(PreSubmissionBlocked,match='KILL_SWITCH'):
        asyncio.run(broker.place_order({'account_id':'DU_TEST','symbol':'TSLA'},
                    before_submit=lambda:'KILL_SWITCH' if controls['killed'] else None))


@pytest.mark.parametrize('response,status',[
    ({},'SUBMITTED'), ({'accepted':False},'BLOCK'),
    ({'accepted':False,'order_id':491},'SUBMITTED'),
])
def test_ambiguous_submission_response_is_never_called_rejected(monkeypatch,response,status):
    from unit.test_ibkr_whole_share_sizing import route as shared_route
    DB,Broker,_=shared_route.__wrapped__(monkeypatch)
    async def health(self):return {'connected':True,'simulation':True}
    async def orders(self):return {'list':[]}
    async def place(self,*args,**kwargs):return response
    monkeypatch.setattr(Broker,'health',health,raising=False)
    monkeypatch.setattr(Broker,'orders',orders,raising=False)
    monkeypatch.setattr(Broker,'place_order',place,raising=False)
    monkeypatch.setattr(engine,'_entry_authorization_blocker',lambda *args:None)
    result=asyncio.run(engine._execute_ibkr(DB(),user_id=1,item={
        'market':'STOCK','symbol':'TSLA','request':{'side':'BUY','shares':2}}))
    assert result['status']==status


def test_scan_updates_intent_instead_of_inserting_a_second_trade(route,monkeypatch):
    from app.db.models.automation import AutomationScan
    db,profile,cfg,state,item,_=route
    state.interval_seconds=300
    cfg.user_id=profile.user_id
    db.__class__.__enter__=lambda self:self
    db.__class__.__exit__=lambda *args:None
    db.scalars=lambda query:NS(all=lambda:[cfg])
    original_add=db.add
    def add(row):
        if isinstance(row,AutomationScan):
            row.id=uuid.uuid4()
            row.signals_count=row.approved_count=row.executed_count=0
            db.scan=row
        else:original_add(row)
    db.add=add
    async def preflight(*args,**kwargs):return {'items':[{**item,'preflight':'PASS'}]}
    async def execute(*args,**kwargs):return {'status':'SUBMITTED','broker_result':{'order_id':491},'reason':'BROKER_FILL_NOT_CONFIRMED'}
    monkeypatch.setattr(engine,'SessionLocal',lambda:db)
    monkeypatch.setattr(engine,'autotrade_preflight',preflight)
    monkeypatch.setattr(engine,'_execute_ibkr',execute)
    result=asyncio.run(engine.run_safe_scan())
    assert result['status']=='COMPLETED'
    assert len(db.rows)==1 and db.rows[0].broker_order_id=='491'


@pytest.mark.parametrize('filled,expected',[(0,'CANCELLED'),(1,'SUBMITTED'),
    (None,'SUBMITTED'),(float('nan'),'SUBMITTED'),(-1,'SUBMITTED')])
def test_cancelled_remainder_cannot_release_a_partial_or_unknown_fill(filled,expected):
    class Broker:
        async def order_status(self,order_id):
            return {'status':{'status':'Cancelled','filled':filled,'remaining':0}}
    status,_=asyncio.run(engine._verify_ibkr_fill(Broker(),491,128))
    assert status==expected
