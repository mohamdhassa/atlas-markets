import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace as NS
from xml.etree import ElementTree as ET

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.routes_broker_native import router, _pair_execution_lots, _stats
from app.db.models.automation import AutomationAction
from app.db.models.ibkr_statement import IbkrStatementEvidence
from app.db.session import get_db
from app.services.ibkr_ledger_history import merge_saved_fills
from app.services.ibkr_statement_import import parse_flex, reconcile_statement, imported_fill
from test_ibkr_ledger_history import action as audit_action


def flex(*changes):
    root = ET.Element('FlexQueryResponse')
    parent = ET.SubElement(ET.SubElement(root, 'FlexStatements'), 'FlexStatement', accountId='DU_TEST')
    trades = ET.SubElement(parent, 'Trades')
    for i, change in enumerate(changes or ({},)):
        attributes = dict(accountId='DU_TEST', assetCategory='STK', currency='USD',
                          ibCommissionCurrency='USD', levelOfDetail='EXECUTION', buySell='SELL',
                          quantity='-2', tradePrice='105', ibCommission='-1', fifoPnlRealized='8',
                          symbol='MSFT', openCloseIndicator='C', tradeID=f't{i}',
                          ibOrderID='broker-11', ibExecID=f'exec-{i}', dateTime='20261009;110000', multiplier='1')
        attributes.update(change)
        ET.SubElement(trades, 'Trade', attributes)
    return ET.tostring(root, encoding='unicode')


@pytest.fixture
def data():
    engine = create_engine('sqlite://')
    AutomationAction.__table__.create(engine)
    IbkrStatementEvidence.__table__.create(engine)
    profile = NS(id=uuid.uuid4(), user_id=uuid.uuid4(), provider='IBKR', environment='PAPER', account_label='Paper')
    with Session(engine) as db:
        actions = []
        for order, side, closed, hour in [(10, 'BUY', False, 10), (11, 'SELL', True, 11)]:
            saved = audit_action(order, side, closed, hour)
            action = AutomationAction(id=uuid.uuid4(), scan_id=uuid.uuid4(), user_id=profile.user_id,
                broker_profile_id=profile.id, provider='IBKR', environment='PAPER', market='STOCK',
                symbol='MSFT', side=side, status=saved.status, quantity=2, broker_order_id=str(order),
                raw_json=saved.raw_json, created_at=saved.created_at)
            db.add(action)
            actions.append(action)
        db.commit()
        yield db, profile, actions


def stored(data, action=None):
    row = data[0].get(IbkrStatementEvidence, (action or data[2][1]).id)
    return json.loads(row.evidence_json) if row else None


def statement_map(data):
    return {str(row.action_id): json.loads(row.evidence_json)
            for row in data[0].scalars(select(IbkrStatementEvidence)).all()}


def run(data, xml=None, mapping=None, apply=False):
    db, profile, actions = data
    return reconcile_statement(db, profile, 'DU_TEST', xml or flex(), 'UTC',
                               mapping if mapping is not None else {str(actions[1].id): ['t0']},
                               uuid.uuid4(), apply=apply)


def test_preview_does_not_write_apply_is_idempotent_and_preserves_audit(data):
    db, profile, actions = data
    original = actions[1].raw_json
    assert run(data)['matches'][0]['pnl'] == 8
    assert actions[1].raw_json == original
    assert run(data, apply=True)['mode'] == 'APPLIED'
    db.commit()
    assert actions[1].raw_json == original
    assert stored(data)['file_sha256']
    assert stored(data)['mapping_basis'] == 'ADMIN_REVIEWED_EXPLICIT_MAPPING'
    assert run(data, apply=True)['duplicates'] == 1
    rows = merge_saved_fills([], actions, profile, 'DU_TEST', statement_map(data))
    _pair_execution_lots(rows)
    closed = rows[1]
    assert closed['commission'] == 1 and closed['pnl'] == 8  # No second commission subtraction.
    assert closed['entry_price'] == 100 and closed['return_pct'] == 4
    assert _stats(rows)['realized_pnl'] == 8 and _stats(rows)['pnl_trades'] == 1
    assert closed['time_source'] == 'IBKR_STATEMENT_EXECUTION_TIME'


def test_split_fills_replace_live_fragments_once_and_ignore_summary_rows(data):
    xml = flex({'quantity': '-1', 'ibCommission': '-0.4', 'fifoPnlRealized': '4'},
               {'quantity': '-1', 'ibCommission': '-0.6', 'fifoPnlRealized': '4'},
               {'levelOfDetail': 'ORDER', 'quantity': '-2'})
    run(data, xml, {str(data[2][1].id): ['t0', 't1']}, apply=True)
    live = [{'profile_id': str(data[1].id), 'broker_order_id': '11', 'quantity': 1},
            {'profile_id': str(data[1].id), 'broker_order_id': '11', 'quantity': 1}]
    rows = merge_saved_fills(live, [data[2][1], data[2][1]], data[1], 'DU_TEST', statement_map(data))
    assert len(rows) == 1 and rows[0]['quantity'] == 2 and rows[0]['pnl'] == 8


@pytest.mark.parametrize('change', [
    {'accountId': 'OTHER'}, {'currency': 'EUR'}, {'ibCommissionCurrency': 'EUR'},
    {'quantity': 'NaN'}, {'quantity': '2'}, {'tradePrice': 'Infinity'}, {'ibCommission': ''},
    {'assetCategory': 'OPT'}, {'multiplier': '100'}, {'openCloseIndicator': 'O;C'},
    {'origTradeID': '123'}, {'transactionType': 'TradeCancel'}, {'taxes': '1'},
    {'tradeID': ''}, {'ibOrderID': ''}, {'dateTime': 'unknown'},
])
def test_invalid_statement_is_rejected(change):
    with pytest.raises(ValueError):
        parse_flex(flex(change), 'DU_TEST', 'UTC')


@pytest.mark.parametrize('change', [{'symbol': 'NVDA'}, {'tradePrice': '106'},
                                   {'quantity': '-1'}, {'dateTime': '20260901;110000'},
                                   {'openCloseIndicator': 'O'}])
def test_mismatched_evidence_does_not_modify_audit(data, change):
    original = data[2][1].raw_json
    with pytest.raises(ValueError):
        run(data, flex(change), apply=True)
    assert data[2][1].raw_json == original


def test_atomic_mapping_validation_and_execution_reuse(data):
    before = [a.raw_json for a in data[2]]
    mapping = {str(data[2][1].id): ['t0'], str(uuid.uuid4()): ['t0']}
    with pytest.raises(ValueError):
        run(data, mapping=mapping, apply=True)
    assert [a.raw_json for a in data[2]] == before
    with pytest.raises(ValueError):
        run(data, flex({'quantity': '-1'}, {'quantity': '-1'}), apply=True)


def test_conflicting_repeat_and_read_scope_are_rejected(data):
    run(data, apply=True)
    with pytest.raises(ValueError):
        run(data, flex({'fifoPnlRealized': '9'}), apply=True)
    assert imported_fill(data[2][1], data[1], 'OTHER', stored(data)) is None
    data[2][1].user_id = uuid.uuid4()
    assert imported_fill(data[2][1], data[1], 'DU_TEST', stored(data)) is None


def test_missing_pnl_stays_pending_and_zero_pnl_is_confirmed(data):
    run(data, flex({'fifoPnlRealized': ''}), apply=True)
    row = imported_fill(data[2][1], data[1], 'DU_TEST', stored(data))
    assert row['pnl'] is None and not row['pnl_available'] and row['commission'] == 1
    # A corrected import must be reviewed rather than silently replacing saved evidence.
    with pytest.raises(ValueError):
        run(data, flex({'fifoPnlRealized': '0'}), apply=True)


def test_timezone_and_xml_entity_limits():
    trades = parse_flex(flex(), 'DU_TEST', 'America/New_York')
    assert trades['t0']['time'] == int(datetime(2026, 10, 9, 15, tzinfo=timezone.utc).timestamp() * 1000)
    for xml, zone in [('x' * 5_000_001, 'UTC'), ('<!DOCTYPE a><FlexQueryResponse/>', 'UTC'),
                      (flex(), 'Not/AZone'), (flex({'dateTime': '20261101;013000'}), 'America/New_York'),
                      (flex({'dateTime': '20260308;023000'}), 'America/New_York')]:
        with pytest.raises(ValueError):
            parse_flex(xml, 'DU_TEST', zone)


def test_non_admin_and_unauthenticated_api_cannot_import():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: None
    payload = {'profile_id': str(uuid.uuid4()), 'xml': flex(), 'timezone': 'UTC'}
    with TestClient(app) as client:
        assert client.post('/performance/ibkr-statement/import', json=payload).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: NS(role='USER', id=uuid.uuid4())
        assert client.post('/performance/ibkr-statement/import', json=payload).status_code == 403


def test_zero_pnl_and_entry_commission_do_not_create_false_closed_trade(data):
    run(data, flex({'fifoPnlRealized': '0'}), apply=True)
    closed = imported_fill(data[2][1], data[1], 'DU_TEST', stored(data))
    assert closed['pnl_available'] and closed['pnl'] == 0
    xml = flex({'buySell': 'BUY', 'quantity': '2', 'tradePrice': '100',
                'openCloseIndicator': 'O', 'dateTime': '20261009;100000', 'ibOrderID': 'broker-10',
                'tradeID': 'entry', 'fifoPnlRealized': '0'})
    run(data, xml, {str(data[2][0].id): ['entry']}, apply=True)
    entry = imported_fill(data[2][0], data[1], 'DU_TEST', stored(data, data[2][0]))
    assert entry['commission'] == 1 and not entry['closed_trade'] and not entry['pnl_available']


def test_duplicate_trade_rejected_if_assigned_to_another_action(data):
    run(data, apply=True)
    db, profile, actions = data
    duplicate = AutomationAction(id=uuid.uuid4(), scan_id=uuid.uuid4(), user_id=profile.user_id,
        broker_profile_id=profile.id, provider='IBKR', environment='PAPER', market='STOCK', symbol='MSFT',
        side='SELL', status='EXIT_EXECUTED', quantity=2, broker_order_id='11', raw_json=audit_action(11, 'SELL', True, 11).raw_json,
        created_at=datetime(2026, 10, 9, 11, tzinfo=timezone.utc))
    db.add(duplicate)
    db.commit()
    with pytest.raises(ValueError, match='two actions'):
        run(data, mapping={str(duplicate.id): ['t0']}, apply=True)


def test_conflicting_xml_duplicate_and_foreign_parent_account():
    with pytest.raises(ValueError, match='duplicate'):
        parse_flex(flex({'tradeID': 'same'}, {'tradeID': 'same', 'tradePrice': '106'}), 'DU_TEST', 'UTC')
    with pytest.raises(ValueError, match='account'):
        parse_flex(flex().replace('FlexStatement accountId="DU_TEST"', 'FlexStatement accountId="OTHER"'), 'DU_TEST', 'UTC')


def test_admin_endpoint_preview_commit_and_scope(monkeypatch, data):
    import app.api.routes_broker_native as route
    db, profile, actions = data
    monkeypatch.setattr(route, '_creds', lambda p: {'account_id': 'DU_TEST'})
    class Database:
        def get(self, model, key, **kwargs):
            return profile if key == profile.id else None
        def scalars(self, query): return db.scalars(query)
        def add(self, row): db.add(row)
        def flush(self): db.flush()
        def commit(self): db.commit()
        def rollback(self): db.rollback()
    admin = NS(role='ADMIN', id=uuid.uuid4())
    payload = route.IbkrStatementImport(profile_id=profile.id, xml=flex(), timezone='UTC',
                                      mapping={actions[1].id: ['t0']})
    assert route.import_ibkr_statement(payload, admin, Database())['mode'] == 'PREVIEW'
    assert stored(data) is None
    result = route.import_ibkr_statement(payload.model_copy(update={'apply': True}), admin, Database())
    assert result['mode'] == 'APPLIED'
    db.expire_all()
    assert stored(data)['operator_id'] == str(admin.id)
    with pytest.raises(Exception) as error:
        route.import_ibkr_statement(payload.model_copy(update={'profile_id': uuid.uuid4()}), admin, Database())
    assert error.value.status_code == 404


def test_naive_audit_timestamp_is_utc(data):
    from app.services.ibkr_ledger_history import saved_fill
    saved = saved_fill(data[2][1], data[1], 'DU_TEST')
    assert saved['time'] == int(datetime(2026, 10, 9, 11, tzinfo=timezone.utc).timestamp() * 1000)


def test_migration_upgrade_and_downgrade_preserve_existing_action_table():
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect
    migration = importlib.import_module('migrations.versions.20261010_0023_ibkr_statement_evidence')
    engine = create_engine('sqlite://')
    AutomationAction.__table__.create(engine)
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert 'ibkr_statement_evidence' in inspect(connection).get_table_names()
            assert len(inspect(connection).get_foreign_keys('ibkr_statement_evidence')) == 4
            assert inspect(connection).get_pk_constraint('ibkr_statement_evidence')['constrained_columns'] == ['action_id']
            migration.downgrade()
            assert 'ibkr_statement_evidence' not in inspect(connection).get_table_names()
            assert 'automation_actions' in inspect(connection).get_table_names()


def test_protection_audit_updates_cannot_erase_statement_evidence(data):
    run(data, apply=True)
    db, profile, actions = data
    db.commit()
    raw = json.loads(actions[1].raw_json)
    raw['native_protection'] = {'status': 'PROTECTED', 'order_ids': [10, 11]}
    actions[1].raw_json = json.dumps(raw)
    db.commit()
    assert imported_fill(actions[1], profile, 'DU_TEST', stored(data))['pnl'] == 8
