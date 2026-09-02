from pathlib import Path

from app.api.routes_automation import router as automation_router


def test_scoped_monitor_route_and_production_workspace():
    routes=[r for r in automation_router.routes if str(getattr(r,'path','')).endswith('/monitor-scan')]
    assert routes
    assert 'POST' in routes[0].methods

    js=Path('app/static/atlas-production.js').read_text(encoding='utf-8')
    assert '/automation/monitor-scan?' in js
    assert "markets:c.markets.join(',')" in js
    assert 'Read-only readiness check. It never places a broker order.' in js
    assert "api('/signals?limit=200')" in js
