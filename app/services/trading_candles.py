"""Completed, timestamped candles at the decision boundary; charts are untouched."""
import math
import time

INTERVAL_MS = {f'{n}m': n * 60_000 for n in (1,3,5,15,30)} | {
    f'{n}h': n * 3_600_000 for n in (1,2,4,6,12)} | {'1d': 86_400_000}


def completed_trading_candles(rows, timeframe, *, now_ms=None, limit=200):
    duration = INTERVAL_MS.get(timeframe)
    if duration is None:
        raise ValueError('TRADING_CANDLE_INTERVAL_UNSUPPORTED')
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    completed, previous = [], None
    for row in rows:
        stamp = row.get('timestamp_ms')
        if type(stamp) is not int or stamp <= 0:
            raise ValueError('TRADING_CANDLE_TIMESTAMP_REQUIRED')
        if previous is not None and stamp <= previous:
            raise ValueError('TRADING_CANDLE_ORDER_INVALID')
        previous = stamp
        if row.get('interval', timeframe) != timeframe:
            raise ValueError('TRADING_CANDLE_INTERVAL_MISMATCH')
        end = row.get('bar_end_ms', stamp + duration)
        if type(end) is not int or end <= stamp:
            raise ValueError('TRADING_CANDLE_END_INVALID')
        # Daily exchange-calendar bars may span 23/25 hours across DST.
        if ((timeframe != '1d' and end != stamp + duration)
                or (timeframe == '1d' and not 23*3_600_000 <= end-stamp <= 25*3_600_000)):
            raise ValueError('TRADING_CANDLE_END_INVALID')
        values = [float(row[k]) for k in ('open','high','low','close')]
        o,h,l,c = values
        if not all(math.isfinite(v) and v > 0 for v in values) or l > min(o,c) or h < max(o,c):
            raise ValueError('TRADING_CANDLE_OHLC_INVALID')
        if end <= now_ms:
            completed.append(dict(row))
    if len(completed) < 30:
        raise ValueError('TRADING_COMPLETED_CANDLES_INSUFFICIENT')
    return completed[-limit:]


def completed_ibkr_candles(payload, timeframe):
    if payload.get('actual_timeframe') != timeframe:
        raise ValueError('IBKR_CANDLE_TIMEFRAME_UNVERIFIED')
    return completed_trading_candles(payload.get('list', []), timeframe)
