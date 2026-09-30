from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.models.reporting import DailyAccountReport
from app.db.session import get_db
from app.services.access_scope import scope_broker_profiles
from app.services.reporting import csv_text, generate_daily_reports

router = APIRouter(prefix="/reports", tags=["reports"])


def _allowed_profiles(
    db: Session,
    user: User,
    owner_user_id: uuid.UUID | None = None,
) -> list[BrokerProfile]:
    statement = select(BrokerProfile).where(BrokerProfile.provider == "ATLAS_PAPER")
    statement = scope_broker_profiles(statement, user, owner_user_id)
    return list(db.scalars(statement).all())


@router.post("/generate")
def generate(user: User = Depends(get_current_user)):
    if user.role != "ADMIN":
        raise HTTPException(403, "admin role required")
    return {"generated": generate_daily_reports(), "date": datetime.now(timezone.utc).date()}


@router.get("/daily")
def daily(
    days: int = Query(30, ge=1, le=366),
    owner_user_id: uuid.UUID | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days - 1)
    profiles = _allowed_profiles(db, user, owner_user_id)
    ids = [profile.id for profile in profiles]
    if not ids:
        return {"start": start, "end": end, "accounts": [], "rows": []}

    rows = list(
        db.scalars(
            select(DailyAccountReport).where(
                DailyAccountReport.profile_id.in_(ids),
                DailyAccountReport.report_date >= start,
                DailyAccountReport.report_date <= end,
            )
        ).all()
    )
    indexed = {(row.profile_id, row.report_date): row for row in rows}
    output = []
    for profile in profiles:
        report_date = start
        while report_date <= end:
            row = indexed.get((profile.id, report_date))
            output.append(
                {
                    "profile_id": profile.id,
                    "account_label": profile.account_label,
                    "date": report_date,
                    "realized_pnl": float(row.realized_pnl) if row else 0.0,
                    "closed_trades": row.closed_trades if row else 0,
                    "wins": row.wins if row else 0,
                    "losses": row.losses if row else 0,
                    "signals": row.signals_count if row else 0,
                    "approved": row.approved_count if row else 0,
                }
            )
            report_date += timedelta(days=1)
    return {
        "start": start,
        "end": end,
        "accounts": [
            {"id": profile.id, "label": profile.account_label, "owner_user_id": profile.user_id}
            for profile in profiles
        ],
        "rows": output,
    }


@router.get("/overview")
def overview(
    owner_user_id: uuid.UUID | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = daily(30, owner_user_id, user, db)
    rows = data["rows"]
    return {
        "accounts": len(data["accounts"]),
        "days": 30,
        "realized_pnl": sum(row["realized_pnl"] for row in rows),
        "closed_trades": sum(row["closed_trades"] for row in rows),
        "wins": sum(row["wins"] for row in rows),
        "losses": sum(row["losses"] for row in rows),
        "signals": sum(row["signals"] for row in rows),
        "approved": sum(row["approved"] for row in rows),
    }


@router.get("/export.csv", response_class=PlainTextResponse)
def export_csv(
    days: int = Query(30, ge=1, le=366),
    owner_user_id: uuid.UUID | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = daily(days, owner_user_id, user, db)
    rows = [
        {
            key: row[key]
            for key in [
                "profile_id",
                "date",
                "realized_pnl",
                "closed_trades",
                "wins",
                "losses",
                "signals",
                "approved",
            ]
        }
        for row in data["rows"]
    ]
    return PlainTextResponse(
        csv_text(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=atlas-markets-report.csv"},
    )
