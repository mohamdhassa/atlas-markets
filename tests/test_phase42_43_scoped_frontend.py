from pathlib import Path


def test_global_scope_overlays_are_retired_from_runtime():
    root=Path(__file__).resolve().parents[1]
    html=(root/'app/static/index.html').read_text(encoding='utf-8')
    scope=(root/'app/static/phase42-global-scope.js').read_text(encoding='utf-8')
    ops=(root/'app/static/phase43-scoped-operations.js').read_text(encoding='utf-8')
    assert 'phase42-global-scope.js?v=42.0' not in html
    assert 'phase43-scoped-operations.js?v=43.0' not in html
    for key in ['provider','account','market','symbol']:
        assert key in scope
    for endpoint in ['/portfolio','/broker-orders?limit=200','/performance/broker-native?days=30','/signals?limit=200']:
        assert endpoint in ops
