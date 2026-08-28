from types import SimpleNamespace

from app.services.autotrade_readiness import _ibkr_quote_price, _provider_execution_blockers


def _profile(provider: str):
    return SimpleNamespace(provider=provider)


def test_bybit_is_not_execution_certified():
    assert _provider_execution_blockers(_profile('BYBIT')) == ['PROVIDER_EXECUTION_NOT_CERTIFIED']


def test_mt5_has_no_provider_certification_blocker():
    assert _provider_execution_blockers(_profile('MT5')) == []


def test_ibkr_has_no_provider_certification_blocker():
    assert _provider_execution_blockers(_profile('IBKR')) == []


def test_ibkr_buy_quote_falls_back_to_last_when_ask_is_missing():
    assert _ibkr_quote_price({'ask': None, 'last': 645.25, 'bid': 645.10}, 'BUY') == 645.25


def test_ibkr_sell_quote_falls_back_to_last_when_bid_is_missing():
    assert _ibkr_quote_price({'bid': None, 'last': '645.20', 'ask': 645.30}, 'SELL') == 645.20


def test_ibkr_quote_returns_zero_when_no_usable_price_exists():
    assert _ibkr_quote_price({'bid': None, 'last': None, 'ask': None}, 'BUY') == 0.0
