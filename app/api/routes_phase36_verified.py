from __future__ import annotations

import json
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

MIN_VERIFIED_TRADES_FOR_ELIGIBILITY = 30
MIN_PROFIT_FACTOR_FOR_ELIGIBILITY = 1.20
MIN_WIN_RATE_FOR_ELIGIBILITY = 40.0
MAX_DRAWDOWN_PCT_FOR_ELIGIBILITY = 15.0


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _max_drawdown(pnls: list[float]) -> tuple[float, float]:
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    max_drawdown_pct = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        drawdown = peak - equity
        max_drawdown = max(max_drawdown, drawdown)
        if peak > 0:
            max_drawdown_pct = max(max_drawdown_pct, drawdown / peak * 100)
    return round(max_drawdown, 2), round(max_drawdown_pct, 2)


def _strategy_metrics(trades: list[dict]) -> dict:
    # Broker payloads are not uniform: unified MT5/Bybit rows use closed_at,
    # while some performance sources expose time. Keep realized-P&L drawdown
    # chronological without inventing timestamps.
    ordered = sorted(trades, key=lambda x: str(x.get('closed_at') or x.get('time') or ''))
    pnls = [_f(x.get('realized_pnl')) for x in ordered]
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    max_drawdown, max_drawdown_pct = _max_drawdown(pnls)
    count = len(pnls)
    win_rate = len(wins) / count * 100 if count else 0.0
    avg_win = gross_profit / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    expectancy = sum(pnls) / count if count else 0.0

    blockers = []
    if count < MIN_VERIFIED_TRADES_FOR_ELIGIBILITY:
        blockers.append('INSUFFICIENT_VERIFIED_SAMPLE')
    if sum(pnls) <= 0:
        blockers.append('NON_POSITIVE_VERIFIED_PNL')
    if profit_factor < MIN_PROFIT_FACTOR_FOR_ELIGIBILITY:
        blockers.append('PROFIT_FACTOR_BELOW_THRESHOLD')
    if win_rate < MIN_WIN_RATE_FOR_ELIGIBILITY:
        blockers.append('WIN_RATE_BELOW_THRESHOLD')
    if max_drawdown_pct > MAX_DRAWDOWN_PCT_FOR_ELIGIBILITY:
        blockers.append('DRAWDOWN_ABOVE_THRESHOLD')

    if count < MIN_VERIFIED_TRADES_FOR_ELIGIBILITY:
        readiness = 'VALIDATING'
    elif blockers:
        readiness = 'NOT_ELIGIBLE'
    else:
        readiness = 'ELIGIBLE'

    return {
        'verified_trades': count,
        'verified_wins': len(wins),
        'verified_losses': len(losses),
        'verified_win_rate': round(win_rate, 2),
        'verified_realized_pnl': round(sum(pnls), 2),
        'gross_profit': round(gross_profit, 2),
        'gross_loss': round(gross_loss, 2),
        'profit_factor': round(profit_factor, 2),
        'average_win': round(avg_win, 2),
        'average_loss': round(avg_loss, 2),
        'expectancy_per_trade': round(expectancy, 2),
        'max_drawdown': max_drawdown,
        'max_drawdown_pct': max_drawdown_pct,
        'live_readiness': readiness,
        'readiness_blockers': blockers,
    }


def _ibkr_fill_confirmed(action: AutomationAction) -> bool:
    if str(action.provider or '').upper() != 'IBKR':
        return True
    try:
        raw = json.loads(action.raw_json or '{}')
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    result = raw.get('result') or {}
    broker_result = result.get('broker_result') or {}
    final = broker_result.get('final_status') or {}
    status = final.get('status') or {}
    broker_state = str(status.get('status') or '').upper()
    filled = _f(status.get('filled'))
    requested = _f(action.quantity)
    return broker_state == 'FILLED' and filled > 0 and (requested <= 0 or filled >= requested)


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
    raw_actions = list(db.scalars(action_q).all())
    actions = [action for action in raw_actions if _ibkr_fill_confirmed(action)]
    excluded_unconfirmed_ibkr = [action for action in raw_actions if str(action.provider or '').upper() == 'IBKR' and not _ibkr_fill_confirmed(action)]

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
        metrics = _strategy_metrics(trades)
        strategies.append({
            'profile_id': profile_id,
            'market': market,
            'symbol': symbol,
            **metrics,
            'attribution_confidence': 'ATLAS_BROKER_ID_VERIFIED',
            'automation_action_ids': sorted({x['automation_action_id'] for x in trades}),
        })
    strategies.sort(key=lambda x: (x['live_readiness'] != 'ELIGIBLE', -x['verified_realized_pnl']))

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

    readiness_counts = {
        'ELIGIBLE': sum(x['live_readiness'] == 'ELIGIBLE' for x in strategies),
        'VALIDATING': sum(x['live_readiness'] == 'VALIDATING' for x in strategies),
        'NOT_ELIGIBLE': sum(x['live_readiness'] == 'NOT_ELIGIBLE' for x in strategies),
    }

    return {
        'days': days,
        'summary': {
            'broker_pnl_trades': sum(1 for x in perf.get('trades', []) if x.get('pnl_available')),
            'atlas_verified_trades': len(verified),
            'unverified_broker_trades': len(unverified),
            'executed_actions': len(actions),
            'excluded_unconfirmed_ibkr_actions': len(excluded_unconfirmed_ibkr),
            'matched_actions': len(matched_action_ids),
            'unmatched_actions': len(unmatched_actions),
            'atlas_verified_realized_pnl': round(sum(_f(x.get('realized_pnl')) for x in verified), 2),
            'strategy_readiness': readiness_counts,
        },
        'eligibility_policy': {
            'minimum_verified_trades': MIN_VERIFIED_TRADES_FOR_ELIGIBILITY,
            'minimum_profit_factor': MIN_PROFIT_FACTOR_FOR_ELIGIBILITY,
            'minimum_win_rate_pct': MIN_WIN_RATE_FOR_ELIGIBILITY,
            'maximum_drawdown_pct': MAX_DRAWDOWN_PCT_FOR_ELIGIBILITY,
            'positive_verified_pnl_required': True,
            'note': 'Eligibility is a validation gate only. It never enables Live Money execution automatically.',
        },
        'strategies': strategies,
        'verified_trades': verified,
        'unverified_trades': unverified,
        'unmatched_actions': unmatched_actions,
        'errors': mt5_errors,
        'methodology': {
            'verified': 'ATLAS origin is verified only by an exact persisted broker position ID or broker order ID match to an EXECUTED automation action. IBKR EXECUTED actions additionally require persisted broker confirmation of an actual fill.',
            'unverified': 'Symbol/account similarity alone is never treated as verified ATLAS performance.',
            'safety': 'Unverified broker history and unconfirmed/cancelled IBKR submissions are excluded from ATLAS strategy optimization decisions.',
            'readiness': 'A strategy remains VALIDATING until it has at least 30 verified closed trades. After that, positive verified P&L, profit factor, win rate and drawdown thresholds determine ELIGIBLE versus NOT_ELIGIBLE. No readiness result can unlock Live Money by itself.',
        },
    }
