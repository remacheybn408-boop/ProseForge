"""Safe startup schema repair for interrupted or incorrectly marked installs."""

from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from proseforge.infrastructure.database.base import Base
from proseforge.infrastructure.database import models  # noqa: F401  # register metadata
from proseforge.settings import Settings


def ensure_schema(settings: Settings | None = None) -> list[str]:
    resolved = settings or Settings()
    url = resolved.sync_database_url or resolved.database_url.replace("+asyncpg", "")
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
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


if __name__ == "__main__":
    created = ensure_schema()
    if created:
        print(f"created missing schema tables: {', '.join(created)}", flush=True)
