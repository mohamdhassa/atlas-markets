"""Operator CLI for Activity Flex XML. Preview by default; --apply requires a reviewed map."""
import argparse
import json
import sys
import uuid
from pathlib import Path

from app.api.routes_broker_native import _creds
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.session import SessionLocal
from app.services.ibkr_statement_import import MAX_XML_BYTES, reconcile_statement


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', required=True)
    parser.add_argument('--profile-id', required=True, type=uuid.UUID)
    parser.add_argument('--admin-id', required=True, type=uuid.UUID)
    parser.add_argument('--timezone', required=True, help='Timezone configured in the Flex export, e.g. America/New_York')
    parser.add_argument('--mapping', help='JSON object mapping action UUIDs to lists of statement trade IDs')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        with Path(args.file).open('rb') as source:
            data = source.read(MAX_XML_BYTES + 1)
        if len(data) > MAX_XML_BYTES:
            raise ValueError('Statement exceeds 5 MB')
        xml = data.decode('utf-8')
        mapping = json.loads(Path(args.mapping).read_text()) if args.mapping else {}
        if not isinstance(mapping, dict) or (args.apply and not mapping):
            raise ValueError('Apply requires a reviewed nonempty mapping')
        with SessionLocal() as db:
            admin = db.get(User, args.admin_id)
            if admin is None or admin.role != 'ADMIN' or not admin.is_active:
                raise ValueError('An active ADMIN operator is required')
            profile = db.get(BrokerProfile, args.profile_id, with_for_update=args.apply)
            if profile is None or profile.provider != 'IBKR' or profile.environment != 'PAPER':
                raise ValueError('IBKR Paper profile not found')
            account_id = _creds(profile).get('account_id')
            result = reconcile_statement(db, profile, account_id, xml, args.timezone,
                                         mapping, admin.id, apply=args.apply)
            if args.apply:
                db.commit()
            print(json.dumps(result, indent=2))
    except (ValueError, OSError):
        print('Import stopped: invalid file, mapping, configuration or conflicting evidence. Use the authenticated preview endpoint for validation details.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
