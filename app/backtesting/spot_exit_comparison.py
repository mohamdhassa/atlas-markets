"""Offline, exploratory comparison of signal exits and fixed ATR protection."""
import argparse
import json
import math
from collections import Counter
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

from app.analysis.technical import atr
from app.backtesting import spot_walk_forward as baseline

ATR_PERIOD = 14
STOP_MULTIPLIER = 1.5
TARGET_RR = 2.0


def _entry_atr(rows, index):
    # The execution candle is excluded, including on the first validation entry.
    window = rows[index - ATR_PERIOD - 1:index]
    return atr(*[[float(r[key]) for r in window]
                 for key in ('high', 'low', 'close')], period=ATR_PERIOD)


def _opening_trigger(row, entry):
    opening = float(row['open'])
    if opening <= entry['stop_loss']:
        return opening, 'GAP_STOP'
    if opening >= entry['take_profit']:
        return entry['take_profit'], 'GAP_TARGET'
    return None


def _intrabar_trigger(row, entry):
    stop = float(row['low']) <= entry['stop_loss']
    target = float(row['high']) >= entry['take_profit']
    if stop:
        return entry['stop_loss'], 'BOTH_TOUCHED_STOP_FIRST' if target else 'STOP'
    if target:
        return entry['take_profit'], 'TARGET'
    return None


def _simulate_atr(rows, signals, start, end, rules, capital, fee_bps, slip_bps):
    cash, quantity, entry, peak, drawdown = capital, 0.0, None, capital, 0.0
    trades, curve, blockers = [], [], Counter()
    fee, slip = fee_bps / 10_000, slip_bps / 10_000

    def close(index, trigger):
        nonlocal cash, quantity, entry
        price, reason = trigger
        price *= 1 - slip
        notional = quantity * price
        if notional < rules['minimum_notional'] or quantity < rules['minimum_quantity']:
            blockers['EXIT_DUST'] += 1
            return
        exit_fee = notional * fee
        pnl = quantity * (price - entry['price']) - entry['fee'] - exit_fee
        cash += notional - exit_fee
        trades.append({**entry, 'exit_index': index, 'exit_price': price,
                       'pnl': pnl, 'exit_fee': exit_fee, 'exit_reason': reason,
                       'entry_ms': rows[entry['index']]['timestamp_ms'],
                       'exit_ms': rows[index]['timestamp_ms']})
        quantity, entry = 0.0, None

    for i in range(start, end):
        signal = signals[i - 1]
        eligible = (signal and not signal['blocked']
                    and signal['strength'] >= baseline.PARAMS['minimum_signal_strength'])
        held_at_open = quantity > 0
        attempted_exit = False
        if held_at_open:
            trigger = _opening_trigger(rows[i], entry)
            if trigger is None and eligible and signal['side'] == 'SELL':
                trigger = float(rows[i]['open']), 'SIGNAL'
            if trigger:
                close(i, trigger)
                attempted_exit = True
        elif eligible and signal['side'] == 'BUY':
            measured_atr = _entry_atr(rows, i)
            price = float(rows[i]['open']) * (1 + slip)
            distance = measured_atr * STOP_MULTIPLIER if measured_atr else 0
            if not math.isfinite(distance) or distance <= 0 or distance >= price:
                blockers['INVALID_ATR_PROTECTION'] += 1
            else:
                # Exactly the baseline sizing call: ATR changes exits, not size.
                plan = baseline.build_execution_plan(decision='BUY',
                    price=float(rows[i - 1]['close']), equity=cash, available_cash=cash,
                    **{k: baseline.PARAMS[k] for k in baseline.PARAMS
                       if k != 'minimum_signal_strength'})
                step = Decimal(str(rules['step']))
                units = float((Decimal(str(plan.quantity)) / step).to_integral_value(
                    rounding=ROUND_DOWN) * step)
                notional = units * price
                if (units <= 0 or units < rules['minimum_quantity']
                        or units > rules['maximum_quantity']
                        or notional < rules['minimum_notional']
                        or notional * (1 + fee) > cash):
                    blockers['ENTRY_SIZE_OR_CASH'] += 1
                else:
                    cash -= notional * (1 + fee)
                    quantity = units
                    entry = {'index': i, 'price': price, 'fee': notional * fee,
                             'route': signal['route']['strategy'], 'quantity': units,
                             'atr': measured_atr, 'stop_loss': price - distance,
                             'take_profit': price + distance * TARGET_RR}
                    # Slippage can place the stop above the raw entry-bar open.
                    trigger = _opening_trigger(rows[i], entry)
                    if trigger:
                        close(i, trigger)
                        attempted_exit = True
        if quantity > 0 and not attempted_exit:
            trigger = _intrabar_trigger(rows[i], entry)
            if trigger:
                close(i, trigger)
        equity = cash + quantity * float(rows[i]['close'])
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak * 100)
        curve.append(equity)
    return {'trades': trades, 'curve': curve, 'end_equity': curve[-1],
            'max_close_equity_drawdown_pct': round(drawdown, 4),
            'open_quantity': quantity, 'open_entry': entry, 'blockers': dict(blockers)}


def compare_spot_exits(bundle, *, capital, fee_bps, slippage_cases,
                       train_bars=2016, test_bars=1008):
    # Preserve the original report/assumption validation and baseline verbatim.
    original = baseline.walk_forward_spot(bundle, capital=capital, fee_bps=fee_bps,
        slippage_cases=slippage_cases, train_bars=train_bars, test_bars=test_bars)
    rows, rules = baseline.validate_bundle(bundle)
    signals = baseline._signals(rows)
    start = baseline.WARMUP + train_bars
    scenarios = []
    for scenario in original['scenarios']:
        result = _simulate_atr(rows, signals, start, len(rows), rules, capital,
                               fee_bps, scenario['slippage_bps_per_leg'])
        trades = result['trades']
        candidate = {**baseline._metrics(trades),
            'end_marked_equity': round(result['end_equity'], 6),
            'marked_return_pct': round((result['end_equity'] / capital - 1) * 100, 4),
            'max_close_equity_drawdown_pct': result['max_close_equity_drawdown_pct'],
            'open_quantity': result['open_quantity'],
            'open_entry': result['open_entry'],
            'open_entry_fee': round(result['open_entry']['fee'], 6) if result['open_entry'] else 0,
            'blockers': result['blockers'],
            'exit_reasons': dict(Counter(t['exit_reason'] for t in trades))}
        folds = []
        for fold in scenario['folds']:
            closed = [t for t in trades if fold['test_start_ms'] <= t['exit_ms']
                      < fold['test_end_exclusive_ms']]
            folds.append({k: fold[k] for k in ('test_start_ms', 'test_end_exclusive_ms', 'test_bars')}
                         | {'signal': fold['validation'],
                            'signal_plus_atr': baseline._metrics(closed)})
        scenarios.append({'fee_bps_per_leg': fee_bps,
            'slippage_bps_per_leg': scenario['slippage_bps_per_leg'],
            'policies': {'signal': scenario['validation'], 'signal_plus_atr': candidate},
            'signal_entry_routes': scenario['entry_routes'],
            'atr_entry_routes': {route: baseline._metrics([t for t in trades if t['route'] == route])
                                 for route in sorted({t['route'] for t in trades})},
            'folds': folds,
            'marked_equity_difference': round(candidate['end_marked_equity']
                - scenario['validation']['end_marked_equity'], 6)})
    return {k: original[k] for k in ('mode', 'executable', 'live_eligible', 'symbol',
        'product', 'interval', 'quote_currency', 'dataset_sha256', 'candles',
        'initial_capital_per_asset', 'frozen_settings', 'parameter_optimization')} | {
        'experiment': 'SIGNAL_VS_SIGNAL_PLUS_FIXED_ATR',
        'evaluation_status': 'EXPLORATORY_PREVIOUSLY_INSPECTED_DATA',
        'atr_period': ATR_PERIOD, 'atr_method': 'MEAN_TRUE_RANGE',
        'stop_atr_multiplier': STOP_MULTIPLIER, 'target_rr': TARGET_RR,
        'validation_start_ms': rows[start]['timestamp_ms'],
        'validation_end_exclusive_ms': bundle['end_ms_exclusive'],
        'scenarios': scenarios,
        'limitations': [
            'Previously inspected data: this comparison is not an independent holdout.',
            'Fixed entry rules and baseline sizing; changed exits can change future trade availability.',
            'ATR uses only completed preceding bars; fixed levels anchor to modeled entry fill.',
            'Opening triggers precede signal exits; intrabar triggers follow entry/open exits.',
            'Stop gaps fill at adverse slipped open; favorable target gaps are capped at target.',
            'Both intrabar levels touched: stop first, including the entry candle.',
            'Hypothetical market-trigger exits with adverse slippage, not native limit/OCO orders.',
            'Only candle-close marked drawdown; intrabar equity extremes are unknown.',
            'Continuous validation inventory, no fold-end liquidation; final inventory remains marked.',
            'Current instrument rules, modeled quote-currency fees; liquidity/rejections/outages omitted.',
            'Independent asset capital, no combined portfolio or live-money eligibility.',
            'Production Bybit exits are unchanged; prospective paper evidence is still required.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--capital', type=float, required=True)
    parser.add_argument('--fee-bps', type=float, required=True)
    parser.add_argument('--slippage-bps', required=True)
    args = parser.parse_args()
    report = compare_spot_exits(json.loads(args.input.read_text()), capital=args.capital,
        fee_bps=args.fee_bps, slippage_cases=[float(v) for v in args.slippage_bps.split(',')])
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    print(json.dumps({'symbol': report['symbol'], 'report': str(args.output),
                     'scenarios': [{k: s[k] for k in ('slippage_bps_per_leg', 'policies',
                                                      'marked_equity_difference')}
                                   for s in report['scenarios']]}), flush=True)


if __name__ == '__main__':
    main()
