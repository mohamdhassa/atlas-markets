from pathlib import Path


def test_consolidated_operations_center_is_loaded():
    html = Path('app/static/index.html').read_text(encoding='utf-8')
    core = Path('app/static/atlas-core.js').read_text(encoding='utf-8')
    assert '/static/atlas-core.js?v=53.0' in html
    assert 'phase38-operations.js' not in html
    assert '/automation/state' in core
    assert '/automation/actions?limit=100' in core
    assert '/accounts' in core
    assert 'Operations' in core
