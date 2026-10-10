import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace as NS

import pytest
import httpx
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import tools.ibkr_bridge as bridge
from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.core.config import Settings
from app.db.models.automation import AutomationAction, AutomationScan
from app.services import ibkr_position_manager as manager
from app.services import safe_automation as execution
from app.services.ibkr_protection import position_has_native_protection
from test_position_slots_and_scan_interruptions import ScanDB


@pytest.fixture
def native(monkeypatch):
    state=bridge.State();state.next_id=10;state.accounts=['DU_TEST'];state.server_connected=True
    monkeypatch.setattr(state,'isConnected',lambda:True)
    monkeypatch.setattr(bridge,'ib',state)
    monkeypatch.setattr(bridge,'cfg',{'account_id':'DU_TEST','simulation':True,'client_id':27})
    live=[{'account':'DU_TEST','symbol':'MSFT','sec_type':'STK','currency':'USD','quantity':3,'avg_cost':100}]
    book=[];submitted=[]
    monkeypatch.setattr(bridge,'positions',lambda *args:{'list':list(live)})
    monkeypatch.setattr(bridge,'orders',lambda *args:{'list':[dict(r) for r in book]})
    monkeypatch.setattr(bridge,'contract_info',lambda *args,**kwargs:{'symbol':'MSFT','sec_type':'STK','currency':'USD','min_tick':.01})
    monkeypatch.setattr(bridge,'order_check',lambda *args:{'ok':True,'what_if':True,'simulation':True})
    def submit(oid,contract,order):
        submitted.append((oid,order))
        book.append({'order_id':oid,'symbol':contract.symbol,'sec_type':'STK','account':order.account,
                     'type':order.orderType,'side':order.action,'quantity':order.totalQuantity,'filled':0,
                     'limit_price':order.lmtPrice,'aux_price':order.auxPrice,'client_id':27,
                     'order_ref':order.orderRef,'oca_group':order.ocaGroup,'oca_type':order.ocaType,
                     'tif':order.tif,'outside_rth':order.outsideRth,'status':'PendingSubmit'})
        if order.transmit:
            book[-1]['status']='Submitted'
    monkeypatch.setattr(state,'placeOrder',submit)
    payload=bridge.ProtectionPayload(symbol='MSFT',account_id='DU_TEST',position_side='LONG',quantity=3,
        stop_loss=98.003,take_profit=104.009,entry_key=uuid.uuid4().hex,allow_submit=True)
    return NS(state=state,live=live,book=book,submitted=submitted,payload=payload)


@pytest.mark.parametrize('position_side,quantity,stop,target,close_side,rounded',[
    ('LONG',3,98.003,104.009,'SELL',(98.01,104)),
    ('SHORT',-3,102.009,96.003,'BUY',(102,96.01)),
])
def test_broker_held_pair_is_gtc_oca_with_partial_fill_block_and_conservative_prices(native,position_side,quantity,stop,target,close_side,rounded):
    native.live[0]['quantity']=quantity
    p=native.payload.model_copy(update={'position_side':position_side,'stop_loss':stop,'take_profit':target})
    result=bridge.protection(p,None)
    assert result['status']=='PROTECTED'
    assert (result['stop_loss'],result['take_profit'])==rounded
    assert [o.transmit for _,o in native.submitted]==[True,True]
    assert all(o.ocaType==2 and o.tif=='GTC' and not o.outsideRth and o.action==close_side for _,o in native.submitted)
    assert [oid for oid,_ in native.submitted]==[10,11]
    assert native.state.next_id==12
    # Repeat verification cannot create another pair, including after bridge restart.
    native.state.protection_attempts.clear()
    assert bridge.protection(p.model_copy(update={'allow_submit':False}),None)['status']=='PROTECTED'
    assert len(native.submitted)==2


@pytest.mark.parametrize('change,detail',[
    ({'account_id':'OTHER'},'INVALID_PROTECTION_ACCOUNT_OR_POSITION'),
    ({'position_side':'SHORT'},'PROTECTION_POSITION_CHANGED'),
    ({'quantity':4},'PROTECTION_POSITION_CHANGED'),
    ({'quantity':float('nan')},'INVALID_PROTECTION_ACCOUNT_OR_POSITION'),
    ({'stop_loss':101},'PROTECTION_LEVELS_DO_NOT_BRACKET_ENTRY'),
    ({'take_profit':float('inf')},'INVALID_PROTECTION_PRICES'),
    ({'allow_submit':False},'PROTECTION_SUBMISSION_OUTCOME_UNRESOLVED'),
])
def test_invalid_or_unverified_request_never_places_orders(native,change,detail):
    with pytest.raises(HTTPException) as exc:bridge.protection(native.payload.model_copy(update=change),None)
    assert exc.value.detail==detail
    assert not native.submitted


def test_live_disconnected_and_wrong_token_are_blocked(native,monkeypatch):
    bridge.cfg['simulation']=False
    with pytest.raises(HTTPException) as exc:bridge.protection(native.payload,None)
    assert exc.value.status_code==403
    bridge.cfg.update(simulation=True,token='test-token')
    with pytest.raises(HTTPException) as exc:bridge.protection(native.payload,None)
    assert exc.value.status_code==401
    native.state.server_connected=False
    with pytest.raises(HTTPException) as exc:bridge.protection(native.payload,'test-token')
    assert exc.value.status_code==503
    assert not native.submitted


@pytest.mark.parametrize('field,value',[
    ('account','OTHER'),('client_id',99),('order_ref','manual'),('oca_type',1),
    ('quantity',4),('aux_price',97),('status','PendingSubmit'),('tif','DAY'),
])
def test_existing_pair_mismatch_never_replaces_or_adds_orders(native,field,value):
    bridge.protection(native.payload,None)
    native.book[0][field]=value
    with pytest.raises(HTTPException) as exc:bridge.protection(native.payload,None)
    assert exc.value.detail=='PROTECTION_EXISTING_ORDERS_REQUIRE_RECONCILIATION'
    assert len(native.submitted)==2


def test_partial_fill_verifies_remaining_coverage_without_new_order(native):
    bridge.protection(native.payload,None)
    native.live[0]['quantity']=2
    native.book[0].update(quantity=3,filled=1)
    native.book[1].update(quantity=2,filled=0)
    p=native.payload.model_copy(update={'quantity':2,'allow_submit':False})
    assert bridge.protection(p,None)['status']=='PROTECTED'
    assert len(native.submitted)==2


def test_failed_second_submission_retains_identity_and_does_not_cancel_or_retry(native,monkeypatch):
    real=native.state.placeOrder
    def fail_second(oid,contract,order):
        if order.orderType=='LMT':raise TimeoutError('sensitive broker URL')
        real(oid,contract,order)
    monkeypatch.setattr(native.state,'placeOrder',fail_second)
    result=bridge.protection(native.payload,None)
    assert result['status']=='PROTECTION_PENDING' and result['order_ids']==[10,11]
    assert 'sensitive' not in json.dumps(result)
    with pytest.raises(HTTPException):bridge.protection(native.payload,None)
    assert len(native.submitted)==1


def test_unknown_submission_with_empty_broker_book_is_not_retried(native,monkeypatch):
    monkeypatch.setattr(native.state,'placeOrder',lambda *args:None)
    assert bridge.protection(native.payload,None)['status']=='PROTECTION_PENDING'
    with pytest.raises(HTTPException) as exc:bridge.protection(native.payload,None)
    assert exc.value.detail=='PROTECTION_SUBMISSION_OUTCOME_UNRESOLVED'


def staged_pair(native):
    bridge.protection(native.payload,None)
    stop=native.submitted[0][1]
    stop.transmit=False;stop.permId=0
    native.book[0].update(status='ApiPending',transmit=False,perm_id=0)
    native.state.open_order_objects[(27,10)]=(bridge.contract('MSFT'),stop)
    return native.payload.model_copy(update={'allow_submit':False,'existing_order_ids':[10,11]})


def test_exact_staged_stop_is_transmitted_using_same_id_and_preserved_order(native,monkeypatch):
    p=staged_pair(native);calls=[]
    def recover(oid,c,o):
        calls.append((oid,c,o));native.book[0].update(status='Submitted',transmit=True,perm_id=123)
    monkeypatch.setattr(native.state,'placeOrder',recover)
    result=bridge.protection(p,None)
    assert result['status']=='PROTECTED' and result['recovery']=='EXACT_STAGED_STOP_TRANSMITTED'
    assert len(calls)==1 and calls[0][0]==10 and calls[0][2].transmit is True
    assert calls[0][2].auxPrice==98.01 and calls[0][2].ocaGroup==native.book[1]['oca_group']
    assert native.state.next_id==12 and len(native.book)==2
    assert bridge.protection(p,None)['status']=='PROTECTED' and len(calls)==1


@pytest.mark.parametrize('change',[
    {'client_id':99},{'account':'OTHER'},{'order_ref':'manual'},
    {'quantity':4},{'aux_price':97},{'perm_id':123},{'transmit':True},
    {'status':'Inactive'},{'oca_type':1},
])
def test_staged_recovery_refuses_mismatch_without_mutation(native,monkeypatch,change):
    p=staged_pair(native);native.book[0].update(change);calls=[]
    monkeypatch.setattr(native.state,'placeOrder',lambda *args:calls.append(args))
    with pytest.raises(HTTPException):bridge.protection(p,None)
    assert not calls


def test_staged_recovery_requires_persisted_pair_and_fresh_position(native,monkeypatch):
    p=staged_pair(native);calls=[]
    monkeypatch.setattr(native.state,'placeOrder',lambda *args:calls.append(args))
    for ids in ([],[10,12],[10,10]):
        with pytest.raises(HTTPException):bridge.protection(p.model_copy(update={'existing_order_ids':ids}),None)
    native.state.open_order_objects.clear()
    with pytest.raises(HTTPException) as exc:bridge.protection(p,None)
    assert exc.value.detail=='PROTECTION_STAGED_ORDER_NOT_VERIFIED'
    count=0
    def positions(*args):
        nonlocal count
        count+=1
        return {'list':[{**native.live[0],'quantity':3 if count==1 else 2}]}
    monkeypatch.setattr(bridge,'positions',positions)
    with pytest.raises(HTTPException) as exc:bridge.protection(p,None)
    assert exc.value.detail=='PROTECTION_POSITION_CHANGED' and not calls


def test_staged_recovery_timeout_never_allocates_another_id(native,monkeypatch):
    p=staged_pair(native);calls=[]
    def timeout(oid,c,o):calls.append(oid);raise TimeoutError()
    monkeypatch.setattr(native.state,'placeOrder',timeout)
    assert bridge.protection(p,None)['status']=='PROTECTION_PENDING'
    assert calls==[10] and native.state.next_id==12


def test_stop_first_position_change_prevents_target_submission(native,monkeypatch):
    submit=native.state.placeOrder
    def fill_stop(oid,c,o):submit(oid,c,o);native.live[0]['quantity']=0
    monkeypatch.setattr(native.state,'placeOrder',fill_stop)
    assert bridge.protection(native.payload,None)['status']=='PROTECTION_PENDING'
    assert len(native.submitted)==1 and native.submitted[0][1].orderType=='STP'
    assert native.submitted[0][1].transmit is True


def test_orders_merge_active_all_client_and_local_staged_without_duplicates(monkeypatch):
    state=bridge.State();state.server_connected=True
    monkeypatch.setattr(bridge,'ib',state);monkeypatch.setattr(bridge,'cfg',{'simulation':True,'client_id':27})
    monkeypatch.setattr(state,'isConnected',lambda:True)
    c=bridge.contract('MSFT');active=bridge.Order();active.account='DU_TEST';active.clientId=27
    active.action='SELL';active.totalQuantity=3;active.orderType='LMT';active.transmit=True;active.permId=123
    stop=bridge.Order();stop.account='DU_TEST';stop.clientId=27
    stop.action='SELL';stop.totalQuantity=3;stop.orderType='STP';stop.transmit=False;stop.permId=0
    def all_orders():state.openOrder(11,c,active,NS(status='Submitted'));state.openOrderEnd()
    def own_orders():
        state.openOrder(11,c,active,NS(status='Submitted'))
        state.openOrder(10,c,stop,NS(status='ApiPending'));state.openOrderEnd()
    monkeypatch.setattr(state,'reqAllOpenOrders',all_orders);monkeypatch.setattr(state,'reqOpenOrders',own_orders)
    rows=bridge.orders(None)['list']
    assert len(rows)==2 and {r['order_id'] for r in rows}=={10,11}
    assert next(r for r in rows if r['order_id']==10)['transmit'] is False
    assert state.open_order_objects[(27,10)][1].orderType=='STP'


def test_whatif_rejection_and_position_change_prevent_submission(native,monkeypatch):
    monkeypatch.setattr(bridge,'order_check',lambda *args:{'ok':False})
    with pytest.raises(HTTPException) as exc:bridge.protection(native.payload,None)
    assert exc.value.detail=='PROTECTION_WHATIF_REJECTED'
    def change(*args):
        native.live[0]['quantity']=2
        return {'ok':True,'what_if':True,'simulation':True}
    monkeypatch.setattr(bridge,'order_check',change)
    with pytest.raises(HTTPException) as exc:bridge.protection(native.payload,None)
    assert exc.value.detail=='PROTECTION_POSITION_CHANGED'
    assert not native.submitted


def test_other_client_or_manual_orders_prevent_protection(native):
    native.book.append({'symbol':'MSFT','account':'OTHER','status':'Submitted'})
    with pytest.raises(HTTPException):bridge.protection(native.payload,None)
    assert not native.submitted


def test_concurrent_broker_mutation_fails_fast(native):
    held=threading.Event();release=threading.Event()
    def hold():
        with bridge.mutation_lock:held.set();assert release.wait(3)
    thread=threading.Thread(target=hold);thread.start();assert held.wait(1)
    try:
        with pytest.raises(HTTPException) as exc:bridge.protection(native.payload,None)
        assert exc.value.detail=='IBKR_MUTATION_ALREADY_IN_PROGRESS'
    finally:release.set();thread.join()
    assert not native.submitted


@pytest.fixture
def db():
    engine=create_engine('sqlite://')
    AutomationAction.__table__.create(engine)
    with Session(engine) as session:yield session
    engine.dispose()


def entry(db):
    row=AutomationAction(id=uuid.uuid4(),scan_id=uuid.uuid4(),user_id=uuid.uuid4(),broker_profile_id=uuid.uuid4(),
        provider='IBKR',environment='PAPER',market='STOCK',symbol='MSFT',side='BUY',status='EXECUTED',
        quantity=3,broker_order_id='1',created_at=datetime.now(timezone.utc),
        raw_json=json.dumps({'preflight':{'request':{'stop_loss':98,'take_profit':104}},'result':{'status':'EXECUTED'}}))
    db.add(row);db.commit();return row


def test_intent_survives_timeout_and_retry_only_verifies_same_pair(db):
    row=entry(db);calls=[]
    class Broker:
        async def ensure_protection(self,payload):
            calls.append(payload)
            saved=json.loads(db.get(AutomationAction,row.id).raw_json)
            assert saved['native_protection']['status']=='SUBMITTING'
            raise TimeoutError('private URL')
    item={'symbol':'MSFT','position_side':'LONG','quantity':3}
    for _ in range(2):
        with pytest.raises(TimeoutError):asyncio.run(manager._ensure_native_protection(db,row,Broker(),item,'DU_TEST'))
    assert [p['allow_submit'] for p in calls]==[True,False]
    assert calls[0]['entry_key']==calls[1]['entry_key']==row.id.hex
    saved=json.loads(row.raw_json)
    assert saved['result']=={'status':'EXECUTED'}
    assert row.status=='EXECUTED'


def test_manager_passes_persisted_pair_ids_without_enabling_new_submission(db):
    row=entry(db);raw=json.loads(row.raw_json)
    raw['native_protection']={'status':'PROTECTION_PENDING','order_ids':[216,217]}
    row.raw_json=json.dumps(raw);db.commit();calls=[]
    class Broker:
        async def ensure_protection(self,payload):
            calls.append(payload)
            return {'status':'PROTECTED','simulation':True,'oca_group':'atlas-protect-'+row.id.hex}
    result=asyncio.run(manager._ensure_native_protection(db,row,Broker(),
        {'symbol':'MSFT','position_side':'LONG','quantity':3},'DU_TEST'))
    assert result['status']=='PROTECTED'
    assert calls[0]['existing_order_ids']==[216,217] and calls[0]['allow_submit'] is False
    assert json.loads(row.raw_json)['native_protection']['order_ids']==[216,217]


def test_only_explicit_pre_submission_busy_response_can_release_submission_intent(db):
    row=entry(db);calls=[]
    class Broker:
        async def ensure_protection(self,payload):
            calls.append(payload)
            response=httpx.Response(503,json={'detail':'IBKR_READ_ALREADY_IN_PROGRESS'},request=httpx.Request('POST','http://bridge/protection'))
            raise httpx.HTTPStatusError('busy',request=response.request,response=response)
    item={'symbol':'MSFT','position_side':'LONG','quantity':3}
    for _ in range(2):
        assert asyncio.run(manager._ensure_native_protection(db,row,Broker(),item,'DU_TEST'))['status']=='PROTECTION_BLOCKED'
    assert [p['allow_submit'] for p in calls]==[True,True]


def test_missing_saved_levels_and_wrong_quantity_never_submit(db):
    row=entry(db)
    class Broker:
        async def ensure_protection(self,payload):raise AssertionError('must not submit')
    item={'symbol':'MSFT','position_side':'LONG','quantity':4}
    result=asyncio.run(manager._ensure_native_protection(db,row,Broker(),item,'DU_TEST'))
    assert result['reason']=='PROTECTION_OWNERSHIP_QUANTITY_MISMATCH'
    row.raw_json='{}'
    assert asyncio.run(manager._ensure_native_protection(db,row,Broker(),item,'DU_TEST'))['reason']=='SAVED_PROTECTION_LEVELS_INVALID'


@pytest.mark.parametrize('wrong', ['account','symbol','side','order_id','quantity','live_position',None])
def test_protective_exit_requires_exact_executions_and_flat_position(db,wrong,monkeypatch):
    row=entry(db)
    raw=json.loads(row.raw_json);raw['native_protection']={'orders':[{'order_id':10},{'order_id':11}]}
    row.raw_json=json.dumps(raw);db.commit()
    profile=NS(id=row.broker_profile_id,user_id=row.user_id)
    scan=NS(id=uuid.uuid4(),executed_count=0)
    execution={'execution_id':'fill','order_id':10,'account':'DU_TEST','symbol':'MSFT','side':'SLD','quantity':3}
    changes={'account':'OTHER','symbol':'AAPL','side':'BOT','order_id':12,'quantity':2}
    if wrong in changes:execution[wrong]=changes[wrong]
    positions=[{'account':'DU_TEST','symbol':'MSFT','quantity':1}] if wrong=='live_position' else []
    result=manager._reconcile_native_exits(db,scan,profile,[execution,execution],positions,'DU_TEST')
    assert len(result)==(1 if wrong is None else 0)
    if wrong is None:
        assert scan.executed_count==1
        assert db.scalar(select(AutomationAction).where(AutomationAction.status=='EXIT_EXECUTED')).reason=='BROKER_NATIVE_PROTECTIVE_EXIT'
        assert manager._reconcile_native_exits(db,scan,profile,[execution],positions,'DU_TEST')==[]


def test_native_protection_defaults_off_until_explicit_activation():
    assert Settings(_env_file=None).ibkr_native_protection_enabled is False


def test_client_refuses_non_paper_protection(monkeypatch):
    client=IbkrBridgeClient('http://bridge')
    async def health():return {'connected':True,'simulation':False}
    async def post(*args):raise AssertionError('must not place protection')
    monkeypatch.setattr(client,'health',health);monkeypatch.setattr(client,'_post',post)
    with pytest.raises(RuntimeError,match='IBKR_PAPER_BRIDGE_REQUIRED'):
        asyncio.run(client.ensure_protection({'account_id':'DU_TEST','symbol':'MSFT'}))


@pytest.mark.parametrize('status',['PROTECTED','PROTECTION_PENDING','PROTECTION_BLOCKED'])
def test_manager_never_races_an_opposite_close_against_protection(monkeypatch,status):
    db=ScanDB();profile=NS(id=uuid.uuid4(),user_id=uuid.uuid4())
    db.scalars=lambda query:NS(all=lambda:[profile])
    db.scalar=lambda query:NS(market='STOCK')
    async def health():return {'connected':True,'simulation':True}
    async def executions(*args):return {'list':[]}
    async def positions():return {'list':[{'account':'DU_TEST','symbol':'MSFT','quantity':3}]}
    async def order_status(*args):return {'status':{'status':'Filled'}}
    async def unexpected(*args,**kwargs):raise AssertionError('no signal or duplicate close')
    broker=NS(health=health,executions=executions,positions=positions,order_status=order_status,
              candles=unexpected,close_position=unexpected)
    monkeypatch.setattr(manager,'SessionLocal',lambda:db)
    monkeypatch.setattr(manager,'get_settings',lambda:NS(ibkr_native_protection_enabled=True,market_data_timeout_seconds=8))
    monkeypatch.setattr(manager,'get_or_create_state',lambda db:NS(enabled=True,killed=False,auto_execute_paper=True))
    monkeypatch.setattr(manager,'IbkrBridgeClient',lambda *args:broker)
    monkeypatch.setattr(manager,'_secret',lambda p:{'account_id':'DU_TEST'})
    monkeypatch.setattr(manager,'_default_strategy',lambda db:None)
    monkeypatch.setattr(manager,'_latest_entry',lambda *args:NS(id=uuid.uuid4(),side='BUY',status='EXECUTED',quantity=3,broker_order_id='1'))
    for name in ('_reconcile_submitted_entries','_reconcile_submitted_entries_from_positions'):
        monkeypatch.setattr(manager,name,lambda *args:None)
    monkeypatch.setattr(manager,'_reconcile_native_exits',lambda *args:[])
    monkeypatch.setattr(manager,'_has_pending_exit',lambda *args:False)
    async def protection(*args):return {'status':status}
    monkeypatch.setattr(manager,'_ensure_native_protection',protection)
    saved=[];monkeypatch.setattr(manager,'_persist',lambda *args:saved.append(args[-1]))
    result=asyncio.run(manager.run_ibkr_position_manager())
    assert result['status']=='COMPLETED' and result['exit_executed']==0
    assert result['results'][0]['status']==status and saved[0]['status']==status


@pytest.mark.parametrize('change', [{'enabled':False},{'killed':True},{'auto_execute_paper':False}])
def test_existing_engine_and_kill_gates_still_prevent_mutations(monkeypatch,change):
    db=ScanDB();state=NS(enabled=True,killed=False,auto_execute_paper=True)
    for key,value in change.items():setattr(state,key,value)
    monkeypatch.setattr(manager,'SessionLocal',lambda:db)
    monkeypatch.setattr(manager,'get_or_create_state',lambda db:state)
    assert asyncio.run(manager.run_ibkr_position_manager())['status']=='SKIPPED'


def test_unresolved_exit_gate_is_scoped_to_owner_profile_paper_and_symbol(db):
    row=entry(db);row.status='EXIT_SUBMITTED';db.commit()
    profile=NS(id=row.broker_profile_id,user_id=row.user_id)
    assert manager._has_pending_exit(db,profile,'MSFT')
    assert not manager._has_pending_exit(db,NS(id=uuid.uuid4(),user_id=row.user_id),'MSFT')
    assert not manager._has_pending_exit(db,NS(id=profile.id,user_id=uuid.uuid4()),'MSFT')
    assert not manager._has_pending_exit(db,profile,'AAPL')
    row.environment='LIVE';db.commit()
    assert not manager._has_pending_exit(db,profile,'MSFT')


def test_existing_coverage_check_rejects_missing_or_mismatched_orders(native):
    assert not position_has_native_protection(native.live[0],[],'DU_TEST')
    bridge.protection(native.payload,None)
    assert position_has_native_protection(native.live[0],native.book,'DU_TEST')
    native.book[0]['quantity']=2
    assert not position_has_native_protection(native.live[0],native.book,'DU_TEST')


def test_orders_read_all_clients_and_excludes_whatif_callbacks(monkeypatch):
    state=bridge.State();state.next_id=10;state.server_connected=True
    monkeypatch.setattr(bridge,'ib',state);monkeypatch.setattr(bridge,'cfg',{'simulation':True})
    monkeypatch.setattr(state,'isConnected',lambda:True)
    contract=bridge.contract('MSFT');order=bridge.Order();order.account='DU_TEST';order.clientId=99
    order.action='SELL';order.totalQuantity=3;order.orderType='STP';order.whatIf=True
    def read():
        state.openOrder(22,contract,order,NS(status='Submitted'))
        order.whatIf=False
        state.openOrder(23,contract,order,NS(status='Submitted'))
        state.order_statuses[23]={'filled':1}
        state.openOrderEnd()
    monkeypatch.setattr(state,'reqAllOpenOrders',read)
    monkeypatch.setattr(state,'reqOpenOrders',lambda:state.openOrderEnd())
    rows=bridge.orders(None)['list']
    assert len(rows)==1 and rows[0]['client_id']==99 and rows[0]['filled']==1
    assert state.next_id==24


def test_safe_scan_attaches_only_after_committing_the_confirmed_entry(monkeypatch):
    db=ScanDB();profile=NS(id=uuid.uuid4(),user_id=uuid.uuid4())
    db.scalars=lambda query:NS(all=lambda:[NS(user_id=profile.user_id,profile_id=profile.id)])
    state=NS(enabled=True,killed=False,auto_execute_paper=True,interval_seconds=300)
    monkeypatch.setattr(execution,'SessionLocal',lambda:db)
    monkeypatch.setattr(execution,'get_or_create_state',lambda db:state)
    monkeypatch.setattr(execution,'get_settings',lambda:NS(ibkr_native_protection_enabled=True))
    committed=[];saved=[]
    db.commit=lambda:committed.append(True)
    async def preflight(*args,**kwargs):return {'items':[{'market':'STOCK','symbol':'MSFT','provider':'IBKR','preflight':'PASS'}]}
    async def filled(*args,**kwargs):return {'status':'EXECUTED','provider':'IBKR','broker_result':{'order_id':128}}
    def persist(*args):
        row=NS(id=uuid.uuid4());saved.append((row,len(committed)));return row
    async def protect(db_arg,row):
        assert db_arg is db and row is saved[0][0]
        assert len(committed)>saved[0][1]
        return {'status':'PROTECTED'}
    monkeypatch.setattr(execution,'autotrade_preflight',preflight)
    monkeypatch.setattr(execution,'_execute_ibkr',filled)
    monkeypatch.setattr(execution,'_persist_action',persist)
    monkeypatch.setattr(manager,'protect_saved_entry',protect)
    result=asyncio.run(execution.run_safe_scan())
    assert result['status']=='COMPLETED' and result['executed']==1
    assert result['results'][0]['native_protection']['status']=='PROTECTED'


def test_protection_payload_is_in_running_openapi():
    api=bridge.app.openapi()
    assert '/protection' in api['paths']
    assert api['components']['schemas']['ProtectionPayload']['properties']['allow_submit']['default'] is False


@pytest.mark.parametrize('case,reason',[
    ('missing_levels','SAVED_PROTECTION_LEVELS_INVALID'),
    ('old_bridge','IBKR_PROTECTION_BRIDGE_UPGRADE_REQUIRED'),
    ('unprotected_position','IBKR_EXISTING_POSITION_PROTECTION_UNVERIFIED'),
])
def test_new_entries_block_before_submission_when_protection_is_not_ready(monkeypatch,case,reason):
    profile=NS(id=1,provider='IBKR',environment='PAPER',is_enabled=True,is_active=True,
               credentials_configured=True,last_connection_status='CONNECTED')
    class DB:
        def scalar(self,query):return NS(profile_id=1)
        def get(self,model,key):return profile
    class Broker:
        async def health(self):return {'connected':True,'simulation':True,'native_protection_available':case!='old_bridge'}
        async def positions(self):return {'list':[{'account':'DU_TEST','symbol':'MSFT','quantity':3}]}
        async def orders(self):return {'list':[]}
        async def place_order(self,*args):raise AssertionError('must not place entry')
    monkeypatch.setattr(execution,'IbkrBridgeClient',lambda *args:Broker())
    monkeypatch.setattr(execution,'_secret',lambda *args:{'account_id':'DU_TEST'})
    monkeypatch.setattr(execution,'get_settings',lambda:NS(ibkr_native_protection_enabled=True,
                        ibkr_fractional_api_enabled=False,market_data_timeout_seconds=8))
    request={'side':'BUY','shares':3,'stop_loss':98,'take_profit':104}
    if case=='missing_levels':request.pop('stop_loss')
    result=asyncio.run(execution._execute_ibkr(DB(),user_id=1,item={'market':'STOCK','symbol':'AMZN','request':request}))
    assert result['status']=='BLOCK' and result['reason']==reason
