from pathlib import Path


def test_desktop_sidebar_uses_viewport_height_and_internal_navigation_scroll():
    css = Path("app/static/responsive-v1.css").read_text()

    assert "@media(min-width:761px)" in css
    assert ".sidebar{height:100dvh;max-height:100dvh;overflow:hidden}" in css
    assert ".nav-list{flex:1;min-height:0;overflow-y:auto" in css
    assert ".sidebar-bottom{flex:0 0 auto}" in css


def test_sidebar_fix_has_a_new_cache_version():
    index = Path("app/static/index.html").read_text()

    assert "responsive-v1.css?v=1.2" in index
