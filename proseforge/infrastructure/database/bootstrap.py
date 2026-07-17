"""Safe startup schema repair for interrupted or incorrectly marked installs."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from proseforge.infrastructure.database.base import Base
from proseforge.infrastructure.database import models  # noqa: F401  # register metadata
from proseforge.infrastructure.database.sqlite import sqlite_sync_url
from proseforge.runtime.profile import RuntimeProfile, capabilities_for
from proseforge.settings import Settings


def ensure_schema(settings: Settings | None = None) -> list[str]:
    resolved = settings or Settings()
    profile = RuntimeProfile(resolved.runtime_profile)
    if capabilities_for(profile).database == "sqlite":
        return _ensure_schema_native(resolved)
    return _ensure_schema_server(resolved)


def _ensure_schema_server(resolved: Settings) -> list[str]:
    url = resolved.sync_database_url or resolved.database_url.replace("+asyncpg", "")
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            before = set(inspect(connection).get_table_names())
            Base.metadata.create_all(connection, checkfirst=True)
            after = set(inspect(connection).get_table_names())
            if "alembic_version" not in after:
                connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
                connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0005_outline_context')"))
                after.add("alembic_version")
            return sorted(after - before)
    finally:
        engine.dispose()


def _ensure_schema_native(resolved: Settings) -> list[str]:
    """native 首启：对 SQLite 文件执行 alembic upgrade head。

    schema 的唯一来源是 alembic 迁移链，没有第二条绕过 alembic 的裸
    create_all 路径。返回本次新建的用户表名（语义与 server 分支一致）。
    """
    from alembic import command
    from alembic.config import Config

    database = make_url(resolved.database_url).database
    if not database or database == ":memory:":
        raise ValueError(
            "native runtime profile requires a file-backed SQLite database_url"
        )
    db_path = Path(database)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    url = sqlite_sync_url(resolved.database_url)
    before = _sqlite_table_names(url)

    config = Config()
    config.set_main_option(
        "script_location",
        str(Path(__file__).resolve().parent / "migrations"),
    )
    config.set_main_option("sqlalchemy.url", resolved.database_url)
    command.upgrade(config, "head")

    after = _sqlite_table_names(url)
    return sorted(after - before - {"alembic_version"})


def _sqlite_table_names(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return set(inspect(connection).get_table_names())
    finally:
        engine.dispose()


if __name__ == "__main__":
    created = ensure_schema()
    if created:
        print(f"created missing schema tables: {', '.join(created)}", flush=True)
