from __future__ import annotations
import json,uuid
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy import select,update
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.brokers.bybit_private import BybitPrivateClient
from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret,encrypt_secret
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.models.paper import PaperWallet
from app.db.session import get_db
from app.market_data.fx import TwelveDataFxMarketData
from app.schemas.broker_profile import BrokerConnectRequest,BrokerConnectResult,BrokerCredentialsUpdate,BrokerProfileCreate,BrokerProfilePublic,LiveExecutionUpdate
router=APIRouter(prefix='/accounts',tags=['accounts'])
PROVIDER_ENVIRONMENTS={'ATLAS_PAPER':{'PAPER'},'BYBIT':{'DEMO','TESTNET','LIVE'},'MT5':{'DEMO','LIVE'},'IBKR':{'PAPER','LIVE'},'TWELVE_DATA':{'LIVE'}}
TRADING_PROVIDERS={'ATLAS_PAPER','BYBIT','MT5','IBKR'}
def _is_admin(u):return u.role=='ADMIN'
def _authorized_profile(db,u,pid):
 p=db.get(BrokerProfile,pid)
 if p is None:raise HTTPException(404,'account not found')
 if not _is_admin(u) and p.user_id!=u.id:raise HTTPException(403,'account access denied')
 return p
def _bybit_client(p):
 if not p.credentials_configured or not p.api_key_encrypted or not p.api_secret_encrypted:raise HTTPException(400,'API credentials are not configured')
 s=get_settings();base=s.bybit_public_base_url if p.environment=='LIVE' else s.bybit_demo_base_url if p.environment=='DEMO' else s.bybit_testnet_base_url
 return BybitPrivateClient(decrypt_secret(p.api_key_encrypted),decrypt_secret(p.api_secret_encrypted),base,s.market_data_timeout_seconds)
def _creds(p):
 if not p.credential_blob_encrypted:raise ValueError('credentials are not configured')
 return json.loads(decrypt_secret(p.credential_blob_encrypted))
def _mt5_client(p):
 c=_creds(p);url=c.get('bridge_url') or 'http://host.docker.internal:8765';return Mt5BridgeClient(url,c.get('bridge_token'),get_settings().market_data_timeout_seconds)
def _generic(provider,values):
 c={str(k):str(v).strip() for k,v in values.items() if str(v).strip()};required={'MT5':{'login','password','server'},'IBKR':{'account_id','host','port','client_id'}}.get(provider,set());missing=sorted(required-set(c))
 if missing:raise HTTPException(400,f"missing credentials: {', '.join(missing)}")
 return c
def _owner_id(db,user,requested):
 if requested is None:return user.id
 if not _is_admin(user):raise HTTPException(403,'admin role required to assign another owner')
 owner=db.get(User,requested)
 if owner is None:raise HTTPException(404,'owner user not found')
 return owner.id
def _new_profile(db,user,payload):
 owner_id=_owner_id(db,user,payload.owner_user_id);allowed=PROVIDER_ENVIRONMENTS.get(payload.provider)
 if allowed is None or payload.environment not in allowed:raise HTTPException(400,f'{payload.provider} does not support {payload.environment} environment')
 p=BrokerProfile(user_id=owner_id,provider=payload.provider,account_label=payload.account_label.strip(),environment=payload.environment,external_account_ref=(payload.external_account_ref or '').strip() or None,live_execution_enabled=False,is_active=False)
 if payload.provider=='ATLAS_PAPER':p.last_connection_status='CONNECTED';p.equity_usd=p.wallet_balance_usd=p.available_balance_usd=100000.0
 db.add(p);db.flush()
 if p.provider=='ATLAS_PAPER':db.add(PaperWallet(profile_id=p.id))
 if db.scalar(select(BrokerProfile).where(BrokerProfile.user_id==owner_id,BrokerProfile.provider==p.provider,BrokerProfile.id!=p.id,BrokerProfile.is_active.is_(True))) is None:p.is_active=True
 return p
def _save_creds(p,api_key=None,api_secret=None,credentials=None):
 if p.provider=='ATLAS_PAPER':return
 if p.provider=='BYBIT':
  if not api_key or not api_secret:raise HTTPException(400,'BYBIT requires API key and API secret')
  p.api_key_encrypted=encrypt_secret(api_key.strip());p.api_secret_encrypted=encrypt_secret(api_secret.strip());p.credential_blob_encrypted=None
 elif p.provider=='TWELVE_DATA':
  if not api_key:raise HTTPException(400,'TWELVE DATA requires API key')
  p.api_key_encrypted=encrypt_secret(api_key.strip());p.api_secret_encrypted=None;p.credential_blob_encrypted=None
 else:
  vals=_generic(p.provider,credentials or {});p.credential_blob_encrypted=encrypt_secret(json.dumps(vals,separators=(',',':')));p.api_key_encrypted=p.api_secret_encrypted=None
 p.credentials_configured=True;p.last_connection_status='NOT_TESTED'
async def _probe(p):
 if p.provider=='ATLAS_PAPER':return 'CONNECTED','ATLAS Paper is ready.'
 if p.provider=='BYBIT':await _bybit_client(p).wallet();return 'CONNECTED','Bybit authenticated successfully.'
 if p.provider=='TWELVE_DATA':
  if not p.api_key_encrypted:raise ValueError('API key is not configured')
  s=get_settings();await TwelveDataFxMarketData(s.fx_market_data_base_url,decrypt_secret(p.api_key_encrypted),s.market_data_timeout_seconds).get_quote('EURUSD');return 'CONNECTED','Twelve Data authenticated successfully.'
 if p.provider=='MT5':
  data=await _mt5_client(p).account();p.equity_usd=float(data.get('equity') or 0);p.wallet_balance_usd=float(data.get('balance') or 0);p.available_balance_usd=float(data.get('margin_free') or 0);return 'CONNECTED','MT5 terminal and broker account connected.'
 if p.provider=='IBKR':return 'CONFIGURED','IBKR settings saved. Start/authorize TWS or IB Gateway, then test again.'
 raise ValueError('unsupported provider')
@router.get('',response_model=list[BrokerProfilePublic])
def list_accounts(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 q=select(BrokerProfile).order_by(BrokerProfile.provider,BrokerProfile.environment,BrokerProfile.created_at.desc());q=q if _is_admin(user) else q.where(BrokerProfile.user_id==user.id);return list(db.scalars(q).all())
@router.get('/capabilities')
def capabilities(user:User=Depends(get_current_user)):
 s=get_settings();return {'providers':{k:sorted(v) for k,v in PROVIDER_ENVIRONMENTS.items()},'trading_providers':sorted(TRADING_PROVIDERS),'credential_fields':{'BYBIT':['api_key','api_secret'],'TWELVE_DATA':['api_key'],'MT5':['login','password','server','bridge_url','bridge_token'],'IBKR':['account_id','host','port','client_id'],'ATLAS_PAPER':[]},'allow_live_trading':bool(s.allow_live_trading),'can_manage_live':_is_admin(user)}
@router.post('/connect',response_model=BrokerConnectResult,status_code=status.HTTP_201_CREATED)
async def connect_account(payload:BrokerConnectRequest,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 p=_new_profile(db,user,payload)
 try:_save_creds(p,payload.api_key,payload.api_secret,payload.credentials)
 except Exception:db.rollback();raise
 now=datetime.now(timezone.utc)
 try:
  state,message=await _probe(p);p.last_connection_status=state;p.last_connection_test_at=now
  if payload.activate:
   db.execute(update(BrokerProfile).where(BrokerProfile.user_id==p.user_id,BrokerProfile.provider==p.provider,BrokerProfile.id!=p.id).values(is_active=False));p.is_active=True
  db.commit();db.refresh(p);return BrokerConnectResult(profile=p,connected=state=='CONNECTED',message=message,next_action=None if state=='CONNECTED' else message)
 except Exception as exc:
  p.last_connection_status='FAILED';p.last_connection_test_at=now;db.commit();db.refresh(p)
  detail=str(exc)[:240];return BrokerConnectResult(profile=p,connected=False,message=f'{p.provider} connection failed: {detail}',next_action=('Open MetaTrader 5 and verify the Fusion account is authenticated, then use Test connection.' if p.provider=='MT5' else 'Check the credentials/environment and try Test connection again.'))
@router.post('',response_model=BrokerProfilePublic,status_code=status.HTTP_201_CREATED)
def create_account(payload:BrokerProfileCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 p=_new_profile(db,user,payload);db.commit();db.refresh(p);return p
@router.put('/{profile_id}/credentials',response_model=BrokerProfilePublic)
def save_credentials(profile_id:uuid.UUID,payload:BrokerCredentialsUpdate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 p=_authorized_profile(db,user,profile_id)
 if p.provider=='ATLAS_PAPER':raise HTTPException(400,'ATLAS PAPER does not require credentials')
 _save_creds(p,payload.api_key,payload.api_secret,payload.credentials);db.commit();db.refresh(p);return p
@router.post('/{profile_id}/activate',response_model=BrokerProfilePublic)
def activate(profile_id:uuid.UUID,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 p=_authorized_profile(db,user,profile_id);db.execute(update(BrokerProfile).where(BrokerProfile.user_id==p.user_id,BrokerProfile.provider==p.provider).values(is_active=False));p.is_active=True;db.commit();db.refresh(p);return p
@router.put('/{profile_id}/live-execution',response_model=BrokerProfilePublic)
def live_execution(profile_id:uuid.UUID,payload:LiveExecutionUpdate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 if not _is_admin(user):raise HTTPException(403,'ADMIN role required')
 p=_authorized_profile(db,user,profile_id)
 if p.provider not in TRADING_PROVIDERS:raise HTTPException(400,'this provider is market data only')
 if p.environment!='LIVE':raise HTTPException(400,'live execution can only be changed for LIVE accounts')
 if payload.enabled and not get_settings().allow_live_trading:raise HTTPException(409,'global ALLOW_LIVE_TRADING is false')
 if payload.enabled and (not p.credentials_configured or p.last_connection_status!='CONNECTED'):raise HTTPException(409,'test and connect the live account before enabling live execution')
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
  if p.provider=='ATLAS_PAPER':
   w=db.scalar(select(PaperWallet).where(PaperWallet.profile_id==p.id));bal=w.cash_balance if w else 100000.0;p.equity_usd=p.wallet_balance_usd=p.available_balance_usd=bal;p.last_connection_status='CONNECTED'
  elif p.provider=='BYBIT':
   c=_bybit_client(p);wallet,positions,orders=await c.wallet(),await c.positions(),await c.open_orders();a=(wallet.get('list') or [{}])[0];p.equity_usd=float(a.get('totalEquity') or 0);p.wallet_balance_usd=float(a.get('totalWalletBalance') or 0);p.available_balance_usd=float(a.get('totalAvailableBalance') or 0);p.open_positions_count=sum(1 for x in positions.get('list',[]) if float(x.get('size') or 0)!=0);p.open_orders_count=len(orders.get('list',[]));p.last_connection_status='CONNECTED'
  elif p.provider=='TWELVE_DATA':p.last_connection_status,_=await _probe(p)
  elif p.provider=='MT5':
   c=_mt5_client(p);a,pos,orders=await c.account(),await c.positions(),await c.orders();p.equity_usd=float(a.get('equity') or 0);p.wallet_balance_usd=float(a.get('balance') or 0);p.available_balance_usd=float(a.get('margin_free') or 0);p.open_positions_count=len(pos.get('list',[]));p.open_orders_count=len(orders.get('list',[]));p.last_connection_status='CONNECTED'
  else:raise HTTPException(501,f'{p.provider} sync adapter is not connected yet')
 except HTTPException:raise
 except Exception as exc:p.last_connection_status='FAILED';db.commit();raise HTTPException(502,f'sync failed: {str(exc)[:240]}') from exc
 p.last_sync_at=datetime.now(timezone.utc);db.commit();db.refresh(p);return p
@router.patch('/{profile_id}/toggle',response_model=BrokerProfilePublic)
def toggle(profile_id:uuid.UUID,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 p=_authorized_profile(db,user,profile_id);p.is_enabled=not p.is_enabled
 if not p.is_enabled:p.live_execution_enabled=False;p.live_execution_armed_at=None
 db.commit();db.refresh(p);return p
