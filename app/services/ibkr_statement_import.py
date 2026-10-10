"""Preview-first IBKR Activity Flex evidence import; never submits broker orders."""
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

from app.db.models.automation import AutomationAction
from app.db.models.ibkr_statement import IbkrStatementEvidence
from app.services.ibkr_ledger_history import saved_fill

MAX_XML_BYTES = 5_000_000


def number(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or abs(result) > Decimal('1e15'):
            raise ValueError('Invalid statement number')
        return result
    except (InvalidOperation, TypeError):
        raise ValueError('Missing or invalid statement number') from None


def execution_time(value, zone):
    try:
        date = datetime.strptime(value, '%Y%m%d;%H%M%S')
    except (ValueError, TypeError):
        raise ValueError('Use Flex dateTime format YYYYMMDD;HHMMSS') from None
    local = date.replace(tzinfo=zone)
    if local.utcoffset() != local.replace(fold=1).utcoffset():
        raise ValueError('Ambiguous statement execution time')
    utc = local.astimezone(timezone.utc)
    if utc.astimezone(zone).replace(tzinfo=None) != date:
        raise ValueError('Invalid statement execution time')
    return int(utc.timestamp() * 1000)


def parse_flex(xml, account_id, timezone_name):
    if not account_id:
        raise ValueError('Profile must have a configured IBKR account ID')
    if not isinstance(xml, str) or len(xml.encode('utf-8')) > MAX_XML_BYTES:
        raise ValueError('Statement exceeds 5 MB')
    if '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():
        raise ValueError('XML declarations and entities are not accepted')
    try:
        zone = ZoneInfo(timezone_name)
        root = ET.fromstring(xml)
    except (ET.ParseError, ZoneInfoNotFoundError):
        raise ValueError('Invalid XML or statement timezone') from None
    if root.tag != 'FlexQueryResponse':
        raise ValueError('An Activity Flex XML export is required')
    trades = {}
    statements = root.findall('./FlexStatements/FlexStatement')
    if not statements:
        raise ValueError('No Flex statements found')
    for statement in statements:
        if statement.get('accountId') != account_id:
            raise ValueError('Statement account does not match selected profile')
        for element in statement.findall('./Trades/Trade'):
            # SUMMARY, ORDER and CLOSED_LOT rows would double count execution detail.
            if element.get('levelOfDetail') != 'EXECUTION':
                continue
            a = element.attrib
            if a.get('accountId') != account_id:
                raise ValueError('Trade account does not match selected profile')
            if a.get('assetCategory') != 'STK' or a.get('currency') != 'USD' or a.get('ibCommissionCurrency') != 'USD':
                raise ValueError('Only USD stock/ETF executions with USD commissions are supported')
            if a.get('openCloseIndicator') not in {'O', 'C'}:
                raise ValueError('Mixed or unspecified open/close executions require review')
            if a.get('buySell') not in {'BUY', 'SELL'}:
                raise ValueError('Unknown trade side')
            qty = number(a.get('quantity'))
            price = number(a.get('tradePrice'))
            if qty == 0 or price <= 0 or (qty > 0) != (a['buySell'] == 'BUY'):
                raise ValueError('Invalid signed quantity or execution price')
            if a.get('multiplier') and number(a['multiplier']) != 1:
                raise ValueError('Only stock multiplier 1 is supported')
            if (a.get('origTradeID') not in (None, '', '0') or a.get('origTransactionID') not in (None, '', '0')
                    or a.get('transactionType', 'ExchTrade') != 'ExchTrade'):
                raise ValueError('Corrections and non-exchange transactions require review')
            if a.get('taxes') and number(a['taxes']) != 0:
                raise ValueError('Executions with separate transaction taxes require review')
            key = a.get('tradeID')
            if not key or not a.get('ibOrderID') or not a.get('symbol'):
                raise ValueError('Trade ID, IB order ID and symbol are required')
            trade = {
                'trade_id': key, 'ib_order_id': a['ibOrderID'], 'execution_id': a.get('ibExecID') or None,
                'symbol': a['symbol'].upper(), 'side': a['buySell'], 'quantity': str(abs(qty)),
                'price': str(price), 'commission_signed': str(number(a.get('ibCommission'))),
                'realized_pnl': str(number(a['fifoPnlRealized'])) if a.get('fifoPnlRealized') not in (None, '') else None,
                'closed': a['openCloseIndicator'] == 'C', 'time': execution_time(a.get('dateTime'), zone),
            }
            if key in trades and trades[key] != trade:
                raise ValueError('Conflicting duplicate trade ID')
            trades[key] = trade
    if not trades:
        raise ValueError('No execution-detail stock trades found')
    return trades


def statement_evidence(action, profile, account_id, trades):
    audit = saved_fill(action, profile, account_id)
    if audit is None or not trades:
        raise ValueError('Mapping requires a verified fully filled ATLAS action')
    if len({t['ib_order_id'] for t in trades}) != 1:
        raise ValueError('Each action must map to one complete broker order')
    if any(t['symbol'] != action.symbol.upper() or t['side'] != action.side
           or t['closed'] != audit['closed_trade'] for t in trades):
        raise ValueError('Statement symbol, side or open/close disagrees with audit')
    quantity = sum((number(t['quantity']) for t in trades), Decimal(0))
    value = sum((number(t['quantity']) * number(t['price']) for t in trades), Decimal(0))
    if abs(quantity - number(audit['quantity'])) > Decimal('0.00000001'):
        raise ValueError('Statement quantity must cover the entire saved fill')
    price = value / quantity
    if abs(price - number(audit['execution_price'])) > Decimal('0.0001'):
        raise ValueError('Statement average price disagrees with broker fill audit')
    # Audit time is recorded after execution; allow asynchronous reconciliation up to 24 hours.
    if any(not -300_000 <= audit['time'] - t['time'] <= 86_400_000 for t in trades):
        raise ValueError('Statement execution time is outside the audit reconciliation window')
    closed = audit['closed_trade']
    available = closed and all(t['realized_pnl'] is not None for t in trades)
    commission_signed = sum((number(t['commission_signed']) for t in trades), Decimal(0))
    pnl = sum((number(t['realized_pnl']) for t in trades), Decimal(0)) if available else None
    return {
        'version': 1, 'source': 'IMPORTED_IBKR_ACTIVITY_FLEX', 'account_id': account_id,
        'profile_id': str(profile.id), 'user_id': str(profile.user_id), 'environment': profile.environment,
        'broker_order_id': str(action.broker_order_id), 'symbol': action.symbol, 'side': action.side,
        'quantity': float(quantity), 'execution_price': float(price), 'time': max(t['time'] for t in trades),
        'closed_trade': closed, 'currency': 'USD', 'commission': float(-commission_signed),
        'commission_signed': float(commission_signed), 'pnl': float(pnl) if pnl is not None else None,
        'pnl_available': bool(available), 'pnl_basis': 'BROKER_FIFO_INCLUDES_COMMISSIONS',
        'trades': sorted(trades, key=lambda t: t['trade_id']),
    }


def reconcile_statement(db, profile, account_id, xml, timezone_name, mapping, operator_id, apply=False):
    if profile.provider != 'IBKR' or profile.environment != 'PAPER':
        raise ValueError('Select an IBKR Paper profile')
    if not isinstance(mapping, dict) or (apply and not mapping):
        raise ValueError('Apply requires a reviewed nonempty mapping')
    trades = parse_flex(xml, account_id, timezone_name)
    # Lock saved fills during apply; the caller locks the profile to serialize evidence assignments.
    query = select(AutomationAction).where(
        AutomationAction.broker_profile_id == profile.id, AutomationAction.user_id == profile.user_id,
        AutomationAction.provider == 'IBKR', AutomationAction.environment == 'PAPER',
        AutomationAction.status.in_(['EXECUTED', 'EXIT_EXECUTED']))
    if apply:
        query = query.order_by(AutomationAction.id).with_for_update()
    actions = list(db.scalars(query).all())
    by_id = {str(a.id): a for a in actions}
    evidence_query = select(IbkrStatementEvidence).where(
        IbkrStatementEvidence.broker_profile_id == profile.id, IbkrStatementEvidence.user_id == profile.user_id)
    existing = {str(row.action_id): json.loads(row.evidence_json) for row in db.scalars(evidence_query).all()}
    assigned = {t['trade_id']: action_id for action_id, evidence in existing.items() for t in evidence.get('trades', [])}
    planned, seen = [], set()
    for action_id, ids in mapping.items():
        action = by_id.get(str(action_id))
        if action is None:
            raise ValueError('Mapped action does not belong to selected profile/owner')
        if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)) or any(t not in trades for t in ids):
            raise ValueError('Mapping must contain distinct known trade IDs')
        if seen.intersection(ids) or any(assigned.get(t, str(action.id)) != str(action.id) for t in ids):
            raise ValueError('A statement execution cannot belong to two actions')
        seen.update(ids)
        group = [trades[t] for t in ids]
        order = group[0]['ib_order_id']
        if {t['trade_id'] for t in trades.values() if t['ib_order_id'] == order} != set(ids):
            raise ValueError('Include every execution of the mapped broker order')
        evidence = statement_evidence(action, profile, account_id, group)
        previous = existing.get(str(action.id))
        if previous and any(previous.get(k) != v for k, v in evidence.items()):
            raise ValueError('Imported evidence conflicts with an earlier import; review required')
        planned.append((action, evidence, previous is not None))
    # No mutations until all mappings have passed validation.
    for action, evidence, duplicate in planned:
        if apply and not duplicate:
            evidence.update({'imported_at': datetime.now(timezone.utc).isoformat(),
                             'operator_id': str(operator_id), 'file_sha256': hashlib.sha256(xml.encode()).hexdigest(),
                             'statement_timezone': timezone_name, 'mapping_basis': 'ADMIN_REVIEWED_EXPLICIT_MAPPING'})
            db.add(IbkrStatementEvidence(action_id=action.id, broker_profile_id=profile.id,
                                         user_id=profile.user_id, operator_id=operator_id,
                                         evidence_json=json.dumps(evidence, allow_nan=False)))
    if apply:
        db.flush()
    return {
        'mode': 'APPLIED' if apply else 'PREVIEW', 'matched': len(planned),
        'duplicates': sum(duplicate for _, _, duplicate in planned),
        'trades': list(trades.values()), 'unmapped_trade_ids': sorted(set(trades) - seen),
        'matches': [{'action_id': str(a.id), 'broker_order_id': str(a.broker_order_id),
                     'symbol': a.symbol, 'commission': e['commission'], 'pnl': e['pnl'],
                     'pnl_available': e['pnl_available'], 'duplicate': duplicate}
                    for a, e, duplicate in planned],
        'audit_actions': [{'action_id': str(a.id), 'symbol': a.symbol, 'side': a.side,
                           'quantity': a.quantity, 'broker_order_id': a.broker_order_id,
                           'created_at': a.created_at.isoformat()} for a in actions
                          if a.status in {'EXECUTED', 'EXIT_EXECUTED'}],
    }


def imported_fill(action, profile, account_id, stored=None):
    """Revalidate stored import scope and financial values when reading the ledger."""
    try:
        if not stored or stored.get('source') != 'IMPORTED_IBKR_ACTIVITY_FLEX':
            return None
        checked = statement_evidence(action, profile, account_id, stored['trades'])
        if any(stored.get(key) != value for key, value in checked.items()):
            return None
        audit = saved_fill(action, profile, account_id)
        return {**audit, 'time': checked['time'], 'time_source': 'IBKR_STATEMENT_EXECUTION_TIME',
                'execution_source': checked['source'], 'commission': checked['commission'],
                'commission_currency': 'USD', 'pnl': checked['pnl'],
                'pnl_available': checked['pnl_available'], 'pnl_basis': checked['pnl_basis'],
                'pnl_status': 'BROKER_STATEMENT_CONFIRMED' if checked['pnl_available'] else 'BROKER_PNL_PENDING',
                'statement_trade_ids': [t['trade_id'] for t in checked['trades']],
                'statement_imported_at': stored.get('imported_at')}
    except (ValueError, TypeError, AttributeError, KeyError, ZeroDivisionError):
        return None
