"""FastAPI application entry point / FastAPI 應用程式進入點。"""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from api.config import get_settings
from api.db import check_database
from api.routers.admin import router as admin_router
from api.routers.public_map import router as public_map_router

logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(admin_router)
app.include_router(public_map_router)


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
