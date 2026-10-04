import asyncio
import threading
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException

import tools.ibkr_bridge as bridge
from app.services.provider_reads import isolated_provider_read


@pytest.fixture
def fake_bridge(monkeypatch):
    state = bridge.State()
    monkeypatch.setattr(bridge, "ib", state)
    monkeypatch.setattr(bridge, "cfg", {"account_id": "paper-test", "simulation": True})
    monkeypatch.setattr(bridge, "account_cache", None)
    monkeypatch.setattr(bridge, "account_cache_at", 0)
    monkeypatch.setattr(state, "isConnected", lambda: True)
    requests, cancelled = [], []

    def request(req_id, *_):
        requests.append(req_id)
        for tag in ("NetLiquidation", "TotalCashValue", "AvailableFunds", "BuyingPower"):
            state.accountSummary(req_id, "paper-test", tag, "100", "USD")
        state.accountSummaryEnd(req_id)

    monkeypatch.setattr(state, "reqAccountSummary", request)
    monkeypatch.setattr(state, "cancelAccountSummary", cancelled.append)
    return SimpleNamespace(state=state, requests=requests, cancelled=cancelled)


def test_account_success_is_cancelled_and_briefly_reused(fake_bridge):
    assert bridge.account(None)["equity"] == 100
    assert bridge.account(None)["equity"] == 100
    assert len(fake_bridge.requests) == 1
    assert fake_bridge.cancelled == fake_bridge.requests
    assert not fake_bridge.state.account_requests
    assert not any(key.startswith("acct:") for key in fake_bridge.state._events)


def test_account_timeout_always_cancels_and_allows_retry(fake_bridge, monkeypatch):
    def timeout(*_):
        raise HTTPException(504, "timeout")

    monkeypatch.setattr(bridge, "wait", timeout)
    with pytest.raises(HTTPException) as exc:
        bridge.account(None)
    assert exc.value.status_code == 504
    assert fake_bridge.cancelled == fake_bridge.requests
    assert not fake_bridge.state.account_requests
    assert bridge.account_cache is None
    assert not bridge.account_lock.locked()


def test_overlapping_summary_does_not_open_another_subscription(fake_bridge):
    with bridge.account_lock:
        with pytest.raises(HTTPException) as exc:
            bridge.account(None)
    assert exc.value.status_code == 503
    assert not fake_bridge.requests


def test_rejected_summary_wakes_wait_and_never_returns_old_values(fake_bridge, monkeypatch):
    def reject(req_id, *_):
        fake_bridge.requests.append(req_id)
        fake_bridge.state.error(req_id, 322, "summary limit")

    monkeypatch.setattr(fake_bridge.state, "reqAccountSummary", reject)
    with pytest.raises(HTTPException) as exc:
        bridge.account(None)
    assert exc.value.status_code == 502
    assert fake_bridge.cancelled == fake_bridge.requests
    assert bridge.account_cache is None


@pytest.mark.asyncio
async def test_blocking_page_work_does_not_delay_health_or_homepage():
    app = FastAPI()
    entered = threading.Event()
    release = threading.Event()

    @app.get("/slow")
    @isolated_provider_read
    async def slow():
        entered.set()
        assert release.wait(2)
        return {"done": True}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/")
    async def root():
        return {"page": "ready"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        task = asyncio.create_task(client.get("/slow"))
        try:
            assert await asyncio.to_thread(entered.wait, 1)
            for path in ("/health", "/"):
                response = await asyncio.wait_for(client.get(path), .5)
                assert response.status_code == 200
        finally:
            release.set()
            assert (await task).status_code == 200


@pytest.mark.asyncio
async def test_capacity_fails_fast_and_recovers():
    release = threading.Event()
    entered = []

    @isolated_provider_read
    async def slow():
        entered.append(True)
        assert release.wait(2)
        return True

    tasks = [asyncio.create_task(slow()) for _ in range(4)]
    try:
        for _ in range(100):
            if len(entered) == 4:
                break
            await asyncio.sleep(.005)
        assert len(entered) == 4
        with pytest.raises(HTTPException) as exc:
            await slow()
        assert exc.value.status_code == 503
    finally:
        release.set()
        assert all(await asyncio.gather(*tasks))
    assert await slow()


@pytest.mark.asyncio
async def test_cancelled_request_waits_for_worker_before_dependency_cleanup():
    entered = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    @isolated_provider_read
    async def slow():
        entered.set()
        assert release.wait(2)
        finished.set()

    task = asyncio.create_task(slow())
    assert await asyncio.to_thread(entered.wait, 1)
    task.cancel()
    await asyncio.sleep(.01)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()
