from fastapi import FastAPI

from travelx_agent.api.routes import router as chat_router
from travelx_agent.core.config import get_settings
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from travelx_agent.api.dependencies import close_database, close_traffic_guard

settings = get_settings()
@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield

    try:
        await close_traffic_guard()
    finally:
        await close_database()

app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(chat_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}