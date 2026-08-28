from types import SimpleNamespace

from app.services.autotrade_readiness import _ibkr_quote_price, _portfolio_guard, _provider_execution_blockers


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


def test_portfolio_guard_allows_position_inside_limits():
    assert _portfolio_guard(equity=1_000_000, existing_positions=0, existing_gross_notional=0, reserved_new_notional=200_000, reserved_new_positions=1, proposed_notional=200_000) == []


def test_portfolio_guard_blocks_projected_gross_exposure_over_half_equity():
    blockers = _portfolio_guard(equity=1_000_000, existing_positions=0, existing_gross_notional=0, reserved_new_notional=400_000, reserved_new_positions=2, proposed_notional=200_000)
    assert 'PORTFOLIO_GROSS_EXPOSURE_LIMIT' in blockers


def test_portfolio_guard_blocks_more_than_five_positions_per_account():
    blockers = _portfolio_guard(equity=1_000_000, existing_positions=2, existing_gross_notional=100_000, reserved_new_notional=100_000, reserved_new_positions=3, proposed_notional=10_000)
    assert 'PORTFOLIO_POSITION_LIMIT' in blockers


def test_portfolio_guard_blocks_when_equity_is_unavailable():
    assert _portfolio_guard(equity=0, existing_positions=0, existing_gross_notional=0, reserved_new_notional=0, reserved_new_positions=0, proposed_notional=1_000) == ['PORTFOLIO_EQUITY_UNAVAILABLE']
