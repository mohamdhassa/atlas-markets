import copy
import json
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select
from app.db.models.ibkr_statement import IbkrStatementEvidence
from app.services.ibkr_closed_recovery import recover_closed_pair, recovered_row
from app.services.ibkr_ledger_history import merge_saved_fills
from app.api.routes_broker_native import _pair_execution_lots
from test_ibkr_statement_import import data, flex


def inputs(data):
    db, profile, (entry, close) = data
    # Original entry was accepted, never received a Filled callback, and filled
    # the next session. The status remains the legacy position reconciliation.
    raw = json.loads(entry.raw_json)
    raw['result']['broker_result']['final_status']['status']['status'] = 'PreSubmitted'
    raw['result']['broker_result']['final_status']['status']['filled'] = 0
    entry.raw_json = json.dumps(raw)
    entry.created_at -= timedelta(days=1)
    raw = json.loads(close.raw_json)
    raw['entry_action_id'] = str(entry.id)
    close.raw_json = json.dumps(raw)
    db.commit()
    xml = flex(dict(buySell='BUY', quantity='2', tradePrice='100',
        openCloseIndicator='O', fifoPnlRealized='0', ibOrderID='statement-entry',
        dateTime='20261009;100000'))
    executions = [dict(execution_id='exit-one', order_id=11, account='DU_TEST',
        symbol='MSFT', sec_type='STK', side='SLD', quantity=2, price=105,
        time='20261009 11:00:00', commission=1, commission_currency='USD',
        realized_pnl=8, pnl_available=True)]
    return dict(db=db, profile=profile, account_id='DU_TEST', entry=entry,
        exit_action=close, xml=xml, zone='UTC', trade_ids=['t0'],
        executions=executions, execution_zone='UTC', operator_id=uuid.uuid4())


def retained(db):
    return {str(r.action_id): json.loads(r.evidence_json)
        for r in db.scalars(select(IbkrStatementEvidence)).all()}


def test_preview_apply_restart_and_duplicate_preserve_original_audits(data):
    args = inputs(data)
    original = args['entry'].raw_json
    preview = recover_closed_pair(**args)
    assert not retained(args['db'])
    assert preview['opening']['statement_order_id'] == 'statement-entry'
    assert preview['opening']['broker_order_id'] == '10'
    assert preview['closing']['pnl'] == 8
    recover_closed_pair(**args, apply=True)
    args['db'].commit()
    recover_closed_pair(**args, apply=True)
    assert len(retained(args['db'])) == 2
    assert args['entry'].raw_json == original
    rows = merge_saved_fills([], [args['entry'], args['exit_action']], args['profile'],
        'DU_TEST', retained(args['db']))
    assert len(rows) == 2
    assert rows[0]['execution_price'] == 100 and not rows[0]['closed_trade']
    assert rows[1]['pnl'] == 8 and rows[1]['commission'] == 1
    live = [{**rows[1], 'quantity': 1}, {**rows[1], 'quantity': 1}]
    merged = merge_saved_fills(live, [args['entry'], args['exit_action']], args['profile'],
        'DU_TEST', retained(args['db']))
    assert len(merged) == 2 and sum(r['pnl'] or 0 for r in merged) == 8


@pytest.mark.parametrize('field,value', [('account','OTHER'), ('quantity',1),
    ('price',106), ('side','BOT'), ('sec_type','OPT'), ('commission',float('nan')),
    ('realized_pnl',float('inf')), ('commission_currency','EUR'),
    ('time','20261010 11:00:01')])
def test_invalid_close_never_writes(data, field, value):
    args = inputs(data)
    args['executions'][0][field] = value
    with pytest.raises(ValueError):
        recover_closed_pair(**args, apply=True)
    assert not retained(args['db'])


def test_conflicting_callback_and_partial_statement_rejected(data):
    args = inputs(data)
    duplicate = {**args['executions'][0], 'commission': 2}
    args['executions'].append(duplicate)
    with pytest.raises(ValueError):
        recover_closed_pair(**args)
    args['executions'].pop()
    args['xml'] = flex(dict(buySell='BUY', quantity='1', tradePrice='100',
        openCloseIndicator='O', dateTime='20261009;100000'))
    with pytest.raises(ValueError):
        recover_closed_pair(**args)


@pytest.mark.parametrize('field,value', [('environment','LIVE'),('user_id',uuid.uuid4()),
    ('symbol','OTHER'),('status','SUBMITTED')])
def test_wrong_entry_scope_rejected(data, field, value):
    args = inputs(data)
    setattr(args['entry'], field, value)
    with pytest.raises(ValueError):
        recover_closed_pair(**args)


def test_missing_financials_remain_unknown_and_zero_is_valid(data):
    args = inputs(data)
    args['executions'][0].update(commission=None, realized_pnl=None, pnl_available=False)
    result = recover_closed_pair(**args)
    assert result['closing']['pnl'] is None and result['closing']['commission'] is None
    args['executions'][0].update(commission=0, realized_pnl=0, pnl_available=True)
    assert recover_closed_pair(**args)['closing']['pnl'] == 0


def test_conflict_cannot_partially_write_and_read_revalidates(data):
    args = inputs(data)
    recover_closed_pair(**args, apply=True)
    args['db'].commit()
    saved = retained(args['db'])
    opening = saved[str(args['entry'].id)]
    altered = copy.deepcopy(opening)
    altered['opening']['execution_price'] = 999
    assert recovered_row(args['entry'], args['profile'], 'DU_TEST', altered,
        [args['entry'], args['exit_action']]) is None
    args['executions'][0]['realized_pnl'] = 9
    with pytest.raises(ValueError):
        recover_closed_pair(**args, apply=True)
    assert retained(args['db']) == saved
    args['exit_action'].status = 'EXIT_SUBMITTED'
    assert recovered_row(args['entry'], args['profile'], 'DU_TEST', opening,
        [args['entry'], args['exit_action']]) is None


def test_reused_order_number_does_not_erase_other_execution(data):
    args = inputs(data)
    recover_closed_pair(**args, apply=True)
    historical = dict(profile_id=str(args['profile'].id), broker_order_id='11',
        execution_id='unrelated-older-execution', symbol='MSFT', quantity=3,
        execution_price=90, pnl=12, pnl_available=True)
    rows = merge_saved_fills([historical], [args['entry'], args['exit_action']],
        args['profile'], 'DU_TEST', retained(args['db']))
    assert historical in rows and len(rows) == 3


def test_link_and_entire_statement_order_required(data):
    args = inputs(data)
    raw = json.loads(args['exit_action'].raw_json)
    del raw['entry_action_id']
    args['exit_action'].raw_json = json.dumps(raw)
    with pytest.raises(ValueError):
        recover_closed_pair(**args)
    raw['entry_action_id'] = str(args['entry'].id)
    args['exit_action'].raw_json = json.dumps(raw)
    changes = dict(buySell='BUY', quantity='1', tradePrice='100',
        openCloseIndicator='O', dateTime='20261009;100000')
    args['xml'] = flex(changes, changes)
    with pytest.raises(ValueError):
        recover_closed_pair(**args)
    args['trade_ids'] = ['t0', 't1']
    assert recover_closed_pair(**args)['opening']['quantity'] == 2


def test_execution_callbacks_are_canonicalized_on_repeated_apply(data):
    args = inputs(data)
    args['executions'].append(dict(args['executions'][0]))
    recover_closed_pair(**args, apply=True)
    args['executions'].pop()
    recover_closed_pair(**args, apply=True)
    assert len(retained(args['db'])) == 2


def test_reviewed_close_uses_exact_entry_with_older_orphan_lots(data):
    args = inputs(data)
    recover_closed_pair(**args, apply=True)
    old = dict(profile_id=str(args['profile'].id), symbol='MSFT', side='BUY',
        quantity=2, execution_price=80, time=1791450000000,
        audit_action_id='older-unmatched-entry', broker_order_id='older-order',
        closed_trade=False, pnl_available=False)
    rows = merge_saved_fills([old], [args['entry'], args['exit_action']],
        args['profile'], 'DU_TEST', retained(args['db']))
    _pair_execution_lots(rows)
    close = next(r for r in rows if r.get('closed_trade'))
    assert close['entry_price'] == 100
    assert close['invested_amount'] == 200
    assert close['duration_seconds'] == 3600
    assert close['entry_action_ids'] == [str(args['entry'].id)]
    assert close['opened_time_source'] == 'IBKR_STATEMENT_EXECUTION_TIME'
    assert close['pnl'] == 8 and close['commission'] == 1
    assert close['return_pct'] == 4
    # The exact pair must consume its own opening lot, leaving the historical
    # orphan for a later ordinary FIFO close rather than reusing the paired lot.
    ordinary = dict(profile_id=str(args['profile'].id), symbol='MSFT', side='SELL',
        quantity=2, execution_price=110, time=close['time'] + 1000,
        closed_trade=True, pnl_available=False)
    _pair_execution_lots(rows + [ordinary])
    assert ordinary['entry_price'] == 80
