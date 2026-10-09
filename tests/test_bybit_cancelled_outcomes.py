import asyncio
import json
import uuid
from types import SimpleNamespace as NS

import pytest

from test_bybit_pending_submission import db, profile, action, execute
from app.db.models.bybit_inventory import BybitManagedInventory
from app.services import bybit_spot_execution as spot


def cancelled(**changes):
    row = dict(orderId='accepted-order', orderLinkId='atlas-auto-test',
               symbol='BNBUSDT', side='Buy', orderStatus='Cancelled', cumExecQty='0',
               rejectReason='EC_NoImmediateQtyToFill', cancelType='UNKNOWN')
    row.update(changes)
    return row


@pytest.mark.parametrize('changes', [
    {'orderId': 'wrong'}, {'orderLinkId': 'wrong'}, {'symbol': 'BTCUSDT'},
    {'side': 'Sell'}, {'orderStatus': 'Filled'}, {'cumExecQty': '.01'},
    {'cumExecQty': '-1'}, {'cumExecQty': 'nan'}, {'cumExecQty': 'inf'},
    {'cumExecQty': None}, {'cumExecQty': ''}, {'cumExecQty':'1e-400'},
])
def test_only_exact_zero_fill_cancellation_is_terminal(changes):
    assert not spot._zero_fill_cancellation(cancelled(**changes), symbol='BNBUSDT',
        side='BUY', order_id='accepted-order', order_link_id='atlas-auto-test')


def test_polling_returns_cancelled_outcome_without_waiting_for_a_fill():
    class Client:
        async def spot_order_history(self, limit):
            return {'list': [cancelled()]}
    assert asyncio.run(spot._verify_spot_fill(Client(), 'atlas-auto-test')) == cancelled()


@pytest.mark.parametrize('side', ['BUY', 'SELL'])
def test_new_cancelled_order_never_changes_managed_inventory(db, profile, monkeypatch, side):
    if side == 'SELL':
        db.add(BybitManagedInventory(user_id=profile.user_id, broker_profile_id=profile.id,
            symbol='BNBUSDT', managed_quantity=.25, average_entry_price=700,
            cumulative_bought_quantity=.25, cumulative_sold_quantity=0))
        db.commit()
    class Client:
        async def wallet(self):
            return {'list':[{'coin':[{'coin':'BNB','walletBalance':'.25'}]}]}
        async def place_test_spot_market_order(self, **kwargs):
            return {'orderId':'accepted-order'}
    async def verify(client, link):
        return cancelled(orderLinkId=link, side=side.title())
    monkeypatch.setattr(spot, '_bybit_client', lambda *args:Client())
    monkeypatch.setattr(spot, '_verify_spot_fill', verify)
    result = execute(db, profile, side=side)
    assert result['status'] == 'CANCELLED'
    assert result['reason'] == 'BROKER_ZERO_FILL_CANCELLED'
    assert result['broker_order_id'] == 'accepted-order'
    assert result['broker_result']['terminal_order']['rejectReason'] == 'EC_NoImmediateQtyToFill'
    inventory = spot.managed_inventory(db, profile.id, 'BNBUSDT')
    if side == 'BUY':
        assert inventory is None
    else:
        assert inventory.managed_quantity == .25
        assert inventory.cumulative_sold_quantity == 0


@pytest.mark.parametrize('response', ['cancelled', 'empty', 'partial', 'wrong', 'timeout'])
def test_reconciliation_preserves_audit_and_only_updates_verified_cancellation(db, profile, monkeypatch, response):
    profile.provider = 'BYBIT'
    original = {'result': {'order_link_id':'atlas-auto-test'}, 'preflight': {'existing':'evidence'}}
    row = action(db, profile, raw_json=json.dumps(original))
    calls = []
    class Client:
        async def get(self, path, params):
            calls.append((path, params))
            if response == 'timeout': raise TimeoutError('private connection')
            if response == 'empty': return {'list':[]}
            if response == 'partial': return {'list':[cancelled(cumExecQty='.01')]}
            if response == 'wrong': return {'list':[cancelled(orderLinkId='other')]}
            return {'list':[cancelled()]}
    monkeypatch.setattr(spot, '_bybit_client', lambda *args:Client())
    result = asyncio.run(spot.reconcile_cancelled_submissions(
        db, profile=profile, user_id=profile.user_id, symbol='BNBUSDT'))
    db.commit()
    assert len(calls) == 1
    params = calls[0][1]
    assert params['orderId'] == row.broker_order_id
    assert params['endTime'] - params['startTime'] == 2*86400000
    assert 'private connection' not in str(result)
    if response == 'cancelled':
        assert row.status == 'CANCELLED'
        audit = json.loads(row.raw_json)
        assert audit['preflight'] == original['preflight']
        assert audit['result'] == original['result']
        assert audit['cancellation_reconciliation']['broker_order']['cumExecQty'] == '0'
        assert asyncio.run(spot.reconcile_cancelled_submissions(
            db, profile=profile, user_id=profile.user_id, symbol='BNBUSDT')) == []
    else:
        assert row.status == 'SUBMITTED'
        assert json.loads(row.raw_json) == original
    assert db.query(BybitManagedInventory).count() == 0


@pytest.mark.parametrize('changes', [
    {'user_id':uuid.uuid4()}, {'broker_profile_id':uuid.uuid4()},
    {'environment':'DEMO'}, {'provider':'IBKR'}, {'symbol':'BTCUSDT'}, {'status':'EXECUTED'},
])
def test_reconciliation_never_reads_or_updates_another_scope(db, profile, monkeypatch, changes):
    profile.provider = 'BYBIT'
    row = action(db, profile, **changes)
    def forbidden(*args): pytest.fail('No broker read for another scope')
    monkeypatch.setattr(spot, '_bybit_client', forbidden)
    assert asyncio.run(spot.reconcile_cancelled_submissions(
        db, profile=profile, user_id=profile.user_id, symbol='BNBUSDT')) == []
    assert row.status == changes.get('status','SUBMITTED')


def test_trade_attempt_reconciles_cancelled_pending_order_before_existing_inventory_guard(db, profile, monkeypatch):
    row = action(db, profile, raw_json=json.dumps({'result':{'order_link_id':'atlas-auto-test'}}))
    class Client:
        async def get(self, path, params): return {'list':[cancelled()]}
    monkeypatch.setattr(spot, '_bybit_client', lambda *args:Client())
    monkeypatch.setattr(spot, 'managed_inventory', lambda *args:NS(managed_quantity=.25))
    assert execute(db, profile)['reason'] == 'ATLAS_MANAGED_POSITION_ALREADY_OPEN'
    assert row.status == 'CANCELLED'


def test_missing_old_order_keeps_guard_after_other_cancellations_are_reconciled(db, profile, monkeypatch):
    old = action(db, profile, broker_order_id='missing-order', raw_json='{}')
    known = action(db, profile, raw_json=json.dumps({'result':{'order_link_id':'atlas-auto-test'}}))
    class Client:
        async def get(self, path, params):
            return {'list':[] if params['orderId']=='missing-order' else [cancelled()]}
        async def place_test_spot_market_order(self, **kwargs):
            pytest.fail('Unresolved old order must prevent placement')
    monkeypatch.setattr(spot, '_bybit_client', lambda *args:Client())
    result = execute(db, profile)
    assert result['reason'] == 'BYBIT_SUBMISSION_RECONCILIATION_REQUIRED'
    assert old.status == 'SUBMITTED'
    assert known.status == 'CANCELLED'
