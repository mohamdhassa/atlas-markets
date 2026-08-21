from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlencode

import httpx


class BybitPrivateError(RuntimeError):
    pass


class BybitPrivateClient:
    def __init__(self, api_key: str, api_secret: str, base_url: str, timeout: float = 8.0):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.recv_window = "5000"

    def _headers(self, query: str) -> dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        plain = timestamp + self.api_key + self.recv_window + query
        signature = hmac.new(self.api_secret.encode(), plain.encode(), hashlib.sha256).hexdigest()
        return {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": self.recv_window,
            "X-BAPI-SIGN": signature,
        }

    async def get(self, path: str, params: dict[str, str | int] | None = None) -> dict:
        params = params or {}
        query = urlencode(params)
        headers = self._headers(query)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}{path}", params=params, headers=headers)
        response.raise_for_status()
        payload = response.json()
        if payload.get("retCode") != 0:
            raise BybitPrivateError(f"Bybit {payload.get('retCode')}: {payload.get('retMsg', 'request failed')}")
        return payload.get("result") or {}

    async def wallet(self) -> dict:
        return await self.get("/v5/account/wallet-balance", {"accountType": "UNIFIED"})

    async def positions(self) -> dict:
        return await self.get("/v5/position/list", {"category": "linear", "settleCoin": "USDT"})

    async def open_orders(self) -> dict:
        return await self.get("/v5/order/realtime", {"category": "linear", "settleCoin": "USDT", "openOnly": 0})
