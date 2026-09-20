"""Async database primitives / 非同步資料庫基礎元件。"""

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from api.config import get_settings


class Base(DeclarativeBase):
    """Base metadata for future domain models / 未來領域模型共用的 metadata。"""


def create_engine() -> AsyncEngine:
    # pool_pre_ping avoids reusing a stale connection after Docker restarts.
    # pool_pre_ping 可避免 Docker 重啟後重用已失效的連線。
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


engine = create_engine()
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    # FastAPI dependencies can inject this session into future route handlers.
    # FastAPI dependency 可將此 session 注入未來的 API route。
    async with session_factory() as session:
        yield session


async def check_database() -> str:
    # SELECT PostGIS_Version verifies both connectivity and the spatial extension.
    # 查詢 PostGIS_Version 同時驗證資料庫連線與空間 extension。
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
        postgis_version = await connection.scalar(text("SELECT PostGIS_Version()"))

    if not isinstance(postgis_version, str) or not postgis_version:
        raise RuntimeError("PostGIS extension is unavailable")

    return postgis_version
