from pathlib import Path

from app.main import app


def test_management_navigation_is_consolidated():
    html = Path('app/static/index.html').read_text(encoding='utf-8')
    core = Path('app/static/atlas-core.js').read_text(encoding='utf-8')
    assert '/static/atlas-core.js?v=53.0' in html
    assert 'phase44-engine-center.js' not in html
    assert 'phase45-management-center.js' not in html
    assert 'Users' in core
    assert 'Strategy' in core
    assert 'Risk' in core
    assert 'Integrations' in core
    assert 'System' in core


def test_admin_user_lifecycle_routes_are_registered():
    paths = {(getattr(r, 'path', ''), frozenset(getattr(r, 'methods', set()))) for r in app.routes}
    assert any(path.endswith('/admin/users/{user_id}') and 'PATCH' in methods for path, methods in paths)
    assert any(path.endswith('/admin/users/{user_id}/reset-password') and 'POST' in methods for path, methods in paths)
