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
    assert status['providers']['BYBIT']['simulation_certification'] == 'CERTIFIED_TESTNET_DEMO_SPOT'
    assert 'BYBIT_PROVIDER_RESTRICTION_10024' not in status['providers']['BYBIT']['blockers']
    assert 'LIVE_BYBIT_EXECUTION_PATH_NOT_CERTIFIED' in status['providers']['BYBIT']['blockers']
    assert status['providers']['TWELVE_DATA']['live_certification'] == 'NOT_APPLICABLE'
    assert all(not status['providers'][p]['live_execution_allowed'] for p in ('MT5', 'IBKR', 'BYBIT', 'TWELVE_DATA'))


def test_bybit_simulation_certification_does_not_unlock_live_money():
    status = _live_certification_status()
    bybit = status['providers']['BYBIT']
    assert bybit['simulation_certification'] == 'CERTIFIED_TESTNET_DEMO_SPOT'
    assert bybit['live_certification'] == 'NOT_CERTIFIED'
    assert bybit['live_execution_allowed'] is False
    assert status['status'] == 'LOCKED'


def test_legacy_live_certification_module_is_not_runtime_loaded():
    root = Path(__file__).resolve().parents[1]
    index = (root / 'app/static/index.html').read_text(encoding='utf-8')
    core = (root / 'app/static/atlas-core.js').read_text(encoding='utf-8')
    assert '/static/atlas-core.js?v=53.0' in index
    assert '/static/phase49-live-certification.js' not in index
    assert 'TESTNET' in core and 'DEMO' in core
    assert 'certify-bybit-test-order' in core
