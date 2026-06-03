#!/usr/bin/env python3
"""
doctor.py — 环境诊断工具 v0.6.5

检查项目运行环境是否就绪，支持 --detail 详细模式：
- OS 信息
- Python 版本
- SQLite 版本 + FTS5 支持
- 依赖
- config.json 路径与完整性
- 数据库状态（表数量、行数、FTS5）
- 项目目录可写性
- 无硬编码 Windows 路径
- 当前活跃 DB slot
- 当前活跃 outline
- pytest 可运行
"""
import sys, os, json, sqlite3, platform
from pathlib import Path
from datetime import datetime
from version import get_version

try:
    from config_utils import normalize_config, resolve_path
except Exception:
    def normalize_config(cfg): return cfg
    def resolve_path(root, value):
        p = Path(value)
        return p if p.is_absolute() else Path(root) / p

PROJECT_ROOT = Path(__file__).parent.parent

# ── output helpers ──────────────────────────────────────────

_status_ok = 0
_status_warn = 0
_status_fail = 0
_detail_mode = False


def _check(desc, ok, detail="", level="error"):
    """Print a check line and track counts."""
    global _status_ok, _status_warn, _status_fail
    if ok:
        _status_ok += 1
        mark = "  ✅"
    else:
        if level == "warning":
            _status_warn += 1
            mark = "  ⚠️ "
        else:
            _status_fail += 1
            mark = "  ❌"
    suffix = f": {detail}" if detail else ""
    print(f"{mark} {desc}{suffix}")
    return ok


def _detail_line(text):
    """Print an indented detail line (only in --detail mode)."""
    if _detail_mode:
        print(f"      {text}")


# ── section header ──────────────────────────────────────────

def _section(title):
    print(f"\n  ── {title} ──")


# ── checks ───────────────────────────────────────────────────

def check_os():
    _section("操作系统")
    system = platform.system()
    release = platform.release()
    version = platform.version()
    machine = platform.machine()
    node = platform.node()
    _check("操作系统类型", True, system)
    _detail_line(f"Release: {release}")
    _detail_line(f"Version: {version}")
    _detail_line(f"Machine: {machine}")
    _detail_line(f"Hostname: {node}")

    # Check if running on Windows
    is_windows = (system == "Windows")
    _check("平台兼容", not is_windows, "Windows 检测到，推荐使用 WSL/Linux" if is_windows else "Linux/macOS", level="warning" if is_windows else "info")


def check_python():
    _section("Python 环境")
    major, minor, micro = sys.version_info[:3]
    py_ver = f"{major}.{minor}.{micro}"
    ok = sys.version_info >= (3, 10)
    _check("Python 版本", ok, py_ver + (" (需要 ≥3.10)" if not ok else ""))
    _detail_line(f"Executable: {sys.executable}")
    _detail_line(f"Implementation: {platform.python_implementation()}")

    # Dependencies
    deps = {
        "pytest": ("pytest", "测试框架"),
        "sqlite3": ("sqlite3", "数据库"),
        "json": ("json", "JSON解析"),
        "argparse": ("argparse", "命令行解析"),
        "pathlib": ("pathlib", "路径处理"),
    }
    for mod, (import_name, desc) in deps.items():
        try:
            __import__(import_name)
            _check(f"依赖 {mod}", True, desc)
            _detail_line(f"  {import_name} 可用")
        except ImportError:
            _check(f"依赖 {mod}", False, f"{desc} 未安装", level="error")


def check_sqlite_fts5():
    _section("SQLite 与 FTS5")
    try:
        sqlite_version = sqlite3.sqlite_version
        sqlite_lib = sqlite3.version
        _check("SQLite 版本", True, f"v{sqlite_version} (lib {sqlite_lib})")

        # Check FTS5
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts_test USING fts5(content)")
            conn.execute("DROP TABLE IF EXISTS _fts_test")
            _check("FTS5 全文搜索", True, "已启用")
            _detail_line("  CREATE VIRTUAL TABLE ... USING fts5 可用")
        except sqlite3.OperationalError as e:
            _check("FTS5 全文搜索", False, f"不可用: {e}", level="error")
        finally:
            conn.close()
    except Exception as e:
        _check("SQLite 检查", False, str(e), level="error")


def check_config():
    _section("配置文件")
    config_path = PROJECT_ROOT / "config.json"
    example_path = PROJECT_ROOT / "config.example.json"

    if config_path.exists():
        _check("config.json 存在", True, str(config_path.relative_to(PROJECT_ROOT)))
        try:
            cfg = normalize_config(json.loads(config_path.read_text(encoding="utf-8")))
            _check("config.json 可解析", True)

            # Show key paths
            for key in ["db_path", "novels_root", "exports_root", "reports_root", "outputs_root", "tmp_root"]:
                val = cfg.get(key, "(未设置)")
                _detail_line(f"  {key}: {val}")

            # Check if paths are relative (good) vs absolute/hardcoded
            _check("路径使用相对路径", True, "推荐做法")
            for key in ["db_path", "novels_root", "exports_root"]:
                val = cfg.get(key, "")
                if val and ":" in str(val):
                    _detail_line(f"  注意: {key} 包含绝对路径: {val}")

            # Check for hardcoded Windows paths
            has_windows_path = False
            cfg_str = json.dumps(cfg)
            for pattern in ["C:\\\\", "D:\\\\", "C:/", "D:/", "C:Users", "\\\\"]:
                if pattern in cfg_str:
                    has_windows_path = True
                    _detail_line(f"  发现可能的硬编码路径模式: {pattern}")
            _check("无硬编码 Windows 路径", not has_windows_path,
                   "良好" if not has_windows_path else "存在硬编码路径，请使用相对路径")

            # Default slug
            slug = cfg.get("default_novel_slug", "(未设置)")
            _detail_line(f"  default_novel_slug: {slug}")

        except json.JSONDecodeError as e:
            _check("config.json 可解析", False, str(e))
        except Exception as e:
            _check("配置文件处理", False, str(e))
    else:
        _check("config.json 存在", False, "请复制 config.example.json")
        if example_path.exists():
            _check("config.example.json 可用", True)
        else:
            _check("config.example.json", False, "缺失")


def check_database():
    _section("数据库状态")
    config_path = PROJECT_ROOT / "config.json"
    if not config_path.exists():
        _check("数据库检查", False, "config.json 不存在，跳过")
        return

    try:
        cfg = normalize_config(json.loads(config_path.read_text(encoding="utf-8")))
        db_path_raw = cfg.get("db_path", "./data/novel_memory.db")
        db_path = resolve_path(PROJECT_ROOT, db_path_raw)

        _detail_line(f"配置路径: {db_path_raw}")
        _detail_line(f"解析路径: {db_path}")

        if db_path.exists():
            size_bytes = db_path.stat().st_size
            size_str = f"{size_bytes/1024:.1f}KB" if size_bytes < 1024 * 1024 else f"{size_bytes/(1024*1024):.1f}MB"
            try:
                rel_path = db_path.relative_to(PROJECT_ROOT)
            except ValueError:
                rel_path = str(db_path)
            _check("数据库文件", True, f"{size_str} — {rel_path}")

            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()

            # Table count
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [r[0] for r in cur.fetchall()]
            _check(f"数据库表", len(tables) >= 10, f"{len(tables)} 张表")
            _detail_line(f"  表: {', '.join(tables[:8])}" + ("..." if len(tables) > 8 else ""))

            # Row counts for key tables
            for tbl in ["chapters", "characters", "events", "novels", "volumes"]:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                    count = cur.fetchone()[0]
                    _detail_line(f"  {tbl}: {count} 行")
                except sqlite3.OperationalError:
                    _detail_line(f"  {tbl}: 表不存在")

            # FTS5 virtual tables
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND sql LIKE '%USING fts%'")
            fts_tables = [r[0] for r in cur.fetchall()]
            if fts_tables:
                _check("FTS5 虚拟表", True, f"{len(fts_tables)} 个: {', '.join(fts_tables)}")
            else:
                _check("FTS5 虚拟表", False, "无 — 全文搜索不可用", level="warning")

            conn.close()
        else:
            _check("数据库文件", False, f"不存在: {db_path}", level="warning")
            _detail_line("  运行 python novel.py init 创建数据库")

    except Exception as e:
        _check("数据库检查", False, str(e))


def check_project_writable():
    _section("项目目录权限")
    test_dirs = [
        PROJECT_ROOT / "data",
        PROJECT_ROOT / "exports",
        PROJECT_ROOT / "outputs",
        PROJECT_ROOT / "novels",
        PROJECT_ROOT / "workspace",
    ]
    for td in test_dirs:
        if td.exists():
            try:
                test_file = td / ".doctor_write_test"
                test_file.write_text("test")
                test_file.unlink()
                _check(f"目录可写", True, str(td.relative_to(PROJECT_ROOT)) if td.is_relative_to(PROJECT_ROOT) else str(td))
            except (PermissionError, OSError):
                _check(f"目录可写", False, str(td) + " — 无写入权限", level="error")
        else:
            parent = td.parent
            if parent.exists():
                try:
                    td.mkdir(parents=True, exist_ok=True)
                    test_file = td / ".doctor_write_test"
                    test_file.write_text("test")
                    test_file.unlink()
                    td.rmdir()
                    _check(f"目录可创建", True, str(td.relative_to(PROJECT_ROOT)))
                except (PermissionError, OSError):
                    _check(f"目录可创建", False, str(td), level="warning")


def check_workspace():
    """Check workspace/registry.json for active DB slot and outline."""
    _section("工作区状态")
    workspace_dir = PROJECT_ROOT / "workspace"
    registry_file = workspace_dir / "registry.json"

    if not registry_file.exists():
        _check("workspace/ 目录", False, "不存在 — 运行 python novel.py db init", level="warning")
        _check("活跃 DB slot", False, "workspace 未初始化", level="warning")
        _check("活跃 outline", False, "workspace 未初始化", level="warning")
        return

    try:
        registry = json.loads(registry_file.read_text(encoding="utf-8"))
        _check("workspace/registry.json", True)

        # Active slot
        active_slot = registry.get("active_slot", "")
        if active_slot:
            _check("活跃 DB slot", True, active_slot)
            slot_dir = workspace_dir / active_slot
            _detail_line(f"  路径: {slot_dir}")
            if slot_dir.exists():
                # Check project.json
                proj_file = slot_dir / "project.json"
                if proj_file.exists():
                    try:
                        proj = json.loads(proj_file.read_text(encoding="utf-8"))
                        outline = proj.get("active_outline", proj.get("outline", ""))
                        _detail_line(f"  项目: {proj.get('title', proj.get('name', '?'))}")
                        if outline:
                            _check("活跃 outline", True, str(outline)[:60])
                        else:
                            _check("活跃 outline", False, "未设定", level="warning")
                    except Exception:
                        _check("活跃 outline", False, "project.json 解析失败", level="warning")
                else:
                    _check("活跃 outline", False, "project.json 不存在", level="warning")
            else:
                _check("活跃 slot 目录", False, str(slot_dir), level="warning")
        else:
            _check("活跃 DB slot", False, "未设置 — python novel.py db use <slot>", level="warning")

        # List all slots
        slots = registry.get("slots", [])
        _detail_line(f"总 slot 数: {len(slots)}")
        for s in slots[:5]:
            sid = s.get("id", "?")
            sname = s.get("name", "")
            sstatus = s.get("status", "?")
            _detail_line(f"  {sid}: {sname} [{sstatus}]")

    except json.JSONDecodeError as e:
        _check("workspace/registry.json", False, f"解析错误: {e}", level="error")
    except Exception as e:
        _check("工作区检查", False, str(e))


def check_core_scripts():
    _section("核心脚本")
    scripts = [
        ("chapter_pipeline.py", "章节流水线"),
        ("guard_orchestrator.py", "守卫编排器"),
        ("revision_loop_controller.py", "修订循环"),
        ("doctor.py", "诊断工具"),
        ("cross_platform_check.py", "跨平台检查"),
    ]
    for script, desc in scripts:
        sp = PROJECT_ROOT / "scripts" / script
        exists = sp.exists()
        _check(f"scripts/{script}", exists, desc if exists else "缺失")
        if exists and _detail_mode:
            size = sp.stat().st_size
            _detail_line(f"  {size} bytes")


def check_jury_configs():
    _section("评审团配置")
    jury_dir = PROJECT_ROOT / "configs" / "jury"
    if not jury_dir.exists():
        _check("configs/jury/ 目录", False, "不存在 — 需要初始化", level="warning")
        return

    yaml_files = list(jury_dir.glob("*.yaml"))
    agent_files = list((jury_dir / "agents").glob("*.yaml")) if (jury_dir / "agents").exists() else []
    _check("评审模式配置", len(yaml_files) > 0, f"{len(yaml_files)} 个模式")
    for yf in yaml_files:
        _detail_line(f"  {yf.name}")
    _check("评审代理配置", len(agent_files) > 0, f"{len(agent_files)} 个代理")
    for af in agent_files:
        _detail_line(f"  {af.name}")


def check_pytest():
    _section("测试框架")
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--version"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT))
        ok = (result.returncode == 0)
        ver_line = result.stdout.strip().split('\n')[0] if result.stdout else ""
        _check("pytest 可运行", ok, ver_line[:60] if ok else "未安装")
    except Exception as e:
        _check("pytest 可运行", False, str(e))


# ── main entry ──────────────────────────────────────────────

def main(detail=False):
    global _detail_mode
    _detail_mode = detail

    print("=" * 58)
    print(f"  Novel Forge - 小说引擎 {get_version()}")
    mode_str = "详细模式 (--detail)" if detail else "标准模式"
    print(f"  环境诊断 {mode_str}")
    print(f"  项目根目录: {PROJECT_ROOT}")
    print("=" * 58)

    check_os()
    check_python()
    check_sqlite_fts5()
    check_config()
    check_database()
    check_project_writable()
    check_workspace()
    check_core_scripts()
    check_jury_configs()
    check_pytest()

    # ── summary ──
    print(f"\n{'=' * 58}")
    total = _status_ok + _status_warn + _status_fail
    print(f"  总计: {total} 项检查")
    print(f"  通过: {_status_ok}  ✅")
    if _status_warn:
        print(f"  警告: {_status_warn}  ⚠️")
    if _status_fail:
        print(f"  失败: {_status_fail}  ❌")

    if _status_fail == 0 and _status_warn == 0:
        print(f"\n  ✅ 环境就绪，可以开始写作。")
    elif _status_fail == 0:
        print(f"\n  ⚠️  存在 {_status_warn} 个警告，建议处理。")
    else:
        print(f"\n  ❌ 存在 {_status_fail} 个错误，请修复后重试。")

    return 0 if _status_fail == 0 else 1


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Novel Forge 环境诊断")
    p.add_argument("--detail", action="store_true", help="显示详细信息")
    args = p.parse_args()
    sys.exit(main(detail=args.detail))
