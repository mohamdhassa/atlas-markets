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
    async def _get(self,path:str)->dict:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r=await client.get(f'{self.base_url}{path}',headers=self._headers())
            r.raise_for_status();return r.json()
        except Exception as exc:
            raise Mt5BridgeError(str(exc)) from exc
    async def health(self)->dict:return await self._get('/health')
    async def account(self)->dict:return await self._get('/account')
    async def positions(self)->dict:return await self._get('/positions')
    async def orders(self)->dict:return await self._get('/orders')
