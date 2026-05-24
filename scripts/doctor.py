#!/usr/bin/env python3
"""
doctor.py — 环境诊断工具 v0.4.0

检查项目运行环境是否就绪：
- Python 版本
- 依赖
- config.json 是否存在
- 数据库是否存在 / schema 是否完整
- demo 文件是否存在
- pytest 是否可运行
"""
import sys, os, json, sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def check(desc, ok, detail=""):
    mark = "✅" if ok else "❌"
    print(f"  {mark} {desc}" + (f": {detail}" if detail and not ok else ""))
    return ok


def main():
    print("Novel Pipeline - Write Engine v0.4.0")
    print("环境诊断 (doctor.py)")
    print("=" * 50)

    all_ok = True

    # 1. Python 版本
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    ok = sys.version_info >= (3, 10)
    all_ok &= check("Python 版本", ok, py_ver)

    # 2. 依赖
    for mod, name in [("pytest", "pytest"), ("re", "re"), ("json", "json"),
                      ("sqlite3", "sqlite3"), ("argparse", "argparse")]:
        try:
            __import__(mod)
            check(f"依赖 {name}", True)
        except ImportError:
            all_ok &= check(f"依赖 {name}", False, "未安装")

    # 3. config.json
    config_path = PROJECT_ROOT / "config.json"
    if config_path.exists():
        check("config.json", True)
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            db_path = cfg.get("db_path", "")
            check("  db_path 配置", bool(db_path), db_path)
        except:
            all_ok &= check("config.json 可解析", False)
    else:
        all_ok &= check("config.json", False, "不存在，请复制 config.example.json")

    # 4. 数据库
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            db_path = Path(cfg.get("db_path", "./data/novel_memory.db"))
            if not db_path.is_absolute():
                db_path = PROJECT_ROOT / db_path
            if db_path.exists():
                check("数据库文件", True, str(db_path))
                conn = sqlite3.connect(str(db_path))
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in cur.fetchall()]
                check(f"  表数量", len(tables) >= 10, f"{len(tables)} 张表")
                conn.close()
            else:
                all_ok &= check("数据库文件", False, "不存在，运行 scripts/init_db.py")
        except Exception as e:
            all_ok &= check("数据库检查", False, str(e))

    # 5. demo 文件
    demo_skel = PROJECT_ROOT / "examples/demo_novel/outline_skeleton.json"
    all_ok &= check("Demo 骨架", demo_skel.exists(), str(demo_skel))

    # 6. 核心脚本
    for script in ["chapter_pipeline.py", "guard_orchestrator.py",
                   "revision_loop_controller.py"]:
        sp = PROJECT_ROOT / "scripts" / script
        all_ok &= check(f"scripts/{script}", sp.exists())

    # 7. pytest
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--version"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT))
        all_ok &= check("pytest 可运行", result.returncode == 0,
                        result.stdout.strip()[:50])
    except:
        all_ok &= check("pytest 可运行", False)

    print("=" * 50)
    if all_ok:
        print("✅ 环境就绪，可以开始写作。")
    else:
        print("⚠️ 存在上述问题，请修复后重试。")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
