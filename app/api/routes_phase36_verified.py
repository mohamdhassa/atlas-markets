from __future__ import annotations

from collections import defaultdict
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.routes_phase35 import _accounts, _aggregate_mt5, _mt5, unified_performance
from app.db.models.auth import User
from app.db.models.automation import AutomationAction
from app.db.session import get_db

router = APIRouter(tags=['strategies', 'performance', 'attribution'])


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _match_action(trade, order_ids, actions):
    profile_id = str(trade.get('profile_id') or '')
    position_id = str(trade.get('position_id') or '')
    market = str(trade.get('market') or '').upper()
    symbol = str(trade.get('symbol') or '').upper()
    for action in actions:
        if str(action.broker_profile_id or '') != profile_id:
            continue
        if str(action.market or '').upper() != market or str(action.symbol or '').upper() != symbol:
            continue
        if action.broker_position_id and str(action.broker_position_id) == position_id:
            return action, 'BROKER_POSITION_ID'
        if action.broker_order_id and str(action.broker_order_id) in order_ids:
            return action, 'BROKER_ORDER_ID'
    return None, None


@router.get('/strategies/performance/verified')
async def verified_strategy_attribution(
    days: int = Query(default=30, ge=1, le=366),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    perf = await unified_performance(days=days, user=user, db=db)
    action_q = select(AutomationAction).where(
        AutomationAction.status == 'EXECUTED',
        AutomationAction.broker_profile_id.is_not(None),
    )
    if user.role != 'ADMIN':
        action_q = action_q.where(AutomationAction.user_id == user.id)
    actions = list(db.scalars(action_q).all())

    mt5_orders_by_position: dict[tuple[str, str], set[str]] = defaultdict(set)
    mt5_errors = []
    for profile in _accounts(db, user):
        if profile.provider != 'MT5' or not profile.credentials_configured:
            continue
        try:
            client = _mt5(profile)
            hist = await client.history_deals(days)
            for deal in hist.get('list', []):
                position_id = str(deal.get('position_id') or deal.get('position') or deal.get('order') or deal.get('ticket') or '')
                order_id = str(deal.get('order') or '')
                if position_id and order_id and order_id != '0':
                    mt5_orders_by_position[(str(profile.id), position_id)].add(order_id)
        except Exception as exc:
            mt5_errors.append({'profile_id': str(profile.id), 'account': profile.account_label, 'error': str(exc)[:300]})

    verified = []
    unverified = []
    matched_action_ids = set()
    strategy_groups = defaultdict(list)

    for trade in perf.get('trades', []):
        if not trade.get('pnl_available'):
            continue
        order_ids = set()
        if trade.get('provider') == 'MT5':
            order_ids = mt5_orders_by_position.get((str(trade.get('profile_id')), str(trade.get('position_id'))), set())
        elif trade.get('provider') == 'BYBIT' and trade.get('position_id'):
            order_ids.add(str(trade.get('position_id')))

        action, method = _match_action(trade, order_ids, actions)
        row = dict(trade)
        row['broker_order_ids'] = sorted(order_ids)
        if action:
            matched_action_ids.add(str(action.id))
            row['atlas_origin_verified'] = True
            row['attribution_confidence'] = 'ATLAS_BROKER_ID_VERIFIED'
            row['match_method'] = method
            row['automation_action_id'] = str(action.id)
            row['automation_scan_id'] = str(action.scan_id)
            verified.append(row)
            strategy_groups[(str(trade.get('profile_id')), str(trade.get('market') or '').upper(), str(trade.get('symbol') or '').upper())].append(row)
        else:
            row['atlas_origin_verified'] = False
            row['attribution_confidence'] = 'BROKER_SYMBOL_MATCH_ONLY'
            row['match_method'] = None
            unverified.append(row)

    strategies = []
    for (profile_id, market, symbol), trades in strategy_groups.items():
        pnls = [_f(x.get('realized_pnl')) for x in trades]
        wins = sum(1 for x in pnls if x > 0)
        losses = sum(1 for x in pnls if x < 0)
        strategies.append({
            'profile_id': profile_id,
            'market': market,
            'symbol': symbol,
            'verified_trades': len(trades),
            'verified_wins': wins,
            'verified_losses': losses,
            'verified_win_rate': round(wins / len(trades) * 100, 2) if trades else 0,
            'verified_realized_pnl': round(sum(pnls), 2),
            'attribution_confidence': 'ATLAS_BROKER_ID_VERIFIED',
            'automation_action_ids': sorted({x['automation_action_id'] for x in trades}),
        })
    strategies.sort(key=lambda x: x['verified_realized_pnl'])

    unmatched_actions = []
    for action in actions:
        if str(action.id) in matched_action_ids:
            continue
        unmatched_actions.append({
            'action_id': str(action.id),
            'scan_id': str(action.scan_id),
            'profile_id': str(action.broker_profile_id) if action.broker_profile_id else None,
            'provider': action.provider,
            'market': action.market,
            'symbol': action.symbol,
            'side': action.side,
            'broker_order_id': action.broker_order_id,
            'broker_position_id': action.broker_position_id,
            'created_at': action.created_at.isoformat() if action.created_at else None,
        })

    return {
        'days': days,
        'summary': {
            'broker_pnl_trades': sum(1 for x in perf.get('trades', []) if x.get('pnl_available')),
            'atlas_verified_trades': len(verified),
            'unverified_broker_trades': len(unverified),
            'executed_actions': len(actions),
            'matched_actions': len(matched_action_ids),
            'unmatched_actions': len(unmatched_actions),
            'atlas_verified_realized_pnl': round(sum(_f(x.get('realized_pnl')) for x in verified), 2),
        },
        'strategies': strategies,
        'verified_trades': verified,
        'unverified_trades': unverified,
        'unmatched_actions': unmatched_actions,
        'errors': mt5_errors,
        'methodology': {
            'verified': 'ATLAS origin is verified only by an exact persisted broker position ID or broker order ID match to an EXECUTED automation action.',
            'unverified': 'Symbol/account similarity alone is never treated as verified ATLAS performance.',
            'safety': 'Unverified broker history is excluded from ATLAS strategy optimization decisions.',
        },
    }
