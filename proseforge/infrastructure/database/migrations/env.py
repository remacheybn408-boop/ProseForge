from __future__ import annotations

import sys
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from proseforge.infrastructure.database.base import Base
from proseforge.infrastructure.database import models  # noqa: F401

config = context.config
target_metadata = Base.metadata


def _sync_driver_url(url: str) -> str:
    """Alembic 用同步驱动执行迁移；aiosqlite 异步 URL 降级为 pysqlite。"""
    return url.replace("+aiosqlite", "")


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_driver_url(config.get_main_option("sqlalchemy.url")),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    url = section.get("sqlalchemy.url")
    if url:
        section["sqlalchemy.url"] = _sync_driver_url(url)
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
