from __future__ import annotations

import json
import math
from sqlalchemy import select

from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.broker import BrokerProfile
from app.db.models.symbol_strategy import SymbolStrategy
from app.services.autotrade_readiness import IBKR_CERTIFIED_MAX_SHARES_PER_ORDER, autotrade_readiness


def _secret(profile) -> dict:
    if not profile.credential_blob_encrypted: raise RuntimeError(f'{profile.provider} bridge configuration missing')
    return json.loads(decrypt_secret(profile.credential_blob_encrypted))

def _mt5_check_ok(result: dict) -> bool:
    payload=result.get('result') or {}
    try:retcode=int(payload.get('retcode'))
    except (TypeError,ValueError):return False
    return retcode in {0,10009}

async def autotrade_preflight(db,*,user_id)->dict:
    readiness=await autotrade_readiness(db,user_id=user_id);settings=get_settings();configs={(x.market,x.symbol):x for x in db.scalars(select(SymbolStrategy).where(SymbolStrategy.user_id==user_id)).all()};profiles={p.id:p for p in db.scalars(select(BrokerProfile).where(BrokerProfile.user_id==user_id)).all()};items=[]
    for row in readiness['items']:
        base={'market':row.get('market'),'symbol':row.get('symbol'),'provider':row.get('provider'),'readiness':row.get('readiness'),'execution':'NONE'}
        if row.get('readiness')!='PASS':items.append({**base,'preflight':'SKIP','reason':'READINESS_BLOCKED'});continue
        cfg=configs.get((row.get('market'),row.get('symbol')))
        if cfg is None:items.append({**base,'preflight':'BLOCK','reason':'STRATEGY_NOT_FOUND'});continue
        profile=profiles.get(cfg.profile_id)
        if profile is None:items.append({**base,'preflight':'BLOCK','reason':'PROFILE_NOT_FOUND'});continue
        proposed=row.get('proposed_order') or {}
        try:
            if profile.provider=='MT5':
                volume=float(proposed.get('volume') or 0)
                if volume<=0:raise RuntimeError('INVALID_MT5_VOLUME')
                c=_secret(profile);broker=Mt5BridgeClient(c.get('bridge_url') or 'http://host.docker.internal:8765',c.get('bridge_token'),settings.market_data_timeout_seconds);result=await broker.order_check({'symbol':row['symbol'],'side':proposed['side'],'volume':volume,'stop_loss':proposed.get('stop_loss'),'take_profit':proposed.get('take_profit'),'comment':'ATLAS PREFLIGHT'});ok=_mt5_check_ok(result)
            elif profile.provider=='IBKR':
                shares=int(proposed.get('shares') or math.floor(float(proposed.get('quantity') or 0)));shares=min(shares,IBKR_CERTIFIED_MAX_SHARES_PER_ORDER)
                if shares<=0:raise RuntimeError('INVALID_IBKR_QUANTITY')
                c=_secret(profile);broker=IbkrBridgeClient(c.get('bridge_url') or 'http://host.docker.internal:8766',c.get('bridge_token'),settings.market_data_timeout_seconds);result=await broker.order_check({'symbol':row['symbol'],'side':proposed['side'],'quantity':shares,'order_type':'MKT','sec_type':'STK','exchange':'SMART','currency':'USD','account_id':c.get('account_id')});ok=bool(result.get('ok')) and bool(result.get('what_if')) and bool(result.get('simulation'))
            else:items.append({**base,'preflight':'BLOCK','reason':'PROVIDER_PREFLIGHT_NOT_SUPPORTED'});continue
            items.append({**base,'preflight':'PASS' if ok else 'BLOCK','reason':None if ok else 'BROKER_PREFLIGHT_REJECTED','request':{'side':proposed.get('side'),'notional':proposed.get('notional'),'shares':shares if profile.provider=='IBKR' else proposed.get('shares'),'strategy_requested_shares':proposed.get('strategy_requested_shares'),'sizing_policy':proposed.get('sizing_policy'),'volume':proposed.get('volume'),'stop_loss':proposed.get('stop_loss'),'take_profit':proposed.get('take_profit')},'broker_check':result})
        except Exception as exc:items.append({**base,'preflight':'BLOCK','reason':f'{type(exc).__name__}: {str(exc) or repr(exc)}'})
    return {'execution_enabled':False,'purpose':'BROKER_PREFLIGHT_NO_EXECUTION','checked_count':sum(x.get('preflight') in {'PASS','BLOCK'} and x.get('reason')!='READINESS_BLOCKED' for x in items),'pass_count':sum(x.get('preflight')=='PASS' for x in items),'block_count':sum(x.get('preflight')=='BLOCK' for x in items),'items':items}
