from pathlib import Path
from types import SimpleNamespace

from app.services.ibkr_position_manager import _entry_fill_verified, _execution_matches_action, _opposite, _reconciliation_evidence


def test_ibkr_exit_direction_logic():
    assert _opposite('LONG','SELL') is True
    assert _opposite('SHORT','BUY') is True
    assert _opposite('LONG','BUY') is False
    assert _opposite('SHORT','SELL') is False
    assert _opposite('LONG','HOLD') is False


def test_ibkr_entry_fill_accepts_broker_filled():
    entry=SimpleNamespace(status='EXECUTED',side='BUY',quantity=1.0)
    assert _entry_fill_verified(entry,{'status':'Filled'},'LONG',1.0)==(True,'BROKER_FILLED')


def test_ibkr_entry_fill_falls_back_only_on_missing_broker_status_and_exact_live_match():
    long_entry=SimpleNamespace(status='EXECUTED',side='BUY',quantity=1.0)
    short_entry=SimpleNamespace(status='EXECUTED',side='SELL',quantity=1.0)
    assert _entry_fill_verified(long_entry,{},'LONG',1.0)==(True,'PERSISTED_EXECUTED_LIVE_POSITION_MATCH')
    assert _entry_fill_verified(short_entry,{},'SHORT',1.0)==(True,'PERSISTED_EXECUTED_LIVE_POSITION_MATCH')
    assert _entry_fill_verified(long_entry,{},'SHORT',1.0)[0] is False
    assert _entry_fill_verified(long_entry,{},'LONG',2.0)[0] is False


def test_ibkr_entry_fill_never_overrides_explicit_broker_nonfilled_state():
    entry=SimpleNamespace(status='EXECUTED',side='BUY',quantity=1.0)
    assert _entry_fill_verified(entry,{'status':'Submitted'},'LONG',1.0)==(False,'BROKER_NOT_FILLED')
    assert _entry_fill_verified(entry,{'status':'Cancelled'},'LONG',1.0)==(False,'BROKER_NOT_FILLED')


def test_ibkr_delayed_fill_reconciliation_requires_exact_broker_identity():
    action=SimpleNamespace(broker_order_id='31',symbol='IWM',side='BUY',quantity=1.0)
    execution={'execution_id':'exec-31','order_id':31,'account':'DUR980544','symbol':'IWM','side':'BOT','quantity':1.0}
    assert _execution_matches_action(action,execution,'DUR980544') is True
    assert _reconciliation_evidence(action,[execution],'DUR980544')['execution_ids']==['exec-31']
    for field,value in [('order_id',32),('account','OTHER'),('symbol','QQQ'),('side','SLD')]:
        changed=dict(execution);changed[field]=value
        assert _execution_matches_action(action,changed,'DUR980544') is False


def test_ibkr_delayed_fill_reconciliation_requires_exact_aggregate_quantity():
    action=SimpleNamespace(broker_order_id='37',symbol='QQQ',side='BUY',quantity=1.0)
    partial={'execution_id':'partial','order_id':37,'account':'DUR980544','symbol':'QQQ','side':'BOT','quantity':0.5}
    assert _reconciliation_evidence(action,[partial],'DUR980544') is None
    second={**partial,'execution_id':'second','quantity':0.5}
    evidence=_reconciliation_evidence(action,[partial,second],'DUR980544')
    assert evidence is not None
    assert evidence['quantity']==1.0
    overfill={**partial,'execution_id':'over','quantity':1.0}
    assert _reconciliation_evidence(action,[partial,overfill],'DUR980544') is None


def test_ibkr_exit_manager_is_paper_owned_and_lifecycle_guarded():
    text=Path('app/services/ibkr_position_manager.py').read_text()
    assert "BrokerProfile.environment=='PAPER'" in text
    assert "AutomationAction.status=='SUBMITTED'" in text
    assert "AutomationAction.reason=='BROKER_FILL_NOT_CONFIRMED'" in text
    assert "broker.executions(30)" in text
    assert 'BROKER_EXECUTION_RECONCILED' in text
    assert "entry is None" in text
    assert 'OWNERSHIP_NOT_VERIFIED' in text
    assert 'ENTRY_FILL_NOT_VERIFIED' in text
    assert 'PERSISTED_EXECUTED_LIVE_POSITION_MATCH' in text
    assert "SymbolStrategy.mode=='AUTO_TRADE'" in text
    assert 'close_position(' in text
    assert "result['status']='EXIT_EXECUTED'" in text


def test_ibkr_close_client_rechecks_simulation_and_position():
    text=Path('app/brokers/ibkr_bridge.py').read_text()
    assert 'async def close_position' in text
    assert "not health.get('simulation')" in text
    assert "raise RuntimeError('POSITION_CHANGED')" in text
    assert "raise RuntimeError('SYMBOL_ALREADY_HAS_OPEN_ORDER')" in text
    assert 'BROKER_WHATIF_REJECTED' in text


def test_ibkr_manager_started_by_app_lifespan():
    text=Path('app/main.py').read_text()
    assert 'from app.services.ibkr_position_manager import ibkr_position_manager_loop' in text
    assert 'asyncio.create_task(ibkr_position_manager_loop(stop))' in text
