import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.api.health import router as health_router
from app.api.routes_accounts import router as accounts_router
from app.api.routes_admin import router as admin_router
from app.api.routes_analysis import router as analysis_router
from app.api.routes_auth import router as auth_router
from app.api.routes_automation import router as automation_router
from app.api.routes_markets import router as markets_router
from app.api.routes_news import router as news_router
from app.api.routes_paper import router as paper_router
from app.api.routes_performance import router as performance_router
from app.api.routes_reporting import router as reporting_router
from app.api.routes_signals import router as signals_router
from app.core.config import get_settings
from app.services.automation import automation_loop
from app.services.reporting import reporting_loop
settings=get_settings();static_dir=Path(__file__).resolve().parent/"static"
@asynccontextmanager
async def lifespan(app:FastAPI):
    stop=asyncio.Event();automation_task=asyncio.create_task(automation_loop(stop));report_task=asyncio.create_task(reporting_loop(stop));app.state.automation_stop=stop;app.state.automation_task=automation_task;app.state.reporting_task=report_task
    try:yield
    finally:
        stop.set()
        for task in (automation_task,report_task):
            try:await asyncio.wait_for(task,timeout=3)
            except (asyncio.TimeoutError,asyncio.CancelledError):task.cancel()
app=FastAPI(title=settings.app_name,version="0.16.0",debug=settings.debug,lifespan=lifespan)
app.include_router(health_router);app.include_router(auth_router);app.include_router(admin_router);app.include_router(markets_router);app.include_router(accounts_router);app.include_router(analysis_router);app.include_router(signals_router);app.include_router(paper_router);app.include_router(automation_router);app.include_router(performance_router);app.include_router(news_router);app.include_router(reporting_router);app.mount("/static",StaticFiles(directory=static_dir),name="static")
@app.get("/",include_in_schema=False)
async def root()->FileResponse:return FileResponse(static_dir/"index.html")
@app.get("/api/system",tags=["system"])
async def system_info()->dict[str,str]:return {"name":settings.app_name,"status":"running","phase":"16","market_data_provider":"BYBIT_CRYPTO+TWELVE_DATA_FX","paper_broker":"ATLAS_PAPER","automation":"ACTIVE","analytics":"STRATEGY_INTELLIGENCE","news_intelligence":"ACTIVE","reporting":"ACTIVE","market_scope":"FX_CRYPTO_STOCKS_ETFS"}
