from __future__ import annotations
import uuid
from pydantic import BaseModel,Field
from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.models.signal import RiskProfile
from app.db.models.symbol_strategy import SymbolStrategy
from app.db.session import get_db
from app.services.instrument_universe import STARTER_UNIVERSE,build_universe,starter_symbols
from app.services.provider_routing import MARKETS,PROVIDER_MARKETS,normalize_market,normalize_symbol,provider_supports_market,providers_for_market,route_candidates,select_execution_route
router=APIRouter(prefix='/strategies/symbols',tags=['strategies'])
MODES={'WATCH','SIGNALS','AUTO_TRADE'}
class SymbolStrategyIn(BaseModel):
    profile_id:uuid.UUID;market:str='CRYPTO';symbol:str=Field(min_length=1,max_length=32);mode:str='WATCH';enabled:bool=True
    timeframe:str|None=None;minimum_signal_strength:float|None=Field(default=None,ge=0,le=100);risk_per_trade_pct:float|None=Field(default=None,gt=0,le=100);stop_atr_multiplier:float|None=Field(default=None,gt=0,le=20);take_profit_rr:float|None=Field(default=None,gt=0,le=20);max_position_notional_pct:float|None=Field(default=None,gt=0,le=100)
class SymbolStrategyPatch(BaseModel):
    mode:str|None=None;enabled:bool|None=None;timeframe:str|None=None;minimum_signal_strength:float|None=Field(default=None,ge=0,le=100);risk_per_trade_pct:float|None=Field(default=None,gt=0,le=100);stop_atr_multiplier:float|None=Field(default=None,gt=0,le=20);take_profit_rr:float|None=Field(default=None,gt=0,le=20);max_position_notional_pct:float|None=Field(default=None,gt=0,le=100)
class RouteRequest(BaseModel):
    market:str;symbol:str=Field(min_length=1,max_length=32)
class UniverseSeedRequest(BaseModel):
    markets:list[str]|None=None
    mode:str='WATCH'
def _admin(u):return u.role=='ADMIN'
def _profile(db,u,pid):
 p=db.get(BrokerProfile,pid)
 if not p or p.provider=='ATLAS_PAPER':raise HTTPException(404,'external trading account not found')
 if not _admin(u) and p.user_id!=u.id:raise HTTPException(403,'account access denied')
 return p
def _normalize_symbol(market,symbol):
 try:return normalize_symbol(market,symbol)
 except ValueError as exc:raise HTTPException(400,str(exc)) from exc
def _validate_provider_market(p,market):
 try:supported=provider_supports_market(p.provider,market)
 except ValueError as exc:raise HTTPException(400,str(exc)) from exc
 if not supported:
  allowed=PROVIDER_MARKETS.get(p.provider,set());text=', '.join(sorted(allowed)) if allowed else 'none'
  raise HTTPException(409,f'{p.provider} cannot be assigned to {market}. Supported markets for this trading account: {text}')
 if not p.is_enabled:raise HTTPException(409,'account is disabled')
def _validate(db,p,payload):
 market=payload.market.upper();mode=payload.mode.upper();symbol=_normalize_symbol(market,payload.symbol)
 if market not in MARKETS:raise HTTPException(400,'unsupported market')
 if mode not in MODES:raise HTTPException(400,'mode must be WATCH, SIGNALS or AUTO_TRADE')
 _validate_provider_market(p,market)
 risk=db.scalar(select(RiskProfile).where(RiskProfile.name=='Default'))
 if risk and payload.risk_per_trade_pct is not None and payload.risk_per_trade_pct>risk.risk_per_trade_pct:raise HTTPException(409,f'risk per trade exceeds Admin safety limit of {risk.risk_per_trade_pct}%')
 return market,mode,symbol
@router.get('/capabilities')
def symbol_capabilities(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 q=select(BrokerProfile).where(BrokerProfile.provider!='ATLAS_PAPER');q=q if _admin(user) else q.where(BrokerProfile.user_id==user.id)
 rows=list(db.scalars(q).all());return {'provider_markets':{k:sorted(v) for k,v in PROVIDER_MARKETS.items()},'accounts':[{'id':str(p.id),'provider':p.provider,'label':p.account_label,'markets':sorted(PROVIDER_MARKETS.get(p.provider,set())),'connected':p.last_connection_status=='CONNECTED','enabled':p.is_enabled,'active':p.is_active,'credentials_configured':p.credentials_configured} for p in rows if p.provider in PROVIDER_MARKETS]}
@router.get('/universe')
def instrument_universe(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 profiles=list(db.scalars(select(BrokerProfile).where(BrokerProfile.user_id==user.id,BrokerProfile.provider!='ATLAS_PAPER')).all())
 strategies=list(db.scalars(select(SymbolStrategy).where(SymbolStrategy.user_id==user.id)).all())
 items=build_universe(profiles,strategies)
 return {'starter_universe':{k:list(v) for k,v in STARTER_UNIVERSE.items()},'configured_count':sum(1 for x in items if x.configured),'routable_count':sum(1 for x in items if x.executable_route),'items':[x.__dict__ for x in items]}
@router.post('/universe/seed')
def seed_instrument_universe(payload:UniverseSeedRequest,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 mode=payload.mode.upper()
 if mode not in {'WATCH','SIGNALS'}:raise HTTPException(400,'bulk universe seed only allows WATCH or SIGNALS; promote symbols to AUTO_TRADE individually after validation')
 try:markets=[normalize_market(x) for x in payload.markets] if payload.markets else list(STARTER_UNIVERSE)
 except ValueError as exc:raise HTTPException(400,str(exc)) from exc
 profiles=list(db.scalars(select(BrokerProfile).where(BrokerProfile.user_id==user.id,BrokerProfile.provider!='ATLAS_PAPER')).all())
 existing={(x.market,x.symbol) for x in db.scalars(select(SymbolStrategy).where(SymbolStrategy.user_id==user.id)).all()}
 created=[];skipped=[]
 for market,symbol in starter_symbols(markets):
  if (market,symbol) in existing:skipped.append({'market':market,'symbol':symbol,'reason':'ALREADY_CONFIGURED'});continue
  selected=select_execution_route(market,profiles)
  if selected is None:skipped.append({'market':market,'symbol':symbol,'reason':'NO_EXECUTABLE_ROUTE'});continue
  p=next((x for x in profiles if str(x.id)==selected.profile_id),None)
  if p is None:skipped.append({'market':market,'symbol':symbol,'reason':'ROUTE_PROFILE_MISSING'});continue
  row=SymbolStrategy(user_id=user.id,profile_id=p.id,market=market,symbol=symbol,mode=mode,enabled=True);db.add(row);created.append({'market':market,'symbol':symbol,'profile_id':str(p.id),'provider':p.provider,'mode':mode});existing.add((market,symbol))
 db.commit();return {'mode':mode,'created_count':len(created),'skipped_count':len(skipped),'created':created,'skipped':skipped}
@router.post('/route')
def resolve_symbol_route(payload:RouteRequest,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 try:
  market=payload.market.upper();symbol=normalize_symbol(market,payload.symbol);supported=providers_for_market(market)
 except ValueError as exc:raise HTTPException(400,str(exc)) from exc
 q=select(BrokerProfile).where(BrokerProfile.provider.in_(supported));q=q if _admin(user) else q.where(BrokerProfile.user_id==user.id)
 profiles=list(db.scalars(q).all());candidates=route_candidates(market,profiles);selected=select_execution_route(market,profiles)
 return {'market':market,'symbol':symbol,'supported_providers':list(supported),'selected':selected.__dict__ if selected else None,'candidates':[{'profile_id':c.profile_id,'provider':c.provider,'label':c.label,'environment':c.environment,'connected':c.connected,'enabled':c.enabled,'active':c.active,'credentials_configured':c.credentials_configured,'executable':c.executable} for c in candidates]}
@router.get('')
def list_symbol_strategies(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 q=select(SymbolStrategy).order_by(SymbolStrategy.market,SymbolStrategy.symbol);q=q if _admin(user) else q.where(SymbolStrategy.user_id==user.id)
 return list(db.scalars(q).all())
@router.post('',status_code=status.HTTP_201_CREATED)
def create_symbol_strategy(payload:SymbolStrategyIn,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 p=_profile(db,user,payload.profile_id);market,mode,symbol=_validate(db,p,payload)
 if db.scalar(select(SymbolStrategy).where(SymbolStrategy.user_id==p.user_id,SymbolStrategy.profile_id==p.id,SymbolStrategy.market==market,SymbolStrategy.symbol==symbol)):raise HTTPException(409,'symbol already exists for this account')
 row=SymbolStrategy(user_id=p.user_id,profile_id=p.id,market=market,symbol=symbol,mode=mode,enabled=payload.enabled,timeframe=payload.timeframe,minimum_signal_strength=payload.minimum_signal_strength,risk_per_trade_pct=payload.risk_per_trade_pct,stop_atr_multiplier=payload.stop_atr_multiplier,take_profit_rr=payload.take_profit_rr,max_position_notional_pct=payload.max_position_notional_pct);db.add(row);db.commit();db.refresh(row);return row
@router.patch('/{row_id}')
def update_symbol_strategy(row_id:uuid.UUID,payload:SymbolStrategyPatch,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 row=db.get(SymbolStrategy,row_id)
 if not row:raise HTTPException(404,'symbol strategy not found')
 if not _admin(user) and row.user_id!=user.id:raise HTTPException(403,'strategy access denied')
 p=_profile(db,user,row.profile_id);_validate_provider_market(p,row.market)
 data=payload.model_dump(exclude_unset=True)
 if 'mode' in data:
  data['mode']=data['mode'].upper()
  if data['mode'] not in MODES:raise HTTPException(400,'invalid mode')
 risk=db.scalar(select(RiskProfile).where(RiskProfile.name=='Default'))
 if risk and data.get('risk_per_trade_pct') is not None and data['risk_per_trade_pct']>risk.risk_per_trade_pct:raise HTTPException(409,f'risk per trade exceeds Admin safety limit of {risk.risk_per_trade_pct}%')
 for k,v in data.items():setattr(row,k,v)
 row.symbol=_normalize_symbol(row.market,row.symbol);db.commit();db.refresh(row);return row
@router.delete('/{row_id}',status_code=status.HTTP_204_NO_CONTENT)
def delete_symbol_strategy(row_id:uuid.UUID,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 row=db.get(SymbolStrategy,row_id)
 if not row:raise HTTPException(404,'symbol strategy not found')
 if not _admin(user) and row.user_id!=user.id:raise HTTPException(403,'strategy access denied')
 db.delete(row);db.commit()
