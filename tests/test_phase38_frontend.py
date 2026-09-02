from pathlib import Path


def test_legacy_phase38_operations_center_is_retired_from_runtime():
    html = Path('app/static/index.html').read_text(encoding='utf-8')
    legacy = Path('app/static/phase38-operations.js').read_text(encoding='utf-8')
    production = Path('app/static/atlas-production.js').read_text(encoding='utf-8')
    assert 'phase38-operations.js' not in html
    assert 'atlas-production.js?v=2.0' in html
    assert 'AUTOMATION OPERATIONS CENTER' in legacy
    assert '/automation/state' in production
    assert '/automation/actions?limit=200' in production
