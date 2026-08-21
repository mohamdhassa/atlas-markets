from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.db.models.auth import User
from app.db.models.historical import HistoricalBacktestRun
from app.db.session import get_db
from app.services.historical_backtest import backtest_strategy
from app.services.historical_intelligence import db_candles,historical_probability,refresh_history

router=APIRouter(prefix="/historical",tags=["historical"])

def _admin(user:User):
    if user.role!="ADMIN":raise HTTPException(status_code=403,detail="admin role required")

@router.post("/refresh")
async def refresh(user:User=Depends(get_current_user)):
    _admin(user);return await refresh_history()

@router.get("/{market}/{symbol}/probability")
def probability(market:str,symbol:str,interval:str=Query("5m"),horizon:int=Query(6,ge=1,le=48),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    candles=db_candles(db,market,symbol,interval)
    result=historical_probability(candles,horizon=horizon)
    return {"market":market.upper(),"symbol":symbol.upper().replace("/",""),"interval":interval,"stored_candles":len(candles),**result}

@router.post("/{market}/{symbol}/backtest")
def backtest(market:str,symbol:str,interval:str=Query("5m"),horizon:int=Query(6,ge=1,le=48),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    _admin(user);candles=db_candles(db,market,symbol,interval);result=backtest_strategy(candles,market=market.upper(),interval=interval,horizon=horizon)
    run=HistoricalBacktestRun(market=market.upper(),symbol=symbol.upper().replace("/",""),interval=interval,sample_count=result["sample_count"],signals=result["signals"],wins=result["wins"],losses=result["losses"],win_rate=result["win_rate"],avg_return_pct=result["avg_return_pct"],max_drawdown_pct=result["max_drawdown_pct"]);db.add(run);db.commit()
    return {"market":market.upper(),"symbol":symbol.upper().replace("/",""),"interval":interval,**result}
