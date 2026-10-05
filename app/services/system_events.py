"""Bounded, non-blocking operational telemetry. Never record request bodies/secrets."""
from __future__ import annotations

import asyncio
import json
import logging
import queue
import re
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from functools import wraps
from contextvars import ContextVar

from redis import Redis

from app.core.config import get_settings

KEY = 'atlas:system-events:v1'
MAX_EVENTS = 20000
_events = deque(maxlen=MAX_EVENTS)
_queue = queue.Queue(maxsize=2000)
_lock = threading.Lock()
_stop = threading.Event()
_thread = None
_health = {'dropped': 0, 'persistence': 'NOT_STARTED'}
_context = ContextVar('system_event_context', default={})


def context(**fields):
    """Set task-local correlation; enclosing traced operations restore it."""
    return _context.set({**_context.get(), **fields})


def traced(event):
    def decorate(handler):
        @wraps(handler)
        async def wrapped(*args, **kwargs):
            token = context(operation_id=str(uuid.uuid4()))
            emit('AUTOMATION', event + '_STARTED', message='Operation started')
            try:
                result = await handler(*args, **kwargs)
                emit('AUTOMATION', event + '_COMPLETED', message='Operation returned', status=result.get('status') if isinstance(result, dict) else None)
                return result
            except asyncio.CancelledError:
                emit('AUTOMATION', event + '_CANCELLED', level='WARNING', message='Operation cancelled')
                raise
            except Exception as exc:
                emit('AUTOMATION', event + '_FAILED', level='ERROR', message='Operation failed', error_kind=type(exc).__name__)
                raise
            finally:
                _context.reset(token)
        return wrapped
    return decorate


def observed_strategy(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        emit('STRATEGY', 'ROUTER_EVALUATION_STARTED', message='Market regime and strategy eligibility evaluation started')
        result = handler(*args, **kwargs)
        emit('STRATEGY', 'ROUTER_EVALUATED', message='Advisory route evaluated; this is not an order',
             strategy=result.get('strategy'), regime=result.get('regime'), confidence=result.get('confidence'),
             eligible='|'.join(result.get('eligible') or ()), reason='|'.join(result.get('reasons') or ()), status=result.get('mode'))
        return result
    return wrapped


def code(value, maximum=160):
    # Error codes and identifiers only: discard free-text exception suffixes.
    return re.sub(r'[^A-Za-z0-9_.|/-]', '_', str(value or '').split(':', 1)[0])[:maximum]


def endpoint(path):
    path = str(path or '').split('?', 1)[0]
    known = {'account', 'health', 'positions', 'orders', 'order', 'order-check', 'executions', 'contract', 'quote', 'candles', 'symbol', 'symbols', 'search', 'history', 'deals', 'status', 'cancel', 'close', 'check', 'v5', 'wallet-balance', 'info', 'user', 'query-api', 'position', 'list', 'market', 'time', 'instruments-info', 'realtime', 'create', 'execution', 'closed-pnl', 'spot'}
    return '/' + '/'.join(part if part in known else '{value}' for part in path.strip('/').split('/'))


def emit(source, event, *, level='INFO', message='', **fields):
    row = {'id': str(uuid.uuid4()), 'time': datetime.now(timezone.utc).isoformat(),
           'source': code(source), 'event': code(event), 'level': level,
           'message': str(message)[:300]}
    allowed = {'provider', 'market', 'symbol', 'strategy', 'regime', 'confidence', 'eligible', 'timeframe', 'article_count', 'candle_count', 'operation_id', 'decision', 'status', 'reason', 'scan_id', 'order_id', 'request_id', 'method', 'path', 'error_kind', 'page', 'quantity', 'duration_ms', 'http_status', 'readiness', 'preflight'}
    for key, value in {**_context.get(), **fields}.items():
        if key in allowed and value is not None:
            row[key] = value if isinstance(value, (int, float)) else code(value)
    with _lock:
        _events.append(row)
    try:
        _queue.put_nowait(row)
    except queue.Full:
        with _lock:
            _health['dropped'] += 1
    return row


def _redis():
    return Redis.from_url(get_settings().redis_url, decode_responses=True,
                          socket_connect_timeout=1, socket_timeout=1)


def _writer():
    client = _redis()
    while not _stop.is_set():
        try:
            row = _queue.get(timeout=.2)
        except queue.Empty:
            continue
        try:
            with client.pipeline() as pipeline:
                pipeline.lpush(KEY, json.dumps(row))
                pipeline.ltrim(KEY, 0, MAX_EVENTS - 1)
                pipeline.expire(KEY, 7 * 86400)
                pipeline.execute()
            _health['persistence'] = 'REDIS'
        except Exception:
            _health['persistence'] = 'MEMORY_ONLY'
            _health['dropped'] += 1
        finally:
            _queue.task_done()
    client.close()


class EventHandler(logging.Handler):
    def emit(self, record):
        # Arbitrary Python log arguments can contain credentials. Capture safe
        # metadata only; raw logs remain in the protected server console.
        if record.name.startswith(('uvicorn.access', 'httpx', 'httpcore')):
            return
        emit('SERVER', 'PYTHON_LOG', level=record.levelname,
             message=f'{code(record.name)} emitted {record.levelname}',
             error_kind=record.exc_info[0].__name__ if record.exc_info else None)


_handler = EventHandler(level=logging.INFO)


def start():
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    logging.getLogger().addHandler(_handler)
    # Uvicorn error logger may not propagate to root.
    if not logging.getLogger('uvicorn.error').propagate:
        logging.getLogger('uvicorn.error').addHandler(_handler)
    _thread = threading.Thread(target=_writer, daemon=True, name='system-event-writer')
    _thread.start()
    emit('SERVER', 'APP_STARTED', message='Application event capture started')


async def stop():
    emit('SERVER', 'APP_STOPPING', message='Application stopping')
    _stop.set()
    logging.getLogger().removeHandler(_handler)
    logging.getLogger('uvicorn.error').removeHandler(_handler)
    if _thread:
        await asyncio.to_thread(_thread.join, 2)


def snapshot():
    with _lock:
        rows = {x['id']: dict(x) for x in _events}
    client = None
    try:
        client = _redis()
        for raw in client.lrange(KEY, 0, MAX_EVENTS - 1):
            row = json.loads(raw)
            rows.setdefault(row['id'], row)
        persistence = 'REDIS'
    except Exception:
        persistence = 'MEMORY_ONLY'
    finally:
        if client is not None:
            client.close()
    return list(rows.values()), {**_health, 'persistence': persistence, 'runtime_limit': MAX_EVENTS}


def observed_provider(provider, method=None):
    def decorate(handler):
        @wraps(handler)
        async def wrapped(self, *args, **kwargs):
            verb = method or str(args[0] if args else kwargs.get('method', 'UNKNOWN'))
            path = (args[0] if args else kwargs.get('path', '')) if method else (args[1] if len(args) > 1 else kwargs.get('path', ''))
            request_id = str(uuid.uuid4())
            started = time.monotonic()
            fields = {'provider': provider, 'method': verb, 'path': endpoint(path), 'request_id': request_id}
            emit('PROVIDER', 'REQUEST_STARTED', message='Provider request started', **fields)
            try:
                result = await handler(self, *args, **kwargs)
                emit('PROVIDER', 'REQUEST_COMPLETED', message='Provider response received', duration_ms=round((time.monotonic()-started)*1000, 2), **fields)
                return result
            except asyncio.CancelledError:
                emit('PROVIDER', 'REQUEST_CANCELLED', level='WARNING', message='Provider request cancelled', **fields)
                raise
            except Exception as exc:
                response = getattr(exc, 'response', None)
                emit('PROVIDER', 'REQUEST_FAILED', level='ERROR', message='Provider request failed', error_kind=type(exc).__name__, http_status=getattr(response, 'status_code', None), duration_ms=round((time.monotonic()-started)*1000, 2), **fields)
                raise
        return wrapped
    return decorate


class EventMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['path'].startswith('/logs'):
            return await self.app(scope, receive, send)
        started, request_id = time.monotonic(), str(uuid.uuid4())
        status = 500
        emit('SERVER', 'HTTP_STARTED', message='Application HTTP request started', method=scope['method'], path=endpoint(scope['path']), request_id=request_id)

        async def tracked_send(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
                message['headers'] = [*message.get('headers', []), (b'x-atlas-request-id', request_id.encode())]
            await send(message)

        try:
            await self.app(scope, receive, tracked_send)
        except Exception as exc:
            emit('SERVER', 'REQUEST_EXCEPTION', level='ERROR', message='Application request raised an exception', error_kind=type(exc).__name__, request_id=request_id)
            raise
        finally:
            route = scope.get('route')
            path = getattr(route, 'path', '/unmatched')
            emit('SERVER', 'HTTP_REQUEST', level='ERROR' if status >= 500 else 'WARNING' if status >= 400 else 'INFO', message='Application HTTP request completed', method=scope['method'], path=path, http_status=status, duration_ms=round((time.monotonic()-started)*1000, 2), request_id=request_id)
