"""Reviewed, reporting-only recovery of a closed Paper round trip.

Statement order identifiers remain separate from TWS local identifiers. This
workflow never changes an action's fill status and cannot arm native protection.
"""
import hashlib
import json
import math
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.db.models.automation import AutomationAction
from app.db.models.ibkr_statement import IbkrStatementEvidence
from app.services.ibkr_entry_fill import execution_fill
from app.services.ibkr_ledger_history import saved_fill
from app.services.ibkr_statement_import import number, parse_flex

SOURCE = 'REVIEWED_IBKR_CLOSED_ROUND_TRIP'


def _scope(action, profile):
    return (profile.provider == action.provider == 'IBKR'
            and profile.environment == action.environment == 'PAPER'
            and action.broker_profile_id == profile.id
            and action.user_id == profile.user_id)


def close_evidence(action, profile, account_id, executions, zone):
    audit = saved_fill(action, profile, account_id)
    proof = execution_fill(action, executions, account_id, zone)
    if (not _scope(action, profile) or action.status != 'EXIT_EXECUTED'
            or not audit or not proof
            or not math.isclose(audit['execution_price'], proof['price'], abs_tol=.0001, rel_tol=0)):
        raise ValueError('Close requires exact full broker status and executions')
    recorded = action.created_at.replace(tzinfo=action.created_at.tzinfo or timezone.utc)
    if not int(recorded.timestamp() * 1000) - 300_000 <= proof['time'] <= int(recorded.timestamp() * 1000) + 86_400_000:
        raise ValueError('Close execution outside audit lifetime')
    # Retain only this account/order, deduplicate identical callbacks, and reject
    # contradictory financial fields even if quantity/price/time agree.
    unique = {}
    for row in executions:
        if row.get('account') != account_id or str(row.get('order_id')) != str(action.broker_order_id):
            continue
        identity = row['execution_id']
        if identity in unique and unique[identity] != row:
            raise ValueError('Conflicting execution callback')
        unique[identity] = row
    rows = [unique[key] for key in sorted(unique)]
    for row in rows:
        for key in ('commission', 'realized_pnl'):
            if row.get(key) is not None:
                number(row[key])
                if row.get('commission_currency') != 'USD':
                    raise ValueError('Only USD financial evidence is supported')
    pnl_available = all(r.get('pnl_available') is True and r.get('realized_pnl') is not None for r in rows)
    commission_available = all(r.get('commission') is not None for r in rows)
    return {**audit, 'time': proof['time'], 'time_source': 'PERSISTED_BROKER_EXECUTION_TIME',
            'execution_source': SOURCE, 'execution_ids': proof['execution_ids'],
            'pnl_available': pnl_available,
            'pnl': float(sum((number(r['realized_pnl']) for r in rows), Decimal(0))) if pnl_available else None,
            'commission': float(sum((number(r['commission']) for r in rows), Decimal(0))) if commission_available else None,
            'commission_currency': 'USD', 'pnl_basis': 'BROKER_REPORTED_REALIZED_PNL',
            'pnl_status': 'BROKER_CONFIRMED' if pnl_available else 'BROKER_PNL_PENDING'}


def opening_evidence(entry, profile, account_id, trades, close, exit_action):
    if (not _scope(entry, profile) or entry.status != 'EXECUTED'
            or entry.side not in {'BUY', 'SELL'} or not entry.broker_order_id
            or entry.symbol != exit_action.symbol or entry.side == exit_action.side
            or not trades or len({t['ib_order_id'] for t in trades}) != 1
            or len({t['trade_id'] for t in trades}) != len(trades)
            or len({t['execution_id'] for t in trades}) != len(trades)
            or any(not t['execution_id'] or t['closed'] or t['symbol'] != entry.symbol
                   or t['side'] != entry.side for t in trades)):
        raise ValueError('Reviewed opening order does not match the closed entry')
    qty = sum((number(t['quantity']) for t in trades), Decimal(0))
    if qty <= 0 or abs(qty - number(entry.quantity)) > Decimal('1e-8') or abs(qty - number(close['quantity'])) > Decimal('1e-8'):
        raise ValueError('Round trip quantities must agree exactly')
    created = entry.created_at.replace(tzinfo=entry.created_at.tzinfo or timezone.utc)
    earliest = int(created.timestamp() * 1000) - 300_000
    # A queued entry may fill on a later session. The independently confirmed
    # close bounds the opening lifetime; no nearest-time assignment is made.
    if any(not earliest <= t['time'] <= close['time'] for t in trades):
        raise ValueError('Opening executions must precede the confirmed close')
    if any(number(t['quantity']) <= 0 or number(t['price']) <= 0 for t in trades):
        raise ValueError('Invalid opening execution')
    return {'profile_id': str(profile.id), 'account': profile.account_label,
            'provider': 'IBKR', 'market': entry.market or 'STOCK', 'symbol': entry.symbol,
            'side': entry.side, 'quantity': float(qty),
            'execution_price': float(sum((number(t['quantity']) * number(t['price']) for t in trades), Decimal(0)) / qty),
            'broker_order_id': str(entry.broker_order_id),
            'statement_order_id': trades[0]['ib_order_id'],
            'time': max(t['time'] for t in trades), 'time_source': 'IBKR_STATEMENT_EXECUTION_TIME',
            'execution_source': SOURCE, 'closed_trade': False,
            'commission': float(-sum((number(t['commission_signed']) for t in trades), Decimal(0))),
            'commission_currency': 'USD', 'pnl': None, 'pnl_available': False,
            'pnl_status': 'OPENING_EXECUTION', 'statement_trade_ids': sorted(t['trade_id'] for t in trades)}


def recover_closed_pair(db, profile, account_id, entry, exit_action, xml, zone,
                        trade_ids, executions, execution_zone, operator_id, apply=False):
    """Caller validates ADMIN and locks profile/actions for apply; preview writes nothing."""
    if not operator_id or entry.id == exit_action.id:
        raise ValueError('Reviewed operator and distinct actions required')
    raw = json.loads(exit_action.raw_json or '{}')
    linked = raw.get('entry_action_id') or raw.get('position', {}).get('entry_action_id')
    if linked != str(entry.id):
        raise ValueError('Exit must explicitly reference this entry')
    trades = parse_flex(xml, account_id, zone)
    if not trade_ids or len(set(trade_ids)) != len(trade_ids) or any(t not in trades for t in trade_ids):
        raise ValueError('Explicit distinct opening trade IDs required')
    group = [trades[t] for t in trade_ids]
    order = group[0]['ib_order_id']
    if set(trade_ids) != {t['trade_id'] for t in trades.values() if t['ib_order_id'] == order}:
        raise ValueError('Map every execution of the opening statement order')
    close = close_evidence(exit_action, profile, account_id, executions, execution_zone)
    executions = list({r['execution_id']: r for r in executions
        if r.get('account') == account_id and str(r.get('order_id')) == str(exit_action.broker_order_id)}.values())
    executions.sort(key=lambda r: r['execution_id'])
    opening = opening_evidence(entry, profile, account_id, group, close, exit_action)
    # An explicit map cannot claim executions already assigned to another action.
    existing = list(db.scalars(select(IbkrStatementEvidence).where(
        IbkrStatementEvidence.broker_profile_id == profile.id)).all())
    for row in existing:
        stored = json.loads(row.evidence_json)
        used = {t['trade_id'] for t in stored.get('trades', [])}
        if row.action_id != entry.id and used.intersection(trade_ids):
            raise ValueError('Statement executions already assigned')
    evidence = {'version': 1, 'source': SOURCE, 'account_id': account_id,
                'entry_action_id': str(entry.id), 'exit_action_id': str(exit_action.id),
                'opening_trades': sorted(group, key=lambda t: t['trade_id']),
                'executions': executions, 'execution_timezone': execution_zone,
                'statement_timezone': zone, 'file_sha256': hashlib.sha256(xml.encode()).hexdigest(),
                'opening': opening, 'closing': close}
    for action, kind in ((entry, 'opening'), (exit_action, 'closing')):
        candidate = {**evidence, 'kind': kind,
                     'trades': evidence['opening_trades'] if kind == 'opening' else []}
        previous = next((r for r in existing if r.action_id == action.id), None)
        if previous:
            stored = json.loads(previous.evidence_json)
            if any(stored.get(k) != v for k, v in candidate.items()):
                raise ValueError('Conflicting retained evidence; no overwrite allowed')
    if apply:
        for action, kind in ((entry, 'opening'), (exit_action, 'closing')):
            if any(r.action_id == action.id for r in existing):
                continue
            db.add(IbkrStatementEvidence(action_id=action.id, broker_profile_id=profile.id,
                user_id=profile.user_id, operator_id=operator_id,
                evidence_json=json.dumps({**evidence, 'kind': kind,
                    'trades': evidence['opening_trades'] if kind == 'opening' else [], 'operator_id': str(operator_id),
                    'imported_at': datetime.now(timezone.utc).isoformat()}, allow_nan=False)))
        db.flush()
    return {'mode': 'APPLIED' if apply else 'PREVIEW', 'opening': opening, 'closing': close}


def recovered_row(action, profile, account_id, stored, actions):
    """Revalidate both current action audits; no trusted cached financial totals."""
    try:
        if stored.get('source') != SOURCE or stored['account_id'] != account_id:
            return None
        by_id = {str(a.id): a for a in actions if getattr(a, 'id', None)}
        entry, exit_action = by_id[stored['entry_action_id']], by_id[stored['exit_action_id']]
        raw = json.loads(exit_action.raw_json or '{}')
        if (raw.get('entry_action_id') or raw.get('position', {}).get('entry_action_id')) != str(entry.id):
            return None
        close = close_evidence(exit_action, profile, account_id, stored['executions'], stored['execution_timezone'])
        opening = opening_evidence(entry, profile, account_id, stored['opening_trades'], close, exit_action)
        kind = 'opening' if action.id == entry.id else 'closing' if action.id == exit_action.id else None
        if kind != stored['kind'] or stored['opening'] != opening or stored['closing'] != close:
            return None
        return {**(opening if kind == 'opening' else close), 'audit_action_id': str(action.id)}
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
        return None
