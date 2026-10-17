import asyncio

import pytest
from app.brokers.bybit_private import BybitPrivateClient
from app.db.models.bybit_inventory import BybitManagedInventory
from app.services import bybit_spot_execution as spot
from test_bybit_pending_submission import db, profile, action


@pytest.mark.parametrize('quantity,slots,blocked',[
    (0,{},False),(.00000386,{'quantity_dust_symbols':['ETHUSDT']},False),
    (.00000386,{},True),(.1,{},True),
    (.00000386,{'quantity_dust_symbols':['ETHUSDT'],'unverified_symbols':['ETHUSDT']},True),
    (float('nan'),{'quantity_dust_symbols':['ETHUSDT']},True),
])
def test_readiness_buy_guard_uses_confirmed_quantity_dust(quantity,slots,blocked):
    assert spot.managed_buy_is_blocked('ETHUSDT',quantity,slots) is blocked


def inventory(db,profile,quantity):
    row=BybitManagedInventory(user_id=profile.user_id,broker_profile_id=profile.id,
        symbol='ETHUSDT',managed_quantity=quantity,average_entry_price=2750,
        cumulative_bought_quantity=.088,cumulative_sold_quantity=.087)
    db.add(row);db.commit()
    return row


def client(monkeypatch,metadata=('.00001','.00001')):
    calls=[]
    class Broker:
        _normalize_spot_qty=staticmethod(BybitPrivateClient._normalize_spot_qty)
        async def _spot_lot_size(self,symbol):
            if metadata is None:raise TimeoutError('unavailable')
            return metadata
        async def place_test_spot_market_order(self,**kwargs):
            calls.append(kwargs)
            return {'orderId':'new-entry'}
    async def fill(*args):return {'orderStatus':'Filled','orderId':'new-entry',
        'cumExecQty':'.1','avgPrice':'2400'}
    monkeypatch.setattr(spot,'_bybit_client',lambda *args:Broker())
    monkeypatch.setattr(spot,'_verify_spot_fill',fill)
    return calls


def execute(db,profile):
    return asyncio.run(spot.execute_managed_spot_order(db,profile=profile,
        user_id=profile.user_id,symbol='ETHUSDT',side='BUY',quantity=.1))


def test_confirmed_dust_allows_one_new_entry_and_preserves_residual_cost(db,profile,monkeypatch):
    residual=.00000386
    row=inventory(db,profile,residual)
    calls=client(monkeypatch)
    result=execute(db,profile)
    assert result['status']=='EXECUTED' and len(calls)==1
    assert result['residual_quantity_dust']==residual
    assert calls[0]['qty']==.1  # No unsolicited top-up or changed sizing.
    assert row.managed_quantity==pytest.approx(.1+residual)
    assert row.average_entry_price==pytest.approx((residual*2750+.1*2400)/(.1+residual))
    assert row.cumulative_sold_quantity==.087
    assert execute(db,profile)['reason']=='ATLAS_MANAGED_POSITION_ALREADY_OPEN'
    assert len(calls)==1


@pytest.mark.parametrize('quantity,metadata',[(.1,('.00001','.00001')),
    (.00000386,None),(.00000386,('0','.00001')),
    (.00000386,('nan','.00001'))])
def test_real_position_and_unverified_dust_never_place(db,profile,monkeypatch,quantity,metadata):
    row=inventory(db,profile,quantity)
    calls=client(monkeypatch,metadata)
    assert execute(db,profile)['reason']=='ATLAS_MANAGED_POSITION_ALREADY_OPEN'
    assert not calls and row.managed_quantity==quantity


def test_pending_submission_still_blocks_even_with_confirmed_dust(db,profile,monkeypatch):
    inventory(db,profile,.00000386)
    action(db,profile,symbol='ETHUSDT',broker_order_id=None)
    calls=client(monkeypatch)
    assert execute(db,profile)['reason']=='BYBIT_SUBMISSION_RECONCILIATION_REQUIRED'
    assert not calls
