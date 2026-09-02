from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.db.models.auth import User
from app.db.session import get_db
from app.services.position_lifecycle import evaluate_mt5_exit_signals, inspect_position_lifecycle

router = APIRouter(prefix='/automation/positions', tags=['automation'])


@router.get('/lifecycle')
async def lifecycle(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return await inspect_position_lifecycle(db, user_id=user.id)


@router.get('/mt5-exit-signals')
async def mt5_exit_signals(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return await evaluate_mt5_exit_signals(db, user_id=user.id)
