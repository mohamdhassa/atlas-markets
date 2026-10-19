"""Standalone offline RSI experiment. Never import into a running web/worker process."""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

from app.analysis import technical
from app.backtesting import spot_walk_forward as baseline

_ORIGINAL_RSI = technical.rsi
POLICY = 'FLAT_RSI_50_V1'


def research_rsi(values, period=14):
    """Only a completely flat lookback becomes neutral; other math stays frozen."""
    if len(values) > period:
        window = values[-period - 1:]
        if all(value == window[0] for value in window):
            return 50.0
    return _ORIGINAL_RSI(values, period)


def compare_rsi(bundle, *, capital, fee_bps, slippage_cases,
                train_bars=2016, test_bars=1008):
    # The unmodified evaluator validates scope, hashes, bars, costs and sample size.
    options = dict(capital=capital, fee_bps=fee_bps,
                   slippage_cases=slippage_cases, train_bars=train_bars,
                   test_bars=test_bars)
    current = baseline.walk_forward_spot(bundle, **options)
    # Process-local and exception-safe, only for this standalone research command.
    # Both the shared signal engine and router see the same candidate indicator.
    with patch.object(technical, 'rsi', research_rsi):
        candidate = baseline.walk_forward_spot(bundle, **options)
    rows = bundle['candles']
    closes = [float(row['close']) for row in rows]
    first = baseline.WARMUP + train_bars
    changed_windows = sum(
        len(set(closes[i - 14:i + 1])) == 1
        for i in range(first - 1, len(rows) - 1))
    return {
        'mode': 'SIMULATED_RESEARCH', 'executable': False, 'live_eligible': False,
        'candidate_policy': POLICY, 'symbol': bundle['symbol'],
        'dataset_sha256': bundle['candles_sha256'],
        'validation_start_ms': rows[first]['timestamp_ms'],
        'validation_end_exclusive_ms': bundle['end_ms_exclusive'],
        'validation_decisions_with_flat_rsi_lookback': changed_windows,
        'policies': {'CURRENT': current, POLICY: candidate},
        'limitations': [
            'Exploratory reuse of previously inspected data, not an independent holdout.',
            'Changes only flat-lookback RSI from 100 to 50; no threshold optimization.',
            'Same router, costs, sizing, next-open fills and marked-equity sampling.',
            'Shared baseline limitations apply to both policies, including no native protection.',
            'No broker orders, database access, live settings or runtime indicator changes.',
            'Standalone single-threaded process only; indicator patch must not run inside an app worker.',
            'Freeze policy before fresh prospective observation; no automatic promotion.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--capital', type=float, required=True)
    parser.add_argument('--fee-bps', type=float, required=True)
    parser.add_argument('--slippage-bps', required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = compare_rsi(json.loads(args.input.read_text()), capital=args.capital,
                         fee_bps=args.fee_bps,
                         slippage_cases=[float(v) for v in args.slippage_bps.split(',')])
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    print(json.dumps({
        'symbol': report['symbol'], 'report': str(args.output),
        'flat_rsi_windows': report['validation_decisions_with_flat_rsi_lookback'],
        'policies': {key: [
            {'slippage_bps': s['slippage_bps_per_leg'], **s['validation']}
            for s in value['scenarios']]
            for key, value in report['policies'].items()},
    }, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
