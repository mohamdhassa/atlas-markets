from __future__ import annotations
import asyncio, json
import httpx
from sqlalchemy import select
from app.brokers.bybit_private import BybitPrivateClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.broker import BrokerProfile
from app.db.session import SessionLocal
from app.market_data.fx import TwelveDataFxMarketData

async def detect_bybit(p: BrokerProfile):
    s=get_settings(); key=decrypt_secret(p.api_key_encrypted or ''); secret=decrypt_secret(p.api_secret_encrypted or '')
    candidates=[('TESTNET',s.bybit_testnet_base_url),('DEMO',s.bybit_demo_base_url),('LIVE',s.bybit_public_base_url)]
    errors={}
    for env,url in candidates:
        try:
            result=await BybitPrivateClient(key,secret,url,s.market_data_timeout_seconds).wallet()
            return env,result
        except Exception as exc: errors[env]=str(exc)
    raise RuntimeError('Bybit key failed in all environments: '+json.dumps(errors))

async def verify_mt5(p: BrokerProfile):
    if not p.credential_blob_encrypted:
        raise RuntimeError('MT5 credentials are not configured')
    creds=json.loads(decrypt_secret(p.credential_blob_encrypted))
    bridge=(creds.get('bridge_url') or '').rstrip('/')
    if not bridge:
        return 'CONFIGURED', None
    headers={}
    if creds.get('bridge_token'):
        headers['X-Atlas-Bridge-Token']=creds['bridge_token']
    async with httpx.AsyncClient(timeout=5.0) as client:
        h=await client.get(f'{bridge}/health',headers=headers); h.raise_for_status(); hp=h.json()
        if not hp.get('connected'):
            raise RuntimeError('MT5 bridge is reachable but terminal is not connected')
        a=await client.get(f'{bridge}/account',headers=headers); a.raise_for_status(); account=a.json()
    expected=str(creds.get('login') or '').strip()
    actual=str(account.get('login') or '').strip()
    if expected and actual and expected!=actual:
        raise RuntimeError(f'MT5 bridge account mismatch: expected {expected}, got {actual}')
    p.equity_usd=float(account.get('equity') or 0)
    p.wallet_balance_usd=float(account.get('balance') or 0)
    p.available_balance_usd=float(account.get('margin_free') or 0)
    return 'CONNECTED', account

async def verify():
    db=SessionLocal(); out=[]
    try:
        profiles=list(db.scalars(select(BrokerProfile).where(BrokerProfile.provider.in_(['BYBIT','TWELVE_DATA','MT5']))).all())
        for p in profiles:
            try:
                if p.provider=='BYBIT':
                    env,result=await detect_bybit(p); p.environment=env; p.last_connection_status='CONNECTED'; out.append(f'BYBIT {env}: CONNECTED')
                elif p.provider=='TWELVE_DATA':
                    s=get_settings(); key=decrypt_secret(p.api_key_encrypted or ''); await TwelveDataFxMarketData(s.fx_market_data_base_url,key,s.market_data_timeout_seconds).get_quote('EURUSD'); p.last_connection_status='CONNECTED'; out.append('TWELVE_DATA: CONNECTED')
                elif p.provider=='MT5':
                    status,account=await verify_mt5(p); p.last_connection_status=status; out.append(f'MT5 {p.environment}: {status}' + (f" login={account.get('login')} equity={account.get('equity')}" if account else ''))
            except Exception as exc:
                p.last_connection_status='FAILED'; out.append(f'{p.provider}: FAILED - {exc}')
        db.commit()
    finally: db.close()
    print('\n'.join(out) if out else 'No provider profiles found')

if __name__=='__main__': asyncio.run(verify())
