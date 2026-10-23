"""Explicit Paper-only ATR sizing candidate; baseline stays opt-out."""
import math
from app.analysis.technical import atr


def sizing_atr(settings, environment, candles):
    enabled = bool(getattr(settings, 'ibkr_paper_atr_sizing_enabled', False))
    if not enabled:
        return None, {'basis': 'PRICE_PERCENT_FALLBACK', 'atr_period': None,
                      'atr_value': None, 'minimum_distance_pct': 0.5}
    if environment != 'PAPER' or getattr(settings, 'allow_live_trading', False):
        raise ValueError('IBKR_ATR_SIZING_PAPER_ONLY')
    if len(candles) < 15:
        raise ValueError('IBKR_SIZING_ATR_HISTORY_INSUFFICIENT')
    # Only the last 15 completed bars contribute to the existing 14-bar SMA ATR.
    window = candles[-15:]
    try:
        highs, lows, closes = ([float(row[key]) for row in window]
                              for key in ('high', 'low', 'close'))
        if any(not math.isfinite(value) or value <= 0
               for values in (highs, lows, closes) for value in values):
            raise ValueError
        if any(h < l or not l <= c <= h for h, l, c in zip(highs, lows, closes)):
            raise ValueError
        value = atr(highs, lows, closes, period=14)
        if value is None or not math.isfinite(value) or value <= 0:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValueError('IBKR_SIZING_ATR_UNAVAILABLE') from None
    return value, {'basis': 'COMPLETED_CANDLE_ATR', 'atr_period': 14,
                   'atr_method': 'SMA_TRUE_RANGE', 'atr_value': value,
                   'reference_bar_end_ms': window[-1].get('bar_end_ms'),
                   'minimum_distance_pct': 0.5}
