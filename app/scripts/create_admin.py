from __future__ import annotations

import argparse
import getpass

from app.db.models.auth import UserRole
from app.db.session import SessionLocal
from app.services.auth import create_user


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an ATLAS MARKETS admin user.")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--email", default=None)
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    password = args.password or getpass.getpass("Admin password (minimum 12 characters): ")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters.")

    with SessionLocal() as db:
        try:
            user = create_user(
                db,
                username=args.username,
                email=args.email,
                password=password,
                role=UserRole.ADMIN.value,
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc

    print(f"Created ADMIN user: {user.username}")


if __name__ == "__main__":
    main()
