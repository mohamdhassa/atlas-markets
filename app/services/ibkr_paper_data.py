"""Explicit delayed reference prices for Paper entries; never Live authorization."""
import math
from app.services.trading_candles import entry_candle_quality

POLICY = 'IBKR_PAPER_DELAYED_DATA'


async def delayed_paper_mode(settings, environment, broker, *, health=None):
    if (not getattr(settings, 'ibkr_paper_delayed_data_enabled', False)
            or str(environment).upper() != 'PAPER'
            or getattr(settings, 'allow_live_trading', False)):
        return False
    health = await broker.health() if health is None else health
    if health.get('connected') is not True or health.get('simulation') is not True:
        raise ValueError('IBKR_PAPER_BRIDGE_REQUIRED')
    return True


def delayed_reference(candles, timeframe, *, now_ms=None):
    quality = entry_candle_quality(candles, timeframe, now_ms=now_ms, paper_delayed=True)
    if quality['reason']:
        raise ValueError(quality['reason'])
    value = float(candles[-1]['close'])
    if not math.isfinite(value) or value <= 0:
        raise ValueError('IBKR_ENTRY_QUOTE_PRICE_INVALID')
    quote = {'last': value, 'source': 'PAPER_DELAYED_CANDLE_REFERENCE',
             'data_status': 'DELAYED_SIMULATION',
             'reference_bar_end_ms': quality['last_end_ms']}
    evidence = {**quote, 'policy': POLICY, 'price_field': 'last',
                'age_ms': quality['age_ms'], 'maximum_age_ms': quality['maximum_age_ms'],
                'reason': None, 'real_time': False}
    return quote, evidence
