import asyncio
import threading

import httpx

from app.main import app
from app.services import reporting


def test_blocked_reporting_keeps_public_web_requests_responsive(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    calls = []
    def blocked_report():
        calls.append(1)
        started.set()
        assert release.wait(5), 'test did not release report worker'
    monkeypatch.setattr(reporting, 'generate_daily_reports', blocked_report)

    async def scenario():
        stop = asyncio.Event()
        task = asyncio.create_task(reporting.reporting_loop(stop))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                response = await asyncio.wait_for(client.get('/api/system'), timeout=1)
                assert response.status_code == 200
            stop.set()
        finally:
            release.set()
            stop.set()
            await asyncio.wait_for(task, 2)
        assert calls == [1]
    asyncio.run(scenario())
