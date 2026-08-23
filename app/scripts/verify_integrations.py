from __future__ import annotations
import asyncio, json
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

async def verify():
    db=SessionLocal(); out=[]
    try:
        profiles=list(db.scalars(select(BrokerProfile).where(BrokerProfile.provider.in_(['BYBIT','TWELVE_DATA','MT5']))).all())
        for p in profiles:
            try:
                if p.provider=='BYBIT':
                    env,result=await detect_bybit(p); p.environment=env; p.last_connection_status='CONNECTED'; out.append(f'BYBIT {env}: CONNECTED')
                elif p.provider=='TWELVE_DATA':
                    s=get_settings(); key=decrypt_secret(p.api_key_encrypted or ''); q=await TwelveDataFxMarketData(s.fx_market_data_base_url,key,s.market_data_timeout_seconds).get_quote('EURUSD'); p.last_connection_status='CONNECTED'; out.append('TWELVE_DATA: CONNECTED')
                elif p.provider=='MT5':
                    creds=json.loads(decrypt_secret(p.credential_blob_encrypted or '')) if p.credential_blob_encrypted else {}; bridge=creds.get('bridge_url'); p.last_connection_status='BRIDGE_READY' if bridge else 'CONFIGURED'; out.append(f'MT5: {p.last_connection_status}')
            except Exception as exc:
                p.last_connection_status='FAILED'; out.append(f'{p.provider}: FAILED - {exc}')
        db.commit()
    finally: db.close()
    print('\n'.join(out) if out else 'No provider profiles found')

if __name__=='__main__': asyncio.run(verify())
