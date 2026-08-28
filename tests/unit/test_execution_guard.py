import asyncio

import pytest

from app.services.execution_guard import (
    canonical_symbol,
    exposure_symbols,
    pending_order_symbols,
    reserve_execution,
)


def test_execution_guard_canonicalizes_aliases():
    assert canonical_symbol("EUR/USD") == "EURUSD"
    assert canonical_symbol(" eur usd ") == "EURUSD"


def test_pending_order_symbols_ignores_terminal_orders():
    rows = [
        {"symbol": "EUR/USD", "status": "Submitted", "remaining": 1},
        {"symbol": "AAPL", "status": "Filled", "remaining": 0},
        {"symbol": "MSFT", "status": "Cancelled", "remaining": 2},
    ]
    assert pending_order_symbols(rows) == {"EURUSD"}


def test_exposure_symbols_ignores_flat_quantities():
    rows = [{"symbol": "AAPL", "quantity": 0}, {"symbol": "MSFT", "quantity": 2}]
    assert exposure_symbols(rows, "quantity") == {"MSFT"}


@pytest.mark.asyncio
async def test_same_profile_symbol_cannot_be_reserved_twice():
    entered = asyncio.Event()
    release = asyncio.Event()

    async def first():
        async with reserve_execution("profile-1", "EUR/USD") as reservation:
            assert reservation is not None
            entered.set()
            await release.wait()

    task = asyncio.create_task(first())
    await entered.wait()
    async with reserve_execution("profile-1", "EURUSD") as reservation:
        assert reservation is None
    release.set()
    await task


@pytest.mark.asyncio
async def test_different_profile_or_symbol_can_execute_concurrently():
    async with reserve_execution("profile-1", "EURUSD") as first:
        assert first is not None
        async with reserve_execution("profile-1", "GBPUSD") as second:
            assert second is not None
        async with reserve_execution("profile-2", "EURUSD") as third:
            assert third is not None
