"""Recover broker-confirmed fills from durable ATLAS audits; never estimate net P&L."""
import json
import math
import uuid
from datetime import timezone
from app.services.ibkr_execution_format import execution_time_ms
from app.services.ibkr_entry_fill import saved_execution_fill


def saved_fill(action, profile, account_id=None):
    if (action.provider != "IBKR" or action.status not in {"EXECUTED", "EXIT_EXECUTED"}
            or action.broker_profile_id != profile.id or action.user_id != profile.user_id
            or action.environment != profile.environment or not action.broker_order_id):
        return None
    try:
        raw = json.loads(action.raw_json or "{}")
        broker = raw.get("result", {}).get("broker_result", {})
        response = broker.get("final_status", {})
        status = response.get("status", {})
        quantity = float(status.get("filled", 0))
        price = float(status.get("avg_fill_price", 0))
        expected = float(action.quantity or 0)
        order_id = str(action.broker_order_id)
        if (str(response.get("order_id")) != order_id
                or str(status.get("order_id")) != order_id
                or str(status.get("status", "")).upper() != "FILLED"
                or not all(math.isfinite(v) and v > 0 for v in (quantity, price, expected))
                or not math.isclose(quantity, expected, rel_tol=0, abs_tol=1e-8)
                or float(status.get("remaining", -1)) != 0
                or action.side not in {"BUY", "SELL"}):
            proof = saved_execution_fill(action, raw, account_id)
            if proof is None or action.status != 'EXECUTED':
                return None
            return {
                'profile_id': str(profile.id), 'account': profile.account_label,
                'provider': 'IBKR', 'market': action.market or 'STOCK',
                'symbol': action.symbol, 'side': action.side,
                'quantity': proof['quantity'], 'execution_price': proof['price'],
                'broker_order_id': order_id, 'time': proof['time'],
                'time_source': 'PERSISTED_BROKER_EXECUTION_TIME',
                'execution_source': proof['source'], 'execution_ids': proof['execution_ids'],
                'commission': None, 'pnl': None, 'pnl_available': False,
                'closed_trade': False, 'pnl_status': 'BROKER_PNL_PENDING',
            }
        if broker.get("account_id") not in (None, "", account_id):
            return None
        return {
            "profile_id": str(profile.id), "account": profile.account_label,
            "provider": "IBKR", "market": action.market or "STOCK",
            "symbol": action.symbol, "side": action.side, "quantity": quantity,
            "execution_price": price, "broker_order_id": order_id,
            "time": int((action.created_at if action.created_at.tzinfo else action.created_at.replace(tzinfo=timezone.utc)).timestamp() * 1000),
            "time_source": "ATLAS_ACTION_RECORDED_AT",
            "execution_source": "PERSISTED_BROKER_FILL_STATUS",
            "commission": None, "pnl": None, "pnl_available": False,
            "closed_trade": action.status == "EXIT_EXECUTED",
            "pnl_status": "BROKER_PNL_PENDING",
        }
    except (ValueError, TypeError, AttributeError, KeyError):
        return None


def protective_fills(action, entry, profile, account_id, entry_row, execution_timezone):
    """Read a complete persisted native close; require its exact saved entry and orders."""
    try:
        if (not account_id or entry_row is None or action.reason != 'BROKER_NATIVE_PROTECTIVE_EXIT'
                or action.status != 'EXIT_EXECUTED' or action.provider != 'IBKR'
                or action.environment != 'PAPER' or profile.environment != 'PAPER'
                or action.broker_profile_id != profile.id or action.user_id != profile.user_id
                or entry.status != 'EXECUTED' or entry.symbol != action.symbol
                or action.id != uuid.uuid5(entry.id, 'IBKR_NATIVE_PROTECTIVE_EXIT')):
            return []
        raw = json.loads(action.raw_json or '{}')
        position, result = raw['position'], raw['result']
        if (position['entry_action_id'] != str(entry.id)
                or str(position['entry_order_id']) != str(entry.broker_order_id)
                or position['symbol'] != action.symbol or result['status'] != 'EXIT_EXECUTED'
                or result['reason'] != action.reason):
            return []
        expected = float(entry.quantity)
        if not (math.isfinite(expected) and expected > 0
                and math.isclose(float(action.quantity), expected, abs_tol=1e-8, rel_tol=0)
                and math.isclose(float(position['quantity']), expected, abs_tol=1e-8, rel_tol=0)):
            return []
        side = 'SELL' if entry.side == 'BUY' else 'BUY'
        if action.side != side or result['close_side'] != side:
            return []
        protection = position['protection']
        ids = {str(x) for x in protection.get('order_ids', [])}
        ids.update(str(x['order_id']) for x in protection.get('orders', []))
        if not ids or str(action.broker_order_id) not in ids:
            return []
        if protection.get('oca_group') != 'atlas-protect-' + entry.id.hex:
            return []
        executions = position['executions']
        seen, rows = set(), []
        audit_time = execution_time_ms({'time': action.created_at.isoformat()})
        for fill in executions:
            execution_id = fill['execution_id']
            quantity, price = float(fill['quantity']), float(fill['price'])
            stamp = execution_time_ms(fill, execution_timezone)
            if (not execution_id or execution_id in seen or fill['account'] != account_id
                    or fill['symbol'] != action.symbol or fill['sec_type'] != 'STK'
                    or str(fill['order_id']) not in ids
                    or fill['side'] not in ({'BOT', 'BUY'} if side == 'BUY' else {'SLD', 'SELL'})
                    or not all(math.isfinite(x) and x > 0 for x in (quantity, price))
                    or not stamp or stamp < entry_row['time'] - 300000 or stamp > audit_time + 300000):
                return []
            seen.add(execution_id)
            commission = float(fill['commission']) if fill.get('commission') is not None else None
            pnl_available = fill.get('pnl_available') is True and fill.get('realized_pnl') is not None
            pnl = float(fill['realized_pnl']) if pnl_available else None
            if ((pnl is not None and (not math.isfinite(pnl) or abs(pnl) > 1e100))
                    or (commission is not None and (not math.isfinite(commission) or abs(commission) > 1e100))
                    or ((pnl_available or commission is not None) and fill.get('commission_currency') != 'USD')):
                return []
            rows.append({'profile_id': str(profile.id), 'account': profile.account_label,
                'provider': 'IBKR', 'market': action.market or 'STOCK', 'symbol': action.symbol,
                'side': side, 'quantity': quantity, 'execution_price': price,
                'broker_order_id': str(fill['order_id']), 'execution_id': execution_id,
                'time': stamp, 'time_source': 'PERSISTED_BROKER_EXECUTION_TIME',
                'execution_source': 'PERSISTED_NATIVE_PROTECTIVE_FILL', 'closed_trade': True,
                'pnl': pnl, 'pnl_available': pnl_available, 'commission': commission,
                'commission_currency': fill.get('commission_currency'),
                'entry_action_id': str(entry.id), 'linked_entry_price': entry_row['execution_price'],
                'linked_entry_time': entry_row['time'], 'linked_entry_time_source': entry_row['time_source'],
                'audit_action_id': str(action.id)})
        if (not rows or seen != set(result['broker_result']['execution_ids'])
                or str(result['broker_result']['order_id']) != str(action.broker_order_id)
                or not math.isclose(sum(x['quantity'] for x in rows), expected, abs_tol=1e-8, rel_tol=0)):
            return []
        return rows
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return []


def merge_saved_fills(rows, actions, profile, account_id=None, statements=None, execution_timezone='Etc/UTC'):
    """Reviewed statements take precedence; otherwise live fills win over saved audits."""
    existing = {str(row.get("broker_order_id")) for row in rows
                if str(row.get("profile_id")) == str(profile.id)}
    from app.services.ibkr_statement_import import imported_fill
    actions = list(actions)
    entries = {str(getattr(a, 'id', '')): a for a in actions}
    entry_rows = {}
    for action in actions:
        statement = imported_fill(action, profile, account_id, (statements or {}).get(str(getattr(action, "id", ""))))
        if statement is not None:
            # A complete reviewed statement order replaces its live execution fragments.
            # Never sum an order aggregate alongside those fragments.
            rows[:] = [r for r in rows if not (
                str(r.get("profile_id")) == str(profile.id)
                and str(r.get("broker_order_id")) == statement["broker_order_id"])]
            rows.append(statement)
            statement['audit_action_id'] = str(getattr(action, 'id', ''))
            entry_rows[str(getattr(action, 'id', ''))] = statement
            existing.add(statement["broker_order_id"])
            continue
        saved = saved_fill(action, profile, account_id)
        if saved is None:
            continue
        saved['audit_action_id'] = str(getattr(action, 'id', ''))
        entry_rows[str(getattr(action, 'id', ''))] = saved
        if saved["broker_order_id"] in existing:
            same_order = [a for a in actions if str(a.broker_order_id) == saved['broker_order_id']]
            if len(same_order) == 1 and not saved['closed_trade']:
                for row in rows:
                    if (str(row.get('profile_id')) == str(profile.id)
                            and str(row.get('broker_order_id')) == saved['broker_order_id']):
                        row['audit_action_id'] = saved['audit_action_id']
            if saved["closed_trade"]:
                for row in rows:
                    if (str(row.get("profile_id")) == str(profile.id)
                            and str(row.get("broker_order_id")) == saved["broker_order_id"]):
                        row["closed_trade"] = True
            continue
        rows.append(saved)
        existing.add(saved["broker_order_id"])
    # Ordinary fill-status audits do not contain protective callbacks. Recover those
    # separately, deduplicating on execution identity rather than reusable order IDs.
    for action in actions:
        try:
            entry_id = json.loads(action.raw_json or '{}')['position']['entry_action_id']
            entry = entries[entry_id]
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
        proof = protective_fills(action, entry, profile, account_id, entry_rows.get(entry_id), execution_timezone)
        conflicts = any(not (str(live.get('broker_order_id')) == saved['broker_order_id']
                             and live.get('symbol') == saved['symbol'] and _same_fill(live, saved))
                        for saved in proof for live in rows
                        if str(live.get('profile_id')) == str(profile.id)
                        and live.get('execution_id') == saved['execution_id'])
        if conflicts:continue
        for saved in proof:
            live = [r for r in rows if str(r.get('profile_id')) == str(profile.id)
                    and r.get('execution_id') == saved['execution_id']]
            if live:
                for row in live:
                    if (str(row.get('broker_order_id')) == saved['broker_order_id']
                            and row.get('symbol') == saved['symbol']
                            and _same_fill(row, saved)):
                        for field in ('entry_action_id', 'linked_entry_price', 'linked_entry_time',
                                      'linked_entry_time_source', 'audit_action_id', 'closed_trade'):
                            row[field] = saved[field]
                        if not row.get('pnl_available') and saved['pnl_available']:
                            row['pnl'], row['pnl_available'] = saved['pnl'], True
                        if row.get('commission') is None:
                            row['commission'] = saved['commission']
                            row['commission_currency'] = saved['commission_currency']
            else:
                rows.append(saved)
    return rows


def _same_fill(left, right):
    try:
        return (math.isclose(float(left['quantity']), right['quantity'], abs_tol=1e-8, rel_tol=0)
                and math.isclose(float(left['execution_price']), right['execution_price'], abs_tol=1e-8, rel_tol=0))
    except (ValueError, TypeError, KeyError):
        return False
