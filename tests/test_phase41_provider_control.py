from pathlib import Path


def test_phase41_provider_control_is_loaded():
    html = Path('app/static/index.html').read_text(encoding='utf-8')
    js = Path('app/static/phase41-provider-control.js').read_text(encoding='utf-8')
    css = Path('app/static/phase41-provider-control.css').read_text(encoding='utf-8')
    assert 'phase41-provider-control.css' in html
    assert 'phase41-provider-control.js' in html
    assert 'Provider Control' in js
    assert '/accounts' in js
    assert '/strategies/symbols' in js
    assert '/strategies/performance?days=30' in js
    assert '/automation/actions?limit=500' in js
    assert 'data-symbol-toggle' in js
    assert 'data-account-toggle' in js
    assert '.p41-provider-grid' in css
