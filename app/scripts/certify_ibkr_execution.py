from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.broker import BrokerProfile
from app.db.session import SessionLocal


def f(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def position_qty(rows: list[dict], account: str, symbol: str) -> float:
    total = 0.0
    for row in rows:
        if str(row.get("account") or "") != account:
            continue
        if str(row.get("symbol") or "").upper() != symbol.upper():
            continue
        total += f(row.get("quantity"))
    return total


async def wait_for_position_delta(
    client: IbkrBridgeClient,
    account: str,
    symbol: str,
    baseline: float,
    expected_delta: float,
    timeout: float = 20.0,
):
    deadline = time.monotonic() + timeout
    latest = baseline
    while time.monotonic() < deadline:
        rows = (await client.positions()).get("list", [])
        latest = position_qty(rows, account, symbol)
        if abs((latest - baseline) - expected_delta) < 1e-9:
            return True, latest
        await asyncio.sleep(0.75)
    return False, latest


async def wait_for_execution(
    client: IbkrBridgeClient,
    before_ids: set[str],
    account: str,
    symbol: str,
    side: str,
    timeout: float = 20.0,
):
    deadline = time.monotonic() + timeout
    latest: list[dict] = []
    while time.monotonic() < deadline:
        latest = (await client.executions(1)).get("list", [])
        for row in latest:
            eid = str(row.get("execution_id") or "")
            if not eid or eid in before_ids:
                continue
            if str(row.get("account") or "") != account:
                continue
            if str(row.get("symbol") or "").upper() != symbol.upper():
                continue
            ib_side = str(row.get("side") or "").upper()
            expected = {"BUY": {"BOT", "BUY"}, "SELL": {"SLD", "SELL"}}[side]
            if ib_side in expected:
                return row, latest
        await asyncio.sleep(0.75)
    return None, latest


async def cancel_if_open(client: IbkrBridgeClient, order_id: int):
    try:
        rows = (await client.orders()).get("list", [])
        if any(int(x.get("order_id") or -1) == order_id for x in rows):
            await client.cancel_order(order_id)
            print(f"CANCEL  | requested order_id={order_id}")
    except Exception as exc:
        print(f"WARN    | could not inspect/cancel order_id={order_id}: {type(exc).__name__}: {exc}")


async def main():
    db = SessionLocal()
    try:
        profiles = list(db.scalars(select(BrokerProfile).where(
            BrokerProfile.provider == "IBKR",
            BrokerProfile.is_enabled.is_(True),
        )).all())
        if len(profiles) != 1:
            raise RuntimeError(f"Expected exactly one enabled IBKR profile, found {len(profiles)}")
        profile = profiles[0]
        if str(profile.environment or "").upper() != "PAPER":
            raise RuntimeError(f"REFUSED: IBKR profile environment is {profile.environment!r}, not PAPER")
        if not profile.credential_blob_encrypted:
            raise RuntimeError("IBKR bridge configuration is missing")

        cfg = json.loads(decrypt_secret(profile.credential_blob_encrypted))
        client = IbkrBridgeClient(
            cfg.get("bridge_url") or "http://host.docker.internal:8766",
            cfg.get("bridge_token"),
            get_settings().market_data_timeout_seconds,
        )

        health = await client.health()
        account = await client.account()
        if not health.get("connected"):
            raise RuntimeError("IBKR bridge reachable but TWS/IB Gateway is disconnected")
        if not bool(health.get("simulation")) or not bool(account.get("simulation")):
            raise RuntimeError("REFUSED: IBKR bridge/account is not in Paper simulation mode")

        expected_account = str(cfg.get("account_id") or profile.external_account_ref or "").strip()
        actual_account = str(account.get("account_id") or "").strip()
        if expected_account and actual_account != expected_account:
            raise RuntimeError(f"REFUSED: IBKR account mismatch expected {expected_account}, got {actual_account}")
        if not actual_account:
            raise RuntimeError("IBKR account id is unavailable")

        # Avoid leaving a market order queued overnight. This is a practical certification
        # gate, not an exchange-calendar replacement; unexpected closures still time out
        # and trigger cancellation attempts.
        now_et = datetime.now(ZoneInfo("America/New_York"))
        minutes = now_et.hour * 60 + now_et.minute
        if now_et.weekday() >= 5 or not (9 * 60 + 35 <= minutes <= 15 * 60 + 50):
            raise RuntimeError(
                f"REFUSED: run IBKR execution certification during regular US market hours "
                f"(09:35-15:50 America/New_York); current={now_et:%Y-%m-%d %H:%M:%S %Z}"
            )

        positions_before = (await client.positions()).get("list", [])
        candidates = ["SPY", "QQQ", "IWM", "DIA"]
        symbol = next(
            (s for s in candidates if abs(position_qty(positions_before, actual_account, s)) < 1e-9),
            None,
        )
        if not symbol:
            raise RuntimeError(
                "REFUSED: certification candidates SPY/QQQ/IWM/DIA already have positions; "
                "will not mix certification shares with existing holdings"
            )

        quantity = 1.0
        baseline_qty = position_qty(positions_before, actual_account, symbol)
        executions_before = (await client.executions(1)).get("list", [])
        before_ids = {str(x.get("execution_id") or "") for x in executions_before if x.get("execution_id")}

        payload = {
            "symbol": symbol,
            "side": "BUY",
            "quantity": quantity,
            "order_type": "MKT",
            "sec_type": "STK",
            "exchange": "SMART",
            "currency": "USD",
            "account_id": actual_account,
        }
        check = await client.order_check(payload)
        if not check.get("ok") or not check.get("simulation"):
            raise RuntimeError(f"IBKR Paper preflight rejected certification order: {check}")

        print(
            f"CERTIFY | IBKR PAPER | account={actual_account} equity={f(account.get('equity')):.2f} "
            f"buying_power={f(account.get('buying_power')):.2f}"
        )
        print(f"PREFLIGHT| simulation=True symbol={symbol} quantity={quantity:g} order_type=MKT")
        print(f"ORDER   | {symbol} BUY Market quantity={quantity:g}")

        opened = await client.place_order(payload)
        open_order_id = int(opened.get("order_id") or 0)
        if not opened.get("accepted") or not opened.get("simulation") or not open_order_id:
            raise RuntimeError(f"IBKR Paper open order was not accepted: {opened}")
        print(f"OPEN    | accepted order_id={open_order_id}")

        open_exec, _ = await wait_for_execution(client, before_ids, actual_account, symbol, "BUY")
        delta_ok, current_qty = await wait_for_position_delta(
            client, actual_account, symbol, baseline_qty, quantity
        )
        if not open_exec or not delta_ok:
            await cancel_if_open(client, open_order_id)
            raise RuntimeError(
                f"IBKR Paper BUY was not safely confirmed; execution={open_exec is not None} "
                f"baseline_qty={baseline_qty:g} current_qty={current_qty:g}"
            )

        open_exec_id = str(open_exec.get("execution_id") or "")
        print(
            f"POSITION| confirmed symbol={symbol} baseline={baseline_qty:g} current={current_qty:g} "
            f"execution_id={open_exec_id} price={open_exec.get('price')}"
        )

        execs_after_open = (await client.executions(1)).get("list", [])
        close_before_ids = {str(x.get("execution_id") or "") for x in execs_after_open if x.get("execution_id")}
        close_payload = {**payload, "side": "SELL"}
        close_check = await client.order_check(close_payload)
        if not close_check.get("ok") or not close_check.get("simulation"):
            raise RuntimeError(f"IBKR Paper close preflight rejected: {close_check}")

        closed = await client.place_order(close_payload)
        close_order_id = int(closed.get("order_id") or 0)
        if not closed.get("accepted") or not closed.get("simulation") or not close_order_id:
            raise RuntimeError(f"IBKR Paper close order was not accepted: {closed}")
        print(f"CLOSE   | accepted order_id={close_order_id} side=SELL quantity={quantity:g}")

        close_exec, _ = await wait_for_execution(client, close_before_ids, actual_account, symbol, "SELL")
        flat_ok, final_qty = await wait_for_position_delta(
            client, actual_account, symbol, baseline_qty + quantity, -quantity
        )
        if not close_exec or not flat_ok:
            await cancel_if_open(client, close_order_id)
            raise RuntimeError(
                f"IBKR Paper close was not safely confirmed; execution={close_exec is not None} "
                f"expected_final={baseline_qty:g} actual_final={final_qty:g}. "
                f"MANUAL REVIEW REQUIRED before rerunning certification."
            )

        close_exec_id = str(close_exec.get("execution_id") or "")
        print(
            f"EXECUTIONS| open={open_exec_id} close={close_exec_id} "
            f"close_price={close_exec.get('price')}"
        )
        print(
            f"PASS    | IBKR PAPER EXECUTION CERTIFIED | account={actual_account} symbol={symbol} "
            f"quantity={quantity:g} restored_baseline_qty={final_qty:g} simulation=True"
        )
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
