"""Frozen 5m versus 15m Spot signal-exit research on one calendar window."""
import argparse
import json
from collections import Counter
from pathlib import Path

from app.backtesting import spot_walk_forward as baseline
from app.backtesting.spot_history import STEP_MS, digest

FIFTEEN_MS = 3 * STEP_MS


def aggregate_fifteen(rows):
    """Input must first pass baseline validation; discard only partial edges."""
    groups = {}
    for i, row in enumerate(rows):
        bucket = row['timestamp_ms'] // FIFTEEN_MS * FIFTEEN_MS
        groups.setdefault(bucket, []).append((i, row))
    candles, last_indices = [], []
    for stamp, group in groups.items():
        if len(group) != 3:
            if stamp not in (next(iter(groups)), next(reversed(groups))):
                raise ValueError('Incomplete interior 15m candle')
            continue
        if [r['timestamp_ms'] for _, r in group] != [stamp + j * STEP_MS for j in range(3)]:
            raise ValueError('Invalid 15m constituent timestamps')
        source = [r for _, r in group]
        candles.append({'timestamp_ms': stamp, 'open': float(source[0]['open']),
            'high': max(float(r['high']) for r in source),
            'low': min(float(r['low']) for r in source),
            'close': float(source[-1]['close']),
            'volume': sum(float(r['volume']) for r in source)})
        last_indices.append(group[-1][0])
    if not candles:
        raise ValueError('No complete 15m candles')
    return candles, last_indices


def fifteen_signals(rows, aggregated, last_indices):
    signals = [None] * len(rows)
    for j in range(baseline.WARMUP - 1, len(aggregated)):
        decision_index = last_indices[j]
        if decision_index + 1 >= len(rows):
            continue  # There is no next open at which to execute.
        window = aggregated[j - baseline.WARMUP + 1:j + 1]
        signal = baseline.generate_signal(window, timeframe='15m', market='CRYPTO')
        route = baseline.route_strategy.__wrapped__(window)
        signals[decision_index] = {'side': signal.decision, 'strength': signal.strength,
            'route': route, 'blocked': baseline._router_blocker(route, signal.decision)}
    return signals


def compare_spot_timeframes(bundle, *, capital, fee_bps, slippage_cases,
                            train_bars=2016, test_bars=1008):
    # Reuse validated assumptions. The baseline module and its CLI stay unchanged.
    original = baseline.walk_forward_spot(bundle, capital=capital, fee_bps=fee_bps,
        slippage_cases=slippage_cases, train_bars=train_bars, test_bars=test_bars)
    rows, rules = baseline.validate_bundle(bundle)
    aggregated, last_indices = aggregate_fifteen(rows)
    if len(aggregated) < baseline.WARMUP:
        raise ValueError('Insufficient 15m warmup')
    earliest = max(baseline.WARMUP + train_bars, last_indices[baseline.WARMUP - 1] + 1)
    starts = [i - 2 for i in last_indices if i - 2 >= earliest]
    if not starts:
        raise ValueError('No common validation window')
    start, end = starts[0], last_indices[-1] + 1
    if end - start < 2 * test_bars:
        raise ValueError('Insufficient common validation history')
    signals = {'5m': baseline._signals(rows),
               '15m': fifteen_signals(rows, aggregated, last_indices)}
    scenarios = []
    for slip in slippage_cases:
        policies = {}
        for timeframe, decisions in signals.items():
            result = baseline._simulate(rows, decisions, start, end, baseline.PARAMS,
                                         rules, capital, fee_bps, slip)
            trades = result['trades']
            folds = []
            for left in range(start, end, test_bars):
                right = min(left + test_bars, end)
                folds.append({'start_ms': rows[left]['timestamp_ms'],
                    'end_exclusive_ms': rows[right - 1]['timestamp_ms'] + STEP_MS,
                    'source_5m_bars': right - left,
                    **baseline._metrics([t for t in trades if left <= t['exit_index'] < right])})
            eligible = [d for d in decisions[start - 1:end - 1] if d and not d['blocked']
                         and d['strength'] >= baseline.PARAMS['minimum_signal_strength']]
            policies[timeframe] = {'validation': {**baseline._metrics(trades),
                'end_marked_equity': round(result['end_equity'], 6),
                'marked_return_pct': round((result['end_equity'] / capital - 1) * 100, 4),
                'max_5m_close_equity_drawdown_pct': result['max_close_equity_drawdown_pct'],
                'open_quantity': result['open_quantity'],
                'open_entry_fee': round(result['open_entry']['fee'], 6) if result['open_entry'] else 0,
                'blockers': result['blockers']},
                'eligible_decisions': dict(Counter(d['side'] for d in eligible)),
                'entry_routes': {r: baseline._metrics([t for t in trades if t['route'] == r])
                                 for r in sorted({t['route'] for t in trades})},
                'folds': folds}
        scenarios.append({'fee_bps_per_leg': fee_bps, 'slippage_bps_per_leg': slip,
                          'policies': policies})
    return {k: original[k] for k in ('mode', 'executable', 'live_eligible', 'symbol',
        'product', 'quote_currency', 'dataset_sha256', 'initial_capital_per_asset',
        'frozen_settings', 'parameter_optimization')} | {
        'experiment': 'FROZEN_5M_VS_15M_SIGNAL_EXITS',
        'evaluation_status': 'EXPLORATORY_PREVIOUSLY_INSPECTED_DATA',
        'source_interval': '5m', 'aggregated_15m_sha256': digest(aggregated),
        'aggregated_15m_candles': len(aggregated),
        'discarded_partial_edge_5m_bars': len(rows) - 3 * len(aggregated),
        'warmup_bars_per_timeframe': baseline.WARMUP,
        'validation_start_ms': rows[start]['timestamp_ms'],
        'validation_end_exclusive_ms': rows[end - 1]['timestamp_ms'] + STEP_MS,
        'baseline_start_shift_5m_bars': start - (baseline.WARMUP + train_bars),
        'scenarios': scenarios,
        'limitations': [
            'Same common calendar window and capital; 15m aggregates complete UTC-aligned 5m triples.',
            'Signals use 200 completed bars per timeframe: 15m lookback spans three times longer.',
            '15m decisions occur once per completed 15m bar, never forward-filled between closes.',
            'Both fill at next source open and mark equity at every 5m close.',
            'Only eligible SELL signal exits; ATR exits, leverage and production changes excluded.',
            'Unchanged readiness fallback sizing, minimums, quote fees and adverse slippage.',
            'Validation starts flat and carries inventory; final open holdings remain marked.',
            'Warmup/common-boundary alignment may shift the original baseline validation start.',
            'Previously inspected data, no optimization; this does not establish a new independent holdout.',
            'Current instrument rules; liquidity, rejections, outages and portfolio exposure omitted.',
            'Independent asset runs, not combined portfolio returns or live-money eligibility.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--capital', type=float, required=True)
    parser.add_argument('--fee-bps', type=float, required=True)
    parser.add_argument('--slippage-bps', required=True)
    args = parser.parse_args()
    report = compare_spot_timeframes(json.loads(args.input.read_text()), capital=args.capital,
        fee_bps=args.fee_bps, slippage_cases=[float(v) for v in args.slippage_bps.split(',')])
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    print(json.dumps({'symbol': report['symbol'], 'report': str(args.output),
        'validation_start_ms': report['validation_start_ms'],
        'validation_end_exclusive_ms': report['validation_end_exclusive_ms'],
        'scenarios': [{'slippage_bps_per_leg': s['slippage_bps_per_leg'],
                      'policies': {p: v['validation'] for p, v in s['policies'].items()}}
                      for s in report['scenarios']]}), flush=True)


if __name__ == '__main__':
    main()
