from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class BrokerAdapter(ABC):
    """Provider-independent interface used by Atlas Markets core services."""

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def test_connection(self) -> dict[str, Any]: ...

    @abstractmethod
    async def get_account(self) -> dict[str, Any]: ...

    @abstractmethod
    async def get_balance(self) -> dict[str, Any]: ...

    @abstractmethod
    async def get_positions(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_orders(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_instruments(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_quote(self, symbol: str) -> dict[str, Any]: ...

    @abstractmethod
    async def get_candles(self, symbol: str, timeframe: str, limit: int) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def stream_prices(self, symbols: list[str]) -> AsyncIterator[dict[str, Any]]: ...

    @abstractmethod
    async def place_order(self, order: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    async def cancel_order(self, external_order_id: str) -> dict[str, Any]: ...

    @abstractmethod
    async def close_position(self, position_id: str) -> dict[str, Any]: ...

    @abstractmethod
    async def modify_stop(self, position_id: str, price: float) -> dict[str, Any]: ...

    @abstractmethod
    async def modify_take_profit(self, position_id: str, price: float) -> dict[str, Any]: ...
