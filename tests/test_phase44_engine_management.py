from pathlib import Path

from app.main import app


def test_production_engine_and_management_are_loaded():
    html = Path('app/static/index.html').read_text(encoding='utf-8')
    production = Path('app/static/atlas-production.js').read_text(encoding='utf-8')
    fixes = Path('app/static/atlas-production-fixes.js').read_text(encoding='utf-8')
    assert 'atlas-production.js?v=1.0' in html
    assert 'atlas-production-fixes.js?v=1.0' in html
    assert 'atlas-production.css?v=1.0' in html
    assert 'phase44-engine-center.js' not in html
    assert 'phase45-management-center.js' not in html
    assert 'phase42-global-scope.js' not in html
    assert 'phase43-scoped-operations.js' not in html
    assert 'ATLAS-verified P&L' in production
    assert 'PROVIDER ENGINES' in production
    assert "group('TRADING & ANALYSIS',['Charts','Strategies','Positions','Orders & History','Performance','Automation'])" in production
    assert "group('ADMINISTRATION',['Accounts & Integrations','Users','Management'])" in production
    assert "window.AtlasIntegrations?.render" in production
    assert "window.usersPage" in production
    assert "window.chartsPage" in production
    assert 'Provider performance over time' in fixes
    assert 'Cumulative realized profit over time' in fixes
    assert "api('/broker-orders?limit=200')" in fixes
    assert "api('/automation/actions?limit=200')" in fixes
    assert 'limit=300' not in fixes


def test_admin_user_lifecycle_routes_are_registered():
    paths = {(getattr(r, 'path', ''), frozenset(getattr(r, 'methods', set()))) for r in app.routes}
    assert any(path.endswith('/admin/users/{user_id}') and 'PATCH' in methods for path, methods in paths)
    assert any(path.endswith('/admin/users/{user_id}/reset-password') and 'POST' in methods for path, methods in paths)
