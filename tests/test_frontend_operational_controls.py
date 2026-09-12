from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def test_operations_exposes_safe_admin_controls():
    js = (STATIC / "phase50-operational-parity.js").read_text()
    assert "/automation/kill" in js
    assert "/automation/restart" in js
    assert "/automation/scan-now" in js
    assert "method:'PUT'" in js
    assert "state.user?.role!=='ADMIN'" in js
    assert "Live Money" in js


def test_ibkr_frontend_uses_current_oracle_gateway_architecture():
    js = (STATIC / "phase51-integration-architecture-fix.js").read_text()
    assert "Oracle Linux execution host" in js
    assert "IB Gateway :4002" in js
    assert "localhost:8766" in js


def test_phase51_is_loaded_after_operations():
    html = (STATIC / "index.html").read_text()
    assert "phase50-operational-parity.js?v=50.1" in html
    assert "phase51-integration-architecture-fix.js?v=51.0" in html
    assert html.index("phase50-operational-parity.js") < html.index("phase51-integration-architecture-fix.js")
