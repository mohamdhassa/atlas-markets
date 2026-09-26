from pathlib import Path


STATIC = Path("app/static")


def test_v87_supersedes_rejected_v85_asset_consolidation():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    required_production_assets = (
        "portfolio-v61.js",
        "portfolio-terminal-v63.js",
        "open-position-charts-v65.js",
        "live-position-charts-v66.js",
        "news-decision-context-v67.js",
        "unified-market-monitor-v71-1.js",
        "operations-v72-1.js",
        "dashboard-v72-2.js",
        "live-activity-v75.js",
    )
    for asset in required_production_assets:
        assert asset in html
    assert "atlas-responsive-v87.css?v=87.1" in html
    assert "atlas-responsive-v87.js?v=87.1" in html


def test_production_shell_preserves_existing_router_and_adds_mobile_navigation():
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    responsive = (STATIC / "atlas-responsive-v87.js").read_text(encoding="utf-8")
    assert "renderPage('Dashboard')" in app
    assert "window.AtlasProduction?.install?.()" not in app
    assert "aria-controls" in responsive
    assert "aria-expanded" in responsive
    assert "event.key==='Escape'" in responsive
    assert "atlas-sidebar-backdrop" in responsive


def test_responsive_layer_does_not_change_execution_or_provider_calls():
    responsive = (
        (STATIC / "atlas-responsive-v87.js").read_text(encoding="utf-8")
        + (STATIC / "atlas-responsive-v87.css").read_text(encoding="utf-8")
    )
    for forbidden in (
        "/orders",
        "/automation/start",
        "/automation/stop",
        "/accounts/connect",
        "fetch(",
    ):
        assert forbidden not in responsive
