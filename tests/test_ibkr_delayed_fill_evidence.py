"""Delayed fills must remain usable for protection after broker history disappears."""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace as NS

import pytest

from app.services import ibkr_position_manager as manager
from app.services.ibkr_entry_fill import execution_fill, saved_execution_fill
from app.services.ibkr_ledger_history import merge_saved_fills
from app.services.ibkr_protection_levels import fill_anchored_levels


def setup_entry():
    row = NS(id=uuid.uuid4(), provider='IBKR', environment='PAPER', status='SUBMITTED',
             reason='BROKER_FILL_NOT_CONFIRMED', side='BUY', symbol='TSLA', quantity=128,
             broker_order_id='491', user_id='u', broker_profile_id='p', market='STOCK',
             created_at=datetime(2026, 10, 14, 20, 19, 47, tzinfo=timezone.utc),
             raw_json=json.dumps({'preflight': {'request': {
                 'reference_price': 367.28, 'stop_loss': 361.7708, 'take_profit': 378.2984}},
                 'result': {'status': 'SUBMITTED', 'broker_result': {
                     'account_id': 'DU_TEST', 'final_status': {'order_id': 491, 'status': {
                         'order_id': 491, 'status': 'PreSubmitted', 'filled': 0,
                         'remaining': 128, 'avg_fill_price': 0}}}}}))
    fills = [dict(execution_id='fill-1', order_id=491, account='DU_TEST', symbol='TSLA',
                  sec_type='STK', side='BOT', quantity=64, price=360,
                  time='20261015-13:30:00'),
             dict(execution_id='fill-2', order_id=491, account='DU_TEST', symbol='TSLA',
                  sec_type='STK', side='BOT', quantity=64, price=362,
                  time='20261015-13:30:01')]
    return row, fills


class DB:
    def flush(self): pass
    def commit(self): pass
    def refresh(self, entry): pass


def test_delayed_fill_reconciles_persists_and_protects_after_history_restart(monkeypatch):
    row, fills = setup_entry()
    original = json.loads(row.raw_json)
    monkeypatch.setattr(manager, '_submitted_entries', lambda *args: [row])
    assert manager._reconcile_submitted_entries(DB(), NS(), fills, 'DU_TEST') == [row]
    assert row.status == 'EXECUTED'
    saved = json.loads(row.raw_json)
    assert saved['preflight'] == original['preflight']
    assert saved['result'] == original['result']  # Do not fabricate a Filled callback.
    assert saved_execution_fill(row, saved)['price'] == 361

    # The subsequent bridge has no status/history; retained callbacks still prove price.
    assert manager._entry_fill_verified(row, {}, 'LONG', 128)[0]
    class Broker:
        calls = 0
        async def ensure_protection(self, payload):
            self.calls += 1
            assert payload['allow_submit'] is (self.calls == 1)
            assert payload['stop_loss'] == pytest.approx(355.4908)
            assert payload['take_profit'] == pytest.approx(372.0184)
            assert json.loads(row.raw_json)['native_protection_levels']['fill_price'] == 361
            return {'status': 'PROTECTED', 'simulation': True,
                    'oca_group': 'atlas-protect-' + row.id.hex, 'order_ids': [500, 501]}
    broker = Broker()
    item = dict(symbol='TSLA', position_side='LONG', quantity=128)
    assert asyncio.run(manager._ensure_native_protection(DB(), row, broker, item, 'DU_TEST'))['status'] == 'PROTECTED'
    assert asyncio.run(manager._ensure_native_protection(DB(), row, broker, item, 'DU_TEST'))['status'] == 'PROTECTED'

    profile = NS(id='p', user_id='u', environment='PAPER', account_label='Paper')
    ledger = merge_saved_fills([], [row, row], profile, 'DU_TEST')
    assert len(ledger) == 1 and ledger[0]['execution_price'] == 361
    assert ledger[0]['time_source'] == 'PERSISTED_BROKER_EXECUTION_TIME'
    assert ledger[0]['time'] > int(row.created_at.timestamp() * 1000)
    assert ledger[0]['pnl'] is None and ledger[0]['commission'] is None


def test_existing_position_reconciled_entry_can_gain_real_execution_evidence():
    row, fills = setup_entry()
    manager._mark_reconciled(row, 'IBKR_CURRENT_POSITION_FALLBACK', {'live_avg_cost': 999})
    with pytest.raises(ValueError, match='PROTECTION_FILL_PRICE_UNVERIFIED'):
        fill_anchored_levels(row)
    assert manager._save_entry_execution_evidence(row, fills, 'DU_TEST')
    assert fill_anchored_levels(row)['fill_price'] == 361
    # Empty history on a later scan never erases the saved callbacks.
    before = row.raw_json
    assert not manager._save_entry_execution_evidence(row, [], 'DU_TEST')
    assert row.raw_json == before


def test_duplicate_callbacks_do_not_inflate_a_partial_fill():
    row, fills = setup_entry()
    assert manager._reconciliation_evidence(row, [fills[0], fills[0]], 'DU_TEST') is None
    assert execution_fill(row, [fills[0], fills[0]], 'DU_TEST') is None
    assert execution_fill(row, fills + fills, 'DU_TEST')['price'] == 361
    assert manager._reconciliation_evidence(row, fills + fills, 'DU_TEST')['quantity'] == 128


@pytest.mark.parametrize('field,value', [
    ('price', 0), ('price', float('nan')), ('price', float('inf')),
    ('quantity', -64), ('quantity', float('nan')), ('quantity', 65),
    ('account', 'OTHER'), ('order_id', 492), ('symbol', 'NVDA'),
    ('side', 'SLD'), ('sec_type', 'OPT'), ('execution_id', ''),
    ('time', ''), ('time', '20261013-13:30:00'), ('time', '20991015-13:30:00'),
])
def test_unverified_or_conflicting_fills_cannot_supply_protection_price(field, value):
    row, fills = setup_entry()
    fills[0][field] = value
    assert execution_fill(row, fills, 'DU_TEST') is None
    assert not manager._save_entry_execution_evidence(row, fills, 'DU_TEST')


def test_conflicting_duplicate_execution_identity_blocks():
    row, fills = setup_entry()
    assert execution_fill(row, fills + [{**fills[0], 'price': 999}], 'DU_TEST') is None
    assert manager._reconciliation_evidence(row, fills + [{**fills[0], 'price': 999}], 'DU_TEST') is None


def test_short_fractional_fills_and_account_scope():
    row, fills = setup_entry()
    row.side, row.quantity = 'SELL', 0.1234
    fills = [{**fills[0], 'side': 'SLD', 'quantity': 0.1234}]
    assert execution_fill(row, fills, 'DU_TEST')['quantity'] == 0.1234
    assert execution_fill(row, fills, '') is None
    row.environment = 'LIVE'
    assert execution_fill(row, fills, 'DU_TEST') is None


def test_saved_fill_is_revalidated_instead_of_trusting_cached_aggregate():
    row, fills = setup_entry()
    row.status = 'EXECUTED'
    assert manager._save_entry_execution_evidence(row, fills, 'DU_TEST')
    raw = json.loads(row.raw_json)
    assert saved_execution_fill(row, raw, 'OTHER') is None
    raw['entry_execution_evidence']['executions'][0]['price'] = 0
    assert saved_execution_fill(row, raw) is None
