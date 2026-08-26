from types import SimpleNamespace

import pytest

from app.services.provider_routing import normalize_symbol,providers_for_market,route_candidates,select_execution_route


def profile(provider, *, connected=True, enabled=True, active=True, credentials=True, label=None):
    return SimpleNamespace(
        id=f'{provider.lower()}-1',
        provider=provider,
        account_label=label or provider,
        environment={'IBKR':'PAPER','MT5':'DEMO','BYBIT':'TESTNET'}.get(provider,''),
        last_connection_status='CONNECTED' if connected else 'FAILED',
        is_enabled=enabled,
        is_active=active,
        credentials_configured=credentials,
    )


def test_market_to_provider_mapping():
    assert providers_for_market('STOCK') == ('IBKR',)
    assert providers_for_market('ETF') == ('IBKR',)
    assert providers_for_market('FX') == ('MT5',)
    assert providers_for_market('METAL') == ('MT5',)
    assert providers_for_market('COMMODITY') == ('MT5',)
    assert providers_for_market('CRYPTO') == ('BYBIT',)


def test_symbol_normalization():
    assert normalize_symbol('FX','eur/usd') == 'EURUSD'
    assert normalize_symbol('CRYPTO','btc/usdt') == 'BTCUSDT'
    assert normalize_symbol('STOCK',' nvda ') == 'NVDA'


def test_router_selects_only_executable_matching_account():
    profiles=[profile('IBKR',connected=False,label='offline'),profile('MT5'),profile('IBKR',label='paper')]
    selected=select_execution_route('STOCK',profiles)
    assert selected is not None
    assert selected.provider == 'IBKR'
    assert selected.label == 'paper'
    assert selected.executable is True


def test_router_returns_none_when_matching_account_not_executable():
    assert select_execution_route('CRYPTO',[profile('BYBIT',credentials=False)]) is None


def test_candidates_exclude_wrong_asset_class():
    rows=route_candidates('FX',[profile('IBKR'),profile('MT5'),profile('BYBIT')])
    assert [row.provider for row in rows] == ['MT5']


def test_unsupported_market_rejected():
    with pytest.raises(ValueError):
        providers_for_market('OPTIONS')
