from pathlib import Path


STATIC = Path("app/static")


def test_responsive_assets_load_last_and_boot_once_after_decorators():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert '/static/responsive-v1.css?v=1.1' in html
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
