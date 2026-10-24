"""Frozen exploratory 15:00 entry cutoff / 15:45 exit; no broker calls."""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from app.backtesting.ibkr_atr_comparison import (
    PARAMETERS, NY, validate, signals, simulate,
)

POLICY = dict(version='IBKR_INTRADAY_V1', timezone='America/New_York',
              entry_before='15:00', exit_at='15:45', timeframe='5m',
              parameters=PARAMETERS, slippage_bps_per_leg=[2,5,10],
              capital_per_independent_symbol=250000,
              commission_per_share=.005, minimum_commission_per_leg=1.)


def validate_sessions(rows):
    sessions = {}
    for row in rows[PARAMETERS['warmup']:]:
        local = datetime.fromtimestamp(row['timestamp_ms']/1000, NY)
        sessions.setdefault(local.date(),set()).add(local.hour*60+local.minute)
    if any(945 not in minutes for minutes in sessions.values()):
        raise ValueError('SESSION_EXIT_BAR_MISSING_OR_EARLY_CLOSE_UNSUPPORTED')


def compare(bundle):
    rows = validate(bundle)
    if bundle['timeframe'] != '5m':
        raise ValueError('INTRADAY_COMPARISON_REQUIRES_5M')
    validate_sessions(rows)
    stream = signals(rows, '5m')
    cases = []
    for slip in POLICY['slippage_bps_per_leg']:
        results = {}
        for measured, label in ((False,'baseline'), (True,'atr')):
            for intraday, mode in ((False,'overnight'), (True,'intraday')):
                result = simulate(rows,stream,measured=measured,slip_bps=slip,
                                  intraday=intraday)
                result['overnight_closed_trades'] = sum(
                    datetime.fromtimestamp(t['entry_ms']/1000,NY).date() !=
                    datetime.fromtimestamp(t['exit_ms']/1000,NY).date()
                    for t in result['trades'])
                if intraday and (result['open_position'] or result['overnight_closed_trades']):
                    raise ValueError('INTRADAY_POLICY_NOT_FLAT')
                results[f'{label}_{mode}'] = result
        cases.append(dict(slippage_bps=slip,results=results,deltas={
            label:dict(
                marked_return_pct=round(results[f'{label}_intraday']['marked_return_pct']-
                                        results[f'{label}_overnight']['marked_return_pct'],6),
                max_close_marked_drawdown_pct=round(
                    results[f'{label}_intraday']['max_close_marked_drawdown_pct']-
                    results[f'{label}_overnight']['max_close_marked_drawdown_pct'],6))
            for label in ('baseline','atr')}))
    return dict(symbol=bundle['symbol'],policy=POLICY,
        dataset_sha256=hashlib.sha256(json.dumps(bundle,sort_keys=True).encode()).hexdigest(),
        policy_sha256=hashlib.sha256(json.dumps(POLICY,sort_keys=True).encode()).hexdigest(),
        eligible_signal_count=len(stream),cases=cases,
        verdict='EXPLORATORY_NOT_APPROVED_FOR_ACTIVATION',
        limitations=[
            'Same selected five-session sample motivated this hypothesis; not a fresh holdout.',
            'No parameter sweep or symbol selection; all nine symbols and cost scenarios required.',
            'Clock cutoffs are frozen hypotheses, not optimized or proven market rules.',
            'Incomplete/early-close sessions rejected; no exchange calendar implementation.',
            'Ideal immediate RTH stops and scheduled-open exit; broker latency/delayed quotes omitted.',
            'Independent accounts; no combined portfolio, borrow, financing or margin model.',
            'Assumed commissions/slippage; close-marked drawdown misses intrabar excursions.',
            'Changes holding duration and entry opportunities; no claim to isolate only gap losses.',
        ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input',required=True)
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    report = compare(json.loads(Path(args.input).read_text()))
    with Path(args.output).open('x') as file:
        json.dump(report,file,indent=2)
    summary = {key:value for key,value in report.items() if key!='cases'}
    summary['cases'] = [dict(slippage_bps=case['slippage_bps'],deltas=case['deltas'],
        results={label:{k:v for k,v in result.items() if k not in {'trades','open_position'}}
                 for label,result in case['results'].items()}) for case in report['cases']]
    print(json.dumps(summary))


if __name__=='__main__':main()
