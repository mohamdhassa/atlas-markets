import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace as NS

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models.automation import AutomationAction
from app.db.models.bybit_inventory import BybitManagedInventory
from app.services import bybit_spot_execution as spot


@pytest.fixture
def db():
    engine = create_engine('sqlite://')
    AutomationAction.__table__.create(engine)
    BybitManagedInventory.__table__.create(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def profile():
    return NS(id=uuid.uuid4(), user_id=uuid.uuid4(), environment='TESTNET',
              execution_certified=True, execution_certification_buy_passed=True,
              execution_certification_sell_passed=True, is_enabled=True,
              is_active=True, credentials_configured=True, last_connection_status='CONNECTED')


def action(db, profile, **changes):
    values = dict(id=uuid.uuid4(), scan_id=uuid.uuid4(), user_id=profile.user_id,
                  broker_profile_id=profile.id, provider='BYBIT', environment='TESTNET',
                  market='CRYPTO', symbol='BNBUSDT', side='BUY', status='SUBMITTED',
                  quantity=.25, broker_order_id='accepted-order',
                  created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    values.update(changes)
    row = AutomationAction(**values)
    db.add(row)
    db.commit()
    return row


def execute(db, profile, side='BUY', symbol='BNBUSDT'):
    return asyncio.run(spot.execute_managed_spot_order(
        db, profile=profile, user_id=profile.user_id, symbol=symbol, side=side, quantity=.25))


@pytest.mark.parametrize('side', ['BUY', 'SELL'])
def test_unresolved_submission_blocks_repeated_orders_before_broker_or_inventory_reads(db, profile, monkeypatch, side):
    pending = action(db, profile, broker_order_id=None)
    def forbidden(*args):
        pytest.fail('No broker or inventory read is allowed before the pending guard')
    monkeypatch.setattr(spot, '_bybit_client', forbidden)
    monkeypatch.setattr(spot, 'managed_inventory', forbidden)
    for _ in range(2):
        result = execute(db, profile, side=side, symbol='bnb/usdt')
        assert result['status'] == 'BLOCK'
        assert result['reason'] == 'BYBIT_SUBMISSION_RECONCILIATION_REQUIRED'
        assert result['pending_action_id'] == str(pending.id)
        assert result['pending_broker_order_id'] is None
    assert pending.status == 'SUBMITTED'


@pytest.mark.parametrize('changes', [
    {'user_id': uuid.uuid4()}, {'broker_profile_id': uuid.uuid4()},
    {'provider': 'IBKR'}, {'environment': 'DEMO'}, {'symbol': 'BTCUSDT'},
    {'status': 'CANCELLED'}, {'status': 'EXECUTED'},
])
def test_guard_is_scoped_and_resolved_actions_do_not_block(db, profile, monkeypatch, changes):
    action(db, profile, **changes)
    # A matching owned position provides the next existing guard, without any order.
    monkeypatch.setattr(spot, 'managed_inventory', lambda *args: NS(managed_quantity=.25))
    assert execute(db, profile)['reason'] == 'ATLAS_MANAGED_POSITION_ALREADY_OPEN'


@pytest.mark.parametrize('read_fails', [False, True])
def test_accepted_identity_survives_missing_fill_then_blocks_another_submission(db, profile, monkeypatch, read_fails):
    calls = []
    class Client:
        async def place_test_spot_market_order(self, **kwargs):
            calls.append(kwargs)
            return {'orderId': 'accepted-order', 'orderLinkId': kwargs['order_link_id']}
    async def verify(*args):
        if read_fails:
            raise TimeoutError('private connection information')
        return None
    monkeypatch.setattr(spot, '_bybit_client', lambda *args: Client())
    monkeypatch.setattr(spot, '_verify_spot_fill', verify)
    result = execute(db, profile)
    assert result['status'] == 'SUBMITTED'
    assert result['broker_order_id'] == 'accepted-order'
    assert result['order_link_id'] == calls[0]['order_link_id']
    assert result['verification_error'] == ('TimeoutError' if read_fails else None)
    assert 'private connection' not in str(result)
    assert db.query(BybitManagedInventory).count() == 0
    # Model the scan's persisted outcome, then use a new session as after a restart.
    action(db, profile, raw_json=str(result))
    with Session(db.bind) as restarted:
        assert execute(restarted, profile)['reason'] == 'BYBIT_SUBMISSION_RECONCILIATION_REQUIRED'
    assert len(calls) == 1
