#!/usr/bin/env python3
"""src/cli/shared.py — Shared helpers (constants, paths, config loading) for novel-pipeline-write-engine v0.6.5"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

from scripts.config_utils import normalize_config, load_json_config, resolve_path

def _load_project_config() -> dict:
    """Load config.json/config.example.json using the shared compatibility layer.

    Auto-resolves db_path to the active slot's novel.db when the slot system
    is active, so all callers get the per-slot database without manual wiring.
    """
    cfg_path = PROJECT_ROOT / "config.json"
    if cfg_path.exists():
        cfg = load_json_config(cfg_path, PROJECT_ROOT)
    else:
        cfg = load_json_config(PROJECT_ROOT / "config.example.json", PROJECT_ROOT)

    # Resolve db_path → active slot novel.db when slot system is in use
    _resolve_db_to_active_slot(cfg)
    return cfg


def _resolve_db_to_active_slot(cfg: dict) -> None:
    """Mutate cfg['db_path'] to point at the active slot's novel.db if one exists."""
    try:
        import json as _j
        ws = PROJECT_ROOT / "workspace"
        reg_file = ws / "registry.json"
        if not reg_file.exists():
            return
        reg = _j.loads(reg_file.read_text(encoding="utf-8"))
        active = reg.get("active_slot", "")
        if not active:
            return
        slot_db = ws / active / "novel.db"
        if slot_db.exists():
            cfg["db_path"] = str(slot_db)
    except Exception:
        pass


def _get_novel_id(cur):
    """Get novel_id from active slot's novels table. Returns None if not found."""
    slug = _get_default_slug()
    cur.execute("SELECT id FROM novels WHERE slug=?", (slug,))
    row = cur.fetchone()
    return row[0] if row else None


def _find_by_title(cur, table: str, nid: int, title: str):
    """Find row by exact title match, fallback to LIKE. Returns sqlite3.Row or None."""
    cur.execute(f"SELECT * FROM {table} WHERE novel_id=? AND title=?", (nid, title))
    row = cur.fetchone()
    if row:
        return row
    cur.execute(f"SELECT * FROM {table} WHERE novel_id=? AND title LIKE ?", (nid, f"%{title}%"))
    return cur.fetchone()

def _get_default_slug(cfg_path=None):
    """Resolve novel slug: active slot DB → config fallback."""
    ws = PROJECT_ROOT / "workspace"
    reg_file = ws / "registry.json"
    if reg_file.exists():
        try:
            import json as _j
            reg = _j.loads(reg_file.read_text(encoding="utf-8"))
            active = reg.get("active_slot", "")
            if active:
                slot_db = ws / active / "novel.db"
                if slot_db.exists():
                    import sqlite3 as _s
                    conn = _s.connect(str(slot_db))
                    row = conn.execute("SELECT slug FROM novels ORDER BY id DESC LIMIT 1").fetchone()
                    conn.close()
                    if row and row[0]:
                        return row[0]
        except Exception:
            pass
    return _load_project_config().get("default_novel_slug", "demo_novel")


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


def _resolve_chapter_path(slug: str, volume_no: int = 1) -> str:
    """Resolve chapters directory for slug + volume. 优先 slot，fallback novels dir."""
    ws = PROJECT_ROOT / "workspace"
    reg_file = ws / "registry.json"
    if reg_file.exists():
        try:
            import json as _j
            reg = _j.loads(reg_file.read_text(encoding="utf-8"))
            active = reg.get("active_slot", "")
            if active:
                base = ws / active / "chapters"
                if volume_no <= 1:
                    return str(base)
                return str(base / f"第{volume_no:02d}卷")
        except Exception:
            pass
    nr = Path(_get_novels_root())
    return str(nr / slug / f"第{volume_no:02d}卷")


def _resolve_post_context(cfg, volume_no: int = 1):
    """v0.6.5-clean7: Resolve chapters_dir + db_path + slug + title from active slot.
    v0.8.0: volume_no 参数控制卷路径，volume=1 保持平铺 chapters/ 不变。
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
                if volume_no > 1:
                    ch_dir = slot_dir / "chapters" / f"第{volume_no:02d}卷"
                else:
                    ch_dir = slot_dir / "chapters"
                db_path = slot_dir / "novel.db"
                if db_path.exists():
                    import sqlite3 as _sql
                    conn = _sql.connect(str(db_path))
                    try:
                        # v0.8.0: prefer the novel with the most chapters, fallback to LIMIT 1
                        row = conn.execute(
                            "SELECT n.slug, n.title FROM novels n "
                            "LEFT JOIN (SELECT novel_id, COUNT(*) as cnt FROM chapters GROUP BY novel_id) c "
                            "ON c.novel_id = n.id "
                            "ORDER BY COALESCE(c.cnt,0) DESC, n.id DESC LIMIT 1"
                        ).fetchone()
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
    return str(Path(_get_novels_root()) / slug / f"第{volume_no:02d}卷"), None, slug, slug


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
#  Chapter file finder (supports Arabic + Chinese numerals)
# ──────────────────────────────────────────────

_CN_DIGITS = "零一二三四五六七八九"


def _arabic_to_chinese_numeral(n: int) -> str:
    """Convert int to Chinese numeral string (1→一, 12→十二, 100→一百)."""
    if not 1 <= n <= 9999:
        return str(n)
    if n <= 10:
        return _CN_DIGITS[n] if n < 10 else "十"
    if n < 20:
        return "十" + (_CN_DIGITS[n - 10] if n > 10 else "")
    if n < 100:
        tens = _CN_DIGITS[n // 10]
        ones = _CN_DIGITS[n % 10] if n % 10 else ""
        return f"{tens}十{ones}"
    if n < 1000:
        hundreds = _CN_DIGITS[n // 100]
        rest = n % 100
        if rest == 0:
            return f"{hundreds}百"
        if rest < 10:
            return f"{hundreds}百零{_CN_DIGITS[rest]}"
        rest_str = _arabic_to_chinese_numeral(rest)
        if 10 <= rest < 20:
            rest_str = "一" + rest_str
        return f"{hundreds}百{rest_str}"
    thousands = _CN_DIGITS[n // 1000]
    rest = n % 1000
    if rest == 0:
        return f"{thousands}千"
    if rest < 100:
        rest_str = _arabic_to_chinese_numeral(rest)
        if 10 <= rest < 20:
            rest_str = "一" + rest_str
        return f"{thousands}千零{rest_str}"
    return f"{thousands}千{_arabic_to_chinese_numeral(rest)}"


def find_chapter_file(chapter_no: int, directory: Path) -> Path | None:
    """Find chapter TXT by chapter number, supporting Arabic and Chinese numerals."""
    patterns = [
        f"第{chapter_no}章*.txt",
        f"第{chapter_no:02d}章*.txt",
        f"第{_arabic_to_chinese_numeral(chapter_no)}章*.txt",
    ]
    for pat in patterns:
        candidates = list(directory.glob(pat))
        if candidates:
            return candidates[0]
    return None
