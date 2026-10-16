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


def entry_candle_quality(rows, timeframe, *, now_ms=None):
    """Additional entry-only coverage/freshness gate, after completion validation."""
    now_ms = int(time.time()*1000) if now_ms is None else now_ms
    duration = INTERVAL_MS[timeframe]
    end = rows[-1].get('bar_end_ms', rows[-1]['timestamp_ms']+duration) if rows else None
    age = now_ms-end if end is not None else None
    reason = ('ENTRY_CANDLE_HISTORY_INSUFFICIENT' if len(rows)<200 else
              'ENTRY_CANDLES_STALE' if age is None or not 0<=age<=duration+90_000 else None)
    return {'count':len(rows), 'required_count':200, 'timeframe':timeframe,
            'last_end_ms':end, 'age_ms':age, 'maximum_age_ms':duration+90_000,
            'reason':reason}


def ibkr_entry_quote_quality(quote, *, side=None, now_ms=None):
    """Arrival freshness is not a claim about the age of a market event."""
    now_ms = int(time.time()*1000) if now_ms is None else now_ms
    fields = ('ask','last','bid') if side=='BUY' else ('bid','last','ask')
    field = next((k for k in fields if isinstance(quote.get(k),(int,float))
                  and math.isfinite(quote[k]) and quote[k]>0), None)
    received = quote.get(str(field)+'_received_at_ms')
    age = now_ms-received if type(received) is int else None
    trade = quote.get('last_trade_at_ms')
    trade_age = now_ms-trade if type(trade) is int else None
    reason = None
    if (quote.get('source')!='SNAPSHOT' or quote.get('market_data_type')!=1
            or quote.get('delayed_ticks')):
        reason = 'IBKR_ENTRY_REALTIME_QUOTE_REQUIRED'
    elif field is None:
        reason = 'IBKR_ENTRY_QUOTE_PRICE_INVALID'
    elif age is None or not 0<=age<=30_000:
        reason = 'IBKR_ENTRY_QUOTE_STALE'
    elif field=='last' and trade is None:
        reason = 'IBKR_ENTRY_LAST_TRADE_TIME_REQUIRED'
    elif field=='last' and (trade_age is None or not -2_000<=trade_age<=30_000):
        reason = 'IBKR_ENTRY_LAST_TRADE_STALE'
    return {'source':quote.get('source'), 'market_data_type':quote.get('market_data_type'),
            'data_status':{1:'LIVE',2:'FROZEN',3:'DELAYED',4:'DELAYED_FROZEN'}.get(quote.get('market_data_type'),'UNKNOWN'),
            'price_field':field, 'received_age_ms':age,
            'last_trade_age_ms':trade_age, 'maximum_age_ms':30_000,
            'source_timestamp_available':trade is not None, 'reason':reason}
