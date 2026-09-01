from pathlib import Path

from app.main import app


def test_phase47_live_market_cards_are_loaded_and_routes_registered():
    html = Path('app/static/index.html').read_text(encoding='utf-8')
    live_js = Path('app/static/phase47-live-market-cards.js').read_text(encoding='utf-8')
    workspace_js = Path('app/static/phase46-market-workspaces.js').read_text(encoding='utf-8')
    assert 'phase46-market-workspaces.js?v=46.1' in html
    assert 'phase47-live-market-cards.js?v=47.2' in html
    assert 'Live stocks & ETF quotes & decisions' in live_js
    assert 'Live crypto quotes & decisions' in live_js
    assert 'Live metals & commodities quotes & decisions' in live_js
    assert "markets:c.markets.join(',')" in live_js
    assert "markets:c.markets.join(',')" in workspace_js
    paths = [getattr(r, 'path', '') for r in app.routes]
    assert '/markets/workspace-quotes' in paths
    assert '/automation/monitor-scan' in paths
