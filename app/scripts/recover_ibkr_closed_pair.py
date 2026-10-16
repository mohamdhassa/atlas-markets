"""Preview reviewed Paper closed-trade recovery; never submits/cancels orders."""
import argparse
import asyncio
import json
import uuid
from pathlib import Path

from sqlalchemy import select
from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.core.config import get_settings
from app.db.models.auth import User
from app.db.models.automation import AutomationAction
from app.db.models.broker import BrokerProfile
from app.db.session import SessionLocal
from app.services.automation import get_or_create_state
from app.services.ibkr_position_manager import _secret
from app.services.ibkr_statement_import import MAX_XML_BYTES
from app.services.ibkr_closed_recovery import recover_closed_pair


async def run(args):
    with Path(args.file).open('rb') as source:
        data = source.read(MAX_XML_BYTES + 1)
    if len(data) > MAX_XML_BYTES:
        raise ValueError('Statement exceeds 5 MB')
    xml = data.decode('utf-8')
    with SessionLocal() as db:
        admin = db.get(User, args.admin_id)
        if not admin or not admin.is_active or admin.role != 'ADMIN':
            raise ValueError('Active ADMIN required')
        profile = db.get(BrokerProfile, args.profile_id, with_for_update=True)
        if not profile or profile.provider != 'IBKR' or profile.environment != 'PAPER':
            raise ValueError('IBKR Paper profile required')
        if get_or_create_state(db).enabled:
            raise ValueError('Pause automation before recovery')
        entry = db.get(AutomationAction, args.entry_id, with_for_update=True)
        exit_action = db.get(AutomationAction, args.exit_id, with_for_update=True)
        if not entry or not exit_action:
            raise ValueError('Actions not found')
        # Require an unambiguous action history over this round trip, not merely
        # a convenient same-symbol quantity match.
        others = list(db.scalars(select(AutomationAction).where(
            AutomationAction.broker_profile_id == profile.id,
            AutomationAction.symbol == entry.symbol,
            AutomationAction.id.notin_([entry.id, exit_action.id]),
            AutomationAction.status.in_(['SUBMITTED', 'EXIT_SUBMITTED', 'EXECUTED', 'EXIT_EXECUTED']),
            AutomationAction.created_at >= entry.created_at,
        )).all())
        if others:
            raise ValueError('Other symbol actions require separate review')
        credentials = _secret(profile)
        account = credentials.get('account_id')
        broker = IbkrBridgeClient(credentials.get('bridge_url') or
            'http://host.docker.internal:8766', credentials.get('bridge_token'))
        health = await broker.health()
        if not health.get('connected') or health.get('simulation') is not True:
            raise ValueError('Connected Paper bridge required')
        positions, orders = await broker.positions(), await broker.orders()
        if not isinstance(positions.get('list'), list) or not isinstance(orders.get('list'), list):
            raise ValueError('Invalid broker state')
        if any(p.get('symbol') == entry.symbol and float(p.get('quantity') or 0) != 0 for p in positions['list']):
            raise ValueError('Symbol must be flat')
        if any(o.get('symbol') == entry.symbol for o in orders['list']):
            raise ValueError('Symbol must have no open orders')
        response = await broker.executions(30)
        if not isinstance(response.get('list'), list):
            raise ValueError('Invalid executions response')
        executions = [r for r in response['list']
            if r.get('account') == account and str(r.get('order_id')) == str(exit_action.broker_order_id)]
        result = recover_closed_pair(db, profile, account, entry, exit_action,
            xml, args.timezone, args.trade_ids, executions,
            get_settings().ibkr_execution_timezone, admin.id, apply=args.apply)
        if args.apply:
            db.commit()
        print(json.dumps(result, indent=2, allow_nan=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', required=True)
    for name in ('profile-id', 'admin-id', 'entry-id', 'exit-id'):
        parser.add_argument('--' + name, type=uuid.UUID, required=True)
    parser.add_argument('--timezone', required=True)
    parser.add_argument('--trade-ids', nargs='+', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except Exception:
        # Do not leak credentials/transport URLs from broker exceptions.
        print('Recovery stopped; no orders submitted. Check mapping, action scope, retained evidence and broker availability.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
