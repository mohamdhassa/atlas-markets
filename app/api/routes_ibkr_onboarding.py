"""Paper-only queue. The web app never executes Docker or accepts container specs."""
import hashlib
import hmac
import json
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user, require_admin
from app.core.config import get_settings
from app.core.crypto import encrypt_secret, decrypt_secret
from app.db.models.ibkr_onboarding import IbkrOnboarding as Job
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.session import get_db
from app.services.account_access import active_owner, validated_owner, assert_ibkr_assignment, identity_lock
from app.services.auth import write_auth_audit
from app.brokers.ibkr_bridge import IbkrBridgeClient

router=APIRouter(prefix='/ibkr/onboarding',tags=['ibkr-onboarding'])
ERRORS={'NODE_CAPACITY','NODE_START_FAILED','NODE_POLICY_INVALID','LEASE_EXPIRED'}


def now():return datetime.now(timezone.utc)
def aware(value):return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

def configured():
    s=get_settings()
    return bool(s.ibkr_provisioning_enabled and len(s.ibkr_provisioner_token)>=32)

def enabled():
    if not configured():raise HTTPException(503,'IBKR setup service is not enabled by the operator')

def audit(db,actor,job,event):
    write_auth_audit(db,action=event,success=True,user_id=actor,
                     detail=f'onboarding={job.id};owner={job.user_id};status={job.status}')

def public(job):
    result={k:getattr(job,k) for k in ('id','user_id','account_id','account_label','status','profile_id','error_code','attempts','created_at','updated_at')}
    if job.status=='PROVISIONING' and job.lease_until and aware(job.lease_until)<now():
        result.update(status='REVIEW_REQUIRED',error_code='LEASE_EXPIRED')
    if job.status=='CONNECTED' and not job.profile_id:
        result.update(status='REVIEW_REQUIRED',error_code='PROFILE_REMOVED_REQUIRES_REVIEW')
    return result

def owned(db,user,key):
    row=db.get(Job,key)
    if not row or (user.role!='ADMIN' and row.user_id!=user.id):raise HTTPException(404,'Setup request not found')
    db.refresh(row,with_for_update=True)
    return row


def account_registered(db,account_id):
    for profile in db.scalars(select(BrokerProfile).where(BrokerProfile.provider=='IBKR',BrokerProfile.environment=='PAPER')).all():
        if profile.external_account_ref==account_id:return True
        if profile.credential_blob_encrypted and json.loads(decrypt_secret(profile.credential_blob_encrypted)).get('account_id')==account_id:return True
    return False


class Request(BaseModel):
    model_config=ConfigDict(extra='forbid')
    account_id:str=Field(pattern=r'^DU[A-Z0-9]{3,32}$')
    account_label:str=Field(min_length=2,max_length=96)
    owner_user_id:uuid.UUID|None=None


class Login(BaseModel):
    username:SecretStr
    password:SecretStr


class Acknowledgment(BaseModel):
    lease_token:SecretStr
    outcome:str=Field(pattern=r'^(STARTED|FAILED)$')
    error_code:str|None=None


@router.get('')
def listing(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    query=select(Job).order_by(Job.created_at.desc())
    if user.role!='ADMIN':query=query.where(Job.user_id==user.id)
    rows=list(db.scalars(query).all())
    names=dict(db.execute(select(User.id,User.username).where(User.id.in_([j.user_id for j in rows]))).all()) if user.role=='ADMIN' and rows else {}
    return {'enabled':configured(),'jobs':[{**public(j),**({'owner_username':names.get(j.user_id,'Unknown user')} if user.role=='ADMIN' else {})} for j in rows]}


@router.post('',status_code=201)
def request(payload:Request,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    owner=validated_owner(db,user,payload.owner_user_id)
    if account_registered(db,payload.account_id):
        raise HTTPException(409,'Account already has a profile; administrator must review it')
    job=Job(user_id=owner,account_id=payload.account_id,account_label=payload.account_label,status='REQUESTED',attempts=0)
    db.add(job)
    try:db.flush()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Owner or account already has a setup request')
    audit(db,user.id,job,'ibkr_setup_requested');db.commit();db.refresh(job)
    return public(job)


@router.put('/{key}')
def amend(key:uuid.UUID,payload:Request,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    job=owned(db,user,key)
    if job.status not in {'REQUESTED','REJECTED'} or job.attempts:
        raise HTTPException(409,'Only unprovisioned requests may be corrected')
    if payload.owner_user_id and payload.owner_user_id!=job.user_id:
        raise HTTPException(409,'Request ownership cannot change')
    if account_registered(db,payload.account_id):
        raise HTTPException(409,'Account already has a profile; administrator must review it')
    job.account_id=payload.account_id;job.account_label=payload.account_label;job.status='REQUESTED'
    job.approved_by=None;job.error_code=None
    audit(db,user.id,job,'ibkr_setup_corrected');db.commit();return public(job)


@router.post('/{key}/approve')
def approve(key:uuid.UUID,user:User=Depends(require_admin),db:Session=Depends(get_db)):
    enabled();job=owned(db,user,key)
    if job.status not in {'REQUESTED','FAILED','REJECTED'}:raise HTTPException(409,'Request cannot be approved in this state')
    if not active_owner(db,job.user_id):raise HTTPException(409,'Owner is disabled')
    identity_lock(db)
    if account_registered(db,job.account_id):raise HTTPException(409,'Account already has a profile; use its existing connection')
    competing=db.scalar(select(Job.id).where(Job.id!=job.id,Job.account_id==job.account_id,Job.status.in_(['APPROVED','QUEUED','PROVISIONING','LOGIN_REQUIRED','CONNECTED'])))
    if competing:raise HTTPException(409,'Account already has an approved setup; administrator review required')
    job.status='APPROVED';job.approved_by=user.id;job.error_code=None;job.attempts=0
    job.credentials_encrypted=None;job.lease_hash=None;job.lease_until=None
    audit(db,user.id,job,'ibkr_setup_approved');db.commit();return public(job)


@router.post('/{key}/reject')
def reject(key:uuid.UUID,user:User=Depends(require_admin),db:Session=Depends(get_db)):
    job=owned(db,user,key)
    if job.status not in {'REQUESTED','APPROVED','FAILED'}:raise HTTPException(409,'Running setup cannot be removed through rejection')
    job.status='REJECTED';job.credentials_encrypted=None
    audit(db,user.id,job,'ibkr_setup_rejected');db.commit();return public(job)


@router.post('/{key}/credentials')
def credentials(key:uuid.UUID,payload:Login,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    enabled();job=owned(db,user,key)
    if job.user_id!=user.id:raise HTTPException(403,'Only the account owner may submit the broker login')
    if job.status not in {'APPROVED','FAILED','LOGIN_REQUIRED'} or not job.approved_by:raise HTTPException(409,'Administrator approval is required')
    if job.attempts>=3:raise HTTPException(409,'Administrator must review and approve another attempt')
    name=payload.username.get_secret_value();password=payload.password.get_secret_value()
    if not re.fullmatch(r'[A-Za-z0-9_.@-]{1,128}',name) or not 1<=len(password)<=256 or any(c in name+password for c in '\r\n\x00'):
        raise HTTPException(400,'Invalid broker login format')
    job.credentials_encrypted=encrypt_secret(json.dumps({'username':name,'password':password}))
    if not job.bridge_token_encrypted:job.bridge_token_encrypted=encrypt_secret(secrets.token_urlsafe(48))
    job.status='QUEUED';job.error_code=None;job.lease_hash=None;job.lease_until=None
    audit(db,user.id,job,'ibkr_setup_login_submitted');db.commit()
    return public(job)


def worker(x_atlas_provisioner:str|None=Header(default=None)):
    enabled()
    if not x_atlas_provisioner or not hmac.compare_digest(x_atlas_provisioner,get_settings().ibkr_provisioner_token):
        raise HTTPException(401,'Provisioner authentication required')


@router.post('/worker/claim',dependencies=[Depends(worker)])
def claim(response:Response,db:Session=Depends(get_db)):
    response.headers['Cache-Control']='no-store'
    # A lost worker must not cause an automatic second deployment or password replay.
    stale=db.scalars(select(Job).where(Job.status=='PROVISIONING',Job.lease_until<now()).with_for_update(skip_locked=True)).all()
    for j in stale:
        j.status='FAILED';j.error_code='LEASE_EXPIRED';j.credentials_encrypted=None;j.lease_hash=None
    job=db.scalar(select(Job).where(Job.status=='QUEUED').order_by(Job.created_at).with_for_update(skip_locked=True).limit(1))
    if not job:
        db.commit();response.status_code=204;return None
    if account_registered(db,job.account_id):
        job.status='FAILED';job.error_code='ACCOUNT_ALREADY_ASSIGNED';job.credentials_encrypted=None;db.commit();response.status_code=204;return None
    if not active_owner(db,job.user_id):
        job.status='FAILED';job.error_code='OWNER_DISABLED';job.credentials_encrypted=None;db.commit();response.status_code=204;return None
    token=secrets.token_urlsafe(48);job.lease_hash=hashlib.sha256(token.encode()).hexdigest()
    job.status='PROVISIONING';job.lease_until=now()+timedelta(minutes=10);job.attempts+=1
    data={'job_id':str(job.id),'account_id':job.account_id,'instance':'setup-'+job.id.hex,
          'login':json.loads(decrypt_secret(job.credentials_encrypted)),
          'bridge_token':decrypt_secret(job.bridge_token_encrypted),'lease_token':token}
    audit(db,None,job,'ibkr_setup_claimed');db.commit();return data


@router.post('/worker/{key}/ack',dependencies=[Depends(worker)])
def acknowledge(key:uuid.UUID,payload:Acknowledgment,db:Session=Depends(get_db)):
    job=db.get(Job,key)
    if not job:raise HTTPException(404,'Setup request not found')
    db.refresh(job,with_for_update=True)
    digest=hashlib.sha256(payload.lease_token.get_secret_value().encode()).hexdigest()
    if job.status!='PROVISIONING' or not job.lease_hash or not hmac.compare_digest(job.lease_hash,digest) or not job.lease_until or aware(job.lease_until)<now():
        raise HTTPException(409,'Provisioning lease is invalid or expired')
    job.status='LOGIN_REQUIRED' if payload.outcome=='STARTED' else 'FAILED'
    job.error_code=None if payload.outcome=='STARTED' else (payload.error_code if payload.error_code in ERRORS else 'NODE_START_FAILED')
    job.credentials_encrypted=None;job.lease_hash=None;job.lease_until=None
    audit(db,None,job,'ibkr_setup_worker_result');db.commit();return public(job)


@router.post('/{key}/verify')
async def verify(key:uuid.UUID,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    enabled();job=owned(db,user,key)
    if job.status=='CONNECTED':return public(job)
    if job.status!='LOGIN_REQUIRED':raise HTTPException(409,'Gateway is not awaiting login verification')
    if not active_owner(db,job.user_id):raise HTTPException(409,'Owner is disabled')
    values={'account_id':job.account_id,'bridge_url':f'http://atlas-ibkr-setup-{job.id.hex}:8766',
            'bridge_token':decrypt_secret(job.bridge_token_encrypted)}
    expected=job.account_id
    # Release the queue-row lock before network waits, then revalidate under lock.
    db.commit()
    broker=IbkrBridgeClient(values['bridge_url'],values['bridge_token'],8,expected_account_id=expected)
    try:
        health=await broker.health()
        if not health.get('connected'):raise RuntimeError('pending')
        if health.get('simulation') is not True:raise ValueError('environment')
        if health.get('accounts') is not None and expected not in health['accounts']:raise ValueError('identity')
        account=await broker.account()
        if account.get('account_id')!=expected or account.get('simulation') is not True:raise ValueError('identity')
    except ValueError:
        job=owned(db,user,key)
        if job.status!='LOGIN_REQUIRED':return public(job)
        job.error_code='ACCOUNT_OR_ENVIRONMENT_MISMATCH';db.commit();return public(job)
    except Exception as exc:
        job=owned(db,user,key)
        if job.status!='LOGIN_REQUIRED':return public(job)
        job.error_code='ACCOUNT_OR_ENVIRONMENT_MISMATCH' if str(exc)=='IBKR_ACCOUNT_IDENTITY_MISMATCH' else 'BROKER_LOGIN_PENDING'
        db.commit();return public(job)
    job=owned(db,user,key)
    if job.status=='CONNECTED':return public(job)
    if job.status!='LOGIN_REQUIRED':raise HTTPException(409,'Setup state changed during verification')
    assert_ibkr_assignment(db,job.user_id,'PAPER',values,onboarding_id=job.id)
    if not active_owner(db,job.user_id):raise HTTPException(409,'Owner is disabled')
    profile=BrokerProfile(user_id=job.user_id,provider='IBKR',environment='PAPER',account_label=job.account_label,
        external_account_ref=job.account_id,credential_blob_encrypted=encrypt_secret(json.dumps(values)),
        credentials_configured=True,is_active=False,is_enabled=False,live_execution_enabled=False,
        last_connection_status='CONNECTED',last_connection_test_at=now())
    db.add(profile);db.flush();job.profile_id=profile.id;job.status='CONNECTED';job.error_code=None
    job.bridge_token_encrypted=None
    audit(db,user.id,job,'ibkr_setup_connected');db.commit();return public(job)
