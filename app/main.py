import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.api.routes_account_lifecycle import router as account_lifecycle_router
from app.api.routes_accounts import router as accounts_router
from app.api.routes_admin import router as admin_router
from app.api.routes_analysis import router as analysis_router
from app.api.routes_auth import router as auth_router
from app.api.routes_automation import router as automation_router
from app.api.routes_broker_native import router as broker_native_router
from app.api.routes_bybit_certification_state import router as bybit_certification_state_router
from app.api.routes_bybit_environment import router as bybit_environment_router
from app.api.routes_bybit_oauth import router as bybit_oauth_router
from app.api.routes_historical import router as historical_router
from app.api.routes_ibkr_external import router as ibkr_external_router
from app.api.routes_markets import router as markets_router
from app.api.routes_news import router as news_router
from app.api.routes_paper import router as legacy_account_router
from app.api.routes_performance import router as performance_router
from app.api.routes_phase35 import router as phase35_router
from app.api.routes_phase36 import router as phase36_router
from app.api.routes_phase36_verified import router as phase36_verified_router
from app.api.routes_position_lifecycle import router as position_lifecycle_router
from app.api.routes_provider_certification import router as provider_certification_router
from app.api.routes_release import router as release_router
from app.api.routes_reporting import router as reporting_router
from app.api.routes_signals import router as signals_router
from app.api.routes_symbol_strategies import router as symbol_strategies_router
from app.api.routes_universe_engine import router as universe_engine_router
from app.api.routes_workspace_quotes import router as workspace_quotes_router
from app.core.config import get_settings
from app.services.historical_intelligence import historical_loop
from app.services.ibkr_position_manager import ibkr_position_manager_loop
from app.services.mt5_position_manager import mt5_position_manager_loop
from app.services.reporting import reporting_loop
from app.services.safe_automation import safe_automation_loop

settings = get_settings()
static_dir = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = asyncio.Event()
    tasks = [
        asyncio.create_task(safe_automation_loop(stop)),
        asyncio.create_task(mt5_position_manager_loop(stop)),
        asyncio.create_task(ibkr_position_manager_loop(stop)),
        asyncio.create_task(reporting_loop(stop)),
        asyncio.create_task(historical_loop(stop)),
    ]
    app.state.automation_stop = stop
    app.state.background_tasks = tasks
    try:
        yield
    finally:
        stop.set()
        for task in tasks:
            try:
                await asyncio.wait_for(task, timeout=3)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task.cancel()


app = FastAPI(title=settings.app_name, version="2.0.0", debug=settings.debug, lifespan=lifespan)

# Canonical route registration. Routers are included exactly once; the old
# post-registration route-copy workaround made route ownership/order ambiguous.
for router in (
    health_router,
    auth_router,
    admin_router,
    markets_router,
    workspace_quotes_router,
    bybit_certification_state_router,
    accounts_router,
    account_lifecycle_router,
    bybit_environment_router,
    bybit_oauth_router,
    ibkr_external_router,
    provider_certification_router,
    analysis_router,
    signals_router,
    legacy_account_router,
    automation_router,
    position_lifecycle_router,
    broker_native_router,
    phase35_router,
    phase36_router,
    phase36_verified_router,
    performance_router,
    news_router,
    reporting_router,
    historical_router,
    symbol_strategies_router,
    universe_engine_router,
    release_router,
):
    app.include_router(router)

app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/api/system", tags=["system"])
async def system_info() -> dict[str, object]:
    """Stable product capabilities only; runtime readiness comes from provider APIs.

    This endpoint intentionally does not claim that a broker is connected or
    certified. Those values change at runtime and are exposed by account,
    certification, automation and release-readiness endpoints.
    """
    return {
        "name": settings.app_name,
        "status": "running",
        "version": "2.0.0",
        "architecture": "CONSOLIDATED_CORE",
        "account_model": "MULTI_USER_EXTERNAL_PROVIDERS",
        "roles": ["ADMIN", "USER"],
        "providers": ["BYBIT", "MT5_FUSION", "IBKR", "TWELVE_DATA"],
        "market_scope": ["FX", "CRYPTO", "STOCKS", "ETFS", "METALS", "COMMODITIES"],
        "execution_policy": "CERTIFIED_ROUTES_ONLY",
        "live_money_policy": "EXPLICITLY_GATED",
        "provider_readiness_source": "RUNTIME_ACCOUNT_AND_CERTIFICATION_ENDPOINTS",
        "analytics": ["TRADE_HISTORY", "PNL", "STRATEGY_PERFORMANCE", "VERIFIED_ATTRIBUTION", "PER_ACCOUNT"],
        "services": ["AUTOMATION", "POSITION_MANAGEMENT", "HISTORICAL_INTELLIGENCE", "NEWS_INTELLIGENCE", "REPORTING"],
    }
