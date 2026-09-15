from pathlib import Path


def test_consolidated_frontend_owns_api_hardening():
    html = Path('app/static/index.html').read_text(encoding='utf-8')
    app_js = Path('app/static/app.js').read_text(encoding='utf-8')
    core_js = Path('app/static/atlas-core.js').read_text(encoding='utf-8')

    assert '/static/app.js?v=53.0' in html
    assert '/static/atlas-core.js?v=53.0' in html
    assert html.index('/static/app.js?v=53.0') < html.index('/static/atlas-core.js?v=53.0')

    # Legacy phase hardening is retained as a reference asset only; the
    # consolidated runtime must not load the old phase chain again.
    assert 'phase48-api-hardening.js' not in html
    assert '/static/phase7.js' not in html

    combined = app_js + '\n' + core_js
    assert 'async function api' in combined or 'window.api' in combined or 'api(' in combined
