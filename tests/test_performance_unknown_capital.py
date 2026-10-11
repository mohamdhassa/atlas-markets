import asyncio
from types import SimpleNamespace as NS

import pytest
import app.api.routes_broker_native as route


@pytest.mark.parametrize('capitals,failed,expected', [
    ([None, None], False, None),
    ([100, None], False, None),
    ([], False, None),
    ([100, 200], False, 300),
    ([0], False, 0),
    ([100, 200], True, None),
])
def test_overall_capital_requires_complete_allocation(monkeypatch, capitals, failed, expected):
    profiles = [NS(id=str(i), user_id='owner', provider='MT5', credentials_configured=True,
                   account_label=str(i), environment='DEMO', simulation_capital_override_usd=value)
                for i, value in enumerate(capitals)]

    class Broker:
        def __init__(self, profile): self.profile = profile
        async def account(self):
            if failed and self.profile.id == '1': raise RuntimeError('unavailable')
            return {'equity': 500, 'margin_free': 400}
        async def history_deals(self, days):
            return {'list': [{'symbol': 'EURUSD', 'entry': 1, 'profit': 10,
                              'commission': -1, 'swap': 0, 'time': 1791555181, 'type': 1}]}

    monkeypatch.setattr(route, '_accounts', lambda db, user: profiles)
    monkeypatch.setattr(route, '_symbol_market_map', lambda *args: {})
    monkeypatch.setattr(route, '_mt5', Broker)
    monkeypatch.setattr(route, '_trade_context', lambda *args: None)
    result = asyncio.run(route.broker_performance.__wrapped__(days=30, user=NS(role='ADMIN'), db=None))
    overall = result['overall']
    assert overall['starting_capital'] == expected
    assert overall['strategy_value'] == (None if expected is None else expected + overall['realized_pnl'])
    assert overall['realized_pnl'] == 9 * (len(capitals) - int(failed))
    assert overall['broker_equity'] == 500 * (len(capitals) - int(failed))
    for account in result['accounts']:
        start = account['starting_capital']
        assert account['strategy_value'] == (None if start is None else start + 9)
