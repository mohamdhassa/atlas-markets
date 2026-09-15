from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def test_frontend_entrypoint_uses_consolidated_core_only():
    html = (STATIC / "index.html").read_text()
    assert '/static/app.js?v=53.0' in html
    assert '/static/atlas-core.js?v=53.0' in html
    assert 'phase50-operational-parity.js' not in html
    assert 'phase51-integration-architecture-fix.js' not in html
    assert 'phase52-bybit-operational-parity.js' not in html


def test_operations_exposes_guarded_bybit_certification():
    js = (STATIC / "atlas-core.js").read_text()
    assert "/certify-bybit-test-order" in js
    assert "/reconcile-bybit-spot-certification" in js
    assert "TESTNET" in js and "DEMO" in js
    assert "state.user?.role==='ADMIN'" in js
    assert "confirm(" in js


def test_core_uses_live_operations_and_account_state():
    js = (STATIC / "atlas-core.js").read_text()
    assert "api('/accounts')" in js
    assert "api('/automation/state')" in js
    assert "api('/automation/actions?limit=100')" in js
    assert "/bybit-spot-state" in js


def test_legacy_provider_architecture_files_remain_available_during_migration():
    # The consolidated entrypoint no longer executes phase scripts, but keeping the
    # files temporarily gives us a rollback/reference path while backend/provider
    # modules are migrated into the core UI.
    assert (STATIC / "phase50-operational-parity.js").exists()
    assert (STATIC / "phase51-integration-architecture-fix.js").exists()
