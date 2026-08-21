from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.models.reporting import DailyAccountReport
from app.db.session import get_db
from app.services.reporting import csv_text, date_series, generate_daily_reports

router=APIRouter(prefix="/reports",tags=["reports"])

def _allowed_profiles(db:Session,user:User):
    q=select(BrokerProfile).where(BrokerProfile.provider=="ATLAS_PAPER")
    if user.role!="ADMIN": q=q.where(BrokerProfile.user_id==user.id)
    return list(db.scalars(q).all())

@router.post("/generate")
def generate(user:User=Depends(get_current_user)):
    if user.role!="ADMIN": raise HTTPException(403,"admin role required")
    return {"generated":generate_daily_reports(),"date":datetime.now(timezone.utc).date()}

@router.get("/daily")
def daily(days:int=Query(30,ge=1,le=366),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    end=datetime.now(timezone.utc).date();start=end-timedelta(days=days-1);profiles=_allowed_profiles(db,user);ids=[p.id for p in profiles]
    if not ids:return {"start":start,"end":end,"accounts":[],"rows":[]}
    rows=list(db.scalars(select(DailyAccountReport).where(DailyAccountReport.profile_id.in_(ids),DailyAccountReport.report_date>=start,DailyAccountReport.report_date<=end)).all())
    # Ensure zero-trade days exist in the returned operational timeline.
    indexed={(r.profile_id,r.report_date):r for r in rows};out=[]
    for p in profiles:
        d=start
        while d<=end:
            r=indexed.get((p.id,d));out.append({"profile_id":p.id,"account_label":p.account_label,"date":d,"realized_pnl":float(r.realized_pnl) if r else 0.0,"closed_trades":r.closed_trades if r else 0,"wins":r.wins if r else 0,"losses":r.losses if r else 0,"signals":r.signals_count if r else 0,"approved":r.approved_count if r else 0});d+=timedelta(days=1)
    return {"start":start,"end":end,"accounts":[{"id":p.id,"label":p.account_label,"owner_user_id":p.user_id} for p in profiles],"rows":out}

@router.get("/overview")
def overview(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    data=daily(30,user,db);rows=data["rows"];return {"accounts":len(data["accounts"]),"days":30,"realized_pnl":sum(r["realized_pnl"] for r in rows),"closed_trades":sum(r["closed_trades"] for r in rows),"wins":sum(r["wins"] for r in rows),"losses":sum(r["losses"] for r in rows),"signals":sum(r["signals"] for r in rows),"approved":sum(r["approved"] for r in rows)}

@router.get("/export.csv",response_class=PlainTextResponse)
def export_csv(days:int=Query(30,ge=1,le=366),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    data=daily(days,user,db);rows=[{k:r[k] for k in ["profile_id","date","realized_pnl","closed_trades","wins","losses","signals","approved"]} for r in data["rows"]]
    return PlainTextResponse(csv_text(rows),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=atlas-markets-report.csv"})
