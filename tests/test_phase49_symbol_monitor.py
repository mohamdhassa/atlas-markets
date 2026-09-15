from pathlib import Path


def test_legacy_symbol_monitor_is_not_runtime_loaded():
    html = Path('app/static/index.html').read_text(encoding='utf-8')
    assert '/static/atlas-core.js?v=53.0' in html
    assert '/static/phase49-symbol-monitor.css' not in html
    assert '/static/phase49-symbol-monitor.js' not in html


def test_legacy_symbol_monitor_reference_uses_atlas_sources():
    js = Path('app/static/phase49-symbol-monitor.js').read_text(encoding='utf-8')
    assert 'Symbol Monitor' in js
    assert 'include_history=true' in js
    assert "api('/signals?limit=200')" in js
    assert "api('/strategies/symbols')" in js
    assert "api('/portfolio')" in js
    assert "api('/performance/broker-native?days=30')" in js
    assert 'BUY' in js and 'SELL' in js and 'HOLD' in js


def test_legacy_symbol_monitor_reference_has_refresh_logic():
    js = Path('app/static/phase49-symbol-monitor.js').read_text(encoding='utf-8')
    assert 'const REFRESH_MS=10000' in js
    assert 'scheduleRefresh()' in js
    assert 'visibilitychange' in js
