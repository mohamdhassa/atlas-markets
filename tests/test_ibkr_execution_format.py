import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace as NS

import pytest
import app.api.routes_broker_native as route


@pytest.mark.parametrize('value,zone,expected', [
    ('20261012  13:30:18', 'Etc/UTC', '2026-10-12T13:30:18+00:00'),
    ('20261012 13:30:18', 'Etc/UTC', '2026-10-12T13:30:18+00:00'),
    ('20261012 09:30:18', 'America/New_York', '2026-10-12T13:30:18+00:00'),
    ('20261012 09:30:18 US/Eastern', 'Etc/UTC', '2026-10-12T13:30:18+00:00'),
    ('20261012-13:30:18', 'America/New_York', '2026-10-12T13:30:18+00:00'),
    ('2026-10-12T09:30:18-04:00', 'Etc/UTC', '2026-10-12T13:30:18+00:00'),
])
def test_execution_formats_use_explicit_timezones(value, zone, expected):
    actual = route._execution_time_ms({'time': value}, zone)
    assert actual == int(datetime.fromisoformat(expected).timestamp() * 1000)


def test_unknown_and_ambiguous_times_remain_unknown():
    for value, zone in [('bad', 'Etc/UTC'), ('20261012 13:30:18', 'Not/AZone'),
                        ('20261101 01:30:18', 'America/New_York'),
                        ('20260308 02:30:18', 'America/New_York')]:
        assert route._execution_time_ms({'time': value}, zone) == 0
    assert route._execution_time_ms({'time': 'bad', 'timestamp': 1791811818}) == 1791811818000


def test_split_protective_fills_have_side_time_and_entry_context(monkeypatch):
    profile = NS(id='paper', user_id='owner', provider='IBKR', environment='PAPER',
                 credentials_configured=True, account_label='Paper', simulation_capital_override_usd=None)
    history = [
        dict(symbol='META', side='SLD', quantity=62, price=718.84,
             time='20261009  18:42:32', order_id=214, pnl_available=False),
        dict(symbol='META', side='BOT', quantity=40, price=732.82,
             time='20261012  13:30:18', order_id=228, execution_id='fill-1',
             realized_pnl=-561.437733, pnl_available=True, commission=1.00012),
        dict(symbol='META', side='BOT', quantity=22, price=732.76,
             time='20261012  13:30:19', order_id=228, execution_id='fill-2',
             realized_pnl=-306.920753, pnl_available=True, commission=0.000066),
    ]
    class Broker:
        async def account(self): return {'equity': 1000, 'available': 500}
        async def executions(self, days): return {'list': history}
    class DB:
        def scalars(self, query): return NS(all=lambda: [])
    monkeypatch.setattr(route, '_accounts', lambda *args: [profile])
    monkeypatch.setattr(route, '_symbol_market_map', lambda *args: {})
    monkeypatch.setattr(route, '_ibkr', lambda *args: Broker())
    monkeypatch.setattr(route, '_creds', lambda *args: {'account_id': 'DU_TEST'})
    monkeypatch.setattr(route, '_trade_context', lambda *args: None)
    monkeypatch.setattr(route, 'get_settings', lambda: NS(ibkr_execution_timezone='Etc/UTC'))
    result = asyncio.run(route.broker_performance.__wrapped__(days=30, user=NS(role='ADMIN'), db=DB()))
    closed = sorted((r for r in result['trades'] if r['pnl_available']), key=lambda r: r['time'])
    assert len(closed) == 2
    assert all(r['side'] == 'BUY' and r['entry_price'] == 718.84 and r['duration_seconds'] > 0 for r in closed)
    assert [r['closed_at_iso'] for r in closed] == ['2026-10-12T13:30:18+00:00', '2026-10-12T13:30:19+00:00']
    assert sum(r['quantity'] for r in closed) == 62
    assert result['overall']['realized_pnl'] == -868.36
    assert [r['commission'] for r in closed] == [1.00012, 0.000066]
    assert [r['execution_id'] for r in closed] == ['fill-1', 'fill-2']
