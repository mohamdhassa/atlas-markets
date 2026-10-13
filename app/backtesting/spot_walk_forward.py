"""Frozen-settings Spot baseline; simulated research, never execution certification."""
import argparse
import json
import math
from collections import Counter
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

from app.backtesting.spot_history import BASE_URL, STEP_MS, SYMBOLS, digest
from app.services.signal_risk import generate_signal
from app.analysis.strategy_router import route_strategy
from app.services.autotrade_readiness import _router_blocker
from app.services.paper_execution import build_execution_plan

PARAMS = {'minimum_signal_strength': 65, 'risk_per_trade_pct': 1,
          'stop_atr_multiplier': 1.5, 'take_profit_rr': 2,
          'max_position_notional_pct': 20}
WARMUP = 200


def validate_bundle(bundle):
    if (bundle.get('schema_version') != 1 or bundle.get('provider') != 'BYBIT'
            or bundle.get('product') != 'SPOT' or bundle.get('source_environment') != 'MAINNET_PUBLIC'
            or bundle.get('source_url') != BASE_URL or bundle.get('endpoint') != '/v5/market/kline'
            or bundle.get('symbol') not in SYMBOLS or bundle.get('interval') != '5m'):
        raise ValueError('Only provenance-tagged Bybit public Spot 5m data is supported')
    rows = bundle['candles']
    if not 1 <= len(rows) <= 30_000 or digest(rows) != bundle['candles_sha256']:
        raise ValueError('Candle integrity or size check failed')
    start, end = bundle['start_ms'], bundle['end_ms_exclusive']
    observed_time = bundle.get('exchange_time_ms')
    if observed_time is None:
        observed_time = bundle['collected_at_ms']
    if type(observed_time) is not int or observed_time <= 0:
        raise ValueError('Invalid closed-bar observation time')
    if (start % STEP_MS or end % STEP_MS or end > observed_time
            or len(rows) != (end - start) // STEP_MS):
        raise ValueError('Incomplete or forming-bar data window')
    for i, row in enumerate(rows):
        values = [float(row[k]) for k in ('open', 'high', 'low', 'close', 'volume')]
        o, h, l, c, v = values
        if (row['timestamp_ms'] != start + i * STEP_MS
                or not all(math.isfinite(x) and abs(x) < 1e12 for x in values)
                or min(o, h, l, c) <= 0 or v < 0 or l > min(o, c) or h < max(o, c) or l > h):
            raise ValueError('Invalid, missing or unordered candle')
    instrument = bundle['instrument']
    if instrument.get('symbol') != bundle['symbol'] or instrument.get('quoteCoin') != 'USDT':
        raise ValueError('Instrument scope mismatch')
    lot = instrument['lotSizeFilter']
    rules = {'step': float(lot.get('qtyStep') or lot.get('basePrecision') or 0),
             'minimum_quantity': float(lot.get('minOrderQty') or 0),
             'minimum_notional': float(lot.get('minOrderAmt') or lot.get('minNotionalValue') or 0),
             'maximum_quantity': float(lot.get('maxMarketOrderQty') or lot.get('maxOrderQty') or 0)}
    if (not all(math.isfinite(v) and v >= 0 for v in rules.values())
            or rules['step'] <= 0 or rules['minimum_notional'] <= 0 or rules['maximum_quantity'] <= 0):
        raise ValueError('Incomplete Spot order-size metadata')
    return rows, rules


def _signals(rows):
    signals = [None] * len(rows)
    for i in range(WARMUP - 1, len(rows) - 1):
        window = rows[i - WARMUP + 1:i + 1]
        signal = generate_signal(window, timeframe='5m', market='CRYPTO')
        # Do not emit thousands of hypothetical router events into runtime telemetry.
        route = route_strategy.__wrapped__(window)
        signals[i] = {'side': signal.decision, 'strength': signal.strength,
                      'route': route, 'blocked': _router_blocker(route, signal.decision)}
    return signals


def _simulate(rows, signals, start, end, params, rules, capital, fee_bps, slip_bps):
    cash, quantity, entry, peak, drawdown = capital, 0.0, None, capital, 0.0
    trades, curve, blockers = [], [], Counter()
    fee, slip = fee_bps / 10_000, slip_bps / 10_000
    for i in range(start, end):
        signal = signals[i - 1]  # Last completed candle; next-bar open fill.
        if signal and not signal['blocked'] and signal['strength'] >= params['minimum_signal_strength']:
            side = signal['side']
            if side == 'BUY' and quantity == 0:
                price = float(rows[i]['open']) * (1 + slip)
                plan = build_execution_plan(decision='BUY', price=float(rows[i - 1]['close']),
                    equity=cash, available_cash=cash, **{k: params[k] for k in PARAMS if k != 'minimum_signal_strength'})
                units = float((Decimal(str(plan.quantity)) / Decimal(str(rules['step']))).to_integral_value(rounding=ROUND_DOWN) * Decimal(str(rules['step'])))
                notional = units * price
                if (units <= 0 or units < rules['minimum_quantity'] or units > rules['maximum_quantity']
                        or notional < rules['minimum_notional'] or notional * (1 + fee) > cash):
                    blockers['ENTRY_SIZE_OR_CASH'] += 1
                else:
                    cash -= notional * (1 + fee); quantity = units
                    entry = {'index': i, 'price': price, 'fee': notional * fee,
                             'route': signal['route']['strategy'], 'quantity': units}
            elif side == 'SELL' and quantity > 0:
                price = float(rows[i]['open']) * (1 - slip)
                notional = quantity * price
                if notional < rules['minimum_notional'] or quantity < rules['minimum_quantity']:
                    blockers['EXIT_DUST'] += 1
                else:
                    exit_fee = notional * fee
                    pnl = quantity * (price - entry['price']) - entry['fee'] - exit_fee
                    cash += notional - exit_fee
                    trades.append({**entry, 'exit_index': i, 'exit_price': price, 'pnl': pnl,
                                   'exit_fee': exit_fee, 'entry_ms': rows[entry['index']]['timestamp_ms'],
                                   'exit_ms': rows[i]['timestamp_ms']})
                    quantity, entry = 0.0, None
        equity = cash + quantity * float(rows[i]['close'])
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak * 100)
        curve.append(equity)
    return {'trades': trades, 'curve': curve, 'end_equity': curve[-1],
            'max_close_equity_drawdown_pct': round(drawdown, 4),
            'open_quantity': quantity, 'open_entry': entry, 'blockers': dict(blockers)}


def _metrics(trades):
    pnls = [t['pnl'] for t in trades]
    wins, losses = [p for p in pnls if p > 0], [p for p in pnls if p < 0]
    return {'closed_trades': len(trades), 'wins': len(wins), 'losses': len(losses),
            'net_realized_pnl': round(sum(pnls), 6),
            'expectancy': round(sum(pnls) / len(pnls), 6) if pnls else None,
            'profit_factor': round(sum(wins) / abs(sum(losses)), 4) if losses else None,
            'win_rate': round(len(wins) / len(pnls) * 100, 2) if pnls else None,
            'modeled_fees': round(sum(t['fee'] + t['exit_fee'] for t in trades), 6)}


def walk_forward_spot(bundle, *, capital, fee_bps, slippage_cases, params=None,
                      train_bars=2016, test_bars=1008):
    rows, rules = validate_bundle(bundle)
    params = dict(PARAMS if params is None else params)
    if set(params) != set(PARAMS) or not all(math.isfinite(float(v)) and float(v) > 0 for v in params.values()):
        raise ValueError('Invalid frozen settings')
    if (params['minimum_signal_strength'] > 100 or params['risk_per_trade_pct'] > 100
            or params['max_position_notional_pct'] > 100):
        raise ValueError('Settings outside percentage bounds')
    if (not math.isfinite(capital) or not 0 < capital <= 1e9
            or not math.isfinite(fee_bps) or not 0 <= fee_bps <= 100
            or not 1 <= len(slippage_cases) <= 5
            or not all(math.isfinite(v) and 0 <= v <= 100 for v in slippage_cases)
            or train_bars < WARMUP or test_bars < 100
            or len(rows) < WARMUP + train_bars + 2 * test_bars):
        raise ValueError('Insufficient history or invalid simulation assumptions')
    signals = _signals(rows)
    first_test = WARMUP + train_bars
    scenarios = []
    for slip in slippage_cases:
        validation = _simulate(rows, signals, first_test, len(rows), params, rules, capital, fee_bps, slip)
        folds = []
        for start in range(first_test, len(rows), test_bars):
            end = min(start + test_bars, len(rows))
            training = _simulate(rows, signals, start - train_bars, start, params, rules, capital, fee_bps, slip)
            closed = [t for t in validation['trades'] if start <= t['exit_index'] < end]
            folds.append({'train_start_ms': rows[start - train_bars]['timestamp_ms'],
                          'train_end_exclusive_ms': rows[start]['timestamp_ms'],
                          'test_start_ms': rows[start]['timestamp_ms'],
                          'test_end_exclusive_ms': rows[end - 1]['timestamp_ms'] + STEP_MS,
                          'test_bars': end - start, 'training': _metrics(training['trades']),
                          'training_open_quantity': training['open_quantity'], 'validation': _metrics(closed)})
        routes = sorted({t['route'] for t in validation['trades']})
        scenarios.append({'fee_bps_per_leg': fee_bps, 'slippage_bps_per_leg': slip,
            'validation': {**_metrics(validation['trades']),
                'end_marked_equity': round(validation['end_equity'], 6),
                'marked_return_pct': round((validation['end_equity'] / capital - 1) * 100, 4),
                'max_close_equity_drawdown_pct': validation['max_close_equity_drawdown_pct'],
                'open_quantity': validation['open_quantity'],
                'open_entry_fee': round(validation['open_entry']['fee'], 6) if validation['open_entry'] else 0,
                'blockers': validation['blockers']},
            'entry_routes': {route: _metrics([t for t in validation['trades'] if t['route'] == route]) for route in routes},
            'folds': folds})
    return {'mode': 'SIMULATED_RESEARCH', 'executable': False, 'live_eligible': False,
            'symbol': bundle['symbol'], 'product': 'SPOT', 'interval': '5m',
            'quote_currency': 'USDT',
            'dataset_sha256': bundle['candles_sha256'], 'candles': len(rows),
            'initial_capital_per_asset': capital, 'frozen_settings': params,
            'training_is_diagnostic_only': True, 'parameter_optimization': False,
            'scenarios': scenarios,
            'limitations': ['Independent single-asset runs, not combined portfolio returns.',
                'Modeled fees in quote currency and adverse next-open slippage; not broker fills.',
                'Current instrument limits proxy historical limits; historical rule changes are unknown.',
                'Long-only Spot; shared signal and router gate; exits require an eligible SELL signal.',
                'ATR sizing uses the current readiness price-percent fallback, not historical ATR.',
                'No hypothetical stop/target executions: current Bybit submission does not send them.',
                'No forced fold-end close; validation inventory carries forward; final inventory is marked.',
                'Training closes never use validation bars. Settings remain fixed; no search for a winner.',
                'No order rejections, liquidity, outages, daily-loss or multi-asset exposure simulation.',
                'Paper/Testnet execution and live-money readiness are not established.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--capital', type=float, required=True)
    parser.add_argument('--fee-bps', type=float, required=True)
    parser.add_argument('--slippage-bps', required=True)
    args = parser.parse_args()
    cases = [float(v) for v in args.slippage_bps.split(',')]
    bundle = json.loads(args.input.read_text())
    report = walk_forward_spot(bundle, capital=args.capital, fee_bps=args.fee_bps, slippage_cases=cases)
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    print(json.dumps({'symbol': report['symbol'], 'report': str(args.output),
        'scenarios': [s['validation'] | {'slippage_bps': s['slippage_bps_per_leg']} for s in report['scenarios']]}), flush=True)


if __name__ == '__main__':
    main()
