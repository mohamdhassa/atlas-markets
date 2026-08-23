from __future__ import annotations
import json,uuid
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy import select,update
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.brokers.bybit_private import BybitPrivateClient,BybitPrivateError
from app.core.config import get_settings
from app.core.crypto import decrypt_secret,encrypt_secret
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.models.paper import PaperWallet
from app.db.session import get_db
from app.market_data.fx import TwelveDataFxMarketData,FxMarketDataError
from app.schemas.broker_profile import BrokerCredentialsUpdate,BrokerProfileCreate,BrokerProfilePublic,LiveExecutionUpdate
router=APIRouter(prefix="/accounts",tags=["accounts"])
PROVIDER_ENVIRONMENTS={"ATLAS_PAPER":{"PAPER"},"BYBIT":{"DEMO","TESTNET","LIVE"},"MT5":{"DEMO","LIVE"},"IBKR":{"PAPER","LIVE"},"TWELVE_DATA":{"LIVE"}}
TRADING_PROVIDERS={"ATLAS_PAPER","BYBIT","MT5","IBKR"}
def _is_admin(user:User)->bool:return user.role=="ADMIN"
def _authorized_profile(db:Session,user:User,profile_id:uuid.UUID)->BrokerProfile:
 p=db.get(BrokerProfile,profile_id)
 if p is None:raise HTTPException(404,"account not found")
 if not _is_admin(user) and p.user_id!=user.id:raise HTTPException(403,"account access denied")
 return p
def _bybit_client(p:BrokerProfile)->BybitPrivateClient:
 if not p.credentials_configured or not p.api_key_encrypted or not p.api_secret_encrypted:raise HTTPException(400,"API credentials are not configured")
 s=get_settings();base=s.bybit_public_base_url if p.environment=="LIVE" else s.bybit_demo_base_url if p.environment=="DEMO" else s.bybit_testnet_base_url
 return BybitPrivateClient(decrypt_secret(p.api_key_encrypted),decrypt_secret(p.api_secret_encrypted),base,s.market_data_timeout_seconds)
def _generic(provider:str,values:dict)->dict:
 c={str(k):str(v).strip() for k,v in values.items() if str(v).strip()};required={"MT5":{"login","password","server"},"IBKR":{"account_id","host","port","client_id"}}.get(provider,set());missing=sorted(required-set(c))
 if missing:raise HTTPException(400,f"missing credentials: {', '.join(missing)}")
 return c
@router.get("",response_model=list[BrokerProfilePublic])
def list_accounts(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 q=select(BrokerProfile).order_by(BrokerProfile.provider,BrokerProfile.environment,BrokerProfile.created_at.desc());q=q if _is_admin(user) else q.where(BrokerProfile.user_id==user.id);return list(db.scalars(q).all())
@router.get("/capabilities")
def capabilities(user:User=Depends(get_current_user)):
 s=get_settings();return {"providers":{k:sorted(v) for k,v in PROVIDER_ENVIRONMENTS.items()},"trading_providers":sorted(TRADING_PROVIDERS),"credential_fields":{"BYBIT":["api_key","api_secret"],"TWELVE_DATA":["api_key"],"MT5":["login","password","server","bridge_url","bridge_token"],"IBKR":["account_id","host","port","client_id"],"ATLAS_PAPER":[]},"allow_live_trading":bool(s.allow_live_trading),"can_manage_live":_is_admin(user)}
@router.post("",response_model=BrokerProfilePublic,status_code=status.HTTP_201_CREATED)
def create_account(payload:BrokerProfileCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 owner_id=user.id
 if payload.owner_user_id is not None:
  if not _is_admin(user):raise HTTPException(403,"admin role required to assign another owner")
  owner=db.get(User,payload.owner_user_id)
  if owner is None:raise HTTPException(404,"owner user not found")
  owner_id=owner.id
 allowed=PROVIDER_ENVIRONMENTS.get(payload.provider)
 if allowed is None or payload.environment not in allowed:raise HTTPException(400,f"{payload.provider} does not support {payload.environment} environment")
 p=BrokerProfile(user_id=owner_id,provider=payload.provider,account_label=payload.account_label.strip(),environment=payload.environment,external_account_ref=(payload.external_account_ref or "").strip() or None,live_execution_enabled=False,is_active=False)
 if payload.provider=="ATLAS_PAPER":p.last_connection_status="CONNECTED";p.equity_usd=p.wallet_balance_usd=p.available_balance_usd=100000.0
 db.add(p);db.flush()
 if p.provider=="ATLAS_PAPER":db.add(PaperWallet(profile_id=p.id))
 if db.scalar(select(BrokerProfile).where(BrokerProfile.user_id==owner_id,BrokerProfile.provider==p.provider,BrokerProfile.id!=p.id,BrokerProfile.is_active.is_(True))) is None:p.is_active=True
 db.commit();db.refresh(p);return p
@router.put("/{profile_id}/credentials",response_model=BrokerProfilePublic)
def save_credentials(profile_id:uuid.UUID,payload:BrokerCredentialsUpdate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 p=_authorized_profile(db,user,profile_id)
 if p.provider=="ATLAS_PAPER":raise HTTPException(400,"ATLAS PAPER does not require credentials")
 if p.provider=="BYBIT":
  if not payload.api_key or not payload.api_secret:raise HTTPException(400,"BYBIT requires API key and API secret")
  p.api_key_encrypted=encrypt_secret(payload.api_key.strip());p.api_secret_encrypted=encrypt_secret(payload.api_secret.strip());p.credential_blob_encrypted=None
 elif p.provider=="TWELVE_DATA":
  if not payload.api_key:raise HTTPException(400,"TWELVE DATA requires API key")
  p.api_key_encrypted=encrypt_secret(payload.api_key.strip());p.api_secret_encrypted=None;p.credential_blob_encrypted=None
 else:
  vals=_generic(p.provider,payload.credentials or {});p.credential_blob_encrypted=encrypt_secret(json.dumps(vals,separators=(",",":")));p.api_key_encrypted=p.api_secret_encrypted=None
 p.credentials_configured=True;p.last_connection_status="NOT_TESTED";db.commit();db.refresh(p);return p
@router.post("/{profile_id}/activate",response_model=BrokerProfilePublic)
def activate(profile_id:uuid.UUID,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 p=_authorized_profile(db,user,profile_id);db.execute(update(BrokerProfile).where(BrokerProfile.user_id==p.user_id,BrokerProfile.provider==p.provider).values(is_active=False));p.is_active=True;db.commit();db.refresh(p);return p
@router.put("/{profile_id}/live-execution",response_model=BrokerProfilePublic)
def live_execution(profile_id:uuid.UUID,payload:LiveExecutionUpdate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 if not _is_admin(user):raise HTTPException(403,"ADMIN role required")
 p=_authorized_profile(db,user,profile_id)
 if p.provider not in TRADING_PROVIDERS:raise HTTPException(400,"this provider is market data only")
 if p.environment!="LIVE":raise HTTPException(400,"live execution can only be changed for LIVE accounts")
 if payload.enabled and not get_settings().allow_live_trading:raise HTTPException(409,"global ALLOW_LIVE_TRADING is false")
 if payload.enabled and (not p.credentials_configured or p.last_connection_status!="CONNECTED"):raise HTTPException(409,"test and connect the live account before enabling live execution")
 p.live_execution_enabled=payload.enabled;p.live_execution_armed_at=datetime.now(timezone.utc) if payload.enabled else None;db.commit();db.refresh(p);return p
@router.post("/{profile_id}/test",response_model=BrokerProfilePublic)
async def test_connection(profile_id:uuid.UUID,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 p=_authorized_profile(db,user,profile_id);now=datetime.now(timezone.utc)
 try:
  if p.provider=="ATLAS_PAPER":p.last_connection_status="CONNECTED"
  elif p.provider=="BYBIT":await _bybit_client(p).wallet();p.last_connection_status="CONNECTED"
  elif p.provider=="TWELVE_DATA":
   if not p.api_key_encrypted:raise ValueError("API key is not configured")
   s=get_settings();await TwelveDataFxMarketData(s.fx_market_data_base_url,decrypt_secret(p.api_key_encrypted),s.market_data_timeout_seconds).get_quote("EURUSD");p.last_connection_status="CONNECTED"
  elif p.provider=="MT5":
   if not p.credentials_configured:raise ValueError("credentials are not configured")
   creds=json.loads(decrypt_secret(p.credential_blob_encrypted or ""));p.last_connection_status="BRIDGE_READY" if creds.get("bridge_url") else "CONFIGURED"
  else:
   if not p.credentials_configured:raise ValueError("credentials are not configured")
   p.last_connection_status="CONFIGURED"
 except Exception as exc:
  p.last_connection_status="FAILED";p.last_connection_test_at=now;db.commit();raise HTTPException(502,f"connection failed: {str(exc)[:180]}") from exc
 p.last_connection_test_at=now;db.commit();db.refresh(p);return p
@router.post("/{profile_id}/sync",response_model=BrokerProfilePublic)
async def sync_account(profile_id:uuid.UUID,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 p=_authorized_profile(db,user,profile_id)
 if p.provider=="ATLAS_PAPER":
  w=db.scalar(select(PaperWallet).where(PaperWallet.profile_id==p.id));bal=w.cash_balance if w else 100000.0;p.equity_usd=p.wallet_balance_usd=p.available_balance_usd=bal;p.last_connection_status="CONNECTED"
 elif p.provider=="BYBIT":
  c=_bybit_client(p);wallet,positions,orders=await c.wallet(),await c.positions(),await c.open_orders();a=(wallet.get("list") or [{}])[0];p.equity_usd=float(a.get("totalEquity") or 0);p.wallet_balance_usd=float(a.get("totalWalletBalance") or 0);p.available_balance_usd=float(a.get("totalAvailableBalance") or 0);p.open_positions_count=sum(1 for x in positions.get("list",[]) if float(x.get("size") or 0)!=0);p.open_orders_count=len(orders.get("list",[]));p.last_connection_status="CONNECTED"
 elif p.provider=="TWELVE_DATA":
  await test_connection(profile_id,user,db);p=db.get(BrokerProfile,profile_id)
 elif p.provider=="MT5":raise HTTPException(501,"MT5 account is configured; install/connect the ATLAS MT5 Bridge on the machine running MetaTrader 5 to enable balance/order sync")
 else:raise HTTPException(501,f"{p.provider} sync adapter is not connected yet")
 p.last_sync_at=datetime.now(timezone.utc);db.commit();db.refresh(p);return p
@router.patch("/{profile_id}/toggle",response_model=BrokerProfilePublic)
def toggle(profile_id:uuid.UUID,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 p=_authorized_profile(db,user,profile_id);p.is_enabled=not p.is_enabled
 if not p.is_enabled:p.live_execution_enabled=False;p.live_execution_armed_at=None
 db.commit();db.refresh(p);return p
