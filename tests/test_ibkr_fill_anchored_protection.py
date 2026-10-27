import asyncio
import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace as NS

import httpx
import pytest

from app.services.ibkr_protection_levels import fill_anchored_levels
from app.services import ibkr_protection_recovery as recovery
from app.services import ibkr_position_manager as manager


def entry(side='BUY'):
    return NS(id=uuid.uuid4(),provider='IBKR',environment='PAPER',status='EXECUTED',
        side=side,symbol='NVDA',quantity=197,broker_order_id='457',user_id=1,broker_profile_id=2,
        created_at=datetime(2026,10,14,13,36,tzinfo=timezone.utc),
        raw_json=json.dumps({'preflight':{'request':{'stop_loss':225.10205,'take_profit':235.3859},
            'strategy_snapshot':{'effective_parameters':{'take_profit_rr':2}}},
            'result':{'broker_result':{'final_status':{'order_id':457,'status':{
                'order_id':457,'status':'Filled','filled':197,'remaining':0,'avg_fill_price':224.68}}}}}))


def test_exact_nvda_fill_preserves_risk_distance_and_original_request():
    row=entry();original=row.raw_json
    levels=fill_anchored_levels(row)
    assert levels['planned_reference_price']==pytest.approx(228.53)
    assert levels['stop_distance']==pytest.approx(3.42795)
    assert levels['stop_loss']==pytest.approx(221.25205)
    assert levels['take_profit']==pytest.approx(231.5359)
    assert row.raw_json==original


def test_short_levels_use_saved_reference_and_preserve_distances():
    row=entry('SELL');raw=json.loads(row.raw_json)
    raw['preflight']['request']={'reference_price':230,'stop_loss':233,'take_profit':224}
    row.raw_json=json.dumps(raw)
    levels=fill_anchored_levels(row)
    assert levels['stop_loss']==pytest.approx(227.68)
    assert levels['take_profit']==pytest.approx(218.68)
    assert levels['reference_inferred_from_saved_rr'] is False


@pytest.mark.parametrize('wrong',['live','partial','order','price','rr','distances'])
def test_unverified_inputs_cannot_anchor(wrong):
    row=entry();raw=json.loads(row.raw_json)
    if wrong=='live':row.environment='LIVE'
    elif wrong=='partial':raw['result']['broker_result']['final_status']['status']['filled']=196
    elif wrong=='order':raw['result']['broker_result']['final_status']['order_id']=456
    elif wrong=='price':raw['result']['broker_result']['final_status']['status']['avg_fill_price']=0
    elif wrong=='rr':raw['preflight']['strategy_snapshot']['effective_parameters']['take_profit_rr']=0
    elif wrong=='distances':raw['preflight']['request']['reference_price']=220
    row.raw_json=json.dumps(raw)
    with pytest.raises((ValueError,KeyError)):fill_anchored_levels(row)


def recovery_setup(monkeypatch):
    row=entry();raw=json.loads(row.raw_json)
    prior={'status':'SUBMITTING','oca_group':'atlas-protect-'+row.id.hex,'attempted_at':'old'}
    raw['native_protection']=prior;row.raw_json=json.dumps(raw)
    profile=NS(user_id=1,provider='IBKR',environment='PAPER',is_active=True,is_enabled=True,
        credentials_configured=True,last_connection_status='CONNECTED')
    class DB:
        commits=0
        def get(self,*args,**kwargs):return profile
        def refresh(self,*args,**kwargs):pass
        def commit(self):self.commits+=1
    class Broker:
        order_rows=[];execution_rows=[];cost=224.68507915;quantity=197;calls=[]
        async def health(self):return {'connected':True,'simulation':True}
        async def positions(self):return {'list':[dict(account='DU_TEST',symbol='NVDA',sec_type='STK',
            currency='USD',quantity=self.quantity,avg_cost=self.cost)]}
        async def orders(self):return {'list':self.order_rows}
        async def executions(self,*args):return {'list':self.execution_rows}
        async def ensure_protection(self,payload):
            self.calls.append(payload)
            assert payload['allow_submit'] is False
            response=httpx.Response(400,json={'detail':'PROTECTION_LEVELS_DO_NOT_BRACKET_ENTRY'},
                request=httpx.Request('POST','http://bridge/protection'))
            raise httpx.HTTPStatusError('precheck',request=response.request,response=response)
    monkeypatch.setattr(recovery,'get_settings',lambda:NS(ibkr_native_protection_enabled=True,
        ibkr_execution_timezone='Etc/UTC',market_data_timeout_seconds=10))
    monkeypatch.setattr(recovery,'IbkrBridgeClient',lambda *args,**kwargs:Broker())
    monkeypatch.setattr(manager,'_secret',lambda *args:{'account_id':'DU_TEST'})
    monkeypatch.setattr(manager,'_has_pending_exit',lambda *args:False)
    monkeypatch.setattr(manager,'_latest_entry',lambda *args:row)
    return row,DB(),Broker,prior


def test_recovery_preview_never_changes_database_or_submits(monkeypatch):
    row,db,Broker,_=recovery_setup(monkeypatch);before=row.raw_json
    result=asyncio.run(recovery.recover_rejected_levels(db,row))
    assert result['mode']=='PREVIEW' and db.commits==0 and row.raw_json==before
    assert len(Broker.calls)==1 and Broker.calls[0]['allow_submit'] is False


def test_explicit_apply_preserves_original_intent_and_request_then_uses_normal_guard(monkeypatch):
    row,db,_,prior=recovery_setup(monkeypatch);request=json.loads(row.raw_json)['preflight']['request']
    async def protect(db,entry):
        raw=json.loads(entry.raw_json)
        assert raw['native_protection']['status']=='PRE_SUBMISSION_BLOCKED'
        assert raw['native_protection_recovery']['original_intent']==prior
        return {'status':'PROTECTED'}
    monkeypatch.setattr(manager,'protect_saved_entry',protect)
    result=asyncio.run(recovery.recover_rejected_levels(db,row,apply=True))
    assert db.commits==1 and result['result']['status']=='PROTECTED'
    assert json.loads(row.raw_json)['preflight']['request']==request


def test_first_protection_anchors_fill_and_persists_levels_before_send(monkeypatch):
    row,db,_,_=recovery_setup(monkeypatch)
    raw=json.loads(row.raw_json);raw.pop('native_protection');row.raw_json=json.dumps(raw)
    class Broker:
        async def ensure_protection(self,payload):
            assert payload['allow_submit'] is True
            assert payload['stop_loss']==pytest.approx(221.25205)
            assert payload['take_profit']==pytest.approx(231.5359)
            saved=json.loads(row.raw_json)
            assert saved['native_protection']['status']=='SUBMITTING'
            assert saved['native_protection_levels']['fill_price']==224.68
            return {'status':'PROTECTED','simulation':True,'oca_group':'atlas-protect-'+row.id.hex}
    result=asyncio.run(manager._ensure_native_protection(db,row,Broker(),
        dict(symbol='NVDA',position_side='LONG',quantity=197),'DU_TEST'))
    assert result['status']=='PROTECTED'
    assert json.loads(row.raw_json)['preflight']==raw['preflight']


def test_known_error_detail_is_visible_without_leaking_arbitrary_body():
    def error(detail):
        response=httpx.Response(400,json={'detail':detail},request=httpx.Request('POST','http://bridge'))
        return httpx.HTTPStatusError('private',request=response.request,response=response)
    assert manager._protection_error_reason(error('PROTECTION_LEVELS_DO_NOT_BRACKET_ENTRY'))=='PROTECTION_LEVELS_DO_NOT_BRACKET_ENTRY'
    assert manager._protection_error_reason(error('untrusted secret'))=='PROTECTION_CHECK_FAILED:HTTPStatusError'
    assert manager._protection_error_reason(error({'private':'untrusted'}))=='PROTECTION_CHECK_FAILED:HTTPStatusError'


@pytest.mark.parametrize('wrong',['orders','ids','protected','cost','quantity','execution','unknown_time','current'])
def test_recovery_never_releases_ambiguous_or_changed_state(monkeypatch,wrong):
    row,db,Broker,_=recovery_setup(monkeypatch)
    if wrong=='orders':Broker.order_rows=[{'symbol':'NVDA'}]
    elif wrong in {'ids','protected'}:
        raw=json.loads(row.raw_json)
        if wrong=='ids':raw['native_protection']['order_ids']=[459,460]
        else:raw['native_protection']['status']='PROTECTED'
        row.raw_json=json.dumps(raw)
    elif wrong=='cost':Broker.cost=230
    elif wrong=='quantity':Broker.quantity=196
    elif wrong in {'execution','unknown_time'}:
        Broker.execution_rows=[dict(symbol='NVDA',account='DU_TEST',order_id=999,
            time='20261014  14:00:00' if wrong=='execution' else '')]
    elif wrong=='current':monkeypatch.setattr(manager,'_latest_entry',lambda *args:None)
    before=row.raw_json
    with pytest.raises(ValueError):asyncio.run(recovery.recover_rejected_levels(db,row,apply=True))
    assert db.commits==0 and row.raw_json==before
