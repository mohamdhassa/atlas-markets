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


async def wait_for_deals(client: Mt5BridgeClient, deal_ids: set[int], timeout: float = 10.0):
    deadline = time.monotonic() + timeout
    latest = []
    while time.monotonic() < deadline:
        latest = (await client.history_deals(1)).get("list", [])
        seen = {int(row.get("ticket") or 0) for row in latest if row.get("ticket")}
        if deal_ids.issubset(seen):
            return True, latest
        await asyncio.sleep(1.0)
    return False, latest


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

        check = await client.order_check({"symbol": symbol, "side": "BUY", "volume": volume, "comment": "ATLAS CERT MT5"})
        check_result = check.get("result") or {}
        raw_retcode = check_result.get("retcode")
        retcode = int(raw_retcode) if raw_retcode is not None else -1
        if retcode not in {0, 10009}:
            raise RuntimeError(f"MT5 preflight rejected certification order: {check_result}")

        print(f"CERTIFY | MT5 DEMO | login={account.get('login')} server={server} equity={f(account.get('equity')):.2f}")
        print(f"PREFLIGHT| retcode={retcode} comment={check_result.get('comment')}")
        print(f"ORDER   | {symbol} BUY Market volume={volume:g}")
        created = await client.place_demo_order(symbol=symbol, side="BUY", volume=volume, comment="ATLAS CERT MT5")
        result = created.get("result") or {}
        open_retcode = int(result.get("retcode") or -1)
        open_deal = int(result.get("deal") or 0)
        if open_retcode not in {10008, 10009} or not open_deal:
            raise RuntimeError(f"MT5 open execution was not confirmed: {result}")
        print(f"OPEN    | retcode={open_retcode} order={result.get('order')} deal={open_deal}")

        position = await wait_for_new_position(client, before_tickets, symbol)
        if not position:
            raise RuntimeError("MT5 order was accepted but a new EURUSD position could not be identified safely")
        ticket = int(position.get("ticket") or 0)
        if not ticket:
            raise RuntimeError("New MT5 position has no ticket")
        print(f"POSITION| ticket={ticket} symbol={position.get('symbol')} volume={position.get('volume')} price_open={position.get('price_open')}")

        closed = await client.close_demo_position(ticket)
        close_result = closed.get("result") or {}
        close_retcode = int(close_result.get("retcode") or -1)
        close_deal = int(close_result.get("deal") or 0)
        if close_retcode not in {10008, 10009} or not close_deal:
            raise RuntimeError(f"MT5 close execution was not confirmed: {close_result}")
        print(f"CLOSE   | retcode={close_retcode} order={close_result.get('order')} deal={close_deal}")
        if not await wait_until_closed(client, ticket):
            raise RuntimeError(f"MT5 close was submitted but position ticket {ticket} is still open")

        found, history = await wait_for_deals(client, {open_deal, close_deal})
        if found:
            print(f"HISTORY | confirmed deals={open_deal},{close_deal} rows={len(history)}")
        else:
            print(f"WARN    | execution confirmed but /history/deals has not exposed deals {open_deal},{close_deal} yet; rows={len(history)}")

        print(f"PASS    | MT5 DEMO EXECUTION CERTIFIED | ticket={ticket} open_deal={open_deal} close_deal={close_deal} flat=True")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
