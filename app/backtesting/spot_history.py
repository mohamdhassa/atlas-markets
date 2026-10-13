"""Collect public Spot research data without credentials, orders or database writes."""
import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path

import httpx

SYMBOLS = ('BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT')
BASE_URL = 'https://api.bybit.com'
STEP_MS = 300_000


def digest(candles):
    return hashlib.sha256(json.dumps(candles, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


async def public_get(client, path, params):
    # Only public GET endpoints. No private client, credentials or order methods.
    if path not in {'/v5/market/kline', '/v5/market/instruments-info'}:
        raise ValueError('Unsupported public data endpoint')
    for attempt in range(3):
        response = await client.get(path, params=params)
        if response.status_code == 429 and attempt < 2:
            await asyncio.sleep(1 + attempt)
            continue
        response.raise_for_status()
        payload = response.json()
        if payload.get('retCode') != 0:
            raise ValueError(f"Bybit public data error: {payload.get('retCode')}")
        return payload['result']
    raise ValueError('Public data rate limit')


async def collect_spot(client, symbol, start_ms, end_ms):
    if symbol not in SYMBOLS or start_ms % STEP_MS or end_ms % STEP_MS or start_ms >= end_ms:
        raise ValueError('Invalid Spot data window')
    instrument = await public_get(client, '/v5/market/instruments-info',
                                  {'category': 'spot', 'symbol': symbol})
    instruments = instrument.get('list') or []
    if instrument.get('category') != 'spot' or len(instruments) != 1 or instruments[0].get('symbol') != symbol:
        raise ValueError('Spot instrument scope mismatch')
    candles, pages, cursor = {}, [], end_ms - 1
    while cursor >= start_ms:
        params = {'category': 'spot', 'symbol': symbol, 'interval': '5',
                  'start': start_ms, 'end': cursor, 'limit': 1000}
        result = await public_get(client, '/v5/market/kline', params)
        if result.get('category') != 'spot' or result.get('symbol') != symbol:
            raise ValueError('Spot candle provenance mismatch')
        rows = result.get('list') or []
        if not rows:
            raise ValueError('Incomplete Spot history')
        oldest = min(int(row[0]) for row in rows)
        if oldest > cursor:
            raise ValueError('History pagination did not advance')
        for row in rows:
            stamp = int(row[0])
            if not start_ms <= stamp < end_ms or stamp > cursor:
                raise ValueError('Candle outside requested closed-bar window')
            candle = dict(timestamp_ms=stamp, open=float(row[1]), high=float(row[2]),
                          low=float(row[3]), close=float(row[4]), volume=float(row[5]))
            if stamp in candles and candles[stamp] != candle:
                raise ValueError('Conflicting duplicate candle')
            candles[stamp] = candle
        pages.append({'start': start_ms, 'end': cursor, 'rows': len(rows)})
        cursor = oldest - 1
        if len(pages) > 100:
            raise ValueError('History pagination bound exceeded')
        await asyncio.sleep(.15)
    ordered = [candles[t] for t in sorted(candles)]
    return {'schema_version': 1, 'provider': 'BYBIT', 'product': 'SPOT',
            'source_environment': 'MAINNET_PUBLIC', 'source_url': BASE_URL,
            'endpoint': '/v5/market/kline', 'symbol': symbol, 'interval': '5m',
            'start_ms': start_ms, 'end_ms_exclusive': end_ms,
            'collected_at_ms': int(time.time() * 1000), 'pages': pages,
            'instrument': instruments[0], 'candles': ordered,
            'candles_sha256': digest(ordered)}


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--days', type=int, default=42, choices=range(7, 91))
    parser.add_argument('--symbols', nargs='+', choices=SYMBOLS, default=list(SYMBOLS))
    args = parser.parse_args()
    end = int(time.time() * 1000) // STEP_MS * STEP_MS
    start = end - args.days * 86_400_000
    args.output.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        for symbol in args.symbols:
            bundle = await collect_spot(client, symbol, start, end)
            path = args.output / f'{symbol}-spot-5m-{start}-{end}.json'
            # Preserve existing datasets; public history never overwrites the DB.
            with path.open('x') as handle:
                json.dump(bundle, handle, allow_nan=False)
            print(json.dumps({'symbol': symbol, 'candles': len(bundle['candles']),
                              'file': str(path), 'sha256': bundle['candles_sha256']}), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
