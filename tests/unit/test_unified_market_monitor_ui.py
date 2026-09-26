from pathlib import Path


def test_production_market_layers_are_active_in_v87_runtime():
    html=Path('app/static/index.html').read_text(encoding='utf-8')
    assert 'live-position-charts-v66.js' in html
    assert 'unified-market-monitor-v71-1.js' in html
    assert 'atlas-responsive-v87.js?v=87.1' in html


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
