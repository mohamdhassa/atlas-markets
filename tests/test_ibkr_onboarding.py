import asyncio
import hashlib
import json
import uuid
from datetime import timedelta
from types import SimpleNamespace as NS
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.api.dependencies import get_current_user
from app.api import routes_ibkr_onboarding as routes
from app.core.crypto import decrypt_secret
from app.db.models.auth import User,AuthAuditLog
from app.db.models.broker import BrokerProfile
from app.db.models.ibkr_onboarding import IbkrOnboarding as Job
from app.db.session import get_db

TOKEN='x'*48

@pytest.fixture
def setup(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    for model in (User,AuthAuditLog,BrokerProfile,Job):model.__table__.create(engine)
    db=Session(engine)
    users=[User(username=n,password_hash='hash',role=r,is_active=True) for n,r in [('admin','ADMIN'),('alice','USER'),('bob','USER')]]
    db.add_all(users);db.commit();current=[users[1]]
    app=FastAPI();app.include_router(routes.router)
    app.dependency_overrides[get_current_user]=lambda:current[0]
    app.dependency_overrides[get_db]=lambda:db
    monkeypatch.setattr(routes,'get_settings',lambda:NS(ibkr_provisioning_enabled=True,ibkr_provisioner_token=TOKEN))
    yield NS(db=db,client=TestClient(app),admin=users[0],alice=users[1],bob=users[2],current=current)
    db.close();engine.dispose()


def request(s):
    r=s.client.post('/ibkr/onboarding',json={'account_id':'DUALICE123','account_label':'Alice Paper'})
    assert r.status_code==201,r.text
    return r.json()['id']


def approve(s,key):
    s.current[0]=s.admin
    assert s.client.post(f'/ibkr/onboarding/{key}/approve').status_code==200
    s.current[0]=s.alice


def queue(s):
    key=request(s);approve(s,key)
    r=s.client.post(f'/ibkr/onboarding/{key}/credentials',json={'username':'paper_alice','password':'private-broker-password'})
    assert r.status_code==200,r.text
    assert 'private-broker-password' not in r.text
    return key


def claim(s):
    return s.client.post('/ibkr/onboarding/worker/claim',headers={'X-Atlas-Provisioner':TOKEN})


def started(s,key):
    body=claim(s).json()
    r=s.client.post(f'/ibkr/onboarding/worker/{key}/ack',headers={'X-Atlas-Provisioner':TOKEN},json={'lease_token':body['lease_token'],'outcome':'STARTED'})
    assert r.status_code==200,r.text
    return body


def test_other_owner_cannot_approve_read_or_submit_login(setup):
    s=setup;key=request(s)
    assert s.client.post(f'/ibkr/onboarding/{key}/approve').status_code==403
    s.current[0]=s.bob
    assert s.client.get('/ibkr/onboarding').json()['jobs']==[]
    assert s.client.post(f'/ibkr/onboarding/{key}/credentials',json={'username':'test','password':'private'}).status_code==404


def test_only_approved_jobs_can_be_claimed_and_credentials_are_never_listed(setup):
    s=setup;key=request(s)
    assert claim(s).status_code==204
    assert s.client.post(f'/ibkr/onboarding/{key}/credentials',json={'username':'test','password':'private'}).status_code==409
    approve(s,key)
    response=s.client.post(f'/ibkr/onboarding/{key}/credentials',json={'username':'paper_alice','password':'private-broker-password'})
    saved=s.db.get(Job,uuid.UUID(key))
    assert json.loads(decrypt_secret(saved.credentials_encrypted))['password']=='private-broker-password'
    assert 'private-broker-password' not in s.client.get('/ibkr/onboarding').text
    assert s.client.post('/ibkr/onboarding/worker/claim').status_code==401
    response=claim(s);assert response.headers['cache-control']=='no-store'
    data=response.json();assert data['login']['password']=='private-broker-password'
    assert claim(s).status_code==204
    assert saved.lease_hash==hashlib.sha256(data['lease_token'].encode()).hexdigest()


def test_started_ack_erases_pending_login_and_invalidates_lease(setup):
    s=setup;key=queue(s);body=started(s,key);saved=s.db.get(Job,uuid.UUID(key))
    assert saved.credentials_encrypted is None and saved.status=='LOGIN_REQUIRED'
    assert saved.lease_hash is None
    response=s.client.post(f'/ibkr/onboarding/worker/{key}/ack',headers={'X-Atlas-Provisioner':TOKEN},json={'lease_token':body['lease_token'],'outcome':'STARTED'})
    assert response.status_code==409


def test_expired_lease_requires_review_without_automatic_redeployment(setup):
    s=setup;key=queue(s);body=claim(s).json();saved=s.db.get(Job,uuid.UUID(key))
    saved.lease_until=routes.now()-timedelta(seconds=1);s.db.commit()
    assert claim(s).status_code==204
    s.db.refresh(saved);assert saved.status=='FAILED' and saved.credentials_encrypted is None
    assert saved.error_code=='LEASE_EXPIRED'


@pytest.mark.parametrize('account,simulation',[('DUBOB123',True),('DUALICE123',False)])
def test_wrong_broker_account_or_live_session_never_creates_profile(setup,monkeypatch,account,simulation):
    s=setup;key=queue(s);started(s,key)
    class Broker:
        async def health(self):return {'connected':True,'simulation':simulation}
        async def account(self):return {'account_id':account,'simulation':simulation}
    monkeypatch.setattr(routes,'IbkrBridgeClient',lambda *a,**k:Broker())
    r=s.client.post(f'/ibkr/onboarding/{key}/verify')
    assert r.json()['status']=='LOGIN_REQUIRED'
    assert s.db.query(BrokerProfile).count()==0


def test_success_connects_exact_owner_in_standby_and_is_idempotent(setup,monkeypatch):
    s=setup;key=queue(s);started(s,key)
    class Broker:
        async def health(self):return {'connected':True,'simulation':True}
        async def account(self):return {'account_id':'DUALICE123','simulation':True}
    monkeypatch.setattr(routes,'IbkrBridgeClient',lambda *a,**k:Broker())
    for _ in range(2):assert s.client.post(f'/ibkr/onboarding/{key}/verify').json()['status']=='CONNECTED'
    row=s.db.query(BrokerProfile).one()
    assert row.user_id==s.alice.id and not row.is_active and not row.live_execution_enabled
    assert not row.execution_certified
    creds=json.loads(decrypt_secret(row.credential_blob_encrypted))
    assert creds['bridge_url']=='http://atlas-ibkr-setup-'+uuid.UUID(key).hex+':8766'
    assert s.db.get(Job,uuid.UUID(key)).bridge_token_encrypted is None


def test_disabled_owner_not_claimed_and_admin_cannot_submit_owner_password(setup):
    s=setup;key=queue(s);s.current[0]=s.admin
    assert s.client.post(f'/ibkr/onboarding/{key}/credentials',json={'username':'test','password':'private'}).status_code==403
    s.alice.is_active=False;s.db.commit();assert claim(s).status_code==204
    assert s.db.get(Job,uuid.UUID(key)).status=='FAILED'


@pytest.mark.parametrize('name,password',[('evil\nX=1','private'),('name','bad\npassword'),('$(whoami)','private')])
def test_login_rejects_env_injection_without_echoing_secrets(setup,name,password):
    s=setup;key=request(s);approve(s,key)
    response=s.client.post(f'/ibkr/onboarding/{key}/credentials',json={'username':name,'password':password})
    assert response.status_code==400 and password not in response.text


def test_feature_disabled_fail_closed_and_live_requests_rejected(setup,monkeypatch):
    s=setup;key=request(s)
    monkeypatch.setattr(routes,'get_settings',lambda:NS(ibkr_provisioning_enabled=False,ibkr_provisioner_token=''))
    s.current[0]=s.admin
    assert s.client.post(f'/ibkr/onboarding/{key}/approve').status_code==503
    assert claim(s).status_code==503
    assert s.client.post('/ibkr/onboarding',json={'account_id':'U12345','account_label':'Live'}).status_code==422


def test_unapproved_request_cannot_reserve_someone_elses_account(setup):
    s=setup;first=request(s);s.current[0]=s.bob
    r=s.client.post('/ibkr/onboarding',json={'account_id':'DUALICE123','account_label':'Bob request'})
    assert r.status_code==201
    second=r.json()['id'];s.current[0]=s.admin
    assert s.client.post(f'/ibkr/onboarding/{first}/approve').status_code==200
    assert s.client.post(f'/ibkr/onboarding/{second}/approve').status_code==409


def test_wrong_lease_cannot_ack_and_unknown_worker_error_is_sanitized(setup):
    s=setup;key=queue(s);body=claim(s).json()
    headers={'X-Atlas-Provisioner':TOKEN}
    assert s.client.post(f'/ibkr/onboarding/worker/{key}/ack',headers=headers,json={'lease_token':'wrong','outcome':'STARTED'}).status_code==409
    r=s.client.post(f'/ibkr/onboarding/worker/{key}/ack',headers=headers,json={'lease_token':body['lease_token'],'outcome':'FAILED','error_code':'secret-error-text'})
    assert r.json()['error_code']=='NODE_START_FAILED' and 'secret-error-text' not in r.text


def test_owner_can_correct_a_typo_only_before_approval_and_provisioning(setup):
    s=setup;key=request(s)
    response=s.client.put(f'/ibkr/onboarding/{key}',json={'account_id':'DUALICE456','account_label':'Corrected'})
    assert response.status_code==200 and response.json()['status']=='REQUESTED'
    approve(s,key)
    assert s.client.put(f'/ibkr/onboarding/{key}',json={'account_id':'DUALICE789','account_label':'Change after approval'}).status_code==409


def test_suspension_during_broker_verification_prevents_profile_creation(setup,monkeypatch):
    s=setup;key=queue(s);started(s,key)
    class Broker:
        async def health(self):return {'connected':True,'simulation':True}
        async def account(self):
            s.alice.is_active=False;s.db.commit()
            return {'account_id':'DUALICE123','simulation':True}
    monkeypatch.setattr(routes,'IbkrBridgeClient',lambda *a,**k:Broker())
    assert s.client.post(f'/ibkr/onboarding/{key}/verify').status_code==409
    assert s.db.query(BrokerProfile).count()==0


def test_additive_migration_and_downgrade_preserve_existing_users():
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect,insert,select
    migration=importlib.import_module('migrations.versions.20261027_0024_ibkr_onboarding')
    engine=create_engine('sqlite://')
    User.__table__.create(engine);BrokerProfile.__table__.create(engine)
    with engine.begin() as connection:
        identity=uuid.uuid4()
        connection.execute(insert(User).values(id=identity,username='existing',password_hash='hash',role='ADMIN',is_active=True))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert 'ibkr_onboarding' in inspect(connection).get_table_names()
            assert connection.scalar(select(User.username))=='existing'
            migration.downgrade()
            assert 'ibkr_onboarding' not in inspect(connection).get_table_names()
            assert connection.scalar(select(User.username))=='existing'
    engine.dispose()


def test_existing_connection_added_after_request_blocks_gateway_launch(setup):
    s=setup;key=request(s)
    profile=BrokerProfile(user_id=s.bob.id,provider='IBKR',environment='PAPER',account_label='Existing connection',external_account_ref='DUALICE123')
    s.db.add(profile);s.db.commit();s.current[0]=s.admin
    assert s.client.post(f'/ibkr/onboarding/{key}/approve').status_code==409
    assert claim(s).status_code==204


def test_approved_setup_reserves_identity_against_manual_reassignment(setup):
    from app.services.account_access import assert_ibkr_assignment
    from fastapi import HTTPException
    s=setup;key=request(s);approve(s,key)
    with pytest.raises(HTTPException) as exc:
        assert_ibkr_assignment(s.db,s.bob.id,'PAPER',{'account_id':'DUALICE123','bridge_url':'http://other:8766'})
    assert exc.value.status_code==409


def test_request_cannot_supply_live_environment_or_docker_settings(setup):
    response=setup.client.post('/ibkr/onboarding',json={'account_id':'DUALICE123','account_label':'Injected','environment':'LIVE','command':'docker stop production'})
    assert response.status_code==422
    assert setup.db.query(Job).count()==0
