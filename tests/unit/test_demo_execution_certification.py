import pytest

from app.services.demo_execution_certification import _select_certifiable


def _row(**overrides):
    row = {
        'market': 'FX',
        'symbol': 'AUDUSD',
        'provider': 'MT5',
        'preflight': 'PASS',
        'reason': None,
    }
    row.update(overrides)
    return row


def test_select_certifiable_accepts_single_mt5_preflight_pass():
    assert _select_certifiable([_row()], market='fx', symbol='aud/usd')['symbol'] == 'AUDUSD'


def test_select_certifiable_rejects_non_pass_preflight():
    with pytest.raises(RuntimeError, match='PREFLIGHT_NOT_PASS'):
        _select_certifiable([_row(preflight='BLOCK', reason='BROKER_PREFLIGHT_REJECTED')], market='FX', symbol='AUDUSD')


def test_select_certifiable_rejects_ibkr_during_mt5_certification_stage():
    with pytest.raises(RuntimeError, match='CERTIFICATION_STAGE_MT5_ONLY'):
        _select_certifiable([_row(provider='IBKR')], market='FX', symbol='AUDUSD')


def test_select_certifiable_rejects_symbol_not_in_current_preflight():
    with pytest.raises(RuntimeError, match='SYMBOL_NOT_IN_PREFLIGHT'):
        _select_certifiable([_row()], market='FX', symbol='EURUSD')
