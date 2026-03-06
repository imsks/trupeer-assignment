from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from gateway.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory = None


def _init_engine():
    global _engine, _session_factory
    settings = get_settings()
    _engine = create_async_engine(settings.database_url, pool_size=10, max_overflow=20)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        _init_engine()
    async with _session_factory() as session:
        yield session


async def init_db() -> None:
    """Create tables (used in dev; production uses Alembic migrations)."""
    if _engine is None:
        _init_engine()
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
