import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.api.health import router as health_router
from app.api.routes_accounts import router as accounts_router
from app.api.routes_account_lifecycle import router as account_lifecycle_router
from app.api.routes_admin import router as admin_router
from app.api.routes_analysis import router as analysis_router
from app.api.routes_auth import router as auth_router
from app.api.routes_automation import router as automation_router
from app.api.routes_broker_native import router as broker_native_router
from app.api.routes_bybit_environment import router as bybit_environment_router
from app.api.routes_bybit_oauth import router as bybit_oauth_router
from app.api.routes_historical import router as historical_router
from app.api.routes_ibkr_external import router as ibkr_external_router
from app.api.routes_markets import router as markets_router
from app.api.routes_workspace_quotes import router as workspace_quotes_router
from app.api.routes_news import router as news_router
from app.api.routes_paper import router as legacy_account_router
from app.api.routes_performance import router as performance_router
from app.api.routes_provider_certification import router as provider_certification_router
from app.api.routes_release import router as release_router
from app.api.routes_reporting import router as reporting_router
from app.api.routes_signals import router as signals_router
from app.api.routes_symbol_strategies import router as symbol_strategies_router
from app.api.routes_universe_engine import router as universe_engine_router
from app.api.routes_phase35 import router as phase35_router
from app.api.routes_phase36 import router as phase36_router
from app.api.routes_phase36_verified import router as phase36_verified_router
from app.core.config import get_settings
from app.services.safe_automation import safe_automation_loop
from app.services.historical_intelligence import historical_loop
from app.services.reporting import reporting_loop
settings=get_settings();static_dir=Path(__file__).resolve().parent/'static'
@asynccontextmanager
async def lifespan(app:FastAPI):
    stop=asyncio.Event();tasks=[asyncio.create_task(safe_automation_loop(stop)),asyncio.create_task(reporting_loop(stop)),asyncio.create_task(historical_loop(stop))];app.state.automation_stop=stop;app.state.background_tasks=tasks
    try:yield
    finally:
        stop.set()
        for task in tasks:
            try:await asyncio.wait_for(task,timeout=3)
            except (asyncio.TimeoutError,asyncio.CancelledError):task.cancel()
app=FastAPI(title=settings.app_name,version='1.0.0',debug=settings.debug,lifespan=lifespan)
app.include_router(health_router);app.include_router(auth_router);app.include_router(admin_router);app.include_router(markets_router);app.include_router(workspace_quotes_router);app.include_router(accounts_router);app.include_router(account_lifecycle_router);app.include_router(bybit_environment_router);app.include_router(bybit_oauth_router);app.include_router(ibkr_external_router);app.include_router(provider_certification_router);app.include_router(analysis_router);app.include_router(signals_router);app.include_router(legacy_account_router);app.include_router(automation_router);app.include_router(broker_native_router);app.include_router(phase35_router);app.include_router(phase36_router);app.include_router(phase36_verified_router);app.include_router(performance_router);app.include_router(news_router);app.include_router(reporting_router);app.include_router(historical_router);app.include_router(symbol_strategies_router);app.include_router(universe_engine_router);app.include_router(release_router)

def _register_missing_router_routes(router):
    existing={(getattr(r,'path',None),frozenset(getattr(r,'methods',set()) or set())) for r in app.routes}
    for route in router.routes:
        key=(getattr(route,'path',None),frozenset(getattr(route,'methods',set()) or set()))
        if key not in existing:
            app.router.routes.append(route);existing.add(key)

_register_missing_router_routes(admin_router)
_register_missing_router_routes(symbol_strategies_router)
_register_missing_router_routes(automation_router)
_register_missing_router_routes(workspace_quotes_router)
app.mount('/static',StaticFiles(directory=static_dir),name='static')
@app.get('/',include_in_schema=False)
async def root()->FileResponse:return FileResponse(static_dir/'index.html')
@app.get('/api/system',tags=['system'])
async def system_info()->dict[str,str]:return {'name':settings.app_name,'status':'running','phase':'40','version':'1.0.0','release':'SIMULATION_RELEASE','account_model':'EXTERNAL_PROVIDERS_ONLY','account_modes':'SIMULATION+LIVE_MONEY','broker_accounts':'BYBIT+MT5_FUSION+IBKR','market_data_providers':'BYBIT+MT5_FUSION+TWELVE_DATA+IBKR','live_money_execution':'GATED','provider_switching':'FRONTEND','automation':'CERTIFIED_ROUTES_ONLY','certified_automation':'MT5_DEMO+IBKR_PAPER','provider_certification':'IBKR_PAPER_CERTIFIED+BYBIT_PROVIDER_BLOCKED','analytics':'UNIFIED_TRADE_HISTORY+PNL+STRATEGY_PERFORMANCE+VERIFIED_ATTRIBUTION+MULTI_MARKET+PER_ACCOUNT','historical_learning':'ACTIVE','news_intelligence':'ACTIVE','reporting':'BROKER_NATIVE+UNIFIED+STRATEGY_INTELLIGENCE','market_scope':'FX+CRYPTO+STOCKS+ETFS+METALS+COMMODITIES','ibkr':'PAPER_CERTIFIED_MAX_1_SHARE','bybit_agent_connect':'TESTNET_CONNECTED_EXECUTION_NOT_CERTIFIED'}
