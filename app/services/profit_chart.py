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
    records = []
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
        records.append({'key': key, 'day': day, 'pnl': value, 'time': stamp,
                        'broker_order_id': row.get('broker_order_id'),
                        'execution_id': row.get('execution_id')})
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
    insights = None
    if series:
        daily = {day: sum(values.get(day, 0.) for values in amounts.values()) for day in dates}
        peak, peak_day, running, max_drawdown = 0., None, 0., 0.
        for day in dates:
            running += daily[day]
            if running > peak:
                peak, peak_day = running, day
            max_drawdown = max(max_drawdown, peak - running)
        current = series[0]['points'][-1]['value']
        def drivers(after=None):
            values = []
            for key, days in amounts.items():
                value = sum(v for day, v in days.items() if after is None or day > after)
                if value < 0:
                    values.append({**options[key], 'pnl': round(value, 8)})
            return sorted(values, key=lambda row: (row['pnl'], row['key']))[:5]
        worst_day = min(daily, key=lambda day: (daily[day], day))
        losses = sorted((record for record in records if record['pnl'] < 0),
                        key=lambda row: (row['pnl'], row['time'], row['key']))[:5]
        insights = {
            'peak_pnl': round(peak, 8), 'peak_day': peak_day,
            'current_drawdown': round(max(0., peak - current), 8),
            'max_daily_drawdown': round(max_drawdown, 8),
            'worst_day': {'date': worst_day, 'pnl': round(daily[worst_day], 8)} if daily[worst_day] < 0 else None,
            'loss_drivers': drivers(),
            'loss_drivers_since_peak': drivers(peak_day) if peak_day else drivers(),
            'largest_loss_records': [{**options[row['key']], **row,
                                      'pnl': round(row['pnl'], 8)} for row in losses],
            'basis': 'Daily recorded realized P&L; peaks include the zero starting baseline. Since-peak attribution starts after the peak UTC day. Records can be partial fills, not whole trades.',
        }
    return {
        'insights': insights,
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
