from __future__ import annotations
import httpx

class IbkrBridgeClient:
    """ATLAS client for the local Windows IBKR TWS/IB Gateway bridge.

    The bridge owns the official IBKR socket API connection. ATLAS Docker talks
    HTTP to the bridge, matching the MT5 bridge architecture and keeping TWS
    credentials/session state outside the container.
    """
    def __init__(self,base_url:str,token:str|None=None,timeout:float=15.0):
        self.base_url=base_url.rstrip('/');self.token=token;self.timeout=timeout
    def _headers(self):return {'X-ATLAS-Bridge-Token':self.token} if self.token else {}
    async def _get(self,path:str,params:dict|None=None):
        async with httpx.AsyncClient(timeout=self.timeout) as c:r=await c.get(self.base_url+path,params=params,headers=self._headers());r.raise_for_status();return r.json()
    async def _post(self,path:str,payload:dict):
        async with httpx.AsyncClient(timeout=self.timeout) as c:r=await c.post(self.base_url+path,json=payload,headers=self._headers());r.raise_for_status();return r.json()
    async def health(self):return await self._get('/health')
    async def account(self):return await self._get('/account')
    async def positions(self):return await self._get('/positions')
    async def orders(self):return await self._get('/orders')
    async def order_status(self,order_id:int):return await self._get(f'/orders/{order_id}/status')
    async def executions(self,days:int=30):return await self._get('/executions',{'days':days})
    async def contract(self,symbol:str,sec_type:str='STK',exchange:str='SMART',currency:str='USD'):return await self._get('/contract',{'symbol':symbol,'sec_type':sec_type,'exchange':exchange,'currency':currency})
    async def quote(self,symbol:str,sec_type:str='STK',exchange:str='SMART',currency:str='USD'):return await self._get('/quote',{'symbol':symbol,'sec_type':sec_type,'exchange':exchange,'currency':currency})
    async def candles(self,symbol:str,timeframe:str='5m',limit:int=200,sec_type:str='STK',exchange:str='SMART',currency:str='USD'):return await self._get('/candles',{'symbol':symbol,'timeframe':timeframe,'limit':limit,'sec_type':sec_type,'exchange':exchange,'currency':currency})
    async def order_check(self,payload:dict):return await self._post('/order-check',payload)
    async def place_order(self,payload:dict):return await self._post('/orders',payload)
    async def cancel_order(self,order_id:int):return await self._post(f'/orders/{order_id}/cancel',{})
