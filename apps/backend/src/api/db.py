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
    """Base metadata for future domain models."""


def create_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


engine = create_engine()
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


async def check_database() -> str:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
        postgis_version = await connection.scalar(text("SELECT PostGIS_Version()"))

    if not isinstance(postgis_version, str) or not postgis_version:
        raise RuntimeError("PostGIS extension is unavailable")

    return postgis_version

