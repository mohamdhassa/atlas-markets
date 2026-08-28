from types import SimpleNamespace

from app.services.autotrade_readiness import _provider_execution_blockers


def _profile(provider: str):
    return SimpleNamespace(provider=provider)


def test_bybit_is_not_execution_certified():
    assert _provider_execution_blockers(_profile('BYBIT')) == ['PROVIDER_EXECUTION_NOT_CERTIFIED']


def test_mt5_has_no_provider_certification_blocker():
    assert _provider_execution_blockers(_profile('MT5')) == []


def test_ibkr_has_no_provider_certification_blocker():
    assert _provider_execution_blockers(_profile('IBKR')) == []
