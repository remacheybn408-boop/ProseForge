#!/usr/bin/env python3
"""backup_db.py — 一键备份 SQLite 数据库

用法:
  python scripts/backup_db.py --config config.json
  python scripts/backup_db.py --db-path ./data/novel_memory.db
  python scripts/backup_db.py --db-path ./data/novel_memory.db --output ./backups/
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


def backup_db(db_path, output_dir=None):
    db_path = Path(db_path)
    if not db_path.exists():
        print(f"[FAIL] 数据库不存在: {db_path}")
        return None

    # 输出目录
    if output_dir:
        out = Path(output_dir)
    else:
        out = db_path.parent.parent / "backups"
    out.mkdir(parents=True, exist_ok=True)

    # 备份文件名
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    size_mb = db_path.stat().st_size / (1024 * 1024)
    backup_name = f"novel_memory_{ts}.db"
    backup_path = out / backup_name

    # SQLite online backup (safe while DB is in use)
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(backup_path))
    src.backup(dst)
    src.close()
    dst.close()

    print(f"[OK] 备份完成")
    print(f"  源:  {db_path} ({size_mb:.1f} MB)")
    print(f"  目标: {backup_path}")

    # 列出已有备份
    backups = sorted(out.glob("novel_memory_*.db"), reverse=True)
    if len(backups) > 1:
        print(f"  已有备份: {len(backups)} 个")
        for b in backups[:5]:
            age = datetime.now() - datetime.fromtimestamp(b.stat().st_mtime)
            print(f"    {b.name}  ({age.days}d ago, {b.stat().st_size/(1024*1024):.1f} MB)")

    return str(backup_path)


def main():
    parser = argparse.ArgumentParser(description="Novel Pipeline — 数据库备份")
    parser.add_argument("--config", default=None, help="配置文件路径")
    parser.add_argument("--db-path", default=None, help="数据库路径 (覆盖配置)")
    parser.add_argument("--output", default=None, help="备份输出目录")
    args = parser.parse_args()

    cfg = load_config(args.config)
    db_path = args.db_path or cfg["db_path"]

    result = backup_db(db_path, args.output)
    if not result:
        exit(1)


if __name__ == "__main__":
    main()
