"""Validate durable execution evidence without inventing broker order statuses."""
import math
from datetime import datetime, timezone

from app.services.ibkr_execution_format import execution_time_ms
from app.services.ibkr_fractional import ibkr_quantities_match


def execution_fill(entry, executions, account_id, execution_timezone='Etc/UTC'):
    """Prove one full stock entry using unique, exact, priced broker executions.

    Position average cost is never a fill price. Order IDs can be reused, so
    execution timestamps must also belong to the entry's lifetime.
    """
    try:
        if (not account_id or entry.provider != 'IBKR' or entry.environment != 'PAPER'
                or entry.side not in {'BUY', 'SELL'} or not entry.broker_order_id):
            return None
        expected = float(entry.quantity)
        if not math.isfinite(expected) or expected <= 0:
            return None
        created = entry.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        earliest = int(created.timestamp() * 1000) - 300000
        latest = int(datetime.now(timezone.utc).timestamp() * 1000) + 300000
        unique = {}
        for row in executions:
            if str(row.get('order_id')) != str(entry.broker_order_id):
                continue
            # Ignore other accounts, but reject contradictory evidence for ours.
            if row.get('account') != account_id:
                continue
            stamp = execution_time_ms(row, execution_timezone)
            quantity, price = float(row['quantity']), float(row['price'])
            identity = str(row.get('execution_id') or '')
            side = {'BOT', 'BUY'} if entry.side == 'BUY' else {'SLD', 'SELL'}
            if (not identity or row.get('symbol') != entry.symbol
                    or row.get('side') not in side or row.get('sec_type') != 'STK'
                    or not earliest <= stamp <= latest
                    or not all(math.isfinite(v) and v > 0 for v in (quantity, price))):
                return None
            value = (quantity, price, stamp)
            if identity in unique and unique[identity] != value:
                return None
            unique[identity] = value
        filled = sum(q for q, _, _ in unique.values())
        if not unique or not ibkr_quantities_match(filled, expected):
            return None
        price = sum(q * p for q, p, _ in unique.values()) / filled
        if not math.isfinite(price) or price <= 0:
            return None
        return {'quantity': filled, 'price': price,
                'time': max(t for _, _, t in unique.values()),
                'execution_ids': sorted(unique), 'account_id': account_id,
                'source': 'PERSISTED_BROKER_EXECUTIONS'}
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        return None


def saved_execution_fill(entry, raw, account_id=None):
    evidence = raw.get('entry_execution_evidence') or {}
    if not isinstance(evidence, dict) or not evidence.get('account_id'):
        return None
    if account_id is not None and account_id != evidence['account_id']:
        return None
    return execution_fill(entry, evidence.get('executions') or [],
                          evidence['account_id'], evidence.get('execution_timezone', 'Etc/UTC'))
