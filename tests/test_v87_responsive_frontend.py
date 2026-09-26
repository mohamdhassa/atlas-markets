from pathlib import Path


STATIC = Path("app/static")


def test_responsive_assets_are_loaded_last():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = "/static/atlas-responsive-v87.css?v=87.0"
    js = "/static/atlas-responsive-v87.js?v=87.0"
    assert css in html
    assert js in html
    assert html.index(css) > html.index("/static/news-decision-context-v67.css")
    assert html.index(js) > html.index("/static/live-activity-v75.js")


def test_responsive_css_covers_phone_desktop_and_accessibility():
    css = (STATIC / "atlas-responsive-v87.css").read_text(encoding="utf-8")
    for contract in (
        "@media(max-width:1200px)",
        "@media(max-width:760px)",
        "@media(max-width:480px)",
        "@media(hover:none) and (pointer:coarse)",
        "@media(prefers-reduced-motion:reduce)",
        ".table-wrap",
        ".atlas-sidebar-backdrop",
        "env(safe-area-inset-bottom)",
        ":focus-visible",
    ):
        assert contract in css


def test_responsive_runtime_closes_and_labels_mobile_navigation():
    source = (STATIC / "atlas-responsive-v87.js").read_text(encoding="utf-8")
    for contract in (
        "aria-expanded",
        "aria-controls",
        "Escape",
        "atlas-nav-open",
        "MutationObserver",
        "Scrollable data table",
    ):
        assert contract in source
