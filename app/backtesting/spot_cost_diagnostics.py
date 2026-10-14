"""Describe frozen Spot trade costs; never select or modify entry rules."""
import argparse
import json
import math
from collections import Counter
from pathlib import Path
from statistics import median

from app.backtesting import spot_walk_forward as baseline
from app.backtesting import spot_exit_comparison as exits


def _entry_costs(entry, rows, fee_bps, slip_bps):
    fee, slip = fee_bps / 10_000, slip_bps / 10_000
    price, quantity = entry['price'], entry['quantity']
    value = exits._entry_atr(rows, entry['index'])
    distance = value * exits.STOP_MULTIPLIER if value else 0
    valid = math.isfinite(distance) and 0 < distance < price
    target = price + distance * exits.TARGET_RR if valid else None
    # Exact same modeled target fill/fees as the ATR simulator.
    target_net = (quantity * (target * (1 - slip) - price)
                  - entry['fee'] - quantity * target * (1 - slip) * fee) if valid else None
    target_bps = distance * exits.TARGET_RR / price * 10_000 if valid else None
    approximate_cost_bps = 2 * (fee_bps + slip_bps)
    ratio = target_bps / approximate_cost_bps if valid and approximate_cost_bps else None
    return {'entry_index': entry['index'], 'entry_ms': rows[entry['index']]['timestamp_ms'],
            'route': entry['route'], 'quantity': quantity, 'entry_fill': price,
            'entry_notional': quantity * price,
            'atr': value if value is not None and math.isfinite(value) else None,
            'atr_stop_bps': distance / price * 10_000 if valid else None,
            'atr_target_bps': target_bps,
            'approximate_round_trip_cost_bps': approximate_cost_bps,
            'target_to_approximate_cost_ratio': ratio,
            'hypothetical_target_net_pnl': target_net,
            'target_cost_bucket': ('INVALID_ATR' if not valid else 'ZERO_MODELED_COST'
                if not approximate_cost_bps else 'TARGET_LE_COST' if ratio <= 1
                else 'TARGET_LE_2X_COST' if ratio <= 2 else 'TARGET_GT_2X_COST')}


def _closed_costs(trade, rows, slip_bps):
    slip = slip_bps / 10_000
    quantity = trade['quantity']
    reference_entry = float(rows[trade['index']]['open'])
    reference_exit = trade['exit_price'] / (1 - slip)
    reference_move = quantity * (reference_exit - reference_entry)
    slip_drag = quantity * ((trade['price'] - reference_entry)
                            + (reference_exit - trade['exit_price']))
    fees = trade['fee'] + trade['exit_fee']
    if not math.isclose(reference_move - slip_drag - fees, trade['pnl'], abs_tol=1e-8):
        raise ValueError('Trade cost decomposition failed')
    return {'reference_price_move_pnl': reference_move, 'slippage_drag': slip_drag,
            'fees': fees, 'net_pnl': trade['pnl'],
            'exit_ms': rows[trade['exit_index']]['timestamp_ms'],
            'holding_bars': trade['exit_index'] - trade['index'],
            'exit_reason': trade.get('exit_reason', 'SIGNAL'),
            'positive_reference_move_but_net_loss': reference_move > 0 and trade['pnl'] < 0}


def _group(records):
    closed = [r for r in records if r['closed']]
    ratios = [r['target_to_approximate_cost_ratio'] for r in records
              if r['target_to_approximate_cost_ratio'] is not None]
    notionals = [r['entry_notional'] for r in records]
    return {'entries': len(records), 'closes': len(closed),
            'open_entries': len(records) - len(closed),
            'median_entry_notional': round(median(notionals), 6) if notionals else None,
            'median_target_to_approximate_cost_ratio': round(median(ratios), 4) if ratios else None,
            'target_cost_buckets': dict(Counter(r['target_cost_bucket'] for r in records)),
            'hypothetical_target_nonpositive_net_entries': sum(
                r['hypothetical_target_net_pnl'] is not None
                and r['hypothetical_target_net_pnl'] <= 0 for r in records),
            'closed_reference_price_move_pnl': round(sum(r['reference_price_move_pnl'] for r in closed), 6),
            'closed_slippage_drag': round(sum(r['slippage_drag'] for r in closed), 6),
            'closed_fees': round(sum(r['fees'] for r in closed), 6),
            'closed_net_pnl': round(sum(r['net_pnl'] for r in closed), 6),
            'positive_reference_move_but_net_loss_closes': sum(
                r['positive_reference_move_but_net_loss'] for r in closed),
            'median_holding_bars': median([r['holding_bars'] for r in closed]) if closed else None,
            'exit_reasons': dict(Counter(r['exit_reason'] for r in closed))}


def diagnose_spot_costs(bundle, *, capital, fee_bps, slippage_cases,
                        train_bars=2016, test_bars=1008):
    # Use the original assumption validation; simulations themselves are unchanged.
    original = baseline.walk_forward_spot(bundle, capital=capital, fee_bps=fee_bps,
        slippage_cases=slippage_cases, train_bars=train_bars, test_bars=test_bars)
    rows, rules = baseline.validate_bundle(bundle)
    signals = baseline._signals(rows)
    start = baseline.WARMUP + train_bars
    scenarios = []
    for slip in slippage_cases:
        simulations = {
            'signal': baseline._simulate(rows, signals, start, len(rows), baseline.PARAMS,
                                          rules, capital, fee_bps, slip),
            'signal_plus_atr': exits._simulate_atr(rows, signals, start, len(rows), rules,
                                                   capital, fee_bps, slip)}
        policies = {}
        for name, result in simulations.items():
            records = []
            for trade in result['trades']:
                records.append(_entry_costs(trade, rows, fee_bps, slip)
                    | _closed_costs(trade, rows, slip) | {'closed': True})
            if result['open_entry']:
                records.append(_entry_costs(result['open_entry'], rows, fee_bps, slip)
                               | {'closed': False})
            policies[name] = {'summary': _group(records),
                'entry_routes': {route: _group([r for r in records if r['route'] == route])
                                  for route in sorted({r['route'] for r in records})},
                'cost_buckets': {bucket: _group([r for r in records if r['target_cost_bucket'] == bucket])
                                  for bucket in sorted({r['target_cost_bucket'] for r in records})},
                'end_marked_equity': round(result['end_equity'], 6),
                'open_entry_fee': result['open_entry']['fee'] if result['open_entry'] else 0,
                'blockers': result['blockers'], 'entries': records}
        scenarios.append({'fee_bps_per_leg': fee_bps, 'slippage_bps_per_leg': slip,
                          'policies': policies})
    return {k: original[k] for k in ('mode', 'executable', 'live_eligible', 'symbol',
        'product', 'interval', 'quote_currency', 'dataset_sha256', 'frozen_settings',
        'initial_capital_per_asset', 'parameter_optimization')} | {
        'experiment': 'DESCRIPTIVE_ENTRY_COST_DIAGNOSTICS',
        'evaluation_status': 'EXPLORATORY_PREVIOUSLY_INSPECTED_DATA',
        'entry_filters_changed': False,
        'validation_start_ms': rows[start]['timestamp_ms'],
        'validation_end_exclusive_ms': bundle['end_ms_exclusive'],
        'scenarios': scenarios,
        'limitations': [
            'Descriptive buckets are not entry filters; no threshold or strategy is selected.',
            'ATR targets are hypothetical for signal-only entries and do not predict target hits.',
            'Approximate cost is 2*(fee+slippage) bps; exact target net uses modeled entry/exit fees.',
            'Reference move minus slippage minus fees reconciles each frozen trade path.',
            'Reference move is not a zero-cost rerun: quantities, levels and trade timing stay fixed.',
            'Closed-cost sums exclude final open entry fees; those are shown separately.',
            'Route and cost cohorts are observational, dependent and not causal evidence.',
            'Previously inspected data, current size rules and modeled costs; no live eligibility.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--capital', type=float, required=True)
    parser.add_argument('--fee-bps', type=float, required=True)
    parser.add_argument('--slippage-bps', required=True)
    args = parser.parse_args()
    report = diagnose_spot_costs(json.loads(args.input.read_text()), capital=args.capital,
        fee_bps=args.fee_bps, slippage_cases=[float(v) for v in args.slippage_bps.split(',')])
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    print(json.dumps({'symbol': report['symbol'], 'report': str(args.output),
        'scenarios': [{'slippage_bps_per_leg': s['slippage_bps_per_leg'],
                      'policies': {p: v['summary'] for p, v in s['policies'].items()}}
                      for s in report['scenarios']]}), flush=True)


if __name__ == '__main__':
    main()
