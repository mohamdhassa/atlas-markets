from __future__ import annotations
import httpx

from app.services.execution_guard import exposure_symbols, pending_order_symbols, reserve_execution

class IbkrBridgeClient:
    """ATLAS client for the local IBKR TWS/IB Gateway bridge."""
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
    async def place_order(self,payload:dict):
        payload=dict(payload);symbol=str(payload.get('symbol') or '').strip().upper().replace('/','').replace(' ','');payload['symbol']=symbol
        account_key=payload.get('account_id') or self.base_url
        async with reserve_execution(f'IBKR:{account_key}',symbol) as reservation:
            if reservation is None:raise RuntimeError('EXECUTION_ALREADY_IN_PROGRESS')
            positions=(await self.positions()).get('list',[])
            if symbol in exposure_symbols(positions,'quantity'):raise RuntimeError('SYMBOL_ALREADY_HAS_POSITION')
            orders=(await self.orders()).get('list',[])
            if symbol in pending_order_symbols(orders):raise RuntimeError('SYMBOL_ALREADY_HAS_OPEN_ORDER')
            return await self._post('/orders',payload)
    async def close_position(self,*,symbol:str,quantity:float,position_side:str,account_id:str):
        """Close exactly one existing Paper position after re-verifying broker state.

        This deliberately bypasses the entry exposure guard only after proving
        the current symbol, direction and absolute quantity exactly match the
        requested close. The bridge itself still refuses Live execution.
        """
        symbol=str(symbol or '').strip().upper().replace('/','').replace(' ','')
        quantity=float(quantity or 0);position_side=str(position_side or '').upper()
        if quantity<=0 or position_side not in {'LONG','SHORT'}:raise RuntimeError('INVALID_CLOSE_REQUEST')
        async with reserve_execution(f'IBKR:{account_id or self.base_url}',symbol) as reservation:
            if reservation is None:raise RuntimeError('EXECUTION_ALREADY_IN_PROGRESS')
            health=await self.health()
            if not health.get('connected') or not health.get('simulation'):raise RuntimeError('IBKR_PAPER_BRIDGE_REQUIRED')
            positions=(await self.positions()).get('list',[])
            current=next((p for p in positions if str(p.get('symbol') or '').strip().upper().replace('/','').replace(' ','')==symbol and float(p.get('quantity') or 0)!=0),None)
            if current is None:raise RuntimeError('POSITION_NOT_FOUND')
            current_qty=float(current.get('quantity') or 0)
            actual_side='LONG' if current_qty>0 else 'SHORT'
            if actual_side!=position_side or abs(current_qty)!=quantity:raise RuntimeError('POSITION_CHANGED')
            orders=(await self.orders()).get('list',[])
            if symbol in pending_order_symbols(orders):raise RuntimeError('SYMBOL_ALREADY_HAS_OPEN_ORDER')
            payload={'symbol':symbol,'side':'SELL' if position_side=='LONG' else 'BUY','quantity':quantity,'order_type':'MKT','sec_type':'STK','exchange':'SMART','currency':'USD','account_id':account_id}
            check=await self.order_check(payload)
            if not(check.get('ok') and check.get('what_if') and check.get('simulation')):raise RuntimeError('BROKER_WHATIF_REJECTED')
            return await self._post('/orders',payload)
    async def cancel_order(self,order_id:int):return await self._post(f'/orders/{order_id}/cancel',{})
