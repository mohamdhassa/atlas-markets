"""Cumulative recorded realized P&L, built before ledger display truncation."""
import math
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone


def instrument_key(row):
    return ':'.join(str(row.get(key) or '').upper()
                    for key in ('provider', 'environment', 'market', 'symbol'))


def build_profit_chart(rows, *, symbols=None, start=None, end=None, errors=()):
    options = {}
    for row in rows:
        if not row.get('symbol'):
            continue
        key = instrument_key(row)
        options[key] = {'key': key, 'symbol': row['symbol'],
                        'provider': row.get('provider'), 'environment': row.get('environment'),
                        'market': row.get('market')}
    selected = set(symbols or [])
    lower = int(datetime.combine(start, time.min, timezone.utc).timestamp() * 1000) if start else None
    upper = int(datetime.combine(end + timedelta(days=1), time.min, timezone.utc).timestamp() * 1000) if end else None
    amounts = defaultdict(lambda: defaultdict(float))
    included, unknown, invalid_time = 0, 0, 0
    for row in rows:
        key = instrument_key(row)
        if key not in options or (selected and key not in selected):
            continue
        stamp = row.get('time')
        if not isinstance(stamp, (int, float)) or not math.isfinite(stamp) or stamp <= 0:
            invalid_time += 1
            continue
        if (lower is not None and stamp < lower) or (upper is not None and stamp >= upper):
            continue
        try:
            value = float(row['pnl']) if row.get('pnl_available') is True and row.get('pnl') is not None else None
        except (ValueError, TypeError):
            value = None
        if value is None or not math.isfinite(value):
            unknown += 1
            continue
        try:
            day = datetime.fromtimestamp(stamp / 1000, timezone.utc).date().isoformat()
        except (ValueError, OverflowError, OSError):
            invalid_time += 1
            continue
        amounts[key][day] += value
        included += 1
    dates = sorted({day for values in amounts.values() for day in values})
    series = []
    if dates:
        first = start.isoformat() if start else dates[0]
        last = end.isoformat() if end else dates[-1]
        timeline = sorted(set(dates + [first, last]))
        baseline = int(datetime.combine(datetime.fromisoformat(first).date(), time.min, timezone.utc).timestamp() * 1000)
        keys = sorted(selected.intersection(amounts) if selected else amounts)
        running = {key: 0. for key in keys}
        points = {key: [{'time': baseline, 'value': 0.}] for key in keys}
        combined = [{'time': baseline, 'value': 0.}]
        for day in timeline:
            stamp = int(datetime.combine(datetime.fromisoformat(day).date(), time.max, timezone.utc).timestamp() * 1000)
            for key in keys:
                running[key] += amounts[key].get(day, 0.)
                points[key].append({'time': stamp, 'value': round(running[key], 8)})
            combined.append({'time': stamp, 'value': round(sum(running.values()), 8)})
        series.append({'key': 'OVERALL', 'label': 'Selected total' if selected else 'Overall', 'points': combined})
        if selected:
            series.extend({'key': key, 'label': options[key]['symbol'] + ' · ' + options[key]['provider'] + ' · ' + str(options[key]['environment']),
                           'points': points[key]} for key in keys)
    return {
        'metric': 'CUMULATIVE_RECORDED_REALIZED_PNL', 'timezone': 'UTC',
        'currency_label': 'USD / USDT', 'start': start, 'end': end,
        'selected_symbols': sorted(selected),
        'symbols_without_priced_records': [options[key]['symbol'] for key in sorted(selected.intersection(options) - amounts.keys())],
        'symbols': sorted(options.values(), key=lambda x: (x['symbol'], x['key'])),
        'series': series, 'pnl_records': included,
        'recorded_pnl': series[0]['points'][-1]['value'] if series else None,
        'excluded_unknown_pnl_records': unknown, 'excluded_undated_records': invalid_time,
        'partial': bool(errors) or bool(unknown) or bool(invalid_time),
        'provider_errors': [{'provider': e.get('provider'), 'account': e.get('account')} for e in errors],
        'coverage': 'All available recorded history for enabled accounts; broker API retention and history limits still apply.',
        'notes': [
            'Closed/realized P&L only. Open positions, deposits and withdrawals are excluded.',
            'Each date range starts at zero; values accumulate within the selected period.',
            'Recorded fee treatment follows the Performance ledger; this is not a new net-P&L calculation.',
            'USD and USDT follow existing ledger units without an FX conversion.',
            'Missing P&L is excluded and never invented as zero.',
        ],
    }
