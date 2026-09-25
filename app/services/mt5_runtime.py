from __future__ import annotations

from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings


def mt5_client() -> Mt5BridgeClient:
    settings = get_settings()
    url = (settings.mt5_bridge_url or "").strip()
    if not url:
        raise RuntimeError("MT5 execution node is pending and has not been configured on the ATLAS server")
    return Mt5BridgeClient(
        url,
        (settings.mt5_bridge_token or "").strip() or None,
        settings.market_data_timeout_seconds,
    )


async def mt5_runtime_readiness() -> dict:
    settings = get_settings()
    configured = bool((settings.mt5_bridge_url or "").strip())
    if not configured:
        return {
            "provider": "MT5",
            "configured": False,
            "reachable": False,
            "connected": False,
            "simulation_ready": False,
            "execution_ready": False,
            "status": "PENDING_CONFIGURATION",
            "blockers": ["MT5_BRIDGE_URL_NOT_CONFIGURED"],
        }
    try:
        client = mt5_client()
        health = await client.readiness()
        account = await client.account()
    except Exception as exc:
        return {
            "provider": "MT5",
            "configured": True,
            "reachable": False,
            "connected": False,
            "simulation_ready": False,
            "execution_ready": False,
            "status": "UNAVAILABLE",
            "blockers": ["MT5_EXECUTION_NODE_UNAVAILABLE"],
            "error": f"{type(exc).__name__}: {str(exc)[:240]}",
        }
    terminal = health.get("terminal") or {}
    account_state = health.get("account") or {}
    server = str(account.get("server") or health.get("server") or "")
    connected = health.get("connected") is True
    demo = "demo" in server.lower()
    algo = bool(terminal.get("trade_allowed") and account_state.get("trade_allowed") and account_state.get("trade_expert"))
    bridge_trading = health.get("trading_enabled") is True
    blockers = []
    if not connected: blockers.append("MT5_TERMINAL_DISCONNECTED")
    if not demo: blockers.append("MT5_DEMO_SERVER_REQUIRED")
    if not algo: blockers.append("MT5_ALGO_TRADING_DISABLED")
    if not bridge_trading: blockers.append("MT5_BRIDGE_TRADING_DISABLED")
    return {
        "provider": "MT5",
        "configured": True,
        "reachable": True,
        "connected": connected,
        "simulation_ready": connected and demo,
        "execution_ready": connected and demo and algo and bridge_trading,
        "status": "READY" if connected and demo and algo and bridge_trading else "BLOCKED",
        "blockers": blockers,
        "login": account.get("login"),
        "server": server,
        "equity": account.get("equity"),
        "node": health,
    }
