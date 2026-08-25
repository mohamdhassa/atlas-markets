from __future__ import annotations

import asyncio
import json
import time

from sqlalchemy import select

from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.broker import BrokerProfile
from app.db.session import SessionLocal


def f(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


async def wait_for_new_position(client: Mt5BridgeClient, before: set[int], symbol: str, timeout: float = 12.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rows = (await client.positions()).get("list", [])
        for row in rows:
            ticket = int(row.get("ticket") or 0)
            if ticket and ticket not in before and str(row.get("symbol") or "").upper() == symbol.upper():
                return row
        await asyncio.sleep(0.5)
    return None


async def wait_until_closed(client: Mt5BridgeClient, ticket: int, timeout: float = 12.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rows = (await client.positions()).get("list", [])
        if all(int(row.get("ticket") or 0) != ticket for row in rows):
            return True
        await asyncio.sleep(0.5)
    return False


async def main():
    db = SessionLocal()
    try:
        profiles = list(db.scalars(select(BrokerProfile).where(
            BrokerProfile.provider == "MT5",
            BrokerProfile.is_enabled.is_(True),
        )).all())
        if len(profiles) != 1:
            raise RuntimeError(f"Expected exactly one enabled MT5 profile, found {len(profiles)}")
        profile = profiles[0]
        if str(profile.environment or "").upper() != "DEMO":
            raise RuntimeError(f"REFUSED: MT5 profile environment is {profile.environment!r}, not DEMO")
        if not profile.credential_blob_encrypted:
            raise RuntimeError("MT5 bridge configuration is missing")

        cfg = json.loads(decrypt_secret(profile.credential_blob_encrypted))
        client = Mt5BridgeClient(
            cfg.get("bridge_url") or "http://host.docker.internal:8765",
            cfg.get("bridge_token"),
            get_settings().market_data_timeout_seconds,
        )
        health = await client.health()
        account = await client.account()
        if not health.get("connected"):
            raise RuntimeError("MT5 bridge reachable but terminal is disconnected")
        server = str(account.get("server") or "")
        if "demo" not in server.lower():
            raise RuntimeError(f"REFUSED: MT5 server is {server!r}, not a demo server")
        terminal = health.get("terminal") or {}
        if not terminal.get("trade_allowed"):
            raise RuntimeError("REFUSED: MT5 Algo Trading is disabled")

        symbol = "EURUSD"
        info = await client.symbol(symbol)
        volume_min = f(info.get("volume_min")) or 0.01
        volume_step = f(info.get("volume_step")) or volume_min
        volume = max(volume_min, volume_step)
        if volume > 0.10:
            raise RuntimeError(f"REFUSED: minimum {symbol} volume {volume:g} lots is unexpectedly large")

        before_rows = (await client.positions()).get("list", [])
        before_tickets = {int(x.get("ticket") or 0) for x in before_rows if x.get("ticket")}
        deals_before = len((await client.history_deals(1)).get("list", []))

        check = await client.order_check({"symbol": symbol, "side": "BUY", "volume": volume, "comment": "ATLAS CERT MT5"})
        check_result = check.get("result") or {}
        retcode = int(check_result.get("retcode") or -1)
        if retcode not in {0, 10009}:
            raise RuntimeError(f"MT5 preflight rejected certification order: {check_result}")

        print(f"CERTIFY | MT5 DEMO | login={account.get('login')} server={server} equity={f(account.get('equity')):.2f}")
        print(f"ORDER   | {symbol} BUY Market volume={volume:g}")
        created = await client.place_demo_order(symbol=symbol, side="BUY", volume=volume, comment="ATLAS CERT MT5")
        result = created.get("result") or {}
        print(f"OPEN    | retcode={result.get('retcode')} order={result.get('order')} deal={result.get('deal')}")

        position = await wait_for_new_position(client, before_tickets, symbol)
        if not position:
            raise RuntimeError("MT5 order was accepted but a new EURUSD position could not be identified safely")
        ticket = int(position.get("ticket") or 0)
        if not ticket:
            raise RuntimeError("New MT5 position has no ticket")
        print(f"POSITION| ticket={ticket} symbol={position.get('symbol')} volume={position.get('volume')} price_open={position.get('price_open')}")

        closed = await client.close_demo_position(ticket)
        close_result = closed.get("result") or {}
        print(f"CLOSE   | retcode={close_result.get('retcode')} order={close_result.get('order')} deal={close_result.get('deal')}")
        if not await wait_until_closed(client, ticket):
            raise RuntimeError(f"MT5 close was submitted but position ticket {ticket} is still open")

        deals_after = len((await client.history_deals(1)).get("list", []))
        if deals_after < deals_before + 2:
            raise RuntimeError(f"Expected at least 2 new MT5 deals, before={deals_before} after={deals_after}")
        print(f"PASS    | MT5 DEMO EXECUTION CERTIFIED | ticket={ticket} deals_added={deals_after - deals_before}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
