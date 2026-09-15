from pathlib import Path

from app.main import app


def test_market_routes_remain_registered_after_frontend_consolidation():
    html = Path('app/static/index.html').read_text(encoding='utf-8')
    assert '/static/atlas-core.js?v=53.0' in html
    assert 'phase46-market-workspaces.js' not in html
    assert 'phase47-live-market-cards.js' not in html
    paths = [getattr(r, 'path', '') for r in app.routes]
    assert '/markets/workspace-quotes' in paths
    assert '/automation/monitor-scan' in paths
