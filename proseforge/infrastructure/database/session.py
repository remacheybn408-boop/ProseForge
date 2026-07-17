from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from proseforge.infrastructure.database.sqlite import create_sqlite_engine
from proseforge.runtime.profile import RuntimeProfile, capabilities_for


def create_engine_and_sessionmaker(settings) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    profile = RuntimeProfile(settings.runtime_profile)
    if capabilities_for(profile).database == "sqlite":
        engine = _create_native_engine(settings)
    else:
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return engine, session_factory


def _create_native_engine(settings) -> AsyncEngine:
    database = make_url(settings.database_url).database
    if not database or database == ":memory:":
        raise ValueError(
            "native runtime profile requires a file-backed SQLite database_url"
        )
    return create_sqlite_engine(Path(database))
