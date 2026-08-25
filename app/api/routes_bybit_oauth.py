from __future__ import annotations

import base64
import hashlib
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.routes_accounts import _new_profile, _save_creds
from app.brokers.bybit_private import BybitPrivateClient
from app.core.config import get_settings
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.session import get_db
from app.schemas.broker_profile import BrokerProfileCreate

router = APIRouter(prefix="/bybit/oauth", tags=["bybit-oauth"])
CLIENT_ID = "ai-agent"
TESTNET_AUTHORIZE = "https://testnet.bybit.com/oauth"
TESTNET_OAUTH_BASE = "https://api2-testnet.bybit.com"
TESTNET_TRADING_BASE = "https://api-testnet.bybit.com"
SESSION_TTL = 600
_sessions: dict[str, dict[str, Any]] = {}

def _b64url(raw: bytes) -> str:return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
def _cleanup():
    now=time.time()
    for key in [k for k,v in _sessions.items() if now-v['created_at']>SESSION_TTL]:_sessions.pop(key,None)
def _session(session_id:str,user:User|None=None):
    _cleanup();s=_sessions.get(session_id)
    if not s:raise HTTPException(404,'OAuth session expired or not found; start authorization again')
    if user is not None and str(user.id)!=s['user_id']:raise HTTPException(403,'OAuth session belongs to another user')
    return s
class OAuthStart(BaseModel):account_label:str='Bybit Testnet'
class OAuthManualCode(BaseModel):
    session_id:str
    authorization_code:str
class OAuthSelect(BaseModel):
    session_id:str
    sub_member_id:str|None=None
    create_new:bool=False
    activate:bool=True

async def _exchange_code(s:dict[str,Any],code:str):
    code=(code or '').strip()
    if not code:raise HTTPException(400,'Authorization code is required')
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response=await client.post(f'{TESTNET_OAUTH_BASE}/oauth/v1/public/access_token',data={'client_id':CLIENT_ID,'code':code,'code_verifier':s['code_verifier']})
            data=response.json()
        ret=data.get('retCode',data.get('ret_code')) if isinstance(data,dict) else None
        if ret is not None and ret!=0:raise RuntimeError(f"Bybit OAuth {ret}: {data.get('retMsg',data.get('ret_msg','token exchange failed'))}")
        token=(data.get('result') or data) if isinstance(data,dict) else {}
        if not token.get('access_token'):raise RuntimeError('Bybit OAuth response did not contain an access token')
        s['access_token']=token['access_token'];s['refresh_token']=token.get('refresh_token');s['status']='AUTHORIZED';s.pop('code_verifier',None);return token
    except HTTPException:raise
    except Exception as exc:
        s['status']='FAILED';s['error']=str(exc)[:300];raise HTTPException(502,str(exc)[:300])

@router.post('/start')
def start_oauth(payload:OAuthStart,user:User=Depends(get_current_user)):
    _cleanup();session_id=secrets.token_urlsafe(24);state=secrets.token_urlsafe(24);verifier=_b64url(secrets.token_bytes(32));challenge=_b64url(hashlib.sha256(verifier.encode('ascii')).digest())
    redirect_uri='http://127.0.0.1:8000/bybit/oauth/callback'
    params={'client_id':CLIENT_ID,'response_type':'code','scope':'ai-account','state':state,'redirect_uri':redirect_uri,'code_challenge':challenge,'code_challenge_method':'S256'}
    _sessions[session_id]={'created_at':time.time(),'user_id':str(user.id),'state':state,'code_verifier':verifier,'redirect_uri':redirect_uri,'account_label':payload.account_label.strip() or 'Bybit Testnet','status':'WAITING_FOR_AUTHORIZATION'}
    return {'environment':'TESTNET','session_id':session_id,'authorize_url':f'{TESTNET_AUTHORIZE}?{urlencode(params)}','expires_in':SESSION_TTL,'manual_code_supported':True,'message':'Open Bybit Testnet and authorize Agent Connect. For the cloud/manual path, paste the Access Token shown by Bybit directly into ATLAS.'}

@router.post('/manual-code')
async def manual_code(payload:OAuthManualCode,user:User=Depends(get_current_user)):
    s=_session(payload.session_id,user)
    if s.get('status') not in {'WAITING_FOR_AUTHORIZATION','FAILED'}:raise HTTPException(409,'OAuth session is not waiting for an access token')
    token=(payload.authorization_code or '').strip()
    if not token:raise HTTPException(400,'Bybit Agent Connect access token is required')
    # Cloud/headless Agent Connect: Bybit already displays the ACCESS TOKEN.
    # Per Bybit docs, use it directly as Bearer auth for ai_accounts; do not exchange it again.
    s['access_token']=token;s['refresh_token']=None;s['status']='AUTHORIZED';s.pop('code_verifier',None);s.pop('error',None)
    try:
        await _ai_accounts(s)
    except HTTPException:
        s['access_token']=None;s['status']='WAITING_FOR_AUTHORIZATION';raise
    return {'environment':'TESTNET','status':'AUTHORIZED','message':'Bybit access token accepted. Choose an existing AI sub-account; ATLAS will not auto-create one.'}

@router.get('/callback',response_class=HTMLResponse)
async def oauth_callback(code:str|None=Query(None),state:str|None=Query(None),error:str|None=Query(None)):
    _cleanup();match=next((s for s in _sessions.values() if secrets.compare_digest(s['state'],state or '')),None)
    if not match:return HTMLResponse('<h2>ATLAS authorization failed</h2><p>Invalid or expired OAuth state. Return to ATLAS and start again.</p>',status_code=403)
    if error or not code:
        match['status']='FAILED';match['error']=error or 'authorization_failed';return HTMLResponse('<h2>Bybit authorization was not completed</h2><p>You can close this tab and return to ATLAS.</p>',status_code=400)
    try:
        await _exchange_code(match,code)
        return HTMLResponse('<h2>Bybit Testnet authorized</h2><p>Return to ATLAS MARKETS to choose the AI sub-account. You can close this tab.</p>')
    except HTTPException as exc:return HTMLResponse(f'<h2>ATLAS authorization failed</h2><p>{str(exc.detail)[:240]}</p>',status_code=502)

async def _ai_accounts(s:dict[str,Any],query:str=''):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response=await client.get(f'{TESTNET_OAUTH_BASE}/oauth/v1/resource/restrict/ai_accounts{query}',headers={'Authorization':f"Bearer {s['access_token']}"})
        try:data=response.json()
        except ValueError:raise HTTPException(502,f'Bybit OAuth returned HTTP {response.status_code} with a non-JSON response')
    except HTTPException:raise
    except Exception as exc:raise HTTPException(502,f'Bybit OAuth request failed: {str(exc)[:240]}')
    ret=data.get('retCode',data.get('ret_code')) if isinstance(data,dict) else None
    if ret is not None and ret!=0:
        msg=data.get('retMsg',data.get('ret_msg','AI account request failed'))
        if ret==20039:raise HTTPException(409,'Bybit requires 2FA to be bound before Agent Connect can continue')
        raise HTTPException(502,f'Bybit OAuth {ret}: {msg}')
    return data.get('result',data) if isinstance(data,dict) else data
@router.get('/status/{session_id}')
async def oauth_status(session_id:str,user:User=Depends(get_current_user)):
    s=_session(session_id,user);result={'environment':'TESTNET','status':s['status']}
    if s['status']=='FAILED':result['error']=s.get('error')
    if s['status']=='AUTHORIZED':
        raw=await _ai_accounts(s);accounts=raw if isinstance(raw,list) else raw.get('accounts',[]) if isinstance(raw,dict) else []
        result['accounts']=[{'sub_member_id':str(a.get('sub_member_id')),'nickname':a.get('nickname') or 'AI sub-account'} for a in accounts];result['can_create']=len(accounts)<5;result['status']='SELECT_ACCOUNT'
    return result
@router.post('/select')
async def select_ai_account(payload:OAuthSelect,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    s=_session(payload.session_id,user)
    if s.get('status')!='AUTHORIZED':raise HTTPException(409,'OAuth authorization is not ready')
    if payload.create_new==bool(payload.sub_member_id):raise HTTPException(400,'Choose one existing AI sub-account or choose create new')
    query='?is_create=true' if payload.create_new else f'?sub_member_id={payload.sub_member_id}';acct=await _ai_accounts(s,query)
    if isinstance(acct,list):acct=acct[0] if len(acct)==1 else None
    if isinstance(acct,dict) and 'accounts' in acct:
        rows=acct.get('accounts') or [];acct=rows[0] if len(rows)==1 else None
    if not isinstance(acct,dict) or not acct.get('api_key') or not acct.get('api_secret'):raise HTTPException(502,'Bybit did not return API credentials for the selected AI sub-account')
    sub_id=str(acct.get('sub_member_id') or payload.sub_member_id or '').strip() or None
    client=BybitPrivateClient(acct['api_key'],acct['api_secret'],TESTNET_TRADING_BASE,get_settings().market_data_timeout_seconds);wallet=await client.wallet();wallet_row=(wallet.get('list') or [{}])[0]
    profile_payload=BrokerProfileCreate(account_label=s['account_label'],provider='BYBIT',environment='TESTNET',external_account_ref=sub_id);p=_new_profile(db,user,profile_payload,sub_id);_save_creds(p,acct['api_key'],acct['api_secret']);p.last_connection_status='CONNECTED';p.credentials_configured=True;p.equity_usd=float(wallet_row.get('totalEquity') or 0);p.wallet_balance_usd=float(wallet_row.get('totalWalletBalance') or 0);p.available_balance_usd=float(wallet_row.get('totalAvailableBalance') or 0)
    if payload.activate:db.execute(update(BrokerProfile).where(BrokerProfile.user_id==p.user_id,BrokerProfile.provider=='BYBIT',BrokerProfile.id!=p.id).values(is_active=False));p.is_active=True
    db.commit();db.refresh(p);_sessions.pop(payload.session_id,None)
    return {'connected':True,'environment':'TESTNET','profile_id':str(p.id),'account_label':p.account_label,'external_account_ref':p.external_account_ref,'equity':p.equity_usd,'message':'Bybit Testnet AI sub-account authorized, verified and connected to ATLAS.'}
