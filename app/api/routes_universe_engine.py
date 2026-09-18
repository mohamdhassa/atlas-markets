from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.models.strategy import SymbolStrategy
from app.db.session import get_db
from app.services.autotrade_preflight import autotrade_preflight
from app.services.autotrade_readiness import autotrade_readiness
from app.services.demo_execution_certification import certify_single_mt5_demo_order
from app.services.mt5_position_inspection import inspect_mt5_position
from app.services.universe_scanner import scan_user_universe
from app.services.instrument_universe import build_universe
from app.services.universe_seed import seed_validated_universe

router = APIRouter(prefix='/strategies/symbols', tags=['strategies'])


class ValidatedSeedRequest(BaseModel):
    markets: list[str] | None = None
    mode: str = 'SIGNALS'


class DemoCertificationRequest(BaseModel):
    market: str
    symbol: str


@router.post('/universe/seed-validated')
async def seed_validated(payload: ValidatedSeedRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profiles = list(db.scalars(select(BrokerProfile).where(BrokerProfile.user_id == user.id, BrokerProfile.provider != 'ATLAS_PAPER')).all())
    try:
        return await seed_validated_universe(db, user_id=user.id, profiles=profiles, markets=payload.markets, mode=payload.mode)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get('/universe/market-monitor')
async def market_monitor(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """One read-only ATLAS monitor: configured IBKR + configured/starter Bybit instruments."""
    profiles = list(db.scalars(select(BrokerProfile).where(BrokerProfile.user_id == user.id, BrokerProfile.provider.in_(['BYBIT','IBKR']))).all())
    strategies = list(db.scalars(select(SymbolStrategy).where(SymbolStrategy.user_id == user.id)).all())
    universe = build_universe(profiles=profiles, strategies=strategies, markets=['CRYPTO','STOCK','ETF'])
    configured = {(x.market, x.symbol): x for x in db.scalars(select(SymbolStrategy).where(SymbolStrategy.user_id == user.id, SymbolStrategy.enabled.is_(True))).all()}
    # Scan configured SIGNALS/WATCH rows with the existing preview engine. AUTO_TRADE decisions/gates come from readiness.
    preview = await scan_user_universe(db, user_id=user.id, include_watch=True)
    readiness = await autotrade_readiness(db, user_id=user.id)
    pmap = {(x.get('market'), x.get('symbol')): x for x in preview.get('items', [])}
    rmap = {(x.get('market'), x.get('symbol')): x for x in readiness.get('items', [])}
    items=[]
    for u in universe:
        if u.provider not in {'BYBIT','IBKR'}:
            continue
        key=(u.market,u.symbol);cfg=configured.get(key);r=rmap.get(key);p=pmap.get(key)
        analysis=r or p
        decision=(analysis or {}).get('decision') or 'HOLD'
        gate='NOT_CONFIGURED'
        gate_reasons=['RESEARCH_ONLY_NOT_CONFIGURED']
        if r:
            gate=r.get('readiness') or 'BLOCK'
            gate_reasons=r.get('blockers') or ([r.get('reason')] if r.get('reason') else [])
        elif cfg:
            gate='MONITOR_ONLY'
            gate_reasons=['MODE_'+str(cfg.mode)]
        items.append({
            'market':u.market,'symbol':u.symbol,'provider':u.provider,'environment':u.environment,
            'configured':bool(cfg),'mode':cfg.mode if cfg else 'RESEARCH','timeframe':(analysis or {}).get('timeframe') or '5m',
            'analysis_status':(analysis or {}).get('status') or ('SCANNED' if r else 'NOT_SCANNED'),
            'decision':decision,'classification':(analysis or {}).get('classification'),'strength':(analysis or {}).get('strength'),
            'signal_reason':(analysis or {}).get('signal_reason') or (analysis or {}).get('reason'),
            'execution_gate':gate,'gate_reasons':gate_reasons,
        })
    return {'execution_enabled':False,'purpose':'UNIFIED_BYBIT_IBKR_MARKET_MONITOR','providers':['BYBIT','IBKR'],'count':len(items),'items':items}

@router.get('/universe/scan-preview')
async def scan_preview(include_watch: bool = Query(False), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return await scan_user_universe(db, user_id=user.id, include_watch=include_watch)


@router.get('/universe/autotrade-readiness')
async def auto_trade_readiness(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Evaluate signals, broker exposure, risk gates and proposed sizing without placing orders."""
    return await autotrade_readiness(db, user_id=user.id)


@router.post('/universe/autotrade-preflight')
async def auto_trade_preflight(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Run broker-native validation for current PASS proposals without submitting any order."""
    return await autotrade_preflight(db, user_id=user.id)


@router.post('/universe/demo-certify-single')
async def demo_certify_single(payload: DemoCertificationRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Certification-only: submit one MT5 demo order after a fresh readiness and broker preflight cycle."""
    try:
        return await certify_single_mt5_demo_order(db, user_id=user.id, market=payload.market, symbol=payload.symbol)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get('/universe/mt5-position')
async def mt5_position(market: str, symbol: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the current MT5 position including broker-stored stop loss and take profit."""
    try:
        return await inspect_mt5_position(db, user_id=user.id, market=market, symbol=symbol)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
