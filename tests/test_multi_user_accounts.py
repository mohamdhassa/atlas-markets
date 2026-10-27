import asyncio
import json
import uuid
from types import SimpleNamespace as NS

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_current_user, require_admin
from app.api import routes_accounts as accounts, routes_ibkr_external as ibkr
from app.api import routes_account_lifecycle as lifecycle, routes_admin as admin_routes
from app.core.crypto import encrypt_secret, decrypt_secret
from app.db.models.auth import User, UserSession, AuthAuditLog
from app.db.models.broker import BrokerProfile
from app.db.models.ibkr_onboarding import IbkrOnboarding
from app.db.models.live_execution import LiveExecutionEvent
from app.db.session import get_db
from app.services import account_access as access
from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.brokers.bybit_private import BybitPrivateClient, BybitPrivateError


@pytest.fixture
def setup():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    for model in (User,UserSession,AuthAuditLog,BrokerProfile,LiveExecutionEvent,IbkrOnboarding):model.__table__.create(engine)
    db=Session(engine)
    people=[User(username=n,password_hash='hash',role=r,is_active=True) for n,r in [('admin','ADMIN'),('alice','USER'),('bob','USER')]]
    db.add_all(people);db.commit()
    web=FastAPI()
    for router in (accounts.router,lifecycle.router,ibkr.router,admin_routes.router):web.include_router(router)
    current=[people[1]]
    web.dependency_overrides[get_current_user]=lambda:current[0]
    web.dependency_overrides[get_db]=lambda:db
    yield NS(db=db,admin=people[0],alice=people[1],bob=people[2],current=current,client=TestClient(web),web=web)
    db.close();engine.dispose()


def profile(s,owner=None,**kwargs):
    values=dict(user_id=(owner or s.alice).id,provider='IBKR',environment='PAPER',account_label='Paper',external_account_ref='DU_ALICE',credentials_configured=True,is_enabled=True,is_active=True,last_connection_status='CONNECTED',credential_blob_encrypted=encrypt_secret(json.dumps(dict(account_id='DU_ALICE',bridge_url='http://alice:8766',bridge_token='private-token'))))
    values.update(kwargs);row=BrokerProfile(**values);s.db.add(row);s.db.commit();return row


@pytest.mark.parametrize('path', ['/ibkr/validate','/ibkr/connect','/accounts/connect','/accounts'])
def test_user_cannot_submit_arbitrary_bridge_or_assign_node(setup,path,monkeypatch):
    async def forbidden(*args):pytest.fail('No bridge request before authorization')
    monkeypatch.setattr(ibkr,'_validate',forbidden)
    payload=dict(provider='IBKR',environment='PAPER',account_label='Bad',credentials={'account_id':'DU_OTHER','bridge_url':'http://internal/'})
    assert setup.client.post(path,json=payload).status_code==403


def test_other_user_cannot_read_mutate_or_replace_owned_profile(setup):
    row=profile(setup,setup.bob)
    assert setup.client.get('/accounts').json()==[]
    for method,path,body in [('post',f'/ibkr/{row.id}/test',None),('post',f'/ibkr/{row.id}/sync',None),('patch',f'/accounts/{row.id}/toggle',None),('put',f'/accounts/{row.id}/credentials',{'credentials':{'account_id':'DU_ALICE'}})]:
        assert getattr(setup.client,method)(path,json=body).status_code==403


def test_admin_provisions_an_isolated_account_for_selected_user(setup,monkeypatch):
    setup.current[0]=setup.admin
    async def verified(*args):
        return NS(detected_account_ref='DU_ALICE',details={'equity':100,'cash':100,'available':100},message='Verified')
    monkeypatch.setattr(ibkr,'_validate',verified)
    response=setup.client.post('/ibkr/connect',json=dict(provider='IBKR',environment='PAPER',account_label='Alice Paper',owner_user_id=str(setup.alice.id),activate=False,credentials={'account_id':'DU_ALICE','bridge_url':'http://alice:8766','bridge_token':'private-token'}))
    assert response.status_code==201,response.text
    saved=response.json()['profile'];assert saved['user_id']==str(setup.alice.id) and not saved['is_active']
    assert 'private-token' not in response.text and 'encrypted' not in response.text
    setup.current[0]=setup.alice
    assert len(setup.client.get('/accounts').json())==1
    setup.current[0]=setup.bob
    assert setup.client.get('/accounts').json()==[]


@pytest.mark.parametrize('account,url',[('DU_ALICE','http://other:8766'),('DU_OTHER','http://ALICE:8766/')])
def test_admin_cannot_reassign_existing_account_or_bridge_to_other_owner(setup,account,url):
    profile(setup)
    with pytest.raises(HTTPException) as exc:
        access.assert_ibkr_assignment(setup.db,setup.bob.id,'PAPER',{'account_id':account,'bridge_url':url})
    assert exc.value.status_code==409


def test_owner_cannot_reenable_admin_disabled_route_or_activate_it(setup):
    row=profile(setup,is_enabled=False,is_active=False)
    assert setup.client.patch(f'/accounts/{row.id}/toggle').status_code==403
    assert setup.client.post(f'/accounts/{row.id}/activate').status_code==409
    setup.current[0]=setup.admin
    response=setup.client.patch(f'/accounts/{row.id}/toggle')
    assert response.status_code==200 and response.json()['is_enabled'] is True
    assert 'credential_blob_encrypted' not in response.text


def test_bybit_connection_verifies_uid_and_uses_encrypted_owner_credentials(setup,monkeypatch):
    class Client:
        async def api_key_info(self):return {'userID':12345,'permissions':{'Wallet':[]}}
        async def wallet(self):return {'list':[{'totalEquity':'100'}]}
    monkeypatch.setattr(accounts,'BybitPrivateClient',lambda *args:Client())
    payload=dict(provider='BYBIT',environment='TESTNET',account_label='Alice Bybit',api_key='alice-key',api_secret='alice-secret',activate=False)
    response=setup.client.post('/accounts/connect',json=payload)
    assert response.status_code==201,response.text
    saved=setup.db.get(BrokerProfile,uuid.UUID(response.json()['profile']['id']))
    assert saved.user_id==setup.alice.id and saved.external_account_ref=='12345'
    assert decrypt_secret(saved.api_secret_encrypted)=='alice-secret'
    assert 'alice-secret' not in response.text and 'alice-key' not in response.text
    setup.current[0]=setup.bob
    payload.update(api_key='different-key',account_label='Bob same broker UID')
    assert setup.client.post('/accounts/connect',json=payload).status_code==409


def test_bybit_withdrawal_key_rejected(setup,monkeypatch):
    class Client:
        async def api_key_info(self):return {'userID':123,'permissions':{'Wallet':['Withdraw']}}
    monkeypatch.setattr(accounts,'BybitPrivateClient',lambda *args:Client())
    response=setup.client.post('/accounts/connect',json=dict(provider='BYBIT',environment='TESTNET',account_label='Reject',api_key='key',api_secret='secret'))
    assert response.status_code==400


def test_inactive_owner_rejected_and_last_admin_retained(setup):
    setup.current[0]=setup.admin
    row=profile(setup)
    response=setup.client.patch(f'/admin/users/{setup.alice.id}',json={'is_active':False})
    assert response.status_code==200
    assert access.entry_owner_blocker(setup.db,row)=='ACCOUNT_OWNER_DISABLED'
    assert row.is_enabled # Existing protection monitoring still sees this profile.
    assert setup.client.patch(f'/admin/users/{setup.admin.id}',json={'is_active':False}).status_code==409
    assert setup.client.patch(f'/admin/users/{setup.admin.id}',json={'role':'USER'}).status_code==409
    with pytest.raises(HTTPException):access.validated_owner(setup.db,setup.admin,setup.alice.id)


def test_standard_user_cannot_manage_user_lifecycle(setup):
    assert setup.client.get('/admin/users').status_code==403
    assert setup.client.patch(f'/admin/users/{setup.bob.id}',json={'is_active':False}).status_code==403
    assert setup.client.post(f'/admin/users/{setup.bob.id}/reset-password',json={'password':'example-new-password'}).status_code==403


@pytest.mark.parametrize('path',['/positions','/orders','/executions'])
def test_bound_ibkr_client_filters_other_accounts(monkeypatch,path):
    def response(request):return httpx.Response(200,json={'list':[{'account':'DU_ALICE'},{'account':'DU_BOB'},{}]})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(response)))
    client=IbkrBridgeClient('http://bridge',expected_account_id='DU_ALICE')
    assert asyncio.run(client._get(path))=={'list':[{'account':'DU_ALICE'}]}


def test_changed_gateway_identity_blocks_reads_and_submission(monkeypatch):
    requests=[]
    def response(request):
        requests.append(request.method)
        return httpx.Response(200,json={'account_id':'DU_BOB'})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(response)))
    client=IbkrBridgeClient('http://bridge',expected_account_id='DU_ALICE')
    with pytest.raises(RuntimeError,match='IDENTITY_MISMATCH'):
        asyncio.run(client._post('/orders',{'account_id':'DU_ALICE'}))
    assert requests==['GET']


def test_bybit_rechecks_user_after_slow_lot_size_before_post(setup,monkeypatch):
    client=BybitPrivateClient('key','secret','https://api-testnet.bybit.com')
    async def orders():return {'list':[]}
    async def lots(symbol):
        setup.alice.is_active=False;setup.db.commit()
        return '1','1'
    async def forbidden(*args):pytest.fail('Suspended owner must never reach order POST')
    monkeypatch.setattr(client,'spot_open_orders',orders)
    monkeypatch.setattr(client,'_spot_lot_size',lots)
    monkeypatch.setattr(client,'post',forbidden)
    with pytest.raises(BybitPrivateError,match='ACCOUNT_OWNER_DISABLED'):
        asyncio.run(client.place_test_spot_market_order(symbol='TESTUSDT',side='Buy',qty=1,
             before_submit=lambda:None if access.active_owner(setup.db,setup.alice.id) else 'ACCOUNT_OWNER_DISABLED'))


def test_bybit_cannot_claim_other_owner_before_any_provider_reads(setup,monkeypatch):
    # Reject cross-owner requests before credentials touch a provider.
    def forbidden(*args):pytest.fail('Ownership must be checked before provider reads')
    monkeypatch.setattr(accounts,'BybitPrivateClient',forbidden)
    response=setup.client.post('/accounts/connect',json=dict(provider='BYBIT',environment='TESTNET',account_label='Wrong owner',owner_user_id=str(setup.bob.id),api_key='key',api_secret='secret'))
    assert response.status_code==403


def test_credential_replacement_cannot_switch_bybit_account(setup,monkeypatch):
    row=profile(setup,provider='BYBIT',environment='TESTNET',external_account_ref='111',api_key_encrypted=encrypt_secret('old'),api_secret_encrypted=encrypt_secret('old-secret'))
    class Client:
        def __init__(self,key,*args):self.key=key
        async def api_key_info(self):return {'userID':111 if self.key=='old' else 222,'permissions':{'Wallet':[]}}
        async def wallet(self):return {'list':[]}
    monkeypatch.setattr(accounts,'BybitPrivateClient',Client)
    response=setup.client.put(f'/accounts/{row.id}/credentials',json={'api_key':'new','api_secret':'new-secret'})
    assert response.status_code==409
    assert decrypt_secret(row.api_key_encrypted)=='old'


def test_unverified_reference_cannot_squat_another_bybit_uid(setup,monkeypatch):
    profile(setup,setup.bob,provider='BYBIT',environment='TESTNET',external_account_ref='12345',credentials_configured=False,credential_blob_encrypted=None)
    class Client:
        async def api_key_info(self):return {'userID':12345,'permissions':{'Wallet':[]}}
        async def wallet(self):return {'list':[]}
    monkeypatch.setattr(accounts,'BybitPrivateClient',lambda *args:Client())
    response=setup.client.post('/accounts/connect',json=dict(provider='BYBIT',environment='TESTNET',account_label='Verified owner',api_key='key',api_secret='secret',activate=False))
    assert response.status_code==201,response.text
