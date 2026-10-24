"""Read-only Paper candle export. No order, reconciliation or settings calls."""
import argparse
import asyncio
import json
import time
import uuid
from pathlib import Path
from app.db.session import SessionLocal
from app.db.models.broker import BrokerProfile
from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.services.ibkr_position_manager import _secret
from app.services.trading_candles import completed_trading_candles

SYMBOLS=('SPY','QQQ','IWM','AAPL','AMZN','META','MSFT','NVDA','TSLA')


async def collect(args):
    with SessionLocal() as db:
        profile=db.get(BrokerProfile,args.profile_id)
        if not profile or profile.provider!='IBKR' or profile.environment!='PAPER':
            raise ValueError('IBKR_PAPER_PROFILE_REQUIRED')
        credentials=_secret(profile)
    broker=IbkrBridgeClient(credentials.get('bridge_url') or
        'http://host.docker.internal:8766',credentials.get('bridge_token'),30.)
    health=await broker.health()
    if health.get('connected') is not True or health.get('simulation') is not True:
        raise ValueError('CONNECTED_PAPER_BRIDGE_REQUIRED')
    output=Path(args.output);output.mkdir(parents=True,exist_ok=False)
    failed=[]
    for symbol in SYMBOLS:
        try:
            payload=await broker.candles(symbol,args.timeframe,1000,sec_type='STK')
            if payload.get('actual_timeframe')!=args.timeframe:
                raise ValueError('ACTUAL_TIMEFRAME_UNVERIFIED')
            observed=int(time.time()*1000)
            rows=completed_trading_candles(payload.get('list',[]),args.timeframe,
                                           now_ms=observed,limit=1000)
            bundle=dict(provider='IBKR',symbol=symbol,timeframe=args.timeframe,
                regular_hours=True,collected_at_ms=observed,candles=rows,
                provenance='IBKR_BRIDGE_TRADES_USE_RTH_1',
                purpose='EXPLORATORY_ATR_COMPARISON_NO_ORDERS')
            with (output/f'{symbol}-{args.timeframe}.json').open('x') as file:
                json.dump(bundle,file)
            print(json.dumps({'symbol':symbol,'bars':len(rows),'collected':True}),flush=True)
        except Exception as exc:
            failed.append(symbol)
            print(json.dumps({'symbol':symbol,'collected':False,
                              'error_type':type(exc).__name__}),flush=True)
    if failed:raise SystemExit('Incomplete collection: '+','.join(failed))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--profile-id',type=uuid.UUID,required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--timeframe',choices=['3m','5m','15m'],default='5m')
    asyncio.run(collect(parser.parse_args()))


if __name__=='__main__':main()
