from __future__ import annotations

from datetime import datetime, timezone
import httpx

FX_WATCHLIST=("EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD","USDCAD")

class FxMarketDataError(RuntimeError): pass

class TwelveDataFxMarketData:
    def __init__(self,base_url:str,api_key:str,timeout_seconds:float=8.0):
        self.base_url=base_url.rstrip("/");self.api_key=api_key.strip();self.timeout=timeout_seconds
        if not self.api_key: raise ValueError("FX market data API key is not configured")
    @staticmethod
    def provider_symbol(symbol:str)->str:
        s=symbol.upper().replace("/","").strip()
        if len(s)!=6 or not s.isalpha(): raise ValueError("FX symbol must look like EURUSD or EUR/USD")
        return f"{s[:3]}/{s[3:]}"
    async def _get(self,path:str,params:dict)->dict:
        params={**params,"apikey":self.api_key}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:r=await client.get(f"{self.base_url}/{path}",params=params)
            r.raise_for_status();data=r.json()
        except (httpx.HTTPError,ValueError) as exc: raise FxMarketDataError(str(exc)) from exc
        if isinstance(data,dict) and data.get("status")=="error": raise FxMarketDataError(str(data.get("message") or "FX provider error"))
        return data
    async def get_quote(self,symbol:str)->dict:
        normalized=symbol.upper().replace("/","")
        data=await self._get("quote",{"symbol":self.provider_symbol(normalized)})
        close=float(data.get("close") or data.get("price") or 0);prev=float(data.get("previous_close") or close)
        change=close-prev;change_pct=(change/prev*100) if prev else 0
        return {"symbol":normalized,"display_symbol":self.provider_symbol(normalized),"price":close,"change":change,"change_percent":change_pct,"provider":"TWELVE_DATA","as_of":datetime.now(timezone.utc).isoformat()}
    async def get_candles(self,symbol:str,interval:str="5min",limit:int=120)->list[dict]:
        interval_map={"1m":"1min","5m":"5min","15m":"15min","30m":"30min","1h":"1h","4h":"4h","1d":"1day"};provider_interval=interval_map.get(interval,interval)
        data=await self._get("time_series",{"symbol":self.provider_symbol(symbol),"interval":provider_interval,"outputsize":min(max(limit,1),500),"order":"ASC"})
        values=data.get("values") or []
        return [{"timestamp":x.get("datetime"),"open":float(x["open"]),"high":float(x["high"]),"low":float(x["low"]),"close":float(x["close"]),"volume":float(x.get("volume") or 0)} for x in values]
