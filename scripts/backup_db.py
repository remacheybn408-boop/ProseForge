#!/usr/bin/env python3
"""backup_db.py — 极简备份（数据库 + config.json）

用法:
  python scripts/backup_db.py
  python scripts/backup_db.py --config config.json
  python scripts/backup_db.py --db-path ./data/novel_memory.db

输出: backups/YYYYMMDD_HHMMSS/novel_memory.db + config.json
"""

import sqlite3, shutil, argparse, json
from pathlib import Path
from datetime import datetime


def load_config(config_path=None):
    cfg = {"db_path": "./data/novel_memory.db"}
    if config_path and Path(config_path).exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg.update(json.load(f))
    return cfg


def backup_all(db_path, config_path=None):
    db_path = Path(db_path)

    # ── 创建时间戳目录 ──
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path("backups") / ts
    out.mkdir(parents=True, exist_ok=True)

    # ── 备份数据库 ──
    if db_path.exists():
        src = sqlite3.connect(str(db_path))
        dst = sqlite3.connect(str(out / "novel_memory.db"))
        src.backup(dst)
        src.close()
        dst.close()
        size_mb = db_path.stat().st_size / (1024 * 1024)
        print(f"  [OK] novel_memory.db ({size_mb:.1f} MB)")
    else:
        print(f"  [WARN] 数据库不存在: {db_path}")

    # ── 备份 config.json ──
    cfg_file = Path(config_path) if config_path else Path("config.json")
    if cfg_file.exists():
        shutil.copy2(str(cfg_file), str(out / "config.json"))
        print(f"  [OK] config.json")
    else:
        print(f"  [WARN] config.json 不存在")

    print(f"\n[OK] 备份完成 → {out}/")
    return str(out)


def main():
    parser = argparse.ArgumentParser(description="Novel Pipeline — 极简备份")
    parser.add_argument("--config", default=None, help="配置文件路径")
    parser.add_argument("--db-path", default=None, help="数据库路径 (覆盖配置)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    db_path = args.db_path or cfg["db_path"]
    config_path = args.config or "config.json"

    result = backup_all(db_path, config_path)
    if not result:
        exit(1)


if __name__ == "__main__":
    main()
