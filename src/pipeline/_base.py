"""Shared infrastructure for ProseForge pipeline."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from version import get_version

from src.runtime import PipelineContext, build_pipeline_context, resolve_slot_db_path
from src.utils.config_utils import find_project_root, load_default_config, load_json_config, resolve_path
from src.db._conn import connect_sqlite

try:
    from src.story import story_health
    from src.story.contract_builder import load_characters
except Exception:
    story_health = None
    load_characters = None


_PROJECT_ROOT = find_project_root(Path(__file__).resolve())
DEFAULT_CONFIG = load_default_config(_PROJECT_ROOT)

_CN_DIGITS = "零一二三四五六七八九"

# Legacy read-only shim. New code should pass the context/app explicitly.
app = None


def load_config(config_path: str | Path | None = None, project_root: str | Path | None = None) -> dict:
    """Load config from the unified loader."""
    return load_json_config(config_path, project_root or _PROJECT_ROOT)


def _resolve_slot_db_path(cfg: dict, project_root: str | Path | None = None) -> str:
    """Resolve active slot DB or fall back to configured db_path."""
    return str(resolve_slot_db_path(cfg, project_root or _PROJECT_ROOT))


class App(PipelineContext):
    """Backward-compatible wrapper around the unified pipeline context."""

    def __init__(
        self,
        cfg: dict,
        novel_slug: str,
        novel_title: str,
        volume_no: int,
        chapters_dir: str | Path | None = None,
        project_root: str | Path | None = None,
        config_path: str | Path | None = None,
    ):
        ctx = build_pipeline_context(
            novel_slug=novel_slug,
            novel_title=novel_title,
            volume_no=volume_no,
            chapters_dir=chapters_dir,
            db_path=cfg.get("db_path"),
            project_root=project_root or _PROJECT_ROOT,
            config_path=config_path,
        )
        for key, value in ctx.__dict__.items():
            setattr(self, key, value)
        # App historically accepted an already-loaded config object.  The
        # unified context loader must not silently discard its path overrides
        # and fall back to the repository's config.example.json; doing so
        # sends temporary/native pipeline artifacts to the process cwd.  Keep
        # the context defaults, then apply explicit values supplied by the
        # caller (absolute paths remain absolute).
        self.cfg = {**self.cfg, **cfg}
        for config_key, attr in (
            ("db_path", "db_path"),
            ("novels_root", "novels_root"),
            ("exports_root", "exports_root"),
            ("reports_root", "reports_root"),
            ("outputs_root", "outputs_root"),
            ("tmp_root", "tmp_root"),
        ):
            if config_key in cfg:
                setattr(self, attr, resolve_path(self.project_root, cfg[config_key]))
        if "tmp_root" not in cfg and "exports_root" in cfg:
            # Custom pipeline configs commonly override the export root only.
            # Keep transactional ingest snapshots beside that workspace,
            # rather than writing into the repository's default tmp directory.
            self.tmp_root = Path(self.exports_root).parent / "tmp"
        self.state_dir = self.exports_root / "pipeline_state"


def _require_context(app_inst: App | PipelineContext | None = None) -> App | PipelineContext:
    ctx = app_inst or app
    if ctx is None:
        raise RuntimeError("Pipeline context is required; pass app_inst/context explicitly.")
    return ctx


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect(app_inst: App | PipelineContext | None = None) -> sqlite3.Connection:
    ctx = _require_context(app_inst)
    conn = connect_sqlite(ctx.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _get_novel_id(cur: sqlite3.Cursor, app_inst: App | PipelineContext | None = None):
    ctx = _require_context(app_inst)
    cur.execute("SELECT id FROM novels WHERE slug=?", (ctx.novel_slug,))
    row = cur.fetchone()
    return row[0] if row else None


def _strip_selfcheck(text: str) -> str:
    idx = text.find("本章自检")
    return text[:idx] if idx > 0 else text


def _chunk_text(text: str, min_size: int = 800, max_size: int = 1500):
    if not text:
        return []
    chunks, current, chunk_no = [], "", 0
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            if current:
                current += "\n"
            continue
        if len(current) + len(para) > max_size and len(current) >= min_size:
            chunk_no += 1
            chunks.append((chunk_no, current.strip()))
            current = para
        else:
            current += ("\n" + para if current else para)
    if current.strip():
        chunk_no += 1
        chunks.append((chunk_no, current.strip()))
    return chunks


def _count_chinese(text: str) -> int:
    from src.utils.text_metrics import count_chinese
    return count_chinese(text)


def ensure_tables(app_inst: App | PipelineContext | None = None):
    """流水线入口自愈：把活跃槽 novel.db 补齐到当前完整 schema。

    所有入口（pre/post/volume/ingest）都先调它。schema.sql 在场时走全 schema 幂等补齐
    （快路径：表齐则零成本；遗留库缺表才补一次）；schema.sql 缺失时退回内联建最小集兜底。
    """
    ctx = _require_context(app_inst)

    from src.db.init_db import ensure_db_schema, find_schema

    if find_schema(ctx.project_root) is not None:
        ensure_db_schema(ctx.db_path, ctx.project_root)
        return

    # 兜底：没有权威 schema.sql 时，至少建起这两张流水线必需的表。
    conn = connect_sqlite(ctx.db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS chapter_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id INTEGER NOT NULL,
            chapter_id INTEGER,
            chapter_no INTEGER NOT NULL,
            version_no INTEGER NOT NULL DEFAULT 1,
            version_status TEXT DEFAULT 'draft',
            title TEXT DEFAULT '',
            content TEXT NOT NULL,
            word_count INTEGER DEFAULT 0,
            change_reason TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reader_promises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id INTEGER NOT NULL,
            promise_title TEXT NOT NULL,
            promise_detail TEXT NOT NULL,
            introduced_chapter INTEGER,
            expected_payoff_range TEXT DEFAULT '',
            payoff_chapter INTEGER,
            status TEXT DEFAULT 'open',
            importance INTEGER DEFAULT 3,
            reader_emotion TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def _arabic_to_chinese_numeral(n: int) -> str:
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


def _find_chapter_file(chapter_no: int, directory: Path) -> Path | None:
    patterns = [
        f"第{chapter_no}章*.txt",
        f"第{chapter_no:02d}章*.txt",
        f"第{_arabic_to_chinese_numeral(chapter_no)}章*.txt",
    ]
    for pattern in patterns:
        candidates = sorted(directory.glob(pattern))
        if candidates:
            return candidates[0]  # sorted → 多文件命中时顺序确定，不依赖文件系统
    return None


def find_chapter_file_with_fallback(chapter_no: int, app_inst: App | PipelineContext) -> Path | None:
    candidate = _find_chapter_file(chapter_no, app_inst.chapters_dir)
    if candidate:
        return candidate
    if getattr(app_inst, "active_slot", None):
        slot_dir = app_inst.workspace_root / app_inst.active_slot
        for volume_dir in sorted((slot_dir / "chapters").glob("*")):
            candidate = _find_chapter_file(chapter_no, volume_dir)
            if candidate:
                print(f"  [OK] found chapter {chapter_no} under {volume_dir.name}")
                return candidate
        flat_dir = slot_dir / "chapters"
        candidate = _find_chapter_file(chapter_no, flat_dir)
        if candidate:
            return candidate
    return None


# write_json_atomic 已下沉到 src.utils.json_io（避免 db→pipeline 反向依赖）；
# 这里再导出，保持 `from src.pipeline._base import write_json_atomic` 的旧引用可用。
from src.utils.json_io import write_json_atomic  # noqa: E402,F401
