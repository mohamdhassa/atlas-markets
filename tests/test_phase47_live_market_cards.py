from pathlib import Path

from app.main import app


def test_production_live_market_cards_are_loaded_and_routes_registered():
    html = Path('app/static/index.html').read_text(encoding='utf-8')
    js = Path('app/static/atlas-production.js').read_text(encoding='utf-8')
    workspace = Path('app/api/routes_workspace_quotes.py').read_text(encoding='utf-8')
    assert 'atlas-production.js?v=1.0' in html
    assert 'phase46-market-workspaces.js' not in html
    assert 'phase47-live-market-cards.js' not in html
    assert 'Live quotes & decisions' in js
    assert "provider:'IBKR'" in js
    assert "provider:'BYBIT'" in js
    assert "provider:'MT5'" in js
    assert "markets:c.markets.join(',')" in js
    assert "api('/signals?limit=200')" in js
    assert "allowed={'FX','STOCK','ETF','CRYPTO','METAL','COMMODITY'}" in workspace
    paths = [getattr(r, 'path', '') for r in app.routes]
    assert '/markets/workspace-quotes' in paths
    assert '/automation/monitor-scan' in paths
