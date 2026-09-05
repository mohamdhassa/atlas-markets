import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta
from threading import Lock

from fastapi import FastAPI, Header, HTTPException
import MetaTrader5 as mt5

app = FastAPI(title="ATLAS MT5 Bridge", version="1.2.0")

EXPECTED_LOGIN = int(os.getenv("MT5_EXPECTED_LOGIN", "446650"))
EXPECTED_SERVER = os.getenv("MT5_EXPECTED_SERVER", "FusionMarkets-Demo").strip()
BRIDGE_TOKEN = os.getenv("BRIDGE_TOKEN", "").strip()
ALLOW_TRADING = os.getenv("ALLOW_TRADING", "false").strip().lower() == "true"
MAGIC = int(os.getenv("MT5_MAGIC", "446650"))
DEVIATION = int(os.getenv("MT5_DEVIATION", "20"))

_mt5_lock = Lock()


def _auth(token: str | None) -> None:
    if not BRIDGE_TOKEN:
        raise HTTPException(status_code=503, detail="Bridge token is not configured")
    if not token or not secrets.compare_digest(token, BRIDGE_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized")


@contextmanager
def _session():
    with _mt5_lock:
        if not mt5.initialize():
            raise HTTPException(status_code=503, detail={"message": "MT5 initialize failed", "mt5_error": mt5.last_error()})
        try:
            account = mt5.account_info()
            if account is None:
                raise HTTPException(status_code=503, detail={"message": "MT5 account unavailable", "mt5_error": mt5.last_error()})
            if int(account.login) != EXPECTED_LOGIN:
                raise HTTPException(status_code=403, detail=f"Unexpected MT5 login: {account.login}")
            if str(account.server) != EXPECTED_SERVER:
                raise HTTPException(status_code=403, detail=f"Unexpected MT5 server: {account.server}")
            yield account
        finally:
            mt5.shutdown()


def _symbol_name(value: str) -> str:
    return str(value or "").strip().upper().replace("/", "").replace(" ", "")


def _ensure_symbol(symbol: str):
    info = mt5.symbol_info(symbol)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    if not info.visible and not mt5.symbol_select(symbol, True):
        raise HTTPException(status_code=503, detail=f"Unable to select symbol {symbol}")
    return mt5.symbol_info(symbol) or info


def _timeframe(value: str):
    mapping = {
        "1m": mt5.TIMEFRAME_M1,
        "5m": mt5.TIMEFRAME_M5,
        "15m": mt5.TIMEFRAME_M15,
        "30m": mt5.TIMEFRAME_M30,
        "1h": mt5.TIMEFRAME_H1,
        "4h": mt5.TIMEFRAME_H4,
        "1d": mt5.TIMEFRAME_D1,
    }
    key = value.strip().lower()
    if key not in mapping:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe: {value}")
    return mapping[key]


def _validate_volume(info, volume: float) -> None:
    if volume < float(info.volume_min) or volume > float(info.volume_max):
        raise HTTPException(status_code=400, detail={"message": "Volume outside broker limits", "volume_min": info.volume_min, "volume_max": info.volume_max})
    step = float(info.volume_step or 0)
    if step > 0:
        steps = round((volume - float(info.volume_min)) / step)
        normalized = float(info.volume_min) + steps * step
        if abs(normalized - volume) > max(1e-9, step / 1000):
            raise HTTPException(status_code=400, detail={"message": "Volume does not match broker step", "volume_step": info.volume_step})


def _trade_request(payload: dict) -> dict:
    symbol = _symbol_name(payload.get("symbol"))
    side = str(payload.get("side", "")).strip().upper()
    if side not in {"BUY", "SELL"}:
        raise HTTPException(status_code=400, detail="Side must be BUY or SELL")
    try:
        volume = float(payload.get("volume", 0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid volume")
    info = _ensure_symbol(symbol)
    _validate_volume(info, volume)
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise HTTPException(status_code=503, detail={"message": "Unable to read market price", "mt5_error": mt5.last_error()})
    price = float(tick.ask if side == "BUY" else tick.bid)
    if price <= 0:
        raise HTTPException(status_code=503, detail="Invalid market price")
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY if side == "BUY" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "deviation": DEVIATION,
        "magic": MAGIC,
        "comment": str(payload.get("comment") or "ATLAS SIMULATION")[:31],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": int(info.filling_mode),
    }
    sl = payload.get("stop_loss")
    tp = payload.get("take_profit")
    if sl is not None:
        request["sl"] = float(sl)
    if tp is not None:
        request["tp"] = float(tp)
    return request


@app.get("/health")
def health(x_atlas_bridge_token: str | None = Header(default=None, alias="X-ATLAS-BRIDGE-TOKEN")):
    _auth(x_atlas_bridge_token)
    with _session() as account:
        terminal = mt5.terminal_info()
        if terminal is None:
            raise HTTPException(status_code=503, detail="Terminal info unavailable")
        return {
            "status": "ok",
            "connected": bool(terminal.connected),
            "mt5_connected": bool(terminal.connected),
            "login": account.login,
            "server": account.server,
            "trading_enabled": ALLOW_TRADING,
            "terminal": {"connected": terminal.connected, "trade_allowed": terminal.trade_allowed},
            "account": {"trade_allowed": account.trade_allowed, "trade_expert": account.trade_expert},
        }


@app.get("/account")
def account(x_atlas_bridge_token: str | None = Header(default=None, alias="X-ATLAS-BRIDGE-TOKEN")):
    _auth(x_atlas_bridge_token)
    with _session() as info:
        return info._asdict()


@app.get("/positions")
def positions(x_atlas_bridge_token: str | None = Header(default=None, alias="X-ATLAS-BRIDGE-TOKEN")):
    _auth(x_atlas_bridge_token)
    with _session():
        data = mt5.positions_get()
        if data is None:
            raise HTTPException(status_code=503, detail={"message": "Unable to read positions", "mt5_error": mt5.last_error()})
        return {"list": [row._asdict() for row in data]}


@app.get("/orders")
def orders(x_atlas_bridge_token: str | None = Header(default=None, alias="X-ATLAS-BRIDGE-TOKEN")):
    _auth(x_atlas_bridge_token)
    with _session():
        data = mt5.orders_get()
        if data is None:
            raise HTTPException(status_code=503, detail={"message": "Unable to read orders", "mt5_error": mt5.last_error()})
        return {"list": [row._asdict() for row in data]}


@app.get("/history/deals")
def history_deals(days: int = 30, x_atlas_bridge_token: str | None = Header(default=None, alias="X-ATLAS-BRIDGE-TOKEN")):
    _auth(x_atlas_bridge_token)
    with _session():
        end = datetime.now()
        start = end - timedelta(days=max(1, min(days, 366)))
        data = mt5.history_deals_get(start, end)
        if data is None:
            raise HTTPException(status_code=503, detail={"message": "Unable to read deal history", "mt5_error": mt5.last_error()})
        return {"list": [row._asdict() for row in data]}


@app.get("/candles/{symbol}")
def candles(symbol: str, timeframe: str = "5m", limit: int = 200, x_atlas_bridge_token: str | None = Header(default=None, alias="X-ATLAS-BRIDGE-TOKEN")):
    _auth(x_atlas_bridge_token)
    with _session():
        symbol = _symbol_name(symbol)
        _ensure_symbol(symbol)
        data = mt5.copy_rates_from_pos(symbol, _timeframe(timeframe), 0, max(2, min(limit, 500)))
        if data is None:
            raise HTTPException(status_code=503, detail={"message": f"Unable to read candles for {symbol}", "mt5_error": mt5.last_error()})
        return {"symbol": symbol, "timeframe": timeframe, "list": [{"time": int(r["time"]), "open": float(r["open"]), "high": float(r["high"]), "low": float(r["low"]), "close": float(r["close"]), "tick_volume": int(r["tick_volume"]), "spread": int(r["spread"]), "real_volume": int(r["real_volume"])} for r in data]}


@app.get("/symbols/search")
def search_symbols(q: str = "", limit: int = 50, x_atlas_bridge_token: str | None = Header(default=None, alias="X-ATLAS-BRIDGE-TOKEN")):
    _auth(x_atlas_bridge_token)
    with _session():
        data = mt5.symbols_get()
        if data is None:
            raise HTTPException(status_code=503, detail={"message": "Unable to read symbols", "mt5_error": mt5.last_error()})
        query = q.strip().upper()
        out = []
        for item in data:
            if not query or query in item.name.upper():
                out.append(item._asdict())
            if len(out) >= max(1, min(limit, 200)):
                break
        return {"list": out}


@app.get("/symbol/{symbol}")
def symbol_info(symbol: str, x_atlas_bridge_token: str | None = Header(default=None, alias="X-ATLAS-BRIDGE-TOKEN")):
    _auth(x_atlas_bridge_token)
    with _session():
        symbol = _symbol_name(symbol)
        info = _ensure_symbol(symbol)
        tick = mt5.symbol_info_tick(symbol)
        return {"symbol": symbol, "info": info._asdict(), "tick": tick._asdict() if tick else None}


@app.post("/order/check")
def order_check(payload: dict, x_atlas_bridge_token: str | None = Header(default=None, alias="X-ATLAS-BRIDGE-TOKEN")):
    _auth(x_atlas_bridge_token)
    with _session():
        request = _trade_request(payload)
        result = mt5.order_check(request)
        if result is None:
            raise HTTPException(status_code=503, detail={"message": "MT5 order_check failed", "mt5_error": mt5.last_error()})
        return {"ok": result.retcode == 0, "result": result._asdict(), "trading_enabled": ALLOW_TRADING}


@app.post("/order")
def place_order(payload: dict, x_atlas_bridge_token: str | None = Header(default=None, alias="X-ATLAS-BRIDGE-TOKEN")):
    _auth(x_atlas_bridge_token)
    if not ALLOW_TRADING:
        raise HTTPException(status_code=403, detail="Trading is disabled on the MT5 bridge")
    with _session() as account:
        terminal = mt5.terminal_info()
        if not terminal or not terminal.trade_allowed or not account.trade_allowed or not account.trade_expert:
            raise HTTPException(status_code=403, detail="MT5 terminal/account trading is not allowed")
        request = _trade_request(payload)
        check = mt5.order_check(request)
        if check is None or check.retcode != 0:
            raise HTTPException(status_code=400, detail={"message": "MT5 order_check rejected order", "result": check._asdict() if check else None, "mt5_error": mt5.last_error()})
        result = mt5.order_send(request)
        if result is None:
            raise HTTPException(status_code=503, detail={"message": "MT5 order_send failed", "mt5_error": mt5.last_error()})
        success_codes = {mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_DONE_PARTIAL, mt5.TRADE_RETCODE_PLACED}
        if result.retcode not in success_codes:
            raise HTTPException(status_code=400, detail={"message": "MT5 rejected order", "result": result._asdict()})
        return {"ok": True, "result": result._asdict()}


@app.post("/positions/{ticket}/close")
def close_position(ticket: int, x_atlas_bridge_token: str | None = Header(default=None, alias="X-ATLAS-BRIDGE-TOKEN")):
    _auth(x_atlas_bridge_token)
    if not ALLOW_TRADING:
        raise HTTPException(status_code=403, detail="Trading is disabled on the MT5 bridge")
    with _session() as account:
        terminal = mt5.terminal_info()
        if not terminal or not terminal.trade_allowed or not account.trade_allowed or not account.trade_expert:
            raise HTTPException(status_code=403, detail="MT5 terminal/account trading is not allowed")
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            raise HTTPException(status_code=404, detail=f"Position {ticket} not found")
        position = positions[0]
        symbol = position.symbol
        info = _ensure_symbol(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise HTTPException(status_code=503, detail="Unable to read market price")
        is_buy = position.type == mt5.POSITION_TYPE_BUY
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": int(position.ticket),
            "symbol": symbol,
            "volume": float(position.volume),
            "type": mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
            "price": float(tick.bid if is_buy else tick.ask),
            "deviation": DEVIATION,
            "magic": MAGIC,
            "comment": "ATLAS CLOSE",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": int(info.filling_mode),
        }
        check = mt5.order_check(request)
        if check is None or check.retcode != 0:
            raise HTTPException(status_code=400, detail={"message": "MT5 close check rejected", "result": check._asdict() if check else None, "mt5_error": mt5.last_error()})
        result = mt5.order_send(request)
        if result is None:
            raise HTTPException(status_code=503, detail={"message": "MT5 close failed", "mt5_error": mt5.last_error()})
        success_codes = {mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_DONE_PARTIAL, mt5.TRADE_RETCODE_PLACED}
        if result.retcode not in success_codes:
            raise HTTPException(status_code=400, detail={"message": "MT5 rejected close", "result": result._asdict()})
        return {"ok": True, "result": result._asdict()}
