from pathlib import Path

from app.main import app


def test_phase47_live_market_cards_are_loaded_and_route_registered():
    html = Path('app/static/index.html').read_text(encoding='utf-8')
    js = Path('app/static/phase47-live-market-cards.js').read_text(encoding='utf-8')
    assert 'phase47-live-market-cards.js?v=47.1' in html
    assert 'Live stocks & ETF quotes & decisions' in js
    assert 'Live crypto quotes & decisions' in js
    assert 'Live metals & commodities quotes & decisions' in js
    assert "qs.append('markets',m)" in js
    paths = [getattr(r, 'path', '') for r in app.routes]
    assert '/markets/workspace-quotes' in paths
