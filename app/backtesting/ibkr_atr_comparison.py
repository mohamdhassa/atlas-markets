"""Offline exploratory IBKR long/short comparison; never submits orders."""
import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.services.ibkr_atr_sizing import sizing_atr
from app.services.paper_execution import build_execution_plan
from app.services.signal_risk import generate_signal
from app.services.autotrade_readiness import _router_blocker
from app.analysis.strategy_router import route_strategy
from app.services.trading_candles import INTERVAL_MS

PARAMETERS = dict(minimum_strength=65., risk_pct=1., stop_multiplier=1.5,
                  target_rr=2., max_notional_pct=20., warmup=200)
NY = ZoneInfo('America/New_York')


def validate(bundle):
    if bundle.get('provider') != 'IBKR' or bundle.get('regular_hours') is not True:
        raise ValueError('IBKR_RTH_DATASET_REQUIRED')
    timeframe = bundle.get('timeframe')
    if timeframe not in {'3m', '5m', '15m'}:
        raise ValueError('UNSUPPORTED_TIMEFRAME')
    step = INTERVAL_MS[timeframe]
    rows = bundle.get('candles') or []
    collected = bundle.get('collected_at_ms', 0)
    if len(rows) < PARAMETERS['warmup'] + 2:
        raise ValueError('INSUFFICIENT_COMPLETED_HISTORY')
    previous = None
    for row in rows:
        stamp = row['timestamp_ms']
        if not isinstance(stamp, int) or stamp <= 0 or stamp + step > collected:
            raise ValueError('INVALID_OR_UNFINISHED_BAR')
        if previous is not None and stamp <= previous:
            raise ValueError('UNSORTED_OR_DUPLICATE_BARS')
        values = [float(row[k]) for k in ('open', 'high', 'low', 'close')]
        o, h, l, c = values
        if any(not math.isfinite(v) or v <= 0 for v in values) or not l <= min(o,c) <= max(o,c) <= h:
            raise ValueError('INVALID_OHLC')
        volume = float(row.get('volume', 0))
        if not math.isfinite(volume) or volume < 0:
            raise ValueError('INVALID_VOLUME')
        local = datetime.fromtimestamp(stamp/1000, NY)
        minute = local.hour*60 + local.minute
        if local.weekday() >= 5 or not 570 <= minute < 960:
            raise ValueError('NON_RTH_BAR')
        if previous is not None:
            prior = datetime.fromtimestamp(previous/1000, NY)
            if prior.date() == local.date() and stamp-previous != step:
                raise ValueError('INTRADAY_DATA_GAP')
        previous = stamp
    return rows


def signals(rows, timeframe):
    stream = {}
    router = getattr(route_strategy, '__wrapped__', route_strategy)
    for index in range(PARAMETERS['warmup'], len(rows)):
        window = rows[index-PARAMETERS['warmup']:index]
        generated = generate_signal(window, timeframe=timeframe, market='STOCK')
        route = router(window)
        if (generated.decision in {'BUY','SELL'}
                and generated.strength >= PARAMETERS['minimum_strength']
                and not _router_blocker(route, generated.decision)):
            stream[index] = generated.decision
    return stream


def trigger(row, position):
    sign, stop, target = position['sign'], position['stop'], position['target']
    o, h, l = (float(row[k]) for k in ('open','high','low'))
    if sign == 1:
        if o <= stop:return o, 'GAP_STOP'
        if o >= target:return target, 'GAP_TARGET'
        if l <= stop:return stop, 'STOP_FIRST' if h >= target else 'STOP'
        if h >= target:return target, 'TARGET'
    else:
        if o >= stop:return o, 'GAP_STOP'
        if o <= target:return target, 'GAP_TARGET'
        if h >= stop:return stop, 'STOP_FIRST' if l <= target else 'STOP'
        if l <= target:return target, 'TARGET'
    return None


def simulate(rows, stream, *, measured, slip_bps, capital=250000.,
             commission_per_share=.005, minimum_commission=1.):
    cash, position, peak, max_dd = capital, None, capital, 0.
    trades, skipped, fees = [], 0, 0.
    slip = slip_bps/10000
    for index in range(PARAMETERS['warmup'], len(rows)):
        row = rows[index]
        held_at_open = position is not None
        if not held_at_open and index in stream and cash > 0:
            side = stream[index]; sign = 1 if side == 'BUY' else -1
            reference = float(rows[index-1]['close'])
            try:
                value = None
                if measured:
                    value, _ = sizing_atr(SimpleNamespace(
                        ibkr_paper_atr_sizing_enabled=True, allow_live_trading=False),
                        'PAPER', rows[index-200:index])
                plan = build_execution_plan(decision=side, price=reference, equity=cash,
                    available_cash=cash, risk_per_trade_pct=PARAMETERS['risk_pct'],
                    atr=value, stop_atr_multiplier=PARAMETERS['stop_multiplier'],
                    take_profit_rr=PARAMETERS['target_rr'],
                    max_position_notional_pct=PARAMETERS['max_notional_pct'])
                distance = abs(reference-plan.stop_loss)
                price = float(row['open'])*(1+sign*slip)
                budget_qty = max(0, math.floor((plan.risk_amount-2*minimum_commission)
                    / (distance+2*commission_per_share)))
                quantity = min(math.floor(plan.quantity), budget_qty,
                    math.floor(cash*PARAMETERS['max_notional_pct']/100/price))
                stop = price-sign*distance
                target = price+sign*distance*PARAMETERS['target_rr']
                if quantity < 1 or min(stop,target) <= 0:raise ValueError
                fee = max(minimum_commission, quantity*commission_per_share)
                cash -= fee; fees += fee
                position = dict(sign=sign,side=side,quantity=quantity,price=price,
                    stop=stop,target=target,entry_fee=fee,
                    entry_ms=row['timestamp_ms'],atr=value,
                    planned_risk=quantity*distance)
            except (ValueError, KeyError, TypeError):
                skipped += 1
        if position is not None:
            outcome = trigger(row, position)
            if outcome:
                level, reason = outcome
                price = level*(1-position['sign']*slip)
                fee = max(minimum_commission,position['quantity']*commission_per_share)
                gross = position['sign']*position['quantity']*(price-position['price'])
                pnl = gross-position['entry_fee']-fee
                cash += gross-fee; fees += fee
                trades.append({**position,'exit_ms':row['timestamp_ms'],
                    'exit_price':price,'reason':reason,'pnl':round(pnl,8)})
                position = None
        equity = cash + (position['sign']*position['quantity']*
                 (float(row['close'])-position['price']) if position else 0)
        peak = max(peak,equity)
        max_dd = max(max_dd,(peak-equity)/peak*100)
    gains = sum(t['pnl'] for t in trades if t['pnl'] > 0)
    losses = -sum(t['pnl'] for t in trades if t['pnl'] < 0)
    days = len({datetime.fromtimestamp(r['timestamp_ms']/1000,NY).date()
                for r in rows[PARAMETERS['warmup']:]})
    return dict(closed_trades=len(trades), net_realized_pnl=round(sum(t['pnl'] for t in trades),8),
        marked_return_pct=round((equity/capital-1)*100,6),
        max_close_marked_drawdown_pct=round(max_dd,6),
        profit_factor=round(gains/losses,6) if losses else None,
        modeled_commissions=round(fees,8), open_position=position,
        validation_sessions=days, skipped_entries=skipped, trades=trades,
        sample_status='LIMITED' if days<20 or len(trades)<30 else 'DESCRIPTIVE_ONLY')


def compare(bundle):
    rows = validate(bundle)
    stream = signals(rows,bundle['timeframe'])
    policy = {'version':'IBKR_ATR_COMPARE_V1','parameters':PARAMETERS,
              'capital_per_independent_symbol':250000,
              'slippage_bps_per_leg':[2,5,10],
              'commission_per_share':.005,'minimum_commission_per_leg':1.}
    cases = []
    for slip in policy['slippage_bps_per_leg']:
        baseline = simulate(rows,stream,measured=False,slip_bps=slip)
        candidate = simulate(rows,stream,measured=True,slip_bps=slip)
        cases.append(dict(slippage_bps=slip,baseline=baseline,candidate=candidate,
            candidate_minus_baseline_marked_return_pct=round(
                candidate['marked_return_pct']-baseline['marked_return_pct'],6)))
    return dict(symbol=bundle['symbol'],timeframe=bundle['timeframe'],
        dataset_sha256=hashlib.sha256(json.dumps(bundle,sort_keys=True).encode()).hexdigest(),
        policy=policy,policy_sha256=hashlib.sha256(json.dumps(policy,sort_keys=True).encode()).hexdigest(),
        eligible_signal_count=len(stream),cases=cases,
        verdict='EXPLORATORY_NOT_APPROVED_FOR_ACTIVATION',
        limitations=[
            'Recent selected history is not a fresh holdout or reproduction of historical executions.',
            'Independent single-symbol accounts; no combined portfolio/exposure/margin constraints.',
            'Ideal immediate RTH protection, next-open entries, fill-anchored distances, whole shares.',
            'Both-touch bars use stop first; intrabar path and broker latency are unknown.',
            'Costs are stress assumptions, not verified account commission or slippage estimates.',
            'Borrow fees, short availability, financing, dividends and regulatory fees omitted.',
            'No liquidity, spread/order-book, rejected orders, partial fills or quote delay model.',
            'Close-marked drawdown omits intrabar risk; open exits remain unliquidated.',
            'Baseline uses current signal/router code and frozen parameters, not historical configurations.',
        ])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    result=compare(json.loads(Path(args.input).read_text()))
    with Path(args.output).open('x') as file:json.dump(result,file,indent=2)
    summary={key:result[key] for key in ('symbol','timeframe','eligible_signal_count','verdict')}
    summary['cases']=[{**case,'baseline':{k:v for k,v in case['baseline'].items() if k not in {'trades','open_position'}},
                     'candidate':{k:v for k,v in case['candidate'].items() if k not in {'trades','open_position'}}}
                    for case in result['cases']]
    print(json.dumps(summary))


if __name__=='__main__':main()
