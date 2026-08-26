import asyncio
from types import SimpleNamespace

from app.services.instrument_universe import UniverseItem
from app.services.instrument_validation import validate_instrument


def item(market='STOCK', symbol='AAPL'):
    return UniverseItem(
        market=market,
        symbol=symbol,
        configured=False,
        strategy_mode=None,
        strategy_enabled=None,
        profile_id='p1',
        provider='OTHER',
        environment='PAPER',
        executable_route=True,
        route_candidates=1,
    )


def test_validation_rejects_unsupported_provider():
    profile = SimpleNamespace(id='p1', provider='OTHER')
    result = asyncio.run(validate_instrument(profile, item()))
    assert result.supported is False
    assert result.reason == 'UNSUPPORTED_PROVIDER'
    assert result.symbol == 'AAPL'


def test_validation_result_preserves_market_and_profile():
    profile = SimpleNamespace(id='abc', provider='OTHER')
    result = asyncio.run(validate_instrument(profile, item('ETF', 'SPY')))
    assert result.market == 'ETF'
    assert result.profile_id == 'abc'
