"""The connection to PostgreSQL.

One async engine, one session factory. Nothing in `tribunal/` imports this
module -- the trial logic knows nothing about a database.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings
from .models import Base

_settings = get_settings()

engine = create_async_engine(_settings.database_url, future=True)

SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request."""
    async with SessionFactory() as session:
        yield session


async def create_tables() -> None:
    """Create the four tables if they are not there yet.

    Enough for a project that runs on one machine. A schema that has already
    been used by a run is not migrated in place -- a stored run is evidence,
    and evidence is not edited.
    """
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
