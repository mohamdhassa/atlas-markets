from __future__ import annotations

import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.models.symbol_strategy import SymbolStrategy
from app.db.session import get_db
from app.market_data.bybit import BybitPublicMarketData

router=APIRouter(prefix='/markets',tags=['markets'])

def _canon(value:str)->str:return str(value or '').strip().upper().replace('/','').replace(' ','')
def _num(*values):
    for value in values:
        if value not in (None,''):
            try:return float(value)
            except (TypeError,ValueError):pass
    return None
def _is_admin(user:User)->bool:return getattr(user.role,'value',str(user.role))=='ADMIN'
def _profile(db:Session,user:User,provider:str)->BrokerProfile|None:
    q=select(BrokerProfile).where(BrokerProfile.provider==provider,BrokerProfile.is_enabled.is_(True))
    if not _is_admin(user):q=q.where(BrokerProfile.user_id==user.id)
    rows=list(db.scalars(q.order_by(BrokerProfile.is_active.desc(),BrokerProfile.updated_at.desc())).all())
    return next((p for p in rows if p.last_connection_status=='CONNECTED'),rows[0] if rows else None)
def _strategies(db:Session,user:User,provider:str,markets:set[str])->list[SymbolStrategy]:
    q=select(SymbolStrategy).join(BrokerProfile,BrokerProfile.id==SymbolStrategy.profile_id).where(BrokerProfile.provider==provider,SymbolStrategy.enabled.is_(True),SymbolStrategy.market.in_(sorted(markets)))
    if not _is_admin(user):q=q.where(SymbolStrategy.user_id==user.id)
    return list(db.scalars(q.order_by(SymbolStrategy.market,SymbolStrategy.symbol)).all())
def _payload(provider,markets,rows,errors):return {'provider':provider,'markets':sorted(markets),'symbols':rows,'count':len(rows),'errors':errors}

@router.get('/workspace-quotes')
async def workspace_quotes(provider:str=Query(pattern='^(IBKR|BYBIT|MT5)$'),markets:str=Query(min_length=2,max_length=128),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    provider=provider.upper();allowed={'FX','STOCK','ETF','CRYPTO','METAL','COMMODITY'};market_set={x.strip().upper() for x in markets.split(',') if x.strip()} & allowed
    if not market_set:return _payload(provider,market_set,[],[{'error':'NO_SUPPORTED_MARKETS_REQUESTED'}])
    strategies=_strategies(db,user,provider,market_set);symbols=list(dict.fromkeys(_canon(x.symbol) for x in strategies));rows=[];errors=[];settings=get_settings()
    if not strategies:return _payload(provider,market_set,[],[{'error':'NO_CONFIGURED_SYMBOLS'}])
    if provider=='BYBIT':
        try:
            snap=await BybitPublicMarketData(settings.bybit_public_base_url,settings.market_data_timeout_seconds).get_tickers(category='linear',symbols=tuple(symbols));by_symbol={x.symbol:x for x in snap.tickers}
            for cfg in strategies:
                t=by_symbol.get(_canon(cfg.symbol))
                if not t:errors.append({'symbol':cfg.symbol,'error':'QUOTE_UNAVAILABLE'});continue
                price=float(t.last_price);change_pct=_num(t.change_24h_pct) or 0.0;prev=price/(1+change_pct/100) if change_pct!=-100 else price
                rows.append({'market':cfg.market,'symbol':cfg.symbol,'display_symbol':cfg.symbol,'price':price,'bid':t.bid_price,'ask':t.ask_price,'change':price-prev,'change_percent':change_pct,'provider':'BYBIT','mode':cfg.mode,'timeframe':cfg.timeframe})
        except Exception as exc:errors.append({'error':f'BYBIT_DATA_ERROR: {str(exc)[:180]}'})
        return _payload(provider,market_set,rows,errors)
    p=_profile(db,user,provider)
    if not p or not p.credential_blob_encrypted:return _payload(provider,market_set,[],[{'error':f'{provider}_CONNECTED_PROFILE_UNAVAILABLE'}])
    try:creds=json.loads(decrypt_secret(p.credential_blob_encrypted))
    except Exception as exc:return _payload(provider,market_set,[],[{'error':f'{provider}_CREDENTIAL_READ_ERROR: {str(exc)[:160]}'}])
    if provider=='IBKR':
        broker=IbkrBridgeClient(creds.get('bridge_url') or 'http://host.docker.internal:8766',creds.get('bridge_token'),settings.market_data_timeout_seconds)
        for cfg in strategies:
            symbol=_canon(cfg.symbol)
            try:
                q=await broker.quote(symbol);price=_num(q.get('last'),q.get('last_price'),q.get('market_price'),q.get('price'),q.get('close'),q.get('bid'),q.get('ask'));bid=_num(q.get('bid'),q.get('bid_price'));ask=_num(q.get('ask'),q.get('ask_price'))
                candles=(await broker.candles(symbol,'1d',2)).get('list',[]);prev=_num(candles[-2].get('close')) if len(candles)>1 else price;change=(price-prev) if price is not None and prev is not None else 0.0;pct=(change/prev*100) if prev else 0.0
                if price is None:raise RuntimeError('NO_USABLE_IBKR_QUOTE_PRICE')
                rows.append({'market':cfg.market,'symbol':cfg.symbol,'display_symbol':cfg.symbol,'price':price,'bid':bid,'ask':ask,'change':change,'change_percent':pct,'provider':'IBKR','mode':cfg.mode,'timeframe':cfg.timeframe})
            except Exception as exc:errors.append({'symbol':cfg.symbol,'error':str(exc)[:180]})
        return _payload(provider,market_set,rows,errors)
    broker=Mt5BridgeClient(creds.get('bridge_url') or 'http://host.docker.internal:8765',creds.get('bridge_token'),settings.market_data_timeout_seconds)
    for cfg in strategies:
        symbol=_canon(cfg.symbol)
        try:
            info=await broker.symbol(symbol);bid=_num(info.get('bid'));ask=_num(info.get('ask'));price=((bid+ask)/2) if bid is not None and ask is not None else (bid if bid is not None else ask)
            candles=(await broker.candles(symbol,'1d',2)).get('list',[]);prev=_num(candles[-2].get('close')) if len(candles)>1 else price;change=(price-prev) if price is not None and prev is not None else 0.0;pct=(change/prev*100) if prev else 0.0
            if price is None:raise RuntimeError('NO_USABLE_MT5_QUOTE_PRICE')
            rows.append({'market':cfg.market,'symbol':cfg.symbol,'display_symbol':cfg.symbol,'price':price,'bid':bid,'ask':ask,'change':change,'change_percent':pct,'provider':'MT5_FUSION','mode':cfg.mode,'timeframe':cfg.timeframe})
        except Exception as exc:errors.append({'symbol':cfg.symbol,'error':str(exc)[:180]})
    return _payload(provider,market_set,rows,errors)
