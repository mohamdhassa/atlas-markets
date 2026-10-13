"""Read-only cohorts from broker net P&L and decision-time entry evidence."""
import json
import math
from collections import defaultdict


def attach_entry_strategies(rows, actions):
    by_id = {(str(a.broker_profile_id), str(a.id)): a for a in actions}
    by_order = defaultdict(list)
    for action in actions:
        if action.broker_order_id:
            by_order[(str(action.broker_profile_id), str(action.broker_order_id))].append(action)
    for row in rows:
        if not (row.get('pnl_available') or row.get('closed_trade')):
            continue
        row['entry_strategy_status'] = 'UNKNOWN'
        scope = str(row.get('profile_id'))
        close = by_id.get((scope, str(row.get('audit_action_id') or '')))
        if close is None:
            candidates = by_order[(scope, str(row.get('broker_order_id') or ''))]
            close = candidates[0] if len(candidates) == 1 else None
        if (close is None or close.status not in {'EXECUTED', 'EXIT_EXECUTED'}
                or close.provider != row.get('provider') or close.symbol != row.get('symbol')
                or close.market != row.get('market')
                or close.side != row.get('side')
                or str(close.broker_order_id) != str(row.get('broker_order_id'))):
            continue
        row['environment'] = close.environment
        row['expected_close_quantity'] = close.quantity
        entry_ids = row.get('entry_action_ids') or ([row['entry_action_id']] if row.get('entry_action_id') else [])
        if len(entry_ids) != 1:
            continue
        entry = by_id.get((scope, str(entry_ids[0])))
        if (entry is None or entry.status != 'EXECUTED' or entry.user_id != close.user_id
                or entry.provider != close.provider or entry.environment != close.environment
                or entry.market != close.market or entry.symbol != close.symbol
                or entry.side == close.side or entry.side not in {'BUY', 'SELL'}):
            continue
        try:
            raw = json.loads(entry.raw_json or '{}')['preflight']
            snapshot, route = raw['strategy_snapshot'], raw['strategy_route']
            params = snapshot['effective_parameters']
            if (type(snapshot['schema_version']) is not int or snapshot['schema_version'] != 1 or snapshot['profile_id'] != scope
                    or snapshot['symbol'] != entry.symbol or snapshot['market'] != entry.market
                    or not snapshot.get('strategy_id') or snapshot['mode'] != 'AUTO_TRADE'
                    or snapshot['router_role'] != 'ENTRY_FILTER'
                    or snapshot['signal_engine'] != 'app.services.signal_risk.generate_signal'
                    or route['strategy'] not in {'trend', 'darvas_box', 'mean_reversion'}
                    or not isinstance(params['timeframe'], str) or not params['timeframe']):
                continue
            for field in ('minimum_signal_strength', 'risk_per_trade_pct', 'stop_atr_multiplier',
                          'take_profit_rr', 'max_position_notional_pct'):
                if not math.isfinite(float(params[field])) or float(params[field]) <= 0:
                    raise ValueError('Invalid recorded parameters')
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
        row['entry_strategy_status'] = 'RECORDED_ENTRY'
        row['entry_strategy'] = {'entry_action_id': str(entry.id),
            'close_action_id': str(close.id), 'environment': entry.environment,
            'entry_side': entry.side, 'snapshot': snapshot, 'route': route}
    return rows


def strategy_evaluation(rows, cutoff_ms=0, errors=None):
    # Group callback fragments before counting outcomes. Unsupported provider
    # finance and incomplete closing orders never enter strategy metrics.
    orders = defaultdict(list)
    excluded = defaultdict(int)
    seen = {}
    conflicts = set()
    for row in rows:
        if not (row.get('pnl_available') or row.get('closed_trade')):
            continue
        if int(row.get('time') or 0) < cutoff_ms:
            continue
        if row.get('provider') != 'IBKR':
            excluded['UNSUPPORTED_NET_EVIDENCE'] += 1
            continue
        oid = row.get('broker_order_id')
        if not oid:
            excluded['MISSING_CLOSING_ORDER'] += 1
            continue
        key = (str(row.get('profile_id')), str(oid), row.get('symbol'))
        identity = (*key, str(row.get('execution_id') or 'ORDER_AGGREGATE'))
        signature = (row.get('quantity'), row.get('execution_price'), row.get('pnl'), row.get('pnl_available'))
        if identity in seen:
            if seen[identity] != signature: conflicts.add(key)
            continue
        seen[identity] = signature
        orders[key].append(row)
    cohorts = defaultdict(list)
    for key, fills in orders.items():
        if key in conflicts:
            excluded['CONFLICTING_EXECUTION'] += 1
            continue
        if len(fills) > 1 and any(not r.get('execution_id') for r in fills):
            excluded['MIXED_ORDER_AGGREGATE'] += 1
            continue
        try:
            if not all(r.get('pnl_available') is True and r.get('pnl') is not None
                       and math.isfinite(float(r['pnl'])) and abs(float(r['pnl'])) < 1e100 for r in fills):
                raise ValueError('Pending net P&L')
        except (ValueError, TypeError):
            excluded['PNL_PENDING'] += 1
            continue
        expected = {r.get('expected_close_quantity') for r in fills}
        if expected != {None}:
            try:
                if (len(expected) != 1 or None in expected or float(next(iter(expected))) <= 0
                        or not math.isclose(sum(float(r['quantity']) for r in fills),
                                            float(next(iter(expected))), abs_tol=1e-8, rel_tol=0)):
                    raise ValueError('Incomplete order')
            except (ValueError, TypeError, KeyError):
                excluded['INCOMPLETE_CLOSING_ORDER'] += 1
                continue
        evidence = [r.get('entry_strategy') for r in fills]
        # Different entry lots or incomplete attribution stays in the unknown bucket.
        known = all(evidence) and len({json.dumps(e, sort_keys=True) for e in evidence}) == 1
        first = fills[0]
        e = evidence[0] if known else None
        snapshot = e['snapshot'] if e else None
        cohort_key = (key[0], first.get('provider'), e['environment'] if e else first.get('environment', 'UNKNOWN'),
                      first.get('market'), first.get('symbol'),
                      e['entry_side'] if e else 'UNKNOWN',
                      e['route']['strategy'] if e else 'UNKNOWN',
                      json.dumps(snapshot, sort_keys=True) if snapshot else '')
        cohorts[cohort_key].append({'pnl': sum(float(r['pnl']) for r in fills),
            'time': max(int(r.get('time') or 0) for r in fills), 'fills': len(fills),
            'account': first.get('account'), 'snapshot': snapshot})
    result = []
    for key, outcomes in cohorts.items():
        outcomes.sort(key=lambda r: r['time'])
        pnls = [r['pnl'] for r in outcomes]
        wins, losses = [v for v in pnls if v > 0], [v for v in pnls if v < 0]
        curve = peak = drawdown = 0.0
        for pnl in pnls:
            curve += pnl; peak = max(peak, curve); drawdown = max(drawdown, peak - curve)
        snapshot = outcomes[0]['snapshot']
        result.append({'profile_id': key[0], 'provider': key[1], 'environment': key[2],
            'market': key[3], 'symbol': key[4], 'entry_side': key[5], 'strategy': key[6],
            'account': outcomes[0]['account'], 'settings': snapshot['effective_parameters'] if snapshot else None,
            'strategy_id': snapshot['strategy_id'] if snapshot else None,
            'closed_orders': len(outcomes), 'fill_rows': sum(r['fills'] for r in outcomes),
            'wins': len(wins), 'losses': len(losses), 'net_pnl': round(sum(pnls), 2),
            'win_rate': round(len(wins) / len(pnls) * 100, 2),
            'profit_factor': round(sum(wins) / abs(sum(losses)), 3) if losses else None,
            'average_win': round(sum(wins) / len(wins), 2) if wins else None,
            'average_loss': round(sum(losses) / len(losses), 2) if losses else None,
            'expectancy_per_close': round(sum(pnls) / len(pnls), 2),
            'max_realized_drawdown': round(drawdown, 2), 'max_drawdown_pct': None,
            'evaluation': 'STRATEGY_UNKNOWN' if not snapshot else 'VALIDATING',
            'first_close_ms': outcomes[0]['time'], 'last_close_ms': outcomes[-1]['time']})
    return {'cohorts': sorted(result, key=lambda r: (r['strategy'] == 'UNKNOWN', r['net_pnl'])),
        'known_closed_orders': sum(r['closed_orders'] for r in result if r['strategy'] != 'UNKNOWN'),
        'unknown_closed_orders': sum(r['closed_orders'] for r in result if r['strategy'] == 'UNKNOWN'),
        'excluded': dict(excluded), 'provider_errors': len(errors or []), 'live_readiness': 'NOT_ASSESSED',
        'methodology': 'IBKR broker net P&L only. Partial fills count once per closing order. '
                       'Cohorts separate account, environment, asset, entry side and recorded settings. '
                       'Unknown entry evidence is never inferred from current settings. '
                       'Drawdown is realized P&L drawdown in dollars, not account equity drawdown. '
                       'This report cannot establish live-money eligibility.'}
