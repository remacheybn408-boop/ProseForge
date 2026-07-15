#!/usr/bin/env python3
"""
export_novel — 导出小说合集 v0.8.0

从 SQLite 读取指定小说的所有章节，按 chapter_no 排序，输出单个 .txt 或 .md 文件。

用法:
  使用 nf_导出 工具导出
  使用 nf_导出 slug=demo_novel format=txt
  使用 nf_导出 slug=demo_novel format=md

参数:
  --slug        小说 slug 标识 (默认: demo_novel)
  --config      config.json 路径 (默认: PROJECT_ROOT/config.json)
  --format      输出格式: txt 或 md (默认: md)
  --output      输出文件路径 (默认: exports/<slug>_full.<format>)
  --novel-title 手动指定小说标题（覆盖数据库中的标题）
  --from-ch     起始章节号 (默认: 1)
  --to-ch       结束章节号 (默认: 全部)
  --no-toc      不生成目录
  --separator   章节分隔符 (默认: 空行 + --- + 空行)
  --json        输出结果信息为 JSON
"""

import sys
import os
import json
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime
from src.utils.config_utils import DEFAULT_DB_PATH, normalize_config
from src.pipeline._base import _find_chapter_file
from src.db._conn import connect_sqlite

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_SLUG = "demo_novel"


class ExportDataError(RuntimeError):
    """Raised when export data cannot be read reliably."""


def load_config(config_path: str) -> dict:
    """Load config JSON, falling back to defaults."""
    cfg = {}
    p = Path(config_path)
    if p.exists():
        try:
            cfg = normalize_config(json.loads(p.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"[WARN] Cannot parse config: {e}", file=sys.stderr)
    return cfg


def get_db_path(config: dict) -> str:
    """P0-2: Get database path — prefer active slot novel.db, fallback to config."""
    # Try active slot novel.db first
    try:
        ws_dir = PROJECT_ROOT / "workspace"
        registry_file = ws_dir / "registry.json"
        if registry_file.exists():
            registry = json.loads(registry_file.read_text(encoding="utf-8"))
            active = registry.get("active_slot", "")
            if active:
                slot_db = ws_dir / active / "novel.db"
                if slot_db.exists():
                    return str(slot_db)
    except Exception:
        pass
    # Fallback to config.json db_path
    db = config.get("db_path", DEFAULT_DB_PATH)
    p = Path(db)
    if not p.is_absolute():
        p = PROJECT_ROOT / db
    return str(p)


def get_novel_info(conn: sqlite3.Connection, slug: str) -> dict | None:
    """Get novel id and title by slug."""
    try:
        cur = conn.execute(
            "SELECT id, title FROM novels WHERE slug = ?", (slug,)
        )
        row = cur.fetchone()
        if row:
            return {"id": row[0], "title": row[1]}
        return None
    except (sqlite3.Error, OSError) as exc:
        raise ExportDataError(f"novel lookup failed: {exc}") from exc


def get_chapters(
    conn: sqlite3.Connection,
    novel_id: int,
    from_ch: int = 1,
    to_ch: int | None = None,
    chapters_dir: str | Path | None = None,
) -> list[dict]:
    """Get chapters for a novel, ordered by chapter_no. Includes volume_no for cross-volume export.

    If content is empty in DB, tries to read from chapter files on disk
    (when chapters_dir is provided).
    """
    try:
        if to_ch is not None:
            cur = conn.execute(
                """SELECT c.chapter_no, c.title, c.content, c.word_count, c.status,
                          COALESCE(v.volume_no, 1) as volume_no
                   FROM chapters c
                   LEFT JOIN volumes v ON v.id = c.volume_id
                   WHERE c.novel_id = ? AND c.chapter_no >= ? AND c.chapter_no <= ?
                   ORDER BY c.chapter_no ASC""",
                (novel_id, from_ch, to_ch),
            )
        else:
            cur = conn.execute(
                """SELECT c.chapter_no, c.title, c.content, c.word_count, c.status,
                          COALESCE(v.volume_no, 1) as volume_no
                   FROM chapters c
                   LEFT JOIN volumes v ON v.id = c.volume_id
                   WHERE c.novel_id = ? AND c.chapter_no >= ?
                   ORDER BY c.chapter_no ASC""",
                (novel_id, from_ch),
            )
        result = []
        for row in cur.fetchall():
            content = row[2] or ""
            # Fallback: read from chapter file if DB content is empty
            if not content.strip() and chapters_dir:
                ch_dir = Path(chapters_dir)
                if ch_dir.exists():
                    ch_fp = _find_chapter_file(row[0], ch_dir)
                    if not ch_fp:
                        # v0.8.0: check volume subdirectories
                        for vd in sorted(ch_dir.glob("第*卷")):
                            ch_fp = _find_chapter_file(row[0], vd)
                            if ch_fp:
                                break
                    if ch_fp:
                        content = ch_fp.read_text(encoding="utf-8")
            result.append({
                "chapter_no": row[0],
                "title": row[1] or f"第{row[0]}章",
                "content": content,
                "word_count": row[3] or 0,
                "status": row[4] or "draft",
                "volume_no": row[5] if len(row) > 5 else 1,
            })
        return result
    except (sqlite3.Error, OSError) as exc:
        raise ExportDataError(f"chapter query failed: {exc}") from exc


def build_txt(chapters: list[dict], novel_title: str, separator: str = "\n\n---\n\n") -> str:
    """Build a plain-text export with volume separators when crossing volumes."""
    lines = []
    lines.append(novel_title)
    lines.append("=" * len(novel_title))
    lines.append(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"总章节数: {len(chapters)}")
    lines.append(f"总字数:   {sum(ch['word_count'] for ch in chapters):,}")
    lines.append("=" * len(novel_title))
    lines.append("")

    last_vol = None
    for ch in chapters:
        # Volume separator
        vol = ch.get("volume_no", 1)
        if vol != last_vol:
            if last_vol is not None:
                lines.append("")
                lines.append("=" * 40)
                lines.append("")
            lines.append(f"第{vol}卷")
            lines.append("-" * 20)
            lines.append("")
            last_vol = vol
        # Chapter header
        lines.append(f"第{ch['chapter_no']}章  {ch['title']}")
        lines.append("-" * 40)
        lines.append("")
        lines.append(ch["content"].strip())
        lines.append("")
        lines.append(separator.strip())
        lines.append("")

    return "\n".join(lines)


def build_md(
    chapters: list[dict],
    novel_title: str,
    include_toc: bool = True,
    separator: str = "\n\n---\n\n",
) -> str:
    """Build a Markdown export with optional table of contents."""
    lines = []
    lines.append(f"# {novel_title}")
    lines.append("")
    lines.append(f"> 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> 总章节数: {len(chapters)}")
    lines.append(f"> 总字数:   {sum(ch['word_count'] for ch in chapters):,}")
    lines.append("")

    if include_toc and chapters:
        lines.append("## 目录")
        lines.append("")
        last_vol = None
        for ch in chapters:
            vol = ch.get("volume_no", 1)
            if vol != last_vol:
                lines.append(f"### 第{vol}卷")
                lines.append("")
                last_vol = vol
            anchor = f"chapter-{ch['chapter_no']}"
            status_mark = ""
            if ch["status"] == "draft":
                status_mark = " *[草稿]*"
            elif ch["status"] == "revised":
                status_mark = " *[已改]*"
            lines.append(
                f"- [第{ch['chapter_no']}章  {ch['title']}](#{anchor})"
                f"{status_mark} ({ch['word_count']:,}字)"
            )
        lines.append("")

    last_vol = None
    for ch in chapters:
        vol = ch.get("volume_no", 1)
        if vol != last_vol:
            if last_vol is not None:
                lines.append("")
                lines.append("---")
                lines.append("")
            lines.append(f"# 第{vol}卷")
            lines.append("")
            last_vol = vol
        anchor = f"chapter-{ch['chapter_no']}"
        lines.append(f"## 第{ch['chapter_no']}章  {ch['title']} {{#{anchor}}}")
        lines.append("")
        lines.append(ch["content"].strip())
        lines.append("")
        lines.append(separator.strip())
        lines.append("")

    return "\n".join(lines)


def export_novel(
    slug: str,
    config_path: str,
    fmt: str = "md",
    output_path: str | None = None,
    novel_title_override: str | None = None,
    from_ch: int = 1,
    to_ch: int | None = None,
    include_toc: bool = True,
    separator: str = "\n\n---\n\n",
    db_path_override: str | None = None,
    chapters_dir: str | Path | None = None,
) -> dict:
    """Export all chapters of a novel to a single file.

    Returns a dict with status info.
    """
    config = load_config(config_path)
    if db_path_override:
        config["db_path"] = db_path_override
    db_path = get_db_path(config)

    if not Path(db_path).exists():
        return {
            "status": "error",
            "message": f"Database not found: {db_path}",
            "chapters_exported": 0,
        }

    try:
        conn = connect_sqlite(db_path, read_only=True)
    except Exception as e:
        return {
            "status": "error",
            "message": f"Cannot connect to database: {e}",
            "chapters_exported": 0,
        }

    try:
        novel = get_novel_info(conn, slug)
    except ExportDataError as exc:
        conn.close()
        return {"status": "error", "message": str(exc), "chapters_exported": 0}
    if not novel:
        conn.close()
        return {
            "status": "error",
            "message": f"Novel '{slug}' not found in database.",
            "chapters_exported": 0,
        }

    try:
        chapters = get_chapters(conn, novel["id"], from_ch, to_ch, chapters_dir)
    except ExportDataError as exc:
        conn.close()
        return {"status": "error", "message": str(exc), "chapters_exported": 0}
    conn.close()

    if not chapters:
        return {
            "status": "warning",
            "message": f"「{novel.get('title', slug)}」还没有任何章节哦 📭\n\n"
                       f"  目前章节范围 {from_ch}~{to_ch or '结束'} 内没有找到内容。\n"
                       f"  这本书需要先写一些章节才能导出。\n\n"
                       f"  提示：\n"
                       f"  1. 检查是否在正确的作品中（nf_状态）\n"
                       f"  2. 确认已添加大纲（nf_大纲 list）\n"
                       f"  3. 使用「生成写前任务卡」和「写后门禁检查」来写新章节\n"
                       f"  4. 章节写完后会自动入库，届时即可导出",
            "chapters_exported": 0,
        }

    novel_title = novel_title_override or novel["title"]

    # Build output
    if fmt == "md":
        content = build_md(chapters, novel_title, include_toc, separator)
    else:
        content = build_txt(chapters, novel_title, separator)

    # Determine output path
    if not output_path:
        ext = "md" if fmt == "md" else "txt"
        output_dir = PROJECT_ROOT / "exports"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / f"{slug}_full.{ext}")
    else:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        output_path = str(p)

    # Atomic write: stage to .tmp then os.replace (POSIX & Windows both atomic on same FS)
    output_p = Path(output_path)
    tmp_p = output_p.with_suffix(output_p.suffix + ".tmp")
    tmp_p.write_text(content, encoding="utf-8")
    os.replace(str(tmp_p), str(output_p))

    total_words = sum(ch["word_count"] for ch in chapters)
    file_size = output_p.stat().st_size

    return {
        "status": "ok",
        "novel_title": novel_title,
        "novel_slug": slug,
        "chapters_exported": len(chapters),
        "total_words": total_words,
        "file_size_bytes": file_size,
        "output_path": output_path,
        "format": fmt,
        "chapter_range": f"{chapters[0]['chapter_no']}-{chapters[-1]['chapter_no']}",
    }
