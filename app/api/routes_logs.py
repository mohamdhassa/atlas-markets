from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timedelta, timezone
import json
import threading
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.db.models.auth import AuthAuditLog, User
from app.db.models.automation import AutomationAction, AutomationScan
from app.db.models.live_execution import LiveExecutionEvent
from app.db.models.strategy_revision import SymbolStrategyRevision
from app.db.session import get_db
from app.services import system_events as events

router = APIRouter(prefix='/logs', tags=['logs'])


def timestamp(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def stored(source, row, event, message, **fields):
    return {'id': f'{source}:{row.id}', 'time': timestamp(row.created_at),
            'source': source, 'event': events.code(event), 'level': fields.pop('level', 'INFO'),
            'message': message, 'origin': 'PERSISTED_AUDIT',
            **{k: v if isinstance(v, (int, float)) else events.code(v) for k, v in fields.items() if v is not None}}


def history(db, since, source):
    rows, capped = [], False
    def read(model, date):
        nonlocal capped
        found = db.scalars(select(model).where(date >= since).order_by(date.desc(), model.id.desc()).limit(2000)).all()
        capped |= len(found) == 2000
        return found
    if not source or source == 'TRADING':
        for row in read(AutomationAction, AutomationAction.created_at):
            try:
                preflight = json.loads(row.raw_json or '{}').get('preflight', {})
            except (ValueError, AttributeError):
                preflight = {}
            if not isinstance(preflight, dict):
                preflight = {}
            request = preflight.get('request') or {}
            if not isinstance(request, dict):
                request = {}
            rows.append(stored('TRADING', row, row.status, 'Recorded trading decision and outcome',
                              level='WARNING' if row.status in ('BLOCK', 'REJECTED', 'FAILED') else 'INFO',
                              provider=row.provider, symbol=row.symbol, decision=row.side or request.get('side') or 'HOLD',
                              status=row.status, reason=row.reason, quantity=row.quantity, scan_id=row.scan_id,
                              order_id=row.broker_order_id, readiness=preflight.get('readiness'), preflight=preflight.get('preflight')))
    if not source or source == 'AUTOMATION':
        for row in read(AutomationScan, AutomationScan.started_at):
            rows.append({'id': f'AUTOMATION:{row.id}', 'time': timestamp(row.started_at), 'source': 'AUTOMATION',
                         'event': 'SCAN', 'level': 'ERROR' if row.status == 'FAILED' else 'INFO', 'status': events.code(row.status),
                         'scan_id': str(row.id), 'message': f'Scan: {row.symbols_count} symbols, {row.approved_count} approved, {row.executed_count} executed',
                         'origin': 'PERSISTED_AUDIT', 'error_kind': 'SCAN_ERROR' if row.error_message else None})
    if not source or source == 'SECURITY':
        for row in read(AuthAuditLog, AuthAuditLog.created_at):
            rows.append(stored('SECURITY', row, row.action, 'Authentication or access audit', status='SUCCESS' if row.success else 'FAILED', level='INFO' if row.success else 'WARNING'))
    if not source or source == 'SAFETY':
        for row in read(LiveExecutionEvent, LiveExecutionEvent.created_at):
            rows.append(stored('SAFETY', row, row.action, 'Live execution safety event; free-text reason remains in the protected safety history'))
    if not source or source == 'STRATEGY':
        for row in read(SymbolStrategyRevision, SymbolStrategyRevision.created_at):
            rows.append(stored('STRATEGY', row, row.event, f'Strategy revision {row.revision_number}; configuration remains in the protected strategy history'))
    return rows, capped


@router.get('')
def logs(source: str = Query('', pattern='^(|SERVER|PROVIDER|FRONTEND|TRADING|AUTOMATION|SECURITY|SAFETY|STRATEGY)$'),
         level: str = Query('', pattern='^(|INFO|WARNING|ERROR|CRITICAL|DEBUG)$'),
         provider: str = Query('', max_length=32), decision: str = Query('', pattern='^(|BUY|SELL|HOLD)$'),
         status: str = Query('', max_length=32), q: str = Query('', max_length=80),
         hours: int = Query(24, ge=1, le=168), limit: int = Query(200, ge=1, le=500),
         before: datetime | None = None, before_id: str = Query('', max_length=100),
         user: User = Depends(require_admin), db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    runtime, coverage = events.snapshot()
    audit, capped = history(db, since, source)
    all_rows = [*audit, *runtime]
    selected = []
    for row in all_rows:
        if row['time'] < timestamp(since):
            continue
        if source and row['source'] != source or level and row['level'] != level:
            continue
        if provider and row.get('provider') != provider.upper() or decision and row.get('decision') != decision:
            continue
        if status and row.get('status') != status.upper():
            continue
        if q and q.lower() not in json.dumps(row).lower():
            continue
        if before and (row['time'], row['id']) >= (timestamp(before), before_id or '\uffff'):
            continue
        selected.append(row)
    selected.sort(key=lambda x: (x['time'], x['id']), reverse=True)
    page = selected[:limit]
    next_cursor = {'before': page[-1]['time'], 'before_id': page[-1]['id']} if len(selected) > limit else None
    return {'events': page, 'next': next_cursor, 'coverage': {**coverage, 'audit_window_capped': capped,
            'runtime_retention': 'Last 20,000 events; Redis key expires after 7 days without writes',
            'host_logs': 'External Docker, Gateway, Caddy and systemd raw logs are not collected',
            'scope': 'ADMIN_ONLY', 'poll_seconds': 3}}


class BrowserEvent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    event: str = Field(pattern='^(PAGE_OPENED|JS_ERROR|UNHANDLED_REJECTION|API_FAILED|RESOURCE_FAILED)$')
    page: str = Field(default='Unknown', max_length=40, pattern='^[A-Za-z ]+$')
    http_status: int | None = Field(default=None, ge=100, le=599)


_rate = OrderedDict()
_rate_lock = threading.Lock()


@router.post('/browser', status_code=204)
def browser_event(payload: BrowserEvent, user: User = Depends(get_current_user)):
    # Strict schema deliberately excludes text, stacks, headers, URLs and bodies.
    with _rate_lock:
        key, now = str(user.id), time.monotonic()
        start, count = _rate.get(key, (now, 0))
        if now - start >= 60:
            start, count = now, 0
        if count >= 60:
            raise HTTPException(429, 'Browser event limit reached')
        _rate[key] = (start, count + 1)
        _rate.move_to_end(key)
        while len(_rate) > 2000:
            _rate.popitem(last=False)
    events.emit('FRONTEND', payload.event, level='INFO' if payload.event == 'PAGE_OPENED' else 'ERROR',
                message='Browser-reported event', page=payload.page, http_status=payload.http_status)
