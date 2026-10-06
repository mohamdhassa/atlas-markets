from pathlib import Path


STATIC = Path("app/static")


def test_responsive_assets_load_last_and_boot_once_after_decorators():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert '/static/responsive-v1.css?v=1.6' in html
    assert html.rindex('/static/responsive-v1.js?v=1.1') > html.rindex('/static/live-activity-v75.js?v=79.0')
    assert "window.AtlasBoot=boot" in app
    assert "\nboot();" not in app
    assert "window.AtlasBoot()" in (STATIC / "responsive-v1.js").read_text(encoding="utf-8")


def test_mobile_navigation_is_accessible_and_dismissible():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "responsive-v1.js").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert 'id="sidebarBackdrop"' in html
    assert 'aria-controls="sidebar"' in html
    assert 'aria-expanded="false"' in html
    assert "Escape" in js
    assert "orientationchange" in js
    assert "sidebar-open" in js
    assert "sidebar.classList.toggle('open')" not in app


def test_responsive_layer_preserves_horizontal_data_access_and_touch_targets():
    css = (STATIC / "responsive-v1.css").read_text(encoding="utf-8")
    assert "@media(max-width:760px)" in css
    assert "@media(max-width:520px)" in css
    assert "overflow:auto" in css
    assert "min-height:44px" in css
    assert "env(safe-area-inset-top)" in css
    assert "prefers-reduced-motion" in css
    assert ":root" not in css


def test_every_active_page_family_has_final_responsive_coverage():
    css = (STATIC / "responsive-v1.css").read_text(encoding="utf-8")
    page_families = {
        "dashboard": (".v722-hero", ".v722-grid", ".v722-provider-grid"),
        "markets_charts": (".v726-head", ".v726-toolbar", ".v72-chart"),
        "operations": (".v721-hero", ".v721-providers", ".v721-facts"),
        "portfolio": (".v61-hero", ".v61-kpis", ".v63-layout", ".v67-grid"),
        "accounts": (".accounts-hero", ".provider-grid", ".account-bottom-grid"),
        "users_signals": (".polish-hero", ".polish-grid.users-layout", ".signal-polish-grid"),
        "strategy_integrations": (".mg-page", ".account-meta", "#mgEditor"),
        "orders_performance_risk_system": (".metric-grid", ".two-col", ".table-wrap"),
        "legacy_management": (".p21-provider-grid", ".p21-form", ".p21-chart-grid"),
        "activity": (".v75-head", ".v75-tools", ".v75-id"),
    }
    missing = {
        family: [selector for selector in selectors if selector not in css]
        for family, selectors in page_families.items()
        if any(selector not in css for selector in selectors)
    }
    assert not missing, missing


def test_mobile_layout_protects_long_content_and_scrollable_controls():
    css = (STATIC / "responsive-v1.css").read_text(encoding="utf-8")
    assert "overflow-wrap:anywhere" in css
    assert "-webkit-overflow-scrolling:touch" in css
    assert "overscroll-behavior-inline:contain" in css
    assert ".v61-toolbar" in css
    assert ".mg-page .account-meta" in css
    assert ".provider-actions" in css


def test_portfolio_terminal_universe_scrolls_in_one_mobile_row():
    css = (STATIC / "responsive-v1.css").read_text(encoding="utf-8")
    assert ".v63-symbols{display:flex;flex-wrap:nowrap" in css
    assert ".v63-symbols{grid-template-columns:1fr}" not in css
    assert "overflow-x:auto;overflow-y:hidden" in css
    assert ".v63-symbol{flex:0 0 166px" in css
    assert ".v63-symbol span{min-width:0;overflow-wrap:anywhere}" in css
    assert ".v63-symbol em{flex:0 0 auto;white-space:nowrap}" in css


def test_portfolio_mobile_contains_chart_stats_and_toolbar():
    css = (STATIC / "responsive-v1.css").read_text()
    assert ".v63-layout{grid-template-columns:minmax(0,1fr);min-height:0}" in css
    assert "align-items:center;overflow:visible" in css
    assert "width:auto;height:auto;min-height:0;align-self:center" in css
    assert ".v61-toolbar #v61-performance-link{flex:1 0 100%" in css
    assert ".v63-stats{grid-template-columns:repeat(3,minmax(0,1fr))}" in css
    assert ".v63-symbol strong{white-space:nowrap;overflow-wrap:normal}" in css
    assert ".v61-toolbar,.v61-tabs,.v65-controls,.market-tabs{flex-wrap:nowrap" not in css
