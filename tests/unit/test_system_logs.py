import asyncio
import json
import logging
import queue
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_current_user
from app.api.routes_logs import router, _rate
from app.db.session import get_db
from app.db.models.automation import AutomationAction, AutomationScan
from app.db.models.auth import AuthAuditLog, User
from app.db.models.live_execution import LiveExecutionEvent
from app.db.models.strategy_revision import SymbolStrategyRevision
from app.services import system_events as events


@pytest.fixture
def feed(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    for model in (User, AutomationScan, AutomationAction, AuthAuditLog, LiveExecutionEvent, SymbolStrategyRevision):
        model.__table__.create(engine)
    db = Session(engine)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4(), role='ADMIN')
    runtime = []
    monkeypatch.setattr(events, 'snapshot', lambda: (runtime, {'persistence': 'MEMORY_ONLY', 'dropped': 1}))
    _rate.clear()
    with TestClient(app) as client:
        yield client, db, app, runtime
    db.close()
    engine.dispose()


def test_logs_permissions_and_strict_browser_payload(feed):
    client, _, app, _ = feed
    assert client.get('/logs').status_code == 200
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4(), role='USER')
    assert client.get('/logs').status_code == 403
    assert client.post('/logs/browser', json={'event': 'PAGE_OPENED', 'page': 'Portfolio'}).status_code == 204
    assert client.post('/logs/browser', json={'event': 'JS_ERROR', 'message': 'secret'}).status_code == 422
    assert client.post('/logs/browser', json={'event': 'JS_ERROR', 'page': 'https://secret'}).status_code == 422
    app.dependency_overrides.pop(get_current_user)
    assert client.get('/logs').status_code == 401
    assert client.post('/logs/browser', json={'event': 'JS_ERROR'}).status_code == 401


def test_audit_outcomes_filters_and_malformed_raw_are_safe(feed):
    client, db, _, _ = feed
    now = datetime.now(timezone.utc)
    scan = AutomationScan(id=uuid.uuid4(), status='COMPLETED', started_at=now)
    db.add(scan)
    for symbol, side, status, raw in [('MSFT', 'BUY', 'BLOCK', '{"preflight":{"request":{"side":"BUY","token":"secret"}}}'),
                                       ('SPY', None, 'BLOCK', '{"preflight":[]}'),
                                       ('IWM', 'SELL', 'EXECUTED', '{"preflight":{"request":[]}}')]:
        db.add(AutomationAction(scan_id=scan.id, user_id=uuid.uuid4(), provider='IBKR', market='STOCK',
                                symbol=symbol, side=side, status=status, raw_json=raw, created_at=now))
    db.commit()
    response = client.get('/logs?source=TRADING&provider=ibkr&decision=BUY&status=BLOCK').json()
    assert [x['symbol'] for x in response['events']] == ['MSFT']
    assert 'secret' not in json.dumps(response)
    assert 'raw_json' not in json.dumps(response)
    assert client.get('/logs?decision=HOLD').json()['events'][0]['symbol'] == 'SPY'
    assert client.get('/logs?decision=SELL').json()['events'][0]['status'] == 'EXECUTED'
    assert client.get('/logs?hours=169').status_code == 422


def test_equal_timestamp_pagination_and_runtime_retention_notice(feed):
    client, _, _, runtime = feed
    now = datetime.now(timezone.utc).isoformat()
    runtime.extend({'id': str(i), 'time': now, 'source': 'SERVER', 'level': 'INFO', 'event': 'TEST', 'message': 'Test'} for i in range(3))
    first = client.get('/logs?limit=2').json()
    second = client.get('/logs', params={'limit': 2, **first['next']}).json()
    assert [x['id'] for x in first['events'] + second['events']] == ['2', '1', '0']
    assert second['next'] is None
    assert 'not collected' in first['coverage']['host_logs']


def test_browser_reporting_is_rate_limited(feed):
    client, _, app, _ = feed
    user = SimpleNamespace(id=uuid.uuid4(), role='USER')
    app.dependency_overrides[get_current_user] = lambda: user
    for _ in range(60):
        assert client.post('/logs/browser', json={'event': 'API_FAILED'}).status_code == 204
    assert client.post('/logs/browser', json={'event': 'API_FAILED'}).status_code == 429


def test_provider_failure_keeps_exception_no_retry_or_secret(monkeypatch):
    rows = []
    monkeypatch.setattr(events, 'emit', lambda source, event, **fields: rows.append({'source': source, 'event': event, **fields, **events._context.get()}))
    class Broker:
        calls = 0
        @events.observed_provider('IBKR', 'POST')
        async def request(self, path, payload):
            self.calls += 1
            raise RuntimeError('password=secret token=secret')
    broker = Broker()
    async def operation():
        token = events.context(scan_id='scan-1', symbol='MSFT')
        try:
            with pytest.raises(RuntimeError, match='password=secret'):
                await broker.request('/orders?token=secret', {'password': 'secret'})
        finally:
            events._context.reset(token)
    asyncio.run(operation())
    assert broker.calls == 1
    assert rows[-1]['event'] == 'REQUEST_FAILED'
    assert rows[-1]['scan_id'] == 'scan-1'
    assert 'secret' not in json.dumps(rows)


def test_task_local_scan_context_isolated_and_restored(monkeypatch):
    rows = []
    monkeypatch.setattr(events, 'emit', lambda source, event, **fields: rows.append(dict(events._context.get())))
    @events.traced('SCAN')
    async def scan(name):
        events.context(scan_id=name)
        await asyncio.sleep(0)
        events.emit('TRADING', 'TEST')
        return {'status': 'COMPLETED'}
    async def both():
        await asyncio.gather(scan('a'), scan('b'))
    asyncio.run(both())
    assert {x.get('scan_id') for x in rows if x.get('scan_id')} == {'a', 'b'}
    assert events._context.get() == {}


def test_queue_full_never_blocks_and_log_text_is_not_recorded(monkeypatch):
    q = queue.Queue(maxsize=1)
    q.put({})
    monkeypatch.setattr(events, '_queue', q)
    before = events._health['dropped']
    row = events.emit('SERVER', 'TEST', token='secret', body='secret')
    assert 'secret' not in json.dumps(row)
    assert events._health['dropped'] == before + 1
    rows = []
    monkeypatch.setattr(events, 'emit', lambda *args, **kwargs: rows.append(kwargs))
    events.EventHandler().emit(logging.LogRecord('app.worker', logging.ERROR, '', 1, 'password=%s', ('secret',), None))
    assert 'secret' not in json.dumps(rows)


def test_redis_failure_returns_memory_events(monkeypatch):
    class Offline:
        def lrange(self, *args): raise RuntimeError('offline')
        def close(self): pass
    monkeypatch.setattr(events, '_redis', lambda: Offline())
    row = events.emit('SERVER', 'OFFLINE_TEST')
    rows, coverage = events.snapshot()
    assert any(x['id'] == row['id'] for x in rows)
    assert coverage['persistence'] == 'MEMORY_ONLY'


def test_router_records_actual_advisory_strategy_not_fake_order(monkeypatch):
    from app.analysis.strategy_router import route_strategy
    rows = []
    monkeypatch.setattr(events, 'emit', lambda source, event, **fields: rows.append({'event': event, **fields}))
    result = route_strategy([])
    assert result['strategy'] == 'NO_TRADE'
    assert rows[-1]['strategy'] == 'NO_TRADE'
    assert rows[-1]['status'] == 'SHADOW'
    assert not any(x['event'] == 'EXECUTED' for x in rows)
