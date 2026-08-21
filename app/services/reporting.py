from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from io import StringIO
import csv
from sqlalchemy import select

from app.db.models.broker import BrokerProfile
from app.db.models.paper import PaperOrder, PaperPosition, PaperWallet
from app.db.models.reporting import DailyAccountReport
from app.db.models.signal import Signal
from app.db.session import SessionLocal


def _bounds(day: date):
    start=datetime.combine(day,time.min,tzinfo=timezone.utc);return start,start+timedelta(days=1)


def snapshot_account(db, profile: BrokerProfile, day: date) -> DailyAccountReport:
    start,end=_bounds(day)
    exits=list(db.scalars(select(PaperOrder).where(PaperOrder.profile_id==profile.id,PaperOrder.realized_pnl.is_not(None),PaperOrder.created_at>=start,PaperOrder.created_at<end)).all())
    signals=list(db.scalars(select(Signal).where(Signal.profile_id==profile.id,Signal.created_at>=start,Signal.created_at<end)).all())
    wallet=db.scalar(select(PaperWallet).where(PaperWallet.profile_id==profile.id))
    positions=list(db.scalars(select(PaperPosition).where(PaperPosition.profile_id==profile.id)).all())
    pnl=sum(float(x.realized_pnl or 0) for x in exits);ending=(float(wallet.cash_balance) if wallet else 0)+sum(float(p.entry_price*p.quantity) for p in positions)
    row=db.scalar(select(DailyAccountReport).where(DailyAccountReport.profile_id==profile.id,DailyAccountReport.report_date==day))
    if row is None: row=DailyAccountReport(profile_id=profile.id,report_date=day);db.add(row)
    row.realized_pnl=pnl;row.closed_trades=len(exits);row.wins=sum(1 for x in exits if float(x.realized_pnl or 0)>0);row.losses=sum(1 for x in exits if float(x.realized_pnl or 0)<0);row.signals_count=len(signals);row.approved_count=sum(1 for s in signals if s.risk_status=="APPROVED");row.ending_equity=ending;row.starting_equity=ending-pnl;row.generated_at=datetime.now(timezone.utc)
    return row


def generate_daily_reports(day: date | None = None) -> int:
    day=day or datetime.now(timezone.utc).date()
    with SessionLocal() as db:
        profiles=list(db.scalars(select(BrokerProfile).where(BrokerProfile.provider=="ATLAS_PAPER")).all())
        for p in profiles: snapshot_account(db,p,day)
        db.commit();return len(profiles)


def date_series(rows, start: date, end: date):
    index={(r.profile_id,r.report_date):r for r in rows};profiles=sorted({r.profile_id for r in rows},key=str);out=[];d=start
    while d<=end:
        for pid in profiles:
            r=index.get((pid,d));out.append({"profile_id":pid,"date":d,"realized_pnl":float(r.realized_pnl) if r else 0.0,"closed_trades":r.closed_trades if r else 0,"wins":r.wins if r else 0,"losses":r.losses if r else 0,"signals":r.signals_count if r else 0,"approved":r.approved_count if r else 0})
        d+=timedelta(days=1)
    return out


def csv_text(items: list[dict]) -> str:
    buf=StringIO();fields=["profile_id","date","realized_pnl","closed_trades","wins","losses","signals","approved"];w=csv.DictWriter(buf,fieldnames=fields);w.writeheader();w.writerows(items);return buf.getvalue()
