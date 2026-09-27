from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.automation import AutomationAction, AutomationScan
from app.db.models.broker import BrokerProfile
from app.db.session import SessionLocal
from app.services.automation import get_or_create_state
from app.services.position_lifecycle import evaluate_mt5_exit_signals


def _secret(profile):
    if not profile.credential_blob_encrypted:
        raise RuntimeError('MT5 bridge configuration missing')
    return json.loads(decrypt_secret(profile.credential_blob_encrypted))


def _short(value, limit):
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= limit else text[: max(0, limit - 3)] + '...'


def _persist_exit_action(db, scan, user_id, item, result):
    broker_result = result.get('broker_result') or {}
    raw_result = broker_result.get('result') or {}
    db.add(AutomationAction(
        scan_id=scan.id,
        user_id=user_id,
        broker_profile_id=item.get('profile_id'),
        provider='MT5',
        environment='DEMO',
        market=_short(item.get('market') or '', 24),
        symbol=_short(item.get('symbol') or '', 32),
        side=_short(item.get('position_side'), 8),
        status=_short(result.get('status') or 'UNKNOWN', 24),
        reason=_short(result.get('reason'), 128),
        quantity=None,
        sizing_policy='POSITION_LIFECYCLE_EXIT',
        broker_order_id=_short(raw_result.get('order') or raw_result.get('deal'), 128),
        broker_position_id=_short(item.get('position_id'), 128),
        raw_json=json.dumps({'position': item, 'result': result}, default=str),
    ))


async def run_mt5_position_manager():
    """Close only verified ATLAS MT5 Demo positions on strong opposite signals."""
    with SessionLocal() as db:
        state = get_or_create_state(db)
        if not state.enabled:
            return {'status': 'SKIPPED', 'reason': 'ENGINE_DISABLED'}
        if state.killed:
            return {'status': 'SKIPPED', 'reason': 'KILL_SWITCH'}
        if not state.auto_execute_paper:
            return {'status': 'SKIPPED', 'reason': 'SIMULATION_EXECUTION_DISABLED'}

        profiles = list(db.scalars(select(BrokerProfile).where(
            BrokerProfile.provider == 'MT5',
            BrokerProfile.environment == 'DEMO',
            BrokerProfile.is_enabled.is_(True),
            BrokerProfile.is_active.is_(True),
        )).all())
        user_ids = sorted({p.user_id for p in profiles}, key=str)
        if not user_ids:
            return {'status': 'SKIPPED', 'reason': 'NO_MT5_DEMO_PROFILES'}

        scan = AutomationScan(status='RUNNING', symbols_count=0, accounts_count=len(profiles))
        db.add(scan)
        db.commit()
        db.refresh(scan)
        results = []

        try:
            for user_id in user_ids:
                evaluation = await evaluate_mt5_exit_signals(db, user_id=user_id)
                scan.symbols_count += int(evaluation.get('evaluated_count') or 0)
                for item in evaluation.get('items', []):
                    if item.get('action') != 'EXIT_SIGNAL':
                        continue
                    scan.signals_count += 1
                    scan.approved_count += 1
                    profile = db.get(BrokerProfile, item.get('profile_id'))
                    if profile is None:
                        result = {'status': 'EXIT_BLOCKED', 'reason': 'PROFILE_NOT_FOUND'}
                        results.append({**item, **result})
                        _persist_exit_action(db, scan, user_id, item, result)
                        continue
                    if str(profile.provider).upper() != 'MT5' or str(profile.environment).upper() != 'DEMO':
                        result = {'status': 'EXIT_BLOCKED', 'reason': 'MT5_DEMO_ONLY'}
                        results.append({**item, **result})
                        _persist_exit_action(db, scan, user_id, item, result)
                        continue
                    creds = _secret(profile)
                    broker = Mt5BridgeClient(
                        creds.get('bridge_url') or 'http://host.docker.internal:8765',
                        creds.get('bridge_token'),
                        get_settings().market_data_timeout_seconds,
                    )
                    health = await broker.health()
                    server = str(health.get('server') or '')
                    terminal = health.get('terminal') or {}
                    if 'demo' not in server.lower():
                        result = {'status': 'EXIT_BLOCKED', 'reason': 'MT5_DEMO_SERVER_REQUIRED'}
                    elif terminal and not terminal.get('trade_allowed', False):
                        result = {'status': 'EXIT_BLOCKED', 'reason': 'MT5_ALGO_TRADING_DISABLED'}
                    else:
                        positions = (await broker.positions()).get('list', [])
                        ticket = int(item.get('position_id') or 0)
                        current = next((p for p in positions if int(p.get('ticket') or 0) == ticket), None)
                        if current is None:
                            result = {'status': 'EXIT_BLOCKED', 'reason': 'POSITION_NOT_FOUND'}
                        elif not str(current.get('comment') or '').upper().startswith('ATLAS'):
                            result = {'status': 'EXIT_BLOCKED', 'reason': 'OWNERSHIP_NOT_VERIFIED'}
                        else:
                            close_result = await broker.close_demo_position(ticket)
                            result = {
                                'status': 'EXIT_EXECUTED',
                                'reason': 'STRONG_OPPOSITE_SIGNAL',
                                'broker_result': close_result,
                            }
                            scan.executed_count += 1
                    results.append({**item, **result})
                    _persist_exit_action(db, scan, user_id, item, result)

            scan.status = 'COMPLETED'
            scan.finished_at = datetime.now(timezone.utc)
            db.commit()
            return {
                'status': 'COMPLETED',
                'purpose': 'MT5_DEMO_POSITION_LIFECYCLE_EXECUTION',
                'execution_enabled': True,
                'evaluated': scan.symbols_count,
                'exit_signals': scan.signals_count,
                'exit_executed': scan.executed_count,
                'results': results,
            }
        except Exception as exc:
            db.rollback()
            persisted = db.get(AutomationScan, scan.id)
            if persisted is not None:
                persisted.status = 'FAILED'
                persisted.error_message = _short(exc, 500)
                persisted.finished_at = datetime.now(timezone.utc)
                db.commit()
            return {'status': 'FAILED', 'error': _short(exc, 500), 'results': results}


async def mt5_position_manager_loop(stop_event):
    """Run position management on the same configured automation cadence."""
    while not stop_event.is_set():
        try:
            with SessionLocal() as db:
                state = get_or_create_state(db)
                wait = max(30, int(state.interval_seconds or 300))
                enabled = state.enabled and not state.killed and state.auto_execute_paper
            if enabled:
                await run_mt5_position_manager()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=wait)
            except asyncio.TimeoutError:
                pass
        except Exception:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=30)
            except asyncio.TimeoutError:
                pass
