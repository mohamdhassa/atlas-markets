from __future__ import annotations
import httpx

class Mt5BridgeError(RuntimeError):
    pass

class Mt5BridgeClient:
    def __init__(self, base_url:str, token:str|None=None, timeout:float=10.0):
        self.base_url=base_url.rstrip('/')
        self.token=token or ''
        self.timeout=timeout
    def _headers(self)->dict[str,str]:
        return {'X-ATLAS-BRIDGE-TOKEN':self.token} if self.token else {}
    async def _request(self,method:str,path:str,json:dict|None=None)->dict:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r=await client.request(method,f'{self.base_url}{path}',headers=self._headers(),json=json)
            r.raise_for_status();return r.json()
        except Exception as exc:
            raise Mt5BridgeError(str(exc)) from exc
    async def _get(self,path:str)->dict:return await self._request('GET',path)
    async def health(self)->dict:return await self._get('/health')
    async def account(self)->dict:return await self._get('/account')
    async def positions(self)->dict:return await self._get('/positions')
    async def orders(self)->dict:return await self._get('/orders')
    async def symbol(self,symbol:str)->dict:return await self._get(f'/symbol/{symbol}')
    async def history_deals(self,days:int=30)->dict:return await self._get(f'/history/deals?days={max(1,min(days,366))}')
    async def order_check(self,payload:dict)->dict:return await self._request('POST','/order/check',payload)
    async def place_demo_order(self,*,symbol:str,side:str,volume:float,stop_loss:float|None=None,take_profit:float|None=None,comment:str='ATLAS DEMO')->dict:
        return await self._request('POST','/order',{'symbol':symbol,'side':side,'volume':volume,'stop_loss':stop_loss,'take_profit':take_profit,'comment':comment})
    async def close_demo_position(self,ticket:int)->dict:return await self._request('POST',f'/positions/{ticket}/close',{})
