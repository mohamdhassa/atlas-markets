from __future__ import annotations
import json, uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.brokers.bybit_private import BybitPrivateClient
from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.session import get_db
from app.market_data.fx import TwelveDataFxMarketData
from app.schemas.broker_profile import BrokerConnectRequest, BrokerConnectResult, BrokerCredentialsUpdate, BrokerProfileCreate, BrokerProfilePublic, BrokerValidateRequest, BrokerValidationResult, LiveExecutionUpdate

router=APIRouter(prefix='/accounts',tags=['accounts'])
PROVIDER_ENVIRONMENTS={'BYBIT':{'DEMO','TESTNET','LIVE'},'MT5':{'DEMO','LIVE'},'IBKR':{'PAPER','LIVE'},'TWELVE_DATA':{'LIVE'}}
TRADING_PROVIDERS={'BYBIT','MT5','IBKR'}
SIMULATION_ENVIRONMENTS={'DEMO','TESTNET','PAPER'}

def _is_admin(u): return u.role=='ADMIN'
def _authorized_profile(db,u,pid):
    p=db.get(BrokerProfile,pid)
    if p is None or p.provider=='ATLAS_PAPER': raise HTTPException(404,'account not found')
    if not _is_admin(u) and p.user_id!=u.id: raise HTTPException(403,'account access denied')
    return p

def _base_for_bybit(environment):
    s=get_settings();return s.bybit_public_base_url if environment=='LIVE' else s.bybit_demo_base_url if environment=='DEMO' else s.bybit_testnet_base_url

def _bybit_client(p):
    if not p.credentials_configured or not p.api_key_encrypted or not p.api_secret_encrypted: raise HTTPException(400,'API credentials are not configured')
    return BybitPrivateClient(decrypt_secret(p.api_key_encrypted),decrypt_secret(p.api_secret_encrypted),_base_for_bybit(p.environment),get_settings().market_data_timeout_seconds)

def _creds(p):
    if not p.credential_blob_encrypted: raise ValueError('credentials are not configured')
    return json.loads(decrypt_secret(p.credential_blob_encrypted))

def _mt5_client(p):
    c=_creds(p);return Mt5BridgeClient(c.get('bridge_url') or 'http://host.docker.internal:8765',c.get('bridge_token'),get_settings().market_data_timeout_seconds)

def _generic(provider,values):
    c={str(k):str(v).strip() for k,v in (values or {}).items() if str(v).strip()};required={'MT5':{'login','password','server'},'IBKR':{'account_id','host','port','client_id'}}.get(provider,set());missing=sorted(required-set(c))
    if missing: raise HTTPException(400,f"missing credentials: {', '.join(missing)}")
    return c

def _owner_id(db,user,requested):
    if requested is None:return user.id
    if not _is_admin(user):raise HTTPException(403,'admin role required to assign another owner')
    owner=db.get(User,requested)
    if owner is None:raise HTTPException(404,'owner user not found')
    return owner.id

def _validate_environment(provider,environment):
    if provider=='ATLAS_PAPER': raise HTTPException(410,'The built-in ATLAS account has been retired. Connect an external provider account instead.')
    allowed=PROVIDER_ENVIRONMENTS.get(provider)
    if allowed is None or environment not in allowed: raise HTTPException(400,f'{provider} does not support the selected account environment')

def _duplicate(db,owner_id,provider,environment,label,external_ref=None):
    rows=list(db.scalars(select(BrokerProfile).where(BrokerProfile.user_id==owner_id,BrokerProfile.provider==provider,BrokerProfile.environment==environment)).all());label_norm=label.strip().lower();ref_norm=(external_ref or '').strip().lower()
    for row in rows:
        if row.provider=='ATLAS_PAPER':continue
        if row.account_label.strip().lower()==label_norm:return row
        if ref_norm and (row.external_account_ref or '').strip().lower()==ref_norm:return row
    return None

async def _validate_raw(payload:BrokerValidateRequest)->BrokerValidationResult:
    _validate_environment(payload.provider,payload.environment);warnings=[];details={};detected_ref=(payload.external_account_ref or '').strip() or None;detected_name=None
    if payload.provider=='BYBIT':
        if not payload.api_key or not payload.api_secret:raise HTTPException(400,'BYBIT requires API key and API secret')
        client=BybitPrivateClient(payload.api_key.strip(),payload.api_secret.strip(),_base_for_bybit(payload.environment),get_settings().market_data_timeout_seconds);wallet=await client.wallet();a=(wallet.get('list') or [{}])[0];details={'equity':a.get('totalEquity'),'wallet_balance':a.get('totalWalletBalance'),'available_balance':a.get('totalAvailableBalance')}
        return BrokerValidationResult(valid=True,provider='BYBIT',environment=payload.environment,connection_status='CONNECTED',message='Bybit account credentials validated successfully.',detected_account_ref=detected_ref,warnings=warnings,details=details)
    if payload.provider=='TWELVE_DATA':
        if not payload.api_key:raise HTTPException(400,'TWELVE DATA requires API key')
        s=get_settings();quote=await TwelveDataFxMarketData(s.fx_market_data_base_url,payload.api_key.strip(),s.market_data_timeout_seconds).get_quote('EURUSD');details={'probe_symbol':'EURUSD','price':quote.get('price') if isinstance(quote,dict) else getattr(quote,'price',None)}
        return BrokerValidationResult(valid=True,provider='TWELVE_DATA',environment='LIVE',connection_status='CONNECTED',message='Twelve Data API key validated successfully.',warnings=['Twelve Data supplies market data only; positions and orders remain with the selected broker.'],details=details)
    if payload.provider=='MT5':
        c=_generic('MT5',payload.credentials or {});bridge=Mt5BridgeClient(c.get('bridge_url') or 'http://host.docker.internal:8765',c.get('bridge_token'),get_settings().market_data_timeout_seconds);health=await bridge.health();account=await bridge.account()
        if not health.get('connected'):raise HTTPException(400,'MT5 bridge is reachable but the terminal is not connected')
        expected_login=str(c['login']).strip();actual_login=str(account.get('login') or '').strip();expected_server=str(c['server']).strip();actual_server=str(account.get('server') or health.get('server') or '').strip()
        if actual_login!=expected_login:raise HTTPException(409,f'MT5 account mismatch: entered {expected_login}, bridge is connected to {actual_login or "unknown"}')
        if actual_server and actual_server.lower()!=expected_server.lower():raise HTTPException(409,f'MT5 server mismatch: entered {expected_server}, bridge reports {actual_server}')
        terminal=health.get('terminal') or {}
        if terminal.get('trade_allowed') is False:warnings.append('MT5 automated trading is currently disabled in the terminal; analysis remains available but broker orders are blocked.')
        detected_ref=actual_login;detected_name=account.get('name') or None;details={'login':actual_login,'server':actual_server,'balance':account.get('balance'),'equity':account.get('equity'),'margin_free':account.get('margin_free'),'trade_allowed':account.get('trade_allowed'),'trade_expert':account.get('trade_expert'),'terminal_trade_allowed':terminal.get('trade_allowed')}
        return BrokerValidationResult(valid=True,provider='MT5',environment=payload.environment,connection_status='CONNECTED',message=f'MT5 account {actual_login} validated through the ATLAS bridge.',detected_account_ref=detected_ref,detected_account_name=detected_name,warnings=warnings,details=details)
    if payload.provider=='IBKR':
        _generic('IBKR',payload.credentials or {});return BrokerValidationResult(valid=False,provider='IBKR',environment=payload.environment,connection_status='NOT_READY',message='IBKR validation is not enabled yet. ATLAS will not save or activate this connection until the TWS/IB Gateway adapter is complete.',warnings=['No IBKR connection is created until broker validation succeeds.'])
    raise HTTPException(400,'unsupported provider')

def _new_profile(db,user,payload,external_ref=None):
    _validate_environment(payload.provider,payload.environment);owner_id=_owner_id(db,user,payload.owner_user_id);ref=external_ref if external_ref is not None else ((payload.external_account_ref or '').strip() or None);dup=_duplicate(db,owner_id,payload.provider,payload.environment,payload.account_label,ref)
    if dup:raise HTTPException(409,f'duplicate account/profile already exists: {dup.account_label}')
    p=BrokerProfile(user_id=owner_id,provider=payload.provider,account_label=payload.account_label.strip(),environment=payload.environment,external_account_ref=ref,live_execution_enabled=False,is_active=False);db.add(p);db.flush();return p

def _save_creds(p,api_key=None,api_secret=None,credentials=None):
    if p.provider=='BYBIT':p.api_key_encrypted=encrypt_secret((api_key or '').strip());p.api_secret_encrypted=encrypt_secret((api_secret or '').strip());p.credential_blob_encrypted=None
    elif p.provider=='TWELVE_DATA':p.api_key_encrypted=encrypt_secret((api_key or '').strip());p.api_secret_encrypted=None;p.credential_blob_encrypted=None
    else:
        vals=_generic(p.provider,credentials or {});p.credential_blob_encrypted=encrypt_secret(json.dumps(vals,separators=(',',':')));p.api_key_encrypted=p.api_secret_encrypted=None
    p.credentials_configured=True;p.last_connection_status='NOT_TESTED'

async def _probe(p):
    if p.provider=='BYBIT':await _bybit_client(p).wallet();return 'CONNECTED','Bybit authenticated successfully.'
    if p.provider=='TWELVE_DATA':
        s=get_settings();await TwelveDataFxMarketData(s.fx_market_data_base_url,decrypt_secret(p.api_key_encrypted or ''),s.market_data_timeout_seconds).get_quote('EURUSD');return 'CONNECTED','Twelve Data authenticated successfully.'
    if p.provider=='MT5':
        data=await _mt5_client(p).account();p.equity_usd=float(data.get('equity') or 0);p.wallet_balance_usd=float(data.get('balance') or 0);p.available_balance_usd=float(data.get('margin_free') or 0);return 'CONNECTED','MT5 terminal and broker account connected.'
    if p.provider=='IBKR':return 'NOT_READY','IBKR adapter is not connected yet.'
    raise ValueError('unsupported provider')

@router.get('',response_model=list[BrokerProfilePublic])
def list_accounts(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    q=select(BrokerProfile).where(BrokerProfile.provider!='ATLAS_PAPER').order_by(BrokerProfile.provider,BrokerProfile.environment,BrokerProfile.created_at.desc());q=q if _is_admin(user) else q.where(BrokerProfile.user_id==user.id);return list(db.scalars(q).all())

@router.get('/capabilities')
def capabilities(user:User=Depends(get_current_user)):
    s=get_settings();return {'providers':{k:sorted(v) for k,v in PROVIDER_ENVIRONMENTS.items()},'trading_providers':sorted(TRADING_PROVIDERS),'market_data_only':['TWELVE_DATA'],'credential_fields':{'BYBIT':['api_key','api_secret'],'TWELVE_DATA':['api_key'],'MT5':['login','password','server','bridge_url','bridge_token'],'IBKR':['account_id','host','port','client_id']},'allow_live_trading':bool(s.allow_live_trading),'can_manage_live':_is_admin(user),'account_modes':{'simulation':sorted(SIMULATION_ENVIRONMENTS),'live_money':['LIVE']},'external_accounts_only':True,'preflight_validation':True}

@router.post('/validate',response_model=BrokerValidationResult)
async def validate_account(payload:BrokerValidateRequest,user:User=Depends(get_current_user)):
    try:return await _validate_raw(payload)
    except HTTPException:raise
    except Exception as exc:raise HTTPException(400,f'{payload.provider} validation failed: {str(exc)[:300]}') from exc

@router.post('/connect',response_model=BrokerConnectResult,status_code=status.HTTP_201_CREATED)
async def connect_account(payload:BrokerConnectRequest,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    validation=await _validate_raw(BrokerValidateRequest(provider=payload.provider,environment=payload.environment,external_account_ref=payload.external_account_ref,api_key=payload.api_key,api_secret=payload.api_secret,credentials=payload.credentials))
    if not validation.valid:raise HTTPException(409,validation.message)
    p=_new_profile(db,user,payload,validation.detected_account_ref)
    try:_save_creds(p,payload.api_key,payload.api_secret,payload.credentials)
    except Exception:db.rollback();raise
    now=datetime.now(timezone.utc);p.last_connection_status='CONNECTED';p.last_connection_test_at=now
    if validation.details.get('equity') is not None:p.equity_usd=float(validation.details.get('equity') or 0)
    if validation.details.get('wallet_balance') is not None:p.wallet_balance_usd=float(validation.details.get('wallet_balance') or 0)
    if validation.details.get('available_balance') is not None:p.available_balance_usd=float(validation.details.get('available_balance') or 0)
    if payload.provider=='MT5':p.wallet_balance_usd=float(validation.details.get('balance') or 0);p.equity_usd=float(validation.details.get('equity') or 0);p.available_balance_usd=float(validation.details.get('margin_free') or 0)
    if payload.activate:db.execute(update(BrokerProfile).where(BrokerProfile.user_id==p.user_id,BrokerProfile.provider==p.provider,BrokerProfile.id!=p.id).values(is_active=False));p.is_active=True
    db.commit();db.refresh(p);warning_text=' '.join(validation.warnings);return BrokerConnectResult(profile=p,connected=True,message=(validation.message+(f' {warning_text}' if warning_text else '')),next_action=None)

@router.post('',response_model=BrokerProfilePublic,status_code=status.HTTP_201_CREATED)
def create_account(payload:BrokerProfileCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    p=_new_profile(db,user,payload);db.commit();db.refresh(p);return p

@router.put('/{profile_id}/credentials',response_model=BrokerProfilePublic)
def save_credentials(profile_id:uuid.UUID,payload:BrokerCredentialsUpdate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    p=_authorized_profile(db,user,profile_id);_save_creds(p,payload.api_key,payload.api_secret,payload.credentials);db.commit();db.refresh(p);return p

@router.post('/{profile_id}/activate',response_model=BrokerProfilePublic)
def activate(profile_id:uuid.UUID,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    p=_authorized_profile(db,user,profile_id)
    if p.last_connection_status!='CONNECTED':raise HTTPException(409,'only a successfully connected account can be made active')
    db.execute(update(BrokerProfile).where(BrokerProfile.user_id==p.user_id,BrokerProfile.provider==p.provider).values(is_active=False));p.is_active=True;db.commit();db.refresh(p);return p

@router.put('/{profile_id}/live-execution',response_model=BrokerProfilePublic)
def live_execution(profile_id:uuid.UUID,payload:LiveExecutionUpdate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if not _is_admin(user):raise HTTPException(403,'ADMIN role required')
    p=_authorized_profile(db,user,profile_id)
    if p.provider not in TRADING_PROVIDERS:raise HTTPException(400,'this provider is market data only')
    if p.environment!='LIVE':raise HTTPException(400,'live-money execution can only be changed for live-money accounts')
    if payload.enabled and not get_settings().allow_live_trading:raise HTTPException(409,'global live-money trading permission is disabled')
    if payload.enabled and (not p.credentials_configured or p.last_connection_status!='CONNECTED'):raise HTTPException(409,'test and connect the account before enabling live-money execution')
    p.live_execution_enabled=payload.enabled;p.live_execution_armed_at=datetime.now(timezone.utc) if payload.enabled else None;db.commit();db.refresh(p);return p

@router.post('/{profile_id}/test',response_model=BrokerProfilePublic)
async def test_connection(profile_id:uuid.UUID,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    p=_authorized_profile(db,user,profile_id);now=datetime.now(timezone.utc)
    try:p.last_connection_status,_=await _probe(p)
    except Exception as exc:p.last_connection_status='FAILED';p.last_connection_test_at=now;db.commit();raise HTTPException(502,f'{p.provider} connection failed: {str(exc)[:240]}') from exc
    p.last_connection_test_at=now;db.commit();db.refresh(p);return p

@router.post('/{profile_id}/sync',response_model=BrokerProfilePublic)
async def sync_account(profile_id:uuid.UUID,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    p=_authorized_profile(db,user,profile_id)
    try:
        if p.provider=='BYBIT':
            wallet=await _bybit_client(p).wallet();row=(wallet.get('list') or [{}])[0];p.equity_usd=float(row.get('totalEquity') or 0);p.wallet_balance_usd=float(row.get('totalWalletBalance') or 0);p.available_balance_usd=float(row.get('totalAvailableBalance') or row.get('totalWalletBalance') or 0);pos=await _bybit_client(p).positions();p.open_positions_count=sum(1 for x in (pos.get('list') or []) if float(x.get('size') or 0)!=0);orders=await _bybit_client(p).open_orders();p.open_orders_count=len(orders.get('list') or [])
        elif p.provider=='MT5':
            client=_mt5_client(p);a=await client.account();p.equity_usd=float(a.get('equity') or 0);p.wallet_balance_usd=float(a.get('balance') or 0);p.available_balance_usd=float(a.get('margin_free') or 0);p.open_positions_count=len((await client.positions()).get('list') or []);p.open_orders_count=len((await client.orders()).get('list') or [])
        elif p.provider=='TWELVE_DATA':await _probe(p)
        else:raise HTTPException(409,'provider sync is not available yet')
        p.last_connection_status='CONNECTED';p.last_connection_test_at=datetime.now(timezone.utc);db.commit();db.refresh(p);return p
    except HTTPException:raise
    except Exception as exc:p.last_connection_status='FAILED';db.commit();raise HTTPException(502,f'{p.provider} sync failed: {str(exc)[:240]}') from exc
