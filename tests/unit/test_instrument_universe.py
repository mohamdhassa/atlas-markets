from types import SimpleNamespace

from app.services.instrument_universe import STARTER_UNIVERSE,build_universe,starter_symbols


def profile(provider, *, suffix='1', connected=True, enabled=True, active=True, credentials=True):
    return SimpleNamespace(
        id=f'{provider.lower()}-{suffix}',
        provider=provider,
        account_label=f'{provider} {suffix}',
        environment={'IBKR':'PAPER','MT5':'DEMO','BYBIT':'TESTNET'}.get(provider,''),
        last_connection_status='CONNECTED' if connected else 'FAILED',
        is_enabled=enabled,
        is_active=active,
        credentials_configured=credentials,
    )


def strategy(profile_id, market, symbol, mode='WATCH', enabled=True):
    return SimpleNamespace(profile_id=profile_id,market=market,symbol=symbol,mode=mode,enabled=enabled)


def test_starter_universe_spans_all_execution_markets():
    assert set(STARTER_UNIVERSE) == {'STOCK','ETF','FX','METAL','COMMODITY','CRYPTO'}
    assert ('STOCK','NVDA') in starter_symbols()
    assert ('FX','EURUSD') in starter_symbols()
    assert ('CRYPTO','BTCUSDT') in starter_symbols()


def test_starter_symbols_can_be_filtered_by_market():
    rows=starter_symbols(['ETF'])
    assert rows == [('ETF','SPY'),('ETF','QQQ'),('ETF','IWM')]


def test_universe_routes_each_asset_class_to_connected_provider():
    profiles=[profile('IBKR'),profile('MT5'),profile('BYBIT')]
    rows=build_universe(profiles,[])
    by_key={(x.market,x.symbol):x for x in rows}
    assert by_key[('STOCK','NVDA')].provider == 'IBKR'
    assert by_key[('FX','EURUSD')].provider == 'MT5'
    assert by_key[('METAL','XAUUSD')].provider == 'MT5'
    assert by_key[('CRYPTO','BTCUSDT')].provider == 'BYBIT'
    assert by_key[('STOCK','NVDA')].executable_route is True


def test_existing_strategy_is_included_even_when_not_in_starter_list():
    profiles=[profile('IBKR')]
    rows=build_universe(profiles,[strategy('ibkr-1','STOCK','AMD','SIGNALS')],markets=['STOCK'])
    amd=next(x for x in rows if x.symbol=='AMD')
    assert amd.configured is True
    assert amd.strategy_mode == 'SIGNALS'
    assert amd.provider == 'IBKR'


def test_configured_strategy_reports_assigned_profile_health_not_other_profile_health():
    profiles=[profile('IBKR',suffix='offline',connected=False),profile('IBKR',suffix='healthy')]
    rows=build_universe(profiles,[strategy('ibkr-offline','STOCK','NVDA')],markets=['STOCK'])
    nvda=next(x for x in rows if x.symbol=='NVDA')
    assert nvda.profile_id == 'ibkr-offline'
    assert nvda.executable_route is False


def test_unconfigured_item_has_no_executable_route_when_credentials_missing():
    rows=build_universe([profile('BYBIT',credentials=False)],[],markets=['CRYPTO'])
    btc=next(x for x in rows if x.symbol=='BTCUSDT')
    assert btc.provider is None
    assert btc.executable_route is False
    assert btc.route_candidates == 1
