import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from api.config import get_settings
from api.db import check_database

logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health/live", tags=["health"])
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"])
async def readiness() -> dict[str, str]:
    try:
        postgis_version = await check_database()
    except (SQLAlchemyError, RuntimeError) as error:
        logger.exception("Readiness check failed")
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "database": "unavailable"},
        ) from error

    return {"status": "ready", "database": "ready", "postgis": postgis_version}

