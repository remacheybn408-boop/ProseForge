import sqlite3

from src.db.init_db import schema_version


def test_schema_version_reports_applied_migrations():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE schema_migrations (filename TEXT, applied_at TEXT)")
    conn.execute("INSERT INTO schema_migrations VALUES ('0001_initial.sql', 'now')")

    result = schema_version(conn)

    assert result == {
        "count": 1,
        "latest": "0001_initial.sql",
        "applied": ["0001_initial.sql"],
    }
    conn.close()
