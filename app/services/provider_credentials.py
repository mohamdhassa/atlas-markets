from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.crypto import decrypt_secret
from app.db.models.broker import BrokerProfile

def active_provider_profile(db:Session,user_id,provider:str)->BrokerProfile|None:
    return db.scalar(select(BrokerProfile).where(BrokerProfile.user_id==user_id,BrokerProfile.provider==provider,BrokerProfile.is_enabled.is_(True),BrokerProfile.is_active.is_(True)).order_by(BrokerProfile.created_at.desc()))

def active_twelve_data_key(db:Session,user_id)->str|None:
    p=active_provider_profile(db,user_id,"TWELVE_DATA")
    if p and p.credentials_configured and p.api_key_encrypted:return decrypt_secret(p.api_key_encrypted)
    return None
