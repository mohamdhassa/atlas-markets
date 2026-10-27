"""Shared account identity and administrator-provisioning boundaries."""
import json
from urllib.parse import urlsplit, urlunsplit
from fastapi import HTTPException
from sqlalchemy import select, text
from app.core.crypto import decrypt_secret
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile


def admin_bridge_required(user, provider):
    if provider in {'IBKR','MT5'} and user.role != 'ADMIN':
        raise HTTPException(403,'An administrator must provision this broker connection')


def active_owner(db, owner_id):
    owner = db.get(User, owner_id, populate_existing=True)
    return owner is not None and owner.is_active is True


def validated_owner(db, user, requested):
    owner_id = requested or user.id
    if owner_id != user.id and user.role != 'ADMIN':
        raise HTTPException(403,'admin role required to assign another owner')
    if not active_owner(db,owner_id):
        raise HTTPException(409,'Account owner must be an active user')
    return owner_id


def bridge_identity(url):
    parsed=urlsplit(str(url).strip())
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(400,'Bridge URL must be an HTTP(S) address without credentials, query or fragment')
    port=parsed.port or (443 if parsed.scheme=='https' else 80)
    return (parsed.hostname.lower(),port,parsed.path.rstrip('/'))


def identity_lock(db):
    # Serialize provisioning across application workers without changing schema.
    if db.get_bind().dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(687301992)'))


def assert_ibkr_assignment(db, owner_id, environment, credentials, exclude=None):
    identity_lock(db)
    account=str(credentials['account_id']).strip()
    endpoint=bridge_identity(credentials['bridge_url'])
    rows=db.scalars(select(BrokerProfile).where(BrokerProfile.provider=='IBKR')).all()
    for row in rows:
        if row.id==exclude:continue
        saved={}
        if row.credential_blob_encrypted:
            saved=json.loads(decrypt_secret(row.credential_blob_encrypted))
        other=str(saved.get('account_id') or row.external_account_ref or '').strip()
        other_endpoint=bridge_identity(saved.get('bridge_url') or 'http://host.docker.internal:8766')
        if endpoint==other_endpoint and (row.user_id!=owner_id or other!=account or row.environment!=environment):
            raise HTTPException(409,'Bridge connection is already assigned to another account or owner')
        if other==account and row.environment==environment:
            raise HTTPException(409,'IBKR account is already assigned; manage its existing profile')


def assert_bybit_key_assignment(db, owner_id, environment, key, exclude=None):
    identity_lock(db)
    for row in db.scalars(select(BrokerProfile).where(BrokerProfile.provider=='BYBIT',BrokerProfile.environment==environment)).all():
        if row.id==exclude or not row.api_key_encrypted:continue
        if decrypt_secret(row.api_key_encrypted).strip()==str(key or '').strip():
            raise HTTPException(409,'API key is already assigned; manage its existing profile')


def entry_owner_blocker(db,profile):
    if not active_owner(db,profile.user_id):return 'ACCOUNT_OWNER_DISABLED'
    current=db.get(BrokerProfile,profile.id,populate_existing=True)
    if current is None or not (current.is_enabled and current.is_active):return 'ROUTE_NOT_READY'
    return None


def assert_bybit_uid(db, uid, environment, exclude=None):
    identity_lock(db)
    for row in db.scalars(select(BrokerProfile).where(BrokerProfile.provider=='BYBIT',BrokerProfile.environment==environment)).all():
        if row.id==exclude:continue
        verified={}
        if row.credential_blob_encrypted:
            verified=json.loads(decrypt_secret(row.credential_blob_encrypted))
        if verified.get('bybit_verified_uid')==str(uid):
            raise HTTPException(409,'Bybit account is already assigned; manage its existing profile')


def audit_account_change(db,actor,profile,action):
    from app.services.auth import write_auth_audit
    write_auth_audit(db,action=action,success=True,user_id=actor.id,
                     detail=f'profile={profile.id};owner={profile.user_id};provider={profile.provider}')
