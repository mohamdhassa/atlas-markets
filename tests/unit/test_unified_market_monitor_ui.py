from pathlib import Path


def test_v711_is_loaded_after_stable_v66():
    html=Path('app/static/index.html').read_text()
    assert 'live-position-charts-v66.js?v=66.0' in html
    assert 'unified-market-monitor-v71-1.js?v=71.1' in html
    assert html.index('live-position-charts-v66.js?v=66.0') < html.index('unified-market-monitor-v71-1.js?v=71.1')


def test_v711_only_rebuilds_market_monitor_and_uses_unified_endpoint():
    js=Path('app/static/unified-market-monitor-v71-1.js').read_text()
    assert "querySelector('.v62-universe')" in js
    assert "/strategies/symbols/universe/market-monitor" in js
    assert "api('/portfolio')" in js
    assert 'Decision:' in js
    assert 'execution gate' in js.lower()
    assert "['BYBIT','IBKR']" in js
    assert 'AtlasPortfolioV61.render=' not in js
    assert 'MutationObserver' not in js
