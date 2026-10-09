import asyncio
import threading
from datetime import datetime, timezone
from types import SimpleNamespace as NS

import pytest
from fastapi import HTTPException
import tools.ibkr_bridge as bridge
from app.api import routes_broker_native as native
from app.services.autotrade_readiness import _ibkr_connection_verdict


@pytest.fixture
def node(monkeypatch):
    state = bridge.State()
    monkeypatch.setattr(bridge, 'ib', state)
    monkeypatch.setattr(bridge, 'cfg', {'simulation': True, 'account_id': 'DU123', 'host': 'localhost', 'port': 4002, 'client_id': 27})
    monkeypatch.setattr(bridge, 'account_cache', None)
    monkeypatch.setattr(bridge, 'account_cache_at', 0)
    monkeypatch.setattr(state, 'isConnected', lambda: True)
    return state


def test_server_loss_blocks_reads_and_orders_despite_connected_socket(node, monkeypatch):
    node.error(-1, 1100, 'server disconnected')
    health = bridge.health(None)
    assert health['socket_connected'] is True
    assert health['connected'] is health['server_connected'] is False
    calls = []
    monkeypatch.setattr(node, 'placeOrder', lambda *args: calls.append(args))
    payload = bridge.OrderPayload(symbol='TSLA', side='BUY', quantity=1)
    for action in (lambda: bridge.account(None), lambda: bridge.orders(None),
                   lambda: bridge.positions(None), lambda: bridge.order_check(payload, None),
                   lambda: bridge.place(payload, None)):
        with pytest.raises(HTTPException) as exc: action()
        assert exc.value.status_code == 503
        assert exc.value.detail == 'IBKR_SERVER_UNAVAILABLE'
    assert not calls
    # A market-data farm notice or next ID is not proof of server restoration.
    node.error(-1, 2104, 'farm OK')
    node.nextValidId(42)
    assert bridge.health(None)['connected'] is False


@pytest.mark.parametrize('code', [1101, 1102])
def test_restoration_requires_a_fresh_account_summary(node, monkeypatch, code):
    monkeypatch.setattr(bridge, 'account_cache', {'account_id': 'DU123', 'equity': 999})
    monkeypatch.setattr(bridge, 'account_cache_at', bridge.time.monotonic())
    node.error(-1, 1100, 'lost')
    node.error(-1, code, 'restored')
    calls, cancelled = [], []
    def summary(req, *args):
        calls.append(req)
        for tag in ('NetLiquidation', 'TotalCashValue', 'AvailableFunds', 'BuyingPower'):
            node.accountSummary(req, 'DU123', tag, '100', 'USD')
        node.accountSummaryEnd(req)
    monkeypatch.setattr(node, 'reqAccountSummary', summary)
    monkeypatch.setattr(node, 'cancelAccountSummary', cancelled.append)
    result = bridge.account(None)
    assert result['equity'] == 100 and result['data_status'] == 'FRESH'
    assert calls == cancelled and len(calls) == 1
    assert result['observed_at']


def test_disconnect_wakes_wait_and_never_accepts_partial_or_old_session_data(node):
    bridge.prepare('orders')
    node.error(-1, 1100, 'lost')
    assert node._event('orders').is_set()
    node.error(-1, 1102, 'restored quickly')
    with pytest.raises(HTTPException, match='IBKR_READ_INTERRUPTED_BY_DISCONNECT'):
        bridge.wait('orders', .01)


def test_failed_reads_back_off_and_success_resets_cooldown(node, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(bridge.time, 'monotonic', lambda: clock[0])
    for delay in (10, 20, 40, 80, 120, 120):
        bridge.prepare('orders')
        with pytest.raises(HTTPException) as exc: bridge.wait('orders', 0)
        assert exc.value.status_code == 504
        with pytest.raises(HTTPException) as exc: bridge.read_ready('orders')
        assert exc.value.detail == 'IBKR_READ_RECOVERY_COOLDOWN'
        assert exc.value.headers['Retry-After'] == str(delay)
        clock[0] += delay
        bridge.read_ready('orders')
    bridge.prepare('orders');node.openOrderEnd();bridge.wait('orders', 0)
    assert 'orders' not in node.read_failures
    assert 'orders' not in node.read_retry_at


def test_overlapping_orders_fail_fast_and_release_after_timeout(node, monkeypatch):
    calls = []
    with bridge.read_locks['orders']:
        monkeypatch.setattr(node, 'reqAllOpenOrders', lambda: calls.append(True))
        with pytest.raises(HTTPException, match='IBKR_READ_ALREADY_IN_PROGRESS'):
            bridge.orders(None)
    assert not calls
    monkeypatch.setattr(bridge, 'wait', lambda *args: (_ for _ in ()).throw(HTTPException(504, 'timeout')))
    with pytest.raises(HTTPException): bridge.orders(None)
    assert not bridge.read_locks['orders'].locked()


def test_stale_account_never_passes_execution_connection_verdict():
    profile = NS(environment='PAPER', external_account_ref='DU123')
    account = {'account_id': 'DU123', 'simulation': True, 'data_status': 'STALE'}
    assert _ibkr_connection_verdict(profile, {}, {'connected': True}, account) == (False, 'IBKR_ACCOUNT_DATA_STALE')


@pytest.mark.asyncio
async def test_portfolio_keeps_other_provider_and_excludes_stale_ibkr_from_totals(monkeypatch):
    ib = NS(id=1, provider='IBKR', account_label='Paper', environment='PAPER', is_active=True,
            credentials_configured=True, equity_usd=999, last_sync_at=datetime(2026, 10, 5, tzinfo=timezone.utc))
    by = NS(id=2, user_id=2, provider='BYBIT', account_label='Testnet', environment='TESTNET', is_active=True,
            credentials_configured=True, last_connection_status='CONNECTED')
    class IB:
        async def account(self): raise RuntimeError('IBKR_SERVER_UNAVAILABLE')
    class Bybit:
        async def wallet(self): return {'list': [{'totalEquity': '100', 'totalAvailableBalance': '80'}]}
    monkeypatch.setattr(native, '_accounts', lambda *args: [ib, by])
    monkeypatch.setattr(native, '_symbol_market_map', lambda *args: {})
    monkeypatch.setattr(native, '_ibkr', lambda p: IB())
    monkeypatch.setattr(native, '_bybit', lambda p: Bybit())
    db = NS(scalars=lambda query: NS(all=lambda: []))
    data = await native.portfolio(NS(role='ADMIN'), db)
    assert data['totals']['equity'] == 100
    assert data['totals']['available'] == 80
    assert data['totals']['partial'] is True
    stale = data['accounts'][0]
    assert stale['equity'] == 999 and stale['data_status'] == 'STALE'
    assert stale['positions'] is stale['available'] is None
    assert data['accounts'][1]['data_status'] == 'FRESH'


def test_watchdog_preserves_gateway_session_during_server_outage(tmp_path):
    import os
    import subprocess
    bin_dir = tmp_path / 'bin';bin_dir.mkdir()
    calls = tmp_path / 'calls'
    docker = bin_dir / 'docker'
    docker.write_text('#!/bin/bash\necho "$*" >> "$CALLS"\nif [[ "$*" == *".State.Health"* ]]; then echo healthy; elif [[ "$*" == *".State.Status"* ]]; then echo running; fi\n')
    curl = bin_dir / 'curl'
    curl.write_text('#!/bin/bash\necho \'{"connected":false,"socket_connected":true,"server_connected":false}\'\n')
    timeout = bin_dir / 'timeout';timeout.write_text('#!/bin/bash\nexit 0\n')
    for path in (docker, curl, timeout): path.chmod(0o755)
    result = subprocess.run(['bash', 'ops/ibkr_bridge_watchdog.sh'], env={**os.environ, 'PATH': str(bin_dir)+':'+os.environ['PATH'], 'CALLS': str(calls), 'IBKR_WATCHDOG_LOG': str(tmp_path/'watchdog.log')}, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert 'waiting_for_gateway_reconnection' in result.stdout
    assert 'restart' not in calls.read_text()
