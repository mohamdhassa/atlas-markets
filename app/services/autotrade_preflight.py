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

def _readiness_reason(row: dict) -> str:
    blockers=row.get('blockers') or []
    if isinstance(blockers,str):
        blockers=[blockers] if blockers else []
    elif isinstance(blockers,dict):
        blockers=[k for k,v in blockers.items() if v]
    blockers=[str(x) for x in blockers if x]
    if blockers:
        return '|'.join(blockers)
    reason=row.get('reason') or row.get('signal_reason')
    if reason:
        return str(reason)
    return 'READINESS_BLOCKED'

async def autotrade_preflight(db,*,user_id,providers:set[str]|None=None,markets:set[str]|None=None)->dict:
    provider_filter={str(x).upper() for x in (providers or set())}
    market_filter={str(x).upper() for x in (markets or set())}
    readiness=await autotrade_readiness(db,user_id=user_id);settings=get_settings();configs={(x.market,x.symbol):x for x in db.scalars(select(SymbolStrategy).where(SymbolStrategy.user_id==user_id)).all()};profiles={p.id:p for p in db.scalars(select(BrokerProfile).where(BrokerProfile.user_id==user_id)).all()};items=[]
    for row in readiness['items']:
        row_provider=str(row.get('provider') or '').upper();row_market=str(row.get('market') or '').upper()
        if provider_filter and row_provider not in provider_filter:continue
        if market_filter and row_market not in market_filter:continue
        base={'market':row.get('market'),'symbol':row.get('symbol'),'provider':row.get('provider'),'readiness':row.get('readiness'),'execution':'NONE'}
        if row.get('readiness')!='PASS':items.append({**base,'preflight':'SKIP','reason':_readiness_reason(row),'readiness_blockers':row.get('blockers') or [],'readiness_reason':row.get('reason')});continue
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
                raw_quantity=proposed.get('shares') if proposed.get('shares') is not None else proposed.get('quantity')
                try:requested_quantity=float(raw_quantity or 0)
                except (TypeError,ValueError):requested_quantity=0.0
                if not math.isfinite(requested_quantity) or requested_quantity<=0:
                    items.append({**base,'preflight':'BLOCK','reason':'INVALID_IBKR_QUANTITY'});continue
                shares=min(math.floor(requested_quantity),IBKR_CERTIFIED_MAX_SHARES_PER_ORDER)
                if shares<=0:
                    items.append({**base,'preflight':'BLOCK','reason':'IBKR_QUANTITY_BELOW_ONE_SHARE'});continue
                c=_secret(profile);broker=IbkrBridgeClient(c.get('bridge_url') or 'http://host.docker.internal:8766',c.get('bridge_token'),settings.market_data_timeout_seconds);result=await broker.order_check({'symbol':row['symbol'],'side':proposed['side'],'quantity':shares,'order_type':'MKT','sec_type':'STK','exchange':'SMART','currency':'USD','account_id':c.get('account_id')});ok=bool(result.get('ok')) and bool(result.get('what_if')) and bool(result.get('simulation'))
            else:items.append({**base,'preflight':'BLOCK','reason':'PROVIDER_PREFLIGHT_NOT_SUPPORTED'});continue
            items.append({**base,'preflight':'PASS' if ok else 'BLOCK','reason':None if ok else 'BROKER_PREFLIGHT_REJECTED','request':{'side':proposed.get('side'),'notional':proposed.get('notional'),'shares':shares if profile.provider=='IBKR' else proposed.get('shares'),'strategy_requested_shares':proposed.get('strategy_requested_shares'),'sizing_policy':proposed.get('sizing_policy'),'volume':proposed.get('volume'),'stop_loss':proposed.get('stop_loss'),'take_profit':proposed.get('take_profit')},'broker_check':result})
        except Exception as exc:items.append({**base,'preflight':'BLOCK','reason':f'{type(exc).__name__}: {str(exc) or repr(exc)}'})
    return {'execution_enabled':False,'purpose':'BROKER_PREFLIGHT_NO_EXECUTION','scope':{'providers':sorted(provider_filter),'markets':sorted(market_filter)},'checked_count':sum(x.get('preflight') in {'PASS','BLOCK'} for x in items),'pass_count':sum(x.get('preflight')=='PASS' for x in items),'block_count':sum(x.get('preflight')=='BLOCK' for x in items),'skip_count':sum(x.get('preflight')=='SKIP' for x in items),'items':items}