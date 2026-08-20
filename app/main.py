from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.routes_admin import router as admin_router
from app.api.routes_auth import router as auth_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.3.0",
    debug=settings.debug,
)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(admin_router)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "status": "running",
        "phase": "3",
    }
