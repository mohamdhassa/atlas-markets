from __future__ import annotations
import httpx

from app.services.execution_guard import exposure_symbols, pending_order_symbols, reserve_execution

class Mt5BridgeError(RuntimeError):
    pass

class Mt5BridgeClient:
    def __init__(self, base_url:str, token:str|None=None, timeout:float=10.0):
        self.base_url=base_url.rstrip('/')
        self.token=token or ''
        self.timeout=timeout
    @staticmethod
    def _symbol(symbol:str)->str:
        return str(symbol or '').strip().upper().replace('/','').replace(' ','')
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
    async def search_symbols(self,query:str,limit:int=50)->dict:return await self._get(f'/symbols/search?q={str(query).strip()}&limit={max(1,min(limit,200))}')
    async def symbol(self,symbol:str)->dict:return await self._get(f'/symbol/{self._symbol(symbol)}')
    async def candles(self,symbol:str,timeframe:str='5m',limit:int=200)->dict:return await self._get(f'/candles/{self._symbol(symbol)}?timeframe={timeframe}&limit={max(2,min(limit,500))}')
    async def history_deals(self,days:int=30)->dict:return await self._get(f'/history/deals?days={max(1,min(days,366))}')
    async def order_check(self,payload:dict)->dict:
        p=dict(payload);p['symbol']=self._symbol(p.get('symbol'));return await self._request('POST','/order/check',p)
    async def place_demo_order(self,*,symbol:str,side:str,volume:float,stop_loss:float|None=None,take_profit:float|None=None,comment:str='ATLAS SIMULATION')->dict:
        symbol=self._symbol(symbol)
        async with reserve_execution(f'MT5:{self.base_url}',symbol) as reservation:
            if reservation is None:raise Mt5BridgeError('EXECUTION_ALREADY_IN_PROGRESS')
            positions=(await self.positions()).get('list',[])
            if symbol in exposure_symbols(positions):raise Mt5BridgeError('SYMBOL_ALREADY_HAS_POSITION')
            orders=(await self.orders()).get('list',[])
            if symbol in pending_order_symbols(orders):raise Mt5BridgeError('SYMBOL_ALREADY_HAS_OPEN_ORDER')
            return await self._request('POST','/order',{'symbol':symbol,'side':side,'volume':volume,'stop_loss':stop_loss,'take_profit':take_profit,'comment':comment})
    async def close_demo_position(self,ticket:int)->dict:return await self._request('POST',f'/positions/{ticket}/close',{})
