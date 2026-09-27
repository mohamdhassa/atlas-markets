from pathlib import Path


STATIC = Path("app/static")


def test_runtime_uses_small_canonical_asset_set():
    html = (STATIC / "index.html").read_text()
    assert html.count("<script ") == 6
    assert "atlas-production.js?v=85.0" in html
    assert "atlas-router.js?v=85.0" in html
    assert "atlas-accessibility.css?v=85.0" in html
    assert "portfolio-v61.js" not in html
    assert "frontend-v72-6.js" not in html


def test_production_shell_starts_after_login_and_supports_mobile_navigation():
    app = (STATIC / "app.js").read_text()
    production = (STATIC / "atlas-production.js").read_text()
    html = (STATIC / "index.html").read_text()
    assert "window.AtlasProduction?.install?.()" in app
    assert "window.AtlasProduction={render,buildNav:buildProductionNav,install}" in production
    assert 'aria-controls="sidebar"' in html
    assert 'aria-expanded="false"' in html
    assert "event.key==='Escape'" in app


def test_operations_displays_truthful_mt5_runtime_readiness():
    core = (STATIC / "atlas-core.js").read_text()
    assert "api('/mt5/readiness')" in core
    assert "MT5 EXECUTION NODE" in core
    assert "readiness.blockers" in core
    assert "Live Money" in core and "DISABLED" in core
