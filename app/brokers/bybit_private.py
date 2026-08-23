from __future__ import annotations

import hashlib
import hmac
import json
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

    def _headers(self, payload: str) -> dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        plain = timestamp + self.api_key + self.recv_window + payload
        signature = hmac.new(self.api_secret.encode(), plain.encode(), hashlib.sha256).hexdigest()
        return {"X-BAPI-API-KEY":self.api_key,"X-BAPI-TIMESTAMP":timestamp,"X-BAPI-RECV-WINDOW":self.recv_window,"X-BAPI-SIGN":signature,"Content-Type":"application/json"}

    @staticmethod
    def _result(response: httpx.Response) -> dict:
        response.raise_for_status();payload=response.json()
        if payload.get("retCode") != 0:raise BybitPrivateError(f"Bybit {payload.get('retCode')}: {payload.get('retMsg', 'request failed')}")
        return payload.get("result") or {}

    async def get(self,path:str,params:dict[str,str|int]|None=None)->dict:
        params=params or {};query=urlencode(params);headers=self._headers(query)
        async with httpx.AsyncClient(timeout=self.timeout) as client:response=await client.get(f"{self.base_url}{path}",params=params,headers=headers)
        return self._result(response)

    async def post(self,path:str,payload:dict)->dict:
        body=json.dumps(payload,separators=(",",":"),ensure_ascii=False);headers=self._headers(body)
        async with httpx.AsyncClient(timeout=self.timeout) as client:response=await client.post(f"{self.base_url}{path}",content=body,headers=headers)
        return self._result(response)

    async def wallet(self)->dict:return await self.get("/v5/account/wallet-balance",{"accountType":"UNIFIED"})
    async def positions(self)->dict:return await self.get("/v5/position/list",{"category":"linear","settleCoin":"USDT"})
    async def open_orders(self)->dict:return await self.get("/v5/order/realtime",{"category":"linear","settleCoin":"USDT","openOnly":0})

    async def place_demo_market_order(self,*,symbol:str,side:str,qty:float,stop_loss:float|None=None,take_profit:float|None=None,order_link_id:str|None=None)->dict:
        if self.base_url.rstrip("/")=="https://api.bybit.com":raise BybitPrivateError("ATLAS refuses broker-native demo execution on the Bybit LIVE endpoint")
        payload={"category":"linear","symbol":symbol.upper(),"side":side,"orderType":"Market","qty":f"{qty:.8f}".rstrip("0").rstrip("."),"timeInForce":"IOC","reduceOnly":False}
        if stop_loss is not None:payload["stopLoss"]=f"{stop_loss:.8f}".rstrip("0").rstrip(".")
        if take_profit is not None:payload["takeProfit"]=f"{take_profit:.8f}".rstrip("0").rstrip(".")
        if stop_loss is not None or take_profit is not None:payload["tpslMode"]="Full"
        if order_link_id:payload["orderLinkId"]=order_link_id[:36]
        return await self.post("/v5/order/create",payload)
