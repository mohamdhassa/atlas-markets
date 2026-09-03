from pathlib import Path

from app.api.routes_release import _live_certification_status


def test_live_execution_providers_are_separately_locked():
    status = _live_certification_status()
    assert status['status'] == 'LOCKED'
    assert status['execution_providers_required'] == 3
    assert status['execution_providers_certified'] == 0
    assert status['all_execution_providers_certified'] is False
    assert status['providers']['MT5']['simulation_certification'] == 'CERTIFIED_DEMO'
    assert status['providers']['MT5']['live_certification'] == 'NOT_CERTIFIED'
    assert status['providers']['IBKR']['simulation_certification'] == 'CERTIFIED_PAPER'
    assert status['providers']['IBKR']['live_certification'] == 'NOT_CERTIFIED'
    assert status['providers']['BYBIT']['simulation_certification'] == 'PROVIDER_BLOCKED_10024'
    assert 'BYBIT_PROVIDER_RESTRICTION_10024' in status['providers']['BYBIT']['blockers']
    assert status['providers']['TWELVE_DATA']['live_certification'] == 'NOT_APPLICABLE'
    assert all(not status['providers'][p]['live_execution_allowed'] for p in ('MT5', 'IBKR', 'BYBIT', 'TWELVE_DATA'))


def test_live_certification_frontend_module_is_loaded():
    root = Path(__file__).resolve().parents[1]
    index = (root / 'app/static/index.html').read_text(encoding='utf-8')
    script = (root / 'app/static/phase49-live-certification.js').read_text(encoding='utf-8')
    assert '/static/phase49-live-certification.js?v=49.0' in index
    assert '/release/readiness' in script
    assert 'Live provider certification' in script
    assert 'Simulation certification is tracked separately from real-money certification.' in script
