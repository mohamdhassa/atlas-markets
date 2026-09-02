from pathlib import Path

from app.main import app


def test_engine_center_and_management_are_loaded():
    html = Path('app/static/index.html').read_text(encoding='utf-8')
    engine = Path('app/static/phase44-engine-center.js').read_text(encoding='utf-8')
    management = Path('app/static/phase45-management-center.js').read_text(encoding='utf-8')
    assert 'phase44-engine-center.js?v=44.0' in html
    assert 'phase45-management-center.js?v=45.0' in html
    assert 'phase42-global-scope.js' not in html
    assert 'phase43-scoped-operations.js' not in html
    assert 'ATLAS-verified P&L' in engine
    assert 'Strategy audit' in engine
    assert 'Provider integrations' in management
    assert 'User management' in management


def test_admin_user_lifecycle_routes_are_registered():
    paths = {(getattr(r, 'path', ''), frozenset(getattr(r, 'methods', set()))) for r in app.routes}
    assert any(path.endswith('/admin/users/{user_id}') and 'PATCH' in methods for path, methods in paths)
    assert any(path.endswith('/admin/users/{user_id}/reset-password') and 'POST' in methods for path, methods in paths)
