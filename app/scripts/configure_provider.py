from __future__ import annotations
import argparse,getpass,json
from sqlalchemy import select,update
from app.core.crypto import encrypt_secret
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.session import SessionLocal

SUPPORTED={"BYBIT":{"TESTNET","DEMO","LIVE"},"TWELVE_DATA":{"LIVE"},"MT5":{"DEMO","LIVE"}}

def prompt_secret(label:str)->str:
    value=getpass.getpass(f'{label}: ').strip()
    if not value:raise SystemExit(f'{label} is required')
    return value

def main():
    p=argparse.ArgumentParser(description='Configure an ATLAS provider profile securely without using the web UI.')
    p.add_argument('--provider',required=True,choices=sorted(SUPPORTED));p.add_argument('--environment',required=True);p.add_argument('--label',required=True);p.add_argument('--username',default='admin');p.add_argument('--account-ref',default='')
    args=p.parse_args();provider=args.provider.upper();env=args.environment.upper()
    if env not in SUPPORTED[provider]:raise SystemExit(f'{provider} supports: {", ".join(sorted(SUPPORTED[provider]))}')
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.username==args.username))
        if not user:raise SystemExit(f'user {args.username!r} not found')
        profile=db.scalar(select(BrokerProfile).where(BrokerProfile.user_id==user.id,BrokerProfile.provider==provider,BrokerProfile.environment==env,BrokerProfile.account_label==args.label))
        if profile is None:
            profile=BrokerProfile(user_id=user.id,provider=provider,environment=env,account_label=args.label,external_account_ref=args.account_ref or None,is_active=False,live_execution_enabled=False)
            db.add(profile);db.flush()
        if provider=='BYBIT':
            profile.api_key_encrypted=encrypt_secret(prompt_secret('Bybit API key'));profile.api_secret_encrypted=encrypt_secret(prompt_secret('Bybit API secret'));profile.credential_blob_encrypted=None
        elif provider=='TWELVE_DATA':
            profile.api_key_encrypted=encrypt_secret(prompt_secret('Twelve Data API key'));profile.api_secret_encrypted=None;profile.credential_blob_encrypted=None
        elif provider=='MT5':
            login=input('MT5 login: ').strip();server=input('MT5 server [FusionMarkets-Demo]: ').strip() or 'FusionMarkets-Demo';password=prompt_secret('MT5 password');bridge_url=input('Bridge URL [http://host.docker.internal:8765]: ').strip() or 'http://host.docker.internal:8765';bridge_token=getpass.getpass('Bridge token (optional): ').strip()
            if not login:raise SystemExit('MT5 login is required')
            profile.credential_blob_encrypted=encrypt_secret(json.dumps({'login':login,'password':password,'server':server,'bridge_url':bridge_url,'bridge_token':bridge_token},separators=(',',':')));profile.api_key_encrypted=profile.api_secret_encrypted=None
        profile.credentials_configured=True;profile.last_connection_status='NOT_TESTED'
        db.execute(update(BrokerProfile).where(BrokerProfile.user_id==user.id,BrokerProfile.provider==provider,BrokerProfile.id!=profile.id).values(is_active=False));profile.is_active=True
        db.commit();print(f'Configured {provider} {env}: {profile.account_label} ({profile.id})')

if __name__=='__main__':main()
