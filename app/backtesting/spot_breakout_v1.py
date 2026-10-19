"""Frozen prospective Spot breakout research; no production strategy integration."""
import argparse
import json
import math
from collections import Counter
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from statistics import mean

from app.analysis.technical import atr, ema
from app.backtesting.spot_history import STEP_MS, digest
from app.backtesting.spot_timeframe_comparison import aggregate_fifteen
from app.backtesting.spot_walk_forward import validate_bundle, _metrics

POLICY = {
    'id': 'SPOT_BREAKOUT_15M_V1', 'signal_timeframe': '15m',
    'lookback_bars': 200, 'breakout_prior_bars': 20,
    'fast_ema': 20, 'slow_ema': 50, 'volume_multiple': 1.5,
    'atr_period': 14, 'stop_atr_multiple': 2.0, 'target_r_multiple': 3.0,
    'risk_pct': 1.0, 'max_notional_pct': 20.0,
    'fee_bps_per_leg': 10, 'slippage_cases_bps_per_leg': [2, 5, 10],
    'prospective_start_ms': 1792454400000,  # 2026-10-20 00:00 UTC
    'minimum_validation_5m_bars': 4032,  # 14 days after warmup.
}
POLICY_SHA256 = digest(POLICY)


def decisions(rows):
    """Emit once per completed 15m bar; all indicators use at most 200 bars."""
    bars, indices = aggregate_fifteen(rows)
    signals = [None] * len(rows)
    for j in range(POLICY['lookback_bars'] - 1, len(bars)):
        window = bars[j - POLICY['lookback_bars'] + 1:j + 1]
        current, prior = window[-1], window[-21:-1]
        closes = [r['close'] for r in window]
        fast, slow = ema(closes, 20), ema(closes, 50)
        volatility = atr(*[[r[k] for r in window] for k in ('high', 'low', 'close')])
        volume_mean = mean(r['volume'] for r in prior)
        buy = (current['close'] > max(r['high'] for r in prior)
               and fast > slow and volume_mean > 0
               and current['volume'] >= 1.5 * volume_mean)
        # Exit criterion is independent of entry filters and volume.
        side = 'SELL' if current['close'] < fast else 'BUY' if buy else 'HOLD'
        signals[indices[j]] = {'side': side, 'atr': volatility,
                               'decision_end_ms': current['timestamp_ms'] + 3 * STEP_MS}
    return signals


def simulate(rows, signals, start, rules, capital, slip_bps):
    cash, qty, entry, peak, drawdown = capital, 0., None, capital, 0.
    trades, blockers, curve = [], Counter(), []
    fee, slip = .001, slip_bps / 10000

    def close(i, reference, reason):
        nonlocal cash, qty, entry
        price = reference * (1 - slip)
        notional = qty * price
        if notional < rules['minimum_notional'] or qty < rules['minimum_quantity']:
            blockers['EXIT_BELOW_MINIMUM'] += 1
            return False
        exit_fee = notional * fee
        cash += notional - exit_fee
        trades.append({**entry, 'exit_index': i, 'exit_ms': rows[i]['timestamp_ms'],
                       'exit_price': price, 'exit_fee': exit_fee, 'exit_reason': reason,
                       'pnl': qty * (price - entry['price']) - entry['fee'] - exit_fee})
        qty, entry = 0., None
        return True

    for i in range(start, len(rows)):
        row, signal = rows[i], signals[i - 1]
        opening = float(row['open'])
        held = qty > 0
        attempted_exit = False
        if held:
            reason, trigger = None, None
            if opening <= entry['stop_loss']:
                reason, trigger = 'GAP_STOP', opening
            elif opening >= entry['take_profit']:
                reason, trigger = 'GAP_TARGET', entry['take_profit']
            elif signal and signal['side'] == 'SELL':
                reason, trigger = 'EMA_EXIT', opening
            if trigger is not None:
                close(i, trigger, reason)
                attempted_exit = True
        elif signal and signal['side'] == 'BUY':
            price = opening * (1 + slip)
            distance = float(signal['atr'] or 0) * 2
            if not math.isfinite(distance) or not 0 < distance < price:
                blockers['INVALID_STOP_DISTANCE'] += 1
            else:
                # Risk is price-distance risk; fees, slippage and gaps can add loss.
                units = min(cash * .01 / distance, cash * .2 / price,
                            cash / (price * (1 + fee)), rules['maximum_quantity'])
                step = Decimal(str(rules['step']))
                units = float((Decimal(str(units)) / step).to_integral_value(rounding=ROUND_DOWN) * step)
                notional = units * price
                if (units <= 0 or units < rules['minimum_quantity']
                        or notional < rules['minimum_notional']
                        or notional * (1 + fee) > cash):
                    blockers['ENTRY_SIZE_OR_CASH'] += 1
                else:
                    qty = units
                    cash -= notional * (1 + fee)
                    entry = {'index': i, 'entry_ms': row['timestamp_ms'],
                             'price': price, 'quantity': qty, 'fee': notional * fee,
                             'stop_loss': price - distance, 'take_profit': price + 3 * distance,
                             'atr_15m': signal['atr'], 'route': POLICY['id']}
                    if opening <= entry['stop_loss']:
                        close(i, opening, 'ENTRY_GAP_STOP')
                        attempted_exit = True
        if qty > 0 and not attempted_exit:
            stop = row['low'] <= entry['stop_loss']
            target = row['high'] >= entry['take_profit']
            if stop or target:
                close(i, entry['stop_loss'] if stop else entry['take_profit'],
                      'BOTH_TOUCHED_STOP_FIRST' if stop and target else 'STOP' if stop else 'TARGET')
        equity = cash + qty * row['close']
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak * 100)
        curve.append(equity)
    return {'trades': trades, 'end_marked_equity': curve[-1],
            'max_5m_close_equity_drawdown_pct': drawdown,
            'open_quantity': qty, 'open_entry': entry, 'blockers': dict(blockers)}


def evaluate(bundle):
    rows, rules = validate_bundle(bundle)
    if bundle['start_ms'] < POLICY['prospective_start_ms']:
        raise ValueError('Previously inspected history is excluded from this prospective policy')
    if len(rows) < 600 + POLICY['minimum_validation_5m_bars'] + 3:
        raise ValueError('Need 200 completed 15m warmup bars plus 14 validation days')
    signals = decisions(rows)
    first = next(i for i, s in enumerate(signals) if s is not None) + 1
    if len(rows) - first < POLICY['minimum_validation_5m_bars']:
        raise ValueError('Insufficient post-warmup validation history')
    scenarios = []
    for slip in POLICY['slippage_cases_bps_per_leg']:
        result = simulate(rows, signals, first, rules, 100., slip)
        scenarios.append({'slippage_bps_per_leg': slip, 'fee_bps_per_leg': 10,
            **_metrics(result['trades']), **result,
            'marked_return_pct': result['end_marked_equity'] - 100})
    return {'mode': 'SIMULATED_RESEARCH', 'executable': False, 'live_eligible': False,
            'policy': POLICY, 'policy_sha256': POLICY_SHA256,
            'symbol': bundle['symbol'], 'dataset_sha256': bundle['candles_sha256'],
            'initial_capital_per_independent_asset': 100,
            'validation_start_ms': rows[first]['timestamp_ms'],
            'validation_end_exclusive_ms': bundle['end_ms_exclusive'],
            'no_trade_end_equity': 100, 'scenarios': scenarios,
            'limitations': [
                'Hypothesis only; no optimization or automatic production adoption.',
                'Simulated protective exits are not broker-held protection.',
                'Five-minute bars cannot establish intrabar ordering; both touches use stop first.',
                'Current lot rules proxy history. Fees are assumptions in quote currency.',
                'No liquidity, rejected/partial fills, outages or combined portfolio controls.',
                'Close-marked drawdown understates possible intrabar risk. Final inventory stays marked.',
                'Risk sizing excludes fees, slippage and gaps; no guaranteed loss cap.',
                'Prospective date is a cutoff rule, not independent proof of untouched data.',
            ]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = evaluate(json.loads(args.input.read_text()))
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    print(json.dumps({k: v for k, v in report.items() if k != 'scenarios'} | {
        'scenarios': [{k: v for k, v in s.items() if k != 'trades'}
                      for s in report['scenarios']]}, allow_nan=False))


if __name__ == '__main__':
    main()
