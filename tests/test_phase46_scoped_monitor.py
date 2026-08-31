from pathlib import Path

from app.api.routes_automation import router as automation_router


def test_scoped_monitor_route_and_market_workspace():
    routes=[r for r in automation_router.routes if str(getattr(r,'path','')).endswith('/monitor-scan')]
    assert routes
    assert 'POST' in routes[0].methods

    js=Path('app/static/phase46-market-workspaces.js').read_text(encoding='utf-8')
    assert '/automation/monitor-scan?' in js
    assert "qs.set('provider',c.provider)" in js
    assert "c.markets.forEach(m=>qs.append('markets',m))" in js
    assert 'Monitor scan only. No broker order is placed by this action.' in js
    assert 'Running monitored scan…' not in js
