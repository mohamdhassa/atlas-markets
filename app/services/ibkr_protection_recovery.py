"""Explicit Paper-only recovery of a provably invalid, never-bracketing request."""
import json
import math
from datetime import datetime, timezone

import httpx

from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.core.config import get_settings
from app.db.models.broker import BrokerProfile
from app.services.ibkr_fractional import ibkr_quantities_match
from app.services.ibkr_protection_levels import fill_anchored_levels


async def recover_rejected_levels(db, entry, *, apply=False):
    from app.services.ibkr_position_manager import _secret, _has_pending_exit, _latest_entry, protect_saved_entry
    if not get_settings().ibkr_native_protection_enabled:
        raise ValueError('RECOVERY_NATIVE_PROTECTION_NOT_ENABLED')
    db.refresh(entry, with_for_update=True)
    levels = fill_anchored_levels(entry)
    raw = json.loads(entry.raw_json or '{}')
    prior = raw.get('native_protection') or {}
    group = 'atlas-protect-' + entry.id.hex
    if (prior.get('status') != 'SUBMITTING' or prior.get('oca_group') != group
            or prior.get('order_ids') or prior.get('orders')
            or raw.get('native_protection_levels') is not None):
        raise ValueError('RECOVERY_UNRESOLVED_OR_EXISTING_PAIR_NOT_ELIGIBLE')
    # Require original geometry to be invalid even against exact filled price.
    fill = levels['fill_price']
    stop, target = levels['original_stop_loss'], levels['original_take_profit']
    bracketed = stop < fill < target if entry.side == 'BUY' else target < fill < stop
    if bracketed:
        raise ValueError('RECOVERY_ORIGINAL_LEVELS_COULD_HAVE_SUBMITTED')
    profile = db.get(BrokerProfile, entry.broker_profile_id, with_for_update=True)
    if (profile is None or profile.user_id != entry.user_id or profile.provider != 'IBKR'
            or profile.environment != 'PAPER' or not profile.is_active or not profile.is_enabled
            or not profile.credentials_configured or profile.last_connection_status != 'CONNECTED'):
        raise ValueError('RECOVERY_PAPER_PROFILE_REQUIRED')
    if _has_pending_exit(db, profile, entry.symbol):
        raise ValueError('RECOVERY_PENDING_EXIT_REQUIRES_RECONCILIATION')
    latest = _latest_entry(db, entry.user_id, entry.broker_profile_id, entry.symbol)
    if latest is None or latest.id != entry.id:
        raise ValueError('RECOVERY_ENTRY_IS_NOT_CURRENT')
    creds = _secret(profile)
    broker = IbkrBridgeClient(creds.get('bridge_url') or 'http://host.docker.internal:8766',
                              creds.get('bridge_token'), get_settings().market_data_timeout_seconds, expected_account_id=creds.get("account_id"))
    health = await broker.health()
    if not health.get('connected') or health.get('simulation') is not True:
        raise ValueError('RECOVERY_CONNECTED_PAPER_BRIDGE_REQUIRED')
    positions = (await broker.positions()).get('list', [])
    matches = [p for p in positions if p.get('account') == creds.get('account_id')
               and p.get('symbol') == entry.symbol and float(p.get('quantity') or 0) != 0]
    sign = 1 if entry.side == 'BUY' else -1
    if (len(matches) != 1 or matches[0].get('sec_type') != 'STK'
            or matches[0].get('currency') != 'USD'
            or not ibkr_quantities_match(float(matches[0]['quantity']), sign*levels['quantity'])):
        raise ValueError('RECOVERY_POSITION_CHANGED')
    cost = float(matches[0].get('avg_cost') or 0)
    # Permit only the small commission difference from the verified execution.
    if not math.isfinite(cost) or abs(cost-fill) > max(.01, fill*.0001):
        raise ValueError('RECOVERY_POSITION_COST_DOES_NOT_MATCH_FILL')
    cost_bracketed = stop < cost < target if sign == 1 else target < cost < stop
    if cost_bracketed:
        raise ValueError('RECOVERY_ORIGINAL_LEVELS_COULD_HAVE_SUBMITTED')
    orders = (await broker.orders()).get('list', [])
    if any(o.get('symbol') == entry.symbol for o in orders):
        raise ValueError('RECOVERY_EXISTING_ORDERS_REQUIRE_RECONCILIATION')
    fills = (await broker.executions(30)).get('list', [])
    if get_settings().ibkr_execution_timezone not in {'UTC', 'Etc/UTC'}:
        raise ValueError('RECOVERY_EXECUTION_TIMEZONE_UNVERIFIED')
    for execution in fills:
        if execution.get('symbol') != entry.symbol or execution.get('account') != creds.get('account_id'):
            continue
        if str(execution.get('order_id')) == str(entry.broker_order_id):
            continue
        try:
            observed = datetime.strptime(' '.join(str(execution.get('time') or '').split()),
                                         '%Y%m%d %H:%M:%S').replace(tzinfo=timezone.utc)
        except ValueError:
            raise ValueError('RECOVERY_EXECUTION_TIME_UNVERIFIED')
        if observed >= entry.created_at:
            raise ValueError('RECOVERY_OTHER_EXECUTIONS_REQUIRE_RECONCILIATION')
    payload = {'symbol': entry.symbol, 'account_id': creds['account_id'],
        'position_side': 'LONG' if sign == 1 else 'SHORT', 'quantity': levels['quantity'],
        'stop_loss': stop, 'take_profit': target, 'entry_key': entry.id.hex,
        'existing_order_ids': [], 'allow_submit': False}
    try:
        await broker.ensure_protection(payload)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 400 or exc.response.json().get('detail') != 'PROTECTION_LEVELS_DO_NOT_BRACKET_ENTRY':
            raise
    else:
        raise ValueError('RECOVERY_PRE_SUBMISSION_REJECTION_NOT_CONFIRMED')
    preview = {'mode': 'PREVIEW', 'entry_id': str(entry.id), 'symbol': entry.symbol,
               'levels': levels, 'broker_average_cost': cost,
               'proof': 'INVALID_AT_VERIFIED_FILL_AND_MATCHING_POSITION_NO_ORDERS_EXACT_PRECHECK_400'}
    if not apply:
        return preview
    # Preserve original intent and request. Recovery is explicit, never a normal retry.
    raw['native_protection_levels'] = levels
    raw['native_protection_recovery'] = {**preview, 'mode': 'AUTHORIZED_PAPER_RECOVERY',
        'original_intent': prior, 'at': datetime.now(timezone.utc).isoformat()}
    raw['native_protection'] = {**prior, 'status': 'PRE_SUBMISSION_BLOCKED',
        'reason': 'VERIFIED_ORIGINAL_LEVELS_REJECTED_BEFORE_SUBMISSION'}
    entry.raw_json = json.dumps(raw)
    db.commit()
    result = await protect_saved_entry(db, entry)
    return {**preview, 'mode': 'APPLIED', 'result': result}
