"""FastAPI application entry point / FastAPI 應用程式進入點。"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from api.core.config import get_settings
from api.core.database import check_database
from api.realtime import realtime
from api.routers.admin import router as admin_router
from api.routers.auth import router as auth_router
from api.routers.chat import router as chat_router
from api.routers.explore import router as explore_router
from api.routers.meals import router as meals_router
from api.routers.public_map import router as public_map_router
from api.routers.reviews import router as reviews_router
from api.routers.social import router as social_router
from api.routers.tourism import router as tourism_router

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Start and stop cross-instance realtime transport / 啟停跨程序即時事件傳輸。"""
    await realtime.start()
    try:
        yield
    finally:
        await realtime.stop()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
media_root = Path(__file__).resolve().parents[2] / "media"
app.mount("/media", StaticFiles(directory=media_root), name="media")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(public_map_router)
app.include_router(explore_router)
app.include_router(reviews_router)
app.include_router(meals_router)
app.include_router(chat_router)
app.include_router(social_router)
app.include_router(tourism_router)


@app.get("/health/live", tags=["health"])
async def liveness() -> dict[str, str]:
    # Liveness only confirms the process is running; it does not call the database.
    # Liveness 只確認程序存活，不檢查資料庫，避免重啟期間誤判。
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"])
async def readiness() -> dict[str, str]:
    # Readiness is the dependency-aware check used by local tooling and deployments.
    # Readiness 會檢查必要依賴，供本機工具與部署平台判斷是否可接收流量。
    try:
        postgis_version = await check_database()
    except (SQLAlchemyError, RuntimeError) as error:
        logger.exception("Readiness check failed")
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "database": "unavailable"},
        ) from error

    return {"status": "ready", "database": "ready", "postgis": postgis_version}
