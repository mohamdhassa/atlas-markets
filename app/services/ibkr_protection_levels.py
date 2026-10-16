"""Anchor immutable planned distances to exact persisted full-fill evidence."""
import json
import math

from app.services.ibkr_fractional import ibkr_quantities_match
from app.services.ibkr_entry_fill import saved_execution_fill


def fill_anchored_levels(entry):
    if entry.provider != 'IBKR' or entry.environment != 'PAPER' or entry.status != 'EXECUTED':
        raise ValueError('PROTECTION_VERIFIED_PAPER_ENTRY_REQUIRED')
    raw = json.loads(entry.raw_json or '{}')
    request = raw['preflight']['request']
    final = raw.get('result', {}).get('broker_result', {}).get('final_status') or {}
    status = final.get('status') or {}
    fill = float(status.get('avg_fill_price') or 0)
    quantity = float(entry.quantity or 0)
    if (status.get('status') != 'Filled' or not math.isfinite(fill) or fill <= 0
            or quantity <= 0 or not ibkr_quantities_match(float(status.get('filled') or 0), quantity)
            or float(status.get('remaining') or 0) != 0
            or str(final.get('order_id')) != str(entry.broker_order_id)
            or str(status.get('order_id')) != str(entry.broker_order_id)):
        proof = saved_execution_fill(entry, raw)
        if proof is None:
            raise ValueError('PROTECTION_FILL_PRICE_UNVERIFIED')
        fill = proof['price']
    stop, target = float(request['stop_loss']), float(request['take_profit'])
    reference = request.get('reference_price')
    inferred = reference is None
    if inferred:
        rr = float(raw['preflight']['strategy_snapshot']['effective_parameters']['take_profit_rr'])
        if not math.isfinite(rr) or rr <= 0:
            raise ValueError('PROTECTION_PLANNED_REFERENCE_UNVERIFIED')
        reference = (rr * stop + target) / (rr + 1)
    reference = float(reference)
    sign = 1 if entry.side == 'BUY' else -1 if entry.side == 'SELL' else 0
    stop_distance, target_distance = sign * (reference - stop), sign * (target - reference)
    if (not sign or not all(math.isfinite(x) and x > 0 for x in
                           (reference, stop, target, stop_distance, target_distance))):
        raise ValueError('PROTECTION_PLANNED_DISTANCES_INVALID')
    new_stop, new_target = fill - sign * stop_distance, fill + sign * target_distance
    if min(new_stop, new_target) <= 0:
        raise ValueError('PROTECTION_FILL_LEVELS_INVALID')
    return {'source': 'VERIFIED_FULL_FILL_PRESERVED_DISTANCES',
            'entry_order_id': str(entry.broker_order_id), 'fill_price': fill,
            'planned_reference_price': reference, 'reference_inferred_from_saved_rr': inferred,
            'original_stop_loss': stop, 'original_take_profit': target,
            'stop_distance': stop_distance, 'target_distance': target_distance,
            'quantity': quantity, 'stop_loss': new_stop, 'take_profit': new_target}
