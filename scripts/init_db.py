#!/usr/bin/env python3
"""
init_db.py — 数据库初始化脚本

用法:
  python scripts/init_db.py --config config.json
  python scripts/init_db.py --db-path ./data/novel_memory.db
"""

import sqlite3, sys, argparse, json, os
from pathlib import Path
try:
    from config_utils import normalize_config
except Exception:
    def normalize_config(cfg): return cfg


def load_config(config_path=None):
    cfg = {
        "db_path": "./data/novel_memory.db",
    }
    if config_path and Path(config_path).exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            user_cfg = json.load(f)
        cfg.update(normalize_config(user_cfg))
    return normalize_config(cfg)


def find_schema(script_dir):
    """Find schema.sql relative to the project root"""
    candidates = [
        script_dir.parent / "database" / "schema.sql",
        script_dir.parent.parent / "database" / "schema.sql",
        Path("database/schema.sql"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def find_migrations(script_dir):
    """Find migration SQL files"""
    candidates = [
        script_dir.parent / "database" / "migrations",
        script_dir.parent.parent / "database" / "migrations",
        Path("database/migrations"),
    ]
    for p in candidates:
        if p.exists():
            migrations = sorted(p.glob("*.sql"))
            return [(m.name, m) for m in migrations]
    return []


def run_migrations(conn, migrations):
    """Run pending migrations in order, tracking in schema_migrations."""
    cur = conn.cursor()
    # Ensure schema_migrations table exists (may have been created by migration itself)
    cur.execute("CREATE TABLE IF NOT EXISTS schema_migrations (id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT UNIQUE NOT NULL, applied_at TEXT DEFAULT (datetime('now')))")
    conn.commit()

    # Get already-applied migrations
    cur.execute("SELECT filename FROM schema_migrations")
    applied = {r[0] for r in cur.fetchall()}

    for filename, filepath in migrations:
        if filename in applied:
            continue
        print(f"  [MIG] {filename}...")
        with open(filepath, 'r', encoding='utf-8') as f:
            sql = f.read()
        try:
            conn.executescript(sql)
            cur.execute("INSERT INTO schema_migrations(filename) VALUES(?)", (filename,))
            conn.commit()
            print(f"  [OK]  {filename}")
        except Exception as e:
            print(f"  [FAIL] {filename}: {e}")
            conn.rollback()
            return False
    return True


def init_db(db_path, schema_path, migrations=None):
    if migrations is None:
        migrations = []
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        conn.executescript(schema_sql)
        conn.commit()

        # Run migrations
        if migrations:
            run_migrations(conn, migrations)

        # Verify
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts_%' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_fts' ORDER BY name")
        fts_tables = [r[0] for r in cur.fetchall()]
        conn.close()

        print(f"\n[OK] 数据库初始化完成: {db_path}")
        print(f"  普通表 ({len(tables)}): {', '.join(tables)}")
        if fts_tables:
            print(f"  FTS5索引 ({len(fts_tables)}): {', '.join(fts_tables)}")
        return True

    except Exception as e:
        conn.close()
        print(f"[FAIL] 数据库初始化失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Novel Forge — 数据库初始化")
    parser.add_argument("--config", default=None, help="配置文件路径 (默认: config.json)")
    parser.add_argument("--db-path", default=None, help="数据库路径 (覆盖配置文件)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.db_path:
        cfg["db_path"] = args.db_path

    db_path = cfg["db_path"]
    script_dir = Path(__file__).resolve().parent
    schema_path = find_schema(script_dir)
    migrations = find_migrations(script_dir)

    if not schema_path:
        print(f"[FAIL] 找不到 database/schema.sql")
        print(f"  当前脚本目录: {script_dir}")
        sys.exit(1)

    print(f"数据库: {db_path}")
    print(f"Schema: {schema_path}")
    if migrations:
        print(f"Migrations: {len(migrations)} 个")
    print(f"初始化中...")

    success = init_db(db_path, schema_path, migrations)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
