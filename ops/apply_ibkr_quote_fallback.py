from __future__ import annotations

from pathlib import Path
import py_compile
import shutil
import sys

TARGET = Path("tools/ibkr_bridge.py")
BACKUP = Path("tools/ibkr_bridge.py.pre-quote-fallback.bak")

OLD = """@app.get('/quote')\ndef quote(symbol:str,sec_type:str='STK',exchange:str='SMART',currency:str='USD',x_atlas_bridge_token:str|None=Header(default=None)):\n auth(x_atlas_bridge_token);r=rid();key=f'quote:{r}';ib.quotes[r]={};prepare(key);ib.reqMktData(r,contract(symbol,sec_type,exchange,currency),'',True,False,[]);wait(key);ib.cancelMktData(r);q=ib.quotes.pop(r,{})\n if not q:raise HTTPException(502,f'No IBKR quote returned for {symbol}')\n if not q.get('last') and q.get('bid') and q.get('ask'):q['last']=(q['bid']+q['ask'])/2\n return {'symbol':symbol.upper(),'sec_type':sec_type,'currency':currency,**q}\n"""

NEW = """@app.get('/quote')\ndef quote(symbol:str,sec_type:str='STK',exchange:str='SMART',currency:str='USD',x_atlas_bridge_token:str|None=Header(default=None)):\n auth(x_atlas_bridge_token)\n r=rid();key=f'quote:{r}';ib.quotes[r]={};prepare(key)\n ib.reqMktData(r,contract(symbol,sec_type,exchange,currency),'',True,False,[])\n try:\n  wait(key,6)\n except HTTPException:\n  pass\n q=ib.quotes.pop(r,{})\n # Snapshot requests can legitimately end without a usable last/bid/ask on\n # delayed IBKR data. Avoid cancelMktData for snapshot=True: IBKR ends the\n # request itself and cancelling afterwards can emit error 300.\n if not q.get('last') and q.get('bid') and q.get('ask'):\n  q['last']=(q['bid']+q['ask'])/2\n if q.get('last') or q.get('bid') or q.get('ask'):\n  return {'symbol':symbol.upper(),'sec_type':sec_type,'currency':currency,'source':'SNAPSHOT',**q}\n # Safe fallback: use the most recent completed historical trade bar. This is\n # market-data retrieval only; it does not change any execution/risk gate.\n hr=rid();hkey=f'bars:{hr}';ib.bars[hr]=[];prepare(hkey)\n ib.reqHistoricalData(hr,contract(symbol,sec_type,exchange,currency),'','2 D','5 mins','TRADES',1,1,False,[])\n try:\n  wait(hkey,15)\n finally:\n  try:ib.cancelHistoricalData(hr)\n  except Exception:pass\n rows=ib.bars.pop(hr,[])\n if not rows:\n  raise HTTPException(502,f'No IBKR quote or historical fallback returned for {symbol}')\n last=float(rows[-1]['close'])\n return {'symbol':symbol.upper(),'sec_type':sec_type,'currency':currency,'last':last,'source':'HISTORICAL_FALLBACK','bar_time':rows[-1].get('time')}\n"""


def main() -> int:
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found. Run this script from the repository root.")
        return 1

    text = TARGET.read_text(encoding="utf-8")
    if "'source':'HISTORICAL_FALLBACK'" in text:
        print("IBKR quote fallback: already applied")
    else:
        if OLD not in text:
            print("ERROR: Expected /quote block was not found. Local bridge differs from the known structure; no file was changed.")
            return 2
        if not BACKUP.exists():
            shutil.copy2(TARGET, BACKUP)
            print(f"backup created: {BACKUP}")
        TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
        print("IBKR quote fallback: applied")

    try:
        py_compile.compile(str(TARGET), doraise=True)
    except Exception as exc:
        print(f"ERROR: patched bridge failed syntax validation: {exc}")
        if BACKUP.exists():
            shutil.copy2(BACKUP, TARGET)
            print("original bridge restored from backup")
        return 3

    print("SUCCESS: quote fallback applied and Python syntax validated.")
    print("Restart the local IBKR bridge, then test /quote for AAPL, SPY, and QQQ.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
