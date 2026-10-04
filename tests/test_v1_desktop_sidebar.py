from pathlib import Path


def test_desktop_sidebar_is_fixed_while_main_page_scrolls():
    css = Path("app/static/responsive-v1.css").read_text()

    assert "@media(min-width:761px)" in css
    assert ".sidebar{position:fixed;inset:0 auto 0 0;width:260px;height:100dvh" in css
    assert ".main-area{margin-left:260px;width:calc(100% - 260px);min-height:100dvh}" in css
    assert ".nav-list{flex:1;min-height:0;overflow-y:auto" in css
    assert ".sidebar-bottom{flex:0 0 auto}" in css


def test_sidebar_fix_has_a_new_cache_version():
    index = Path("app/static/index.html").read_text()

    assert "responsive-v1.css?v=1.5" in index
