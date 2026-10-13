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
PAGE_SIZE = 500
TRANSIENT_CODES = {10000, 10006, 10016}


def digest(candles):
    return hashlib.sha256(json.dumps(candles, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


async def public_get(client, path, params):
    # Only public GET endpoints. No private client, credentials or order methods.
    if path not in {'/v5/market/kline', '/v5/market/instruments-info', '/v5/market/time'}:
        raise ValueError('Unsupported public data endpoint')
    for attempt in range(3):
        try:
            response = await client.get(path, params=params)
        except (httpx.TimeoutException, httpx.ConnectError):
            if attempt == 2:
                raise
            await asyncio.sleep(1 + attempt)
            continue
        if (response.status_code == 429 or 500 <= response.status_code < 600) and attempt < 2:
            await asyncio.sleep(1 + attempt)
            continue
        response.raise_for_status()
        payload = response.json()
        if payload.get('retCode') in TRANSIENT_CODES and attempt < 2:
            await asyncio.sleep(1 + attempt)
            continue
        if payload.get('retCode') != 0:
            message = ' '.join(str(payload.get('retMsg') or '').split())[:180]
            raise ValueError(f"Bybit public data error: {payload.get('retCode')} {message}")
        return payload['result']
    raise ValueError('Public data rate limit')


async def exchange_time_ms(client):
    result = await public_get(client, '/v5/market/time', {})
    stamp = int(result['timeNano']) // 1_000_000 if result.get('timeNano') else int(result['timeSecond']) * 1000
    if stamp <= 0:
        raise ValueError('Invalid Bybit server time')
    return stamp


async def collect_spot(client, symbol, start_ms, end_ms, exchange_stamp=None):
    if symbol not in SYMBOLS or start_ms % STEP_MS or end_ms % STEP_MS or start_ms >= end_ms:
        raise ValueError('Invalid Spot data window')
    instrument = await public_get(client, '/v5/market/instruments-info',
                                  {'category': 'spot', 'symbol': symbol})
    instruments = instrument.get('list') or []
    if instrument.get('category') != 'spot' or len(instruments) != 1 or instruments[0].get('symbol') != symbol:
        raise ValueError('Spot instrument scope mismatch')
    candles, pages, cursor = {}, [], end_ms - 1
    while cursor >= start_ms:
        page_start = max(start_ms, cursor + 1 - PAGE_SIZE * STEP_MS)
        params = {'category': 'spot', 'symbol': symbol, 'interval': '5',
                  'start': page_start, 'end': cursor, 'limit': PAGE_SIZE}
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
            if not page_start <= stamp < end_ms or stamp > cursor:
                raise ValueError('Candle outside requested closed-bar window')
            candle = dict(timestamp_ms=stamp, open=float(row[1]), high=float(row[2]),
                          low=float(row[3]), close=float(row[4]), volume=float(row[5]))
            if stamp in candles and candles[stamp] != candle:
                raise ValueError('Conflicting duplicate candle')
            candles[stamp] = candle
        pages.append({'start': page_start, 'end': cursor, 'rows': len(rows)})
        cursor = oldest - 1
        if len(pages) > 100:
            raise ValueError('History pagination bound exceeded')
        await asyncio.sleep(.15)
    ordered = [candles[t] for t in sorted(candles)]
    return {'schema_version': 1, 'provider': 'BYBIT', 'product': 'SPOT',
            'source_environment': 'MAINNET_PUBLIC', 'source_url': BASE_URL,
            'endpoint': '/v5/market/kline', 'symbol': symbol, 'interval': '5m',
            'start_ms': start_ms, 'end_ms_exclusive': end_ms,
            'collected_at_ms': int(time.time() * 1000), 'exchange_time_ms': exchange_stamp,
            'pages': pages,
            'instrument': instruments[0], 'candles': ordered,
            'candles_sha256': digest(ordered)}


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--days', type=int, default=42, choices=range(7, 91))
    parser.add_argument('--symbols', nargs='+', choices=SYMBOLS, default=list(SYMBOLS))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        exchange_stamp = await exchange_time_ms(client)
        end = exchange_stamp // STEP_MS * STEP_MS
        start = end - args.days * 86_400_000
        print(json.dumps({'exchange_time_ms': exchange_stamp, 'start_ms': start,
                          'end_ms_exclusive': end, 'page_size': PAGE_SIZE}), flush=True)
        for symbol in args.symbols:
            bundle = await collect_spot(client, symbol, start, end, exchange_stamp)
            path = args.output / f'{symbol}-spot-5m-{start}-{end}.json'
            # Preserve existing datasets; public history never overwrites the DB.
            with path.open('x') as handle:
                json.dump(bundle, handle, allow_nan=False)
            print(json.dumps({'symbol': symbol, 'candles': len(bundle['candles']),
                              'file': str(path), 'sha256': bundle['candles_sha256']}), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
