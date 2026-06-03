#!/usr/bin/env python3
"""src/cli/shared.py — Shared helpers (constants, paths, config loading) for novel-pipeline-write-engine v0.6.5"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
SRC_GUARDS_DIR = PROJECT_ROOT / "src" / "guards"

# Ensure scripts dir is importable
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(SRC_GUARDS_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_GUARDS_DIR))

from config_utils import normalize_config, load_json_config, resolve_path

def _load_project_config() -> dict:
    """Load config.json/config.example.json using the shared compatibility layer."""
    cfg_path = PROJECT_ROOT / "config.json"
    if cfg_path.exists():
        return load_json_config(cfg_path, PROJECT_ROOT)
    return load_json_config(PROJECT_ROOT / "config.example.json", PROJECT_ROOT)


def _cfg_path(key: str, default: str) -> Path:
    cfg = _load_project_config()

def _get_default_slug(cfg_path=None):
    """Resolve default novel slug from config.json."""
    try:
        return _load_project_config().get("default_novel_slug", "demo_novel")
    except Exception:
        return "demo_novel"


def _get_novels_root(cfg_path=None):
    """Read novels_root from config."""
    try:
        cfg = _load_project_config()
        return str(resolve_path(PROJECT_ROOT, cfg.get("novels_root", "./novels")))
    except Exception:
        return str(PROJECT_ROOT / "novels")


def _get_outline_dir():
    """v0.6.5-clean7: 大纲目录 = novels_root 的同级 大纲/."""
    nr = Path(_get_novels_root())
    return str(nr.parent / "大纲")


def _resolve_post_context(cfg):
    """v0.6.5-clean7: Resolve chapters_dir + db_path + slug + title from active slot.
    Returns (chapters_dir, db_path, slug, title). Falls back to config defaults.
    """
    import json as _json
    ws = PROJECT_ROOT / "workspace"
    reg_file = ws / "registry.json"

    if reg_file.exists():
        try:
            reg = _json.loads(reg_file.read_text(encoding="utf-8"))
            active = reg.get("active_slot", "")
            if active:
                slot_dir = ws / active
                ch_dir = slot_dir / "chapters"
                db_path = slot_dir / "novel.db"
                if db_path.exists():
                    import sqlite3 as _sql
                    conn = _sql.connect(str(db_path))
                    try:
                        row = conn.execute("SELECT slug, title FROM novels LIMIT 1").fetchone()
                        slug = row[0] if row else _get_default_slug(cfg)
                        title = row[1] if row and row[1] else slug
                    except Exception:
                        slug = _get_default_slug(cfg)
                        title = slug
                    finally:
                        conn.close()
                    return str(ch_dir), str(db_path), slug, title
        except Exception:
            pass

    # Fallback: old config-based paths
    slug = _get_default_slug(cfg)
    novels_root = _get_novels_root(cfg)
    return str(Path(novels_root) / slug / "第01卷"), None, slug, slug


def _story_exists() -> bool:
    """Check if .story/ has valid story data."""
    sd = _get_story_dir()
    return (sd / "master_setting.json").exists() if sd else False


def _story_missing_msg() -> str:
    return ".story/ 未初始化 — 请运行: python novel.py story init"


def _get_story_dir() -> Path | None:
    """Get the active slot's .story/ directory."""
    try:
        ws_dir = PROJECT_ROOT / "workspace"
        reg_file = ws_dir / "registry.json"
        if not reg_file.exists():
            return PROJECT_ROOT / ".story"
        import json
        reg = json.loads(reg_file.read_text(encoding="utf-8"))
        active = reg.get("active_slot", "")
        if not active:
            return PROJECT_ROOT / ".story"
        sd = ws_dir / active / ".story"
        sd.mkdir(parents=True, exist_ok=True)
        return sd
    except Exception:
        return PROJECT_ROOT / ".story"


def _get_workspace_dir() -> Path:
    """Get workspace directory path."""
    return PROJECT_ROOT / "workspace"


def _get_active_db_path() -> Path:
    """Get the novel.db path for the currently active slot.

    Priority:
    1. workspace/registry.json → active_slot → workspace/<slot>/novel.db
    2. Fallback: config.json db_path (legacy global DB)
    """
    import json as _json
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if registry_file.exists():
        try:
            registry = _json.loads(registry_file.read_text(encoding="utf-8"))
            active = registry.get("active_slot", "")
            if active:
                slot_db = ws_dir / active / "novel.db"
                if slot_db.exists():
                    return slot_db
        except Exception:
            pass

    # Fallback: legacy config.json db_path
    try:
        cfg_data = _load_project_config()
        db = cfg_data.get("db_path", "./data/novel_memory.db")
        p = Path(db)
        if not p.is_absolute():
            p = PROJECT_ROOT / db
        return p
    except Exception:
        return PROJECT_ROOT / "data" / "novel_memory.db"


def _get_outline_manager():
    """Helper: get OutlineManager instance."""
    from scripts.outline.outline_manager import OutlineManager
    return OutlineManager(PROJECT_ROOT)


def _check_outline_gate() -> int:
    """No-outline gate: refuse if active slot has no outline.
    Returns 0 if OK, 1 if blocked.
    """
    try:
        mgr = _get_outline_manager()
        if not mgr.has_active_outline():
            # v0.6.5-clean7: 引导用户放大纲在小说文件夹下
            outline_dir = Path(_get_outline_dir())
            print("=" * 60)
            print("  ⛔ 没有激活的大纲")
            print("=" * 60)
            print()
            print("  当前小说没有激活大纲，不能开写。")
            print()
            print(f"  💡 把大纲.txt放到：{outline_dir}/你的小说名/大纲.txt")
            print()
            print(f"  然后运行 python novel.py outline add")
            return 1
    except Exception as e:
        # If outline module not available, allow pass-through
        pass
    return 0


# ──────────────────────────────────────────────
#  Outline CLI commands
# ──────────────────────────────────────────────
