from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Iterable


def canonical_symbol(symbol: Any) -> str:
    return str(symbol or "").strip().upper().replace("/", "").replace(" ", "")


def exposure_symbols(rows: Iterable[dict] | None, quantity_key: str | None = None) -> set[str]:
    out: set[str] = set()
    for row in rows or []:
        if quantity_key is not None and float(row.get(quantity_key) or 0) == 0:
            continue
        symbol = canonical_symbol(row.get("symbol"))
        if symbol:
            out.add(symbol)
    return out


def pending_order_symbols(rows: Iterable[dict] | None) -> set[str]:
    """Return canonical symbols for broker orders that still represent pending exposure.

    Broker bridges do not expose one common status vocabulary, so terminal states are
    explicitly ignored and unknown/non-terminal states are treated conservatively as open.
    """
    terminal = {"FILLED", "CANCELLED", "CANCELED", "REJECTED", "EXPIRED", "INACTIVE", "DONE"}
    out: set[str] = set()
    for row in rows or []:
        status = str(row.get("status") or row.get("order_status") or "").strip().upper()
        remaining = row.get("remaining")
        if status in terminal:
            continue
        if remaining is not None:
            try:
                if float(remaining) <= 0:
                    continue
            except (TypeError, ValueError):
                pass
        symbol = canonical_symbol(row.get("symbol"))
        if symbol:
            out.add(symbol)
    return out


@dataclass(frozen=True)
class ExecutionReservation:
    profile_id: str
    symbol: str

    @property
    def key(self) -> str:
        return f"{self.profile_id}:{canonical_symbol(self.symbol)}"


_locks: dict[str, asyncio.Lock] = {}
_registry_lock = asyncio.Lock()


async def _lock_for(key: str) -> asyncio.Lock:
    async with _registry_lock:
        lock = _locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _locks[key] = lock
        return lock


@asynccontextmanager
async def reserve_execution(profile_id: Any, symbol: Any) -> AsyncIterator[ExecutionReservation | None]:
    """Try to reserve one profile+symbol execution slot without waiting.

    This prevents overlapping scans in the same ATLAS process from both passing the
    pre-order exposure check. The caller must still re-read broker positions/orders
    after acquiring the reservation and immediately before submitting the order.
    """
    reservation = ExecutionReservation(str(profile_id), canonical_symbol(symbol))
    lock = await _lock_for(reservation.key)
    if lock.locked():
        yield None
        return
    await lock.acquire()
    try:
        yield reservation
    finally:
        lock.release()
