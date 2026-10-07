import asyncio
from types import SimpleNamespace as NS

import pytest

from app.brokers.bybit_private import BybitPrivateClient
from app.services.bybit_spot_execution import managed_position_slots
from app.services.scan_lifecycle import interrupt_scan
from app.services import safe_automation, ibkr_position_manager as manager


def test_only_confirmed_quantity_dust_releases_a_slot_without_erasing_inventory():
    inventories = [NS(symbol='ETHUSDT', managed_quantity=.00001),
                   NS(symbol='SOLUSDT', managed_quantity=2),
                   NS(symbol='XRPUSDT', managed_quantity=3)]
    class Client:
        _normalize_spot_qty = staticmethod(BybitPrivateClient._normalize_spot_qty)
        async def _spot_lot_size(self, symbol):
            if symbol == 'XRPUSDT': raise TimeoutError('private URL')
            return '.001', '.01'
    result = asyncio.run(managed_position_slots(Client(), inventories))
    assert result == {'count':2, 'quantity_dust_symbols':['ETHUSDT'], 'unverified_symbols':['XRPUSDT']}
    assert inventories[0].managed_quantity == .00001


@pytest.mark.parametrize('step,minimum', [('nan','.01'), ('0','.01'), ('.01','-1'), ('.01','bad')])
def test_invalid_broker_metadata_never_releases_a_slot(step, minimum):
    class Client:
        _normalize_spot_qty = staticmethod(BybitPrivateClient._normalize_spot_qty)
        async def _spot_lot_size(self, symbol): return step, minimum
    result = asyncio.run(managed_position_slots(Client(), [NS(symbol='ETHUSDT',managed_quantity=.00001)]))
    assert result['count'] == 1
    assert result['quantity_dust_symbols'] == []


class ScanDB:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def add(self, scan):
        self.scan = scan
        scan.id = 'scan'
        scan.signals_count = scan.approved_count = scan.executed_count = 0
    def commit(self): pass
    def rollback(self): pass
    def refresh(self, row): pass
    def get(self, model, key): return self.scan


def test_cancelled_scan_is_finished_and_cancellation_propagates(monkeypatch):
    db = ScanDB()
    db.scalars = lambda query: NS(all=lambda:[NS(user_id=1,profile_id=1)])
    monkeypatch.setattr(safe_automation, 'SessionLocal', lambda:db)
    monkeypatch.setattr(safe_automation, 'get_or_create_state', lambda db:NS(enabled=True,killed=False,auto_execute_paper=True))
    async def cancelled(*args, **kwargs): raise asyncio.CancelledError()
    monkeypatch.setattr(safe_automation, 'autotrade_preflight', cancelled)
    with pytest.raises(asyncio.CancelledError): asyncio.run(safe_automation.run_safe_scan())
    assert db.scan.status == 'INTERRUPTED'
    assert db.scan.finished_at is not None
    assert db.scan.error_message == 'WORKER_CANCELLED_BROKER_RECONCILIATION_REQUIRED'


def test_interrupt_never_relabels_an_already_completed_scan():
    db = ScanDB()
    db.scan = NS(status='COMPLETED')
    interrupt_scan(db, 'scan')
    assert db.scan.status == 'COMPLETED'


@pytest.mark.parametrize('quantity,decision,position_side', [(3,'SELL','LONG'),(-3,'BUY','SHORT')])
def test_ibkr_existing_position_exit_bypasses_entry_readiness_limits(monkeypatch, quantity, decision, position_side):
    db = ScanDB()
    profile = NS(id=1,user_id=1)
    db.scalars = lambda query:NS(all=lambda:[profile])
    db.scalar = lambda query:NS(market='STOCK')
    broker = NS()
    async def health(): return {'connected':True,'simulation':True}
    async def executions(*args): return {'list':[]}
    async def positions(): return {'list':[{'symbol':'MSFT','quantity':quantity}]}
    async def status(*args): return {'status':{'status':'Filled','filled':3,'remaining':0}}
    async def candles(*args, **kwargs): return {'list':[]}
    closes = []
    async def close(**kwargs): closes.append(kwargs); return {'accepted':True,'order_id':128}
    broker.health, broker.executions, broker.positions = health, executions, positions
    broker.order_status, broker.candles, broker.close_position = status, candles, close
    monkeypatch.setattr(manager,'SessionLocal',lambda:db)
    monkeypatch.setattr(manager,'get_or_create_state',lambda db:NS(enabled=True,killed=False,auto_execute_paper=True))
    monkeypatch.setattr(manager,'IbkrBridgeClient',lambda *args:broker)
    monkeypatch.setattr(manager,'_secret',lambda profile:{'account_id':'DU_TEST'})
    monkeypatch.setattr(manager,'_default_strategy',lambda db:None)
    monkeypatch.setattr(manager,'_latest_entry',lambda *args:NS(side='BUY' if quantity>0 else 'SELL',status='EXECUTED',quantity=3,broker_order_id='1'))
    monkeypatch.setattr(manager,'_reconcile_submitted_entries',lambda *args:None)
    monkeypatch.setattr(manager,'_reconcile_submitted_entries_from_positions',lambda *args:None)
    monkeypatch.setattr(manager,'_timeframe',lambda *args:'5m')
    monkeypatch.setattr(manager,'_minimum_strength',lambda *args:60)
    monkeypatch.setattr(manager,'generate_signal',lambda *args,**kwargs:NS(decision=decision,strength=80))
    monkeypatch.setattr(manager,'_persist',lambda *args:None)
    result = asyncio.run(manager.run_ibkr_position_manager())
    assert result['exit_executed'] == 1
    assert closes == [{'symbol':'MSFT','quantity':3,'position_side':position_side,'account_id':'DU_TEST'}]
