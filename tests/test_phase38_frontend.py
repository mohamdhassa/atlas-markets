from pathlib import Path


def test_phase38_operations_center_is_loaded():
    html = Path('app/static/index.html').read_text(encoding='utf-8')
    js = Path('app/static/phase38-operations.js').read_text(encoding='utf-8')
    assert 'phase38-operations.js' in html
    assert 'AUTOMATION OPERATIONS CENTER' in js
    assert '/automation/state' in js
    assert '/automation/actions?limit=200' in js
    assert '/performance/unified?days=30' in js
