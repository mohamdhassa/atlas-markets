from __future__ import annotations

import asyncio
import math
import time

from sqlalchemy import select

from app.brokers.bybit_private import BybitPrivateClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.broker import BrokerProfile
from app.db.session import SessionLocal


def f(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def floor_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    return math.floor(value / step) * step


async def wait_for_position(client: BybitPrivateClient, symbol: str, timeout: float = 12.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        data = await client.positions()
        for item in data.get("list", []):
            if item.get("symbol") == symbol and f(item.get("size")) > 0:
                return item
        await asyncio.sleep(0.75)
    return None


async def wait_until_flat(client: BybitPrivateClient, symbol: str, timeout: float = 12.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        data = await client.positions()
        active = [x for x in data.get("list", []) if x.get("symbol") == symbol and f(x.get("size")) > 0]
        if not active:
            return True
        await asyncio.sleep(0.75)
    return False


async def main():
    db = SessionLocal()
    try:
        profiles = list(db.scalars(select(BrokerProfile).where(
            BrokerProfile.provider == "BYBIT",
            BrokerProfile.is_enabled.is_(True),
        )).all())
        if len(profiles) != 1:
            raise RuntimeError(f"Expected exactly one enabled BYBIT profile, found {len(profiles)}")
        profile = profiles[0]
        if str(profile.environment or "").upper() not in {"TESTNET", "SIMULATION"}:
            raise RuntimeError(f"REFUSED: profile environment is {profile.environment!r}, not TESTNET/SIMULATION")

        settings = get_settings()
        key = decrypt_secret(profile.api_key_encrypted or "")
        secret = decrypt_secret(profile.api_secret_encrypted or "")
        if not key or not secret:
            raise RuntimeError("Bybit credentials are missing")

        client = BybitPrivateClient(key, secret, settings.bybit_testnet_base_url, settings.market_data_timeout_seconds)
        wallet = await client.wallet()
        account = (wallet.get("list") or [{}])[0]
        available = f(account.get("totalAvailableBalance"))
        if available <= 0:
            raise RuntimeError("No available Testnet balance")

        symbol = "BTCUSDT"
        instrument = await client.get("/v5/market/instruments-info", {"category": "linear", "symbol": symbol})
        rows = instrument.get("list") or []
        if not rows:
            raise RuntimeError(f"No instrument metadata returned for {symbol}")
        meta = rows[0]
        lot = meta.get("lotSizeFilter") or {}
        min_qty = f(lot.get("minOrderQty"))
        qty_step = f(lot.get("qtyStep"))
        min_notional = f(lot.get("minNotionalValue"))

        ticker = await client.get("/v5/market/tickers", {"category": "linear", "symbol": symbol})
        ticker_rows = ticker.get("list") or []
        if not ticker_rows:
            raise RuntimeError(f"No ticker returned for {symbol}")
        price = f(ticker_rows[0].get("lastPrice"))
        if price <= 0:
            raise RuntimeError(f"Invalid {symbol} price")

        required_qty = max(min_qty, (min_notional / price) if min_notional else min_qty)
        if qty_step > 0:
            required_qty = math.ceil(required_qty / qty_step) * qty_step
        qty = max(min_qty, required_qty)
        estimated_notional = qty * price
        if estimated_notional > available * 5:
            raise RuntimeError(
                f"REFUSED: minimum {symbol} test order is about ${estimated_notional:.2f}, "
                f"too large for available Testnet balance ${available:.2f}"
            )

        link = f"atlas-cert-{int(time.time())}"[:36]
        print(f"CERTIFY | BYBIT TESTNET | account={profile.external_account_ref} available=${available:.2f}")
        print(f"ORDER   | {symbol} BUY Market qty={qty:g} approx_notional=${estimated_notional:.2f}")
        created = await client.place_demo_market_order(symbol=symbol, side="Buy", qty=qty, order_link_id=link)
        order_id = created.get("orderId") or ""
        print(f"OPEN    | submitted order_id={order_id or 'unknown'}")

        position = await wait_for_position(client, symbol)
        if not position:
            history = await client.order_history(20)
            raise RuntimeError(f"Order submitted but no open {symbol} position appeared; order_id={order_id}; history={history.get('list', [])[:2]}")

        actual_qty = f(position.get("size"))
        side = position.get("side")
        close_side = "Sell" if side == "Buy" else "Buy"
        print(f"POSITION| confirmed side={side} qty={actual_qty:g} avgPrice={position.get('avgPrice')}")

        close_payload = {
            "category": "linear",
            "symbol": symbol,
            "side": close_side,
            "orderType": "Market",
            "qty": f"{actual_qty:.8f}".rstrip("0").rstrip("."),
            "timeInForce": "IOC",
            "reduceOnly": True,
            "orderLinkId": f"atlas-close-{int(time.time())}"[:36],
        }
        closed = await client.post("/v5/order/create", close_payload)
        print(f"CLOSE   | submitted order_id={closed.get('orderId') or 'unknown'}")
        if not await wait_until_flat(client, symbol):
            raise RuntimeError(f"Close submitted but {symbol} position is still open")

        history = await client.order_history(20)
        pnl = await client.closed_pnl(20)
        print(f"PASS    | BYBIT TESTNET EXECUTION CERTIFIED | history={len(history.get('list', []))} closed={len(pnl.get('list', []))}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
