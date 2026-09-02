from pathlib import Path


def test_api_hardening_loads_before_production_frontend():
    html = Path('app/static/index.html').read_text(encoding='utf-8')
    js = Path('app/static/phase48-api-hardening.js').read_text(encoding='utf-8')
    assert 'phase48-api-hardening.js?v=48.0' in html
    assert html.index('/static/app.js') < html.index('phase48-api-hardening.js?v=48.0') < html.index('atlas-production.js?v=2.0')
    assert 'formatDetail' in js
    assert "window.api=async function" in js
