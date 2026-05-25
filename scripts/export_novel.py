#!/usr/bin/env python3
"""
export_novel.py — 导出小说合集 v0.5.0

从 SQLite 读取指定小说的所有章节，按 chapter_no 排序，输出单个 .txt 或 .md 文件。

用法:
  python scripts/export_novel.py --slug demo_novel --format md --output ./exports/novel.md
  python scripts/export_novel.py --slug demo_novel --format txt --output ./exports/novel.txt
  python scripts/export_novel.py --slug demo_novel --output ./exports/demo_novel.md

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

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_SLUG = "demo_novel"


def load_config(config_path: str) -> dict:
    """Load config JSON, falling back to defaults."""
    cfg = {}
    p = Path(config_path)
    if p.exists():
        try:
            cfg = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] Cannot parse config: {e}", file=sys.stderr)
    return cfg


def get_db_path(config: dict) -> str:
    """Get database path from config."""
    db = config.get("db_path", str(PROJECT_ROOT / "data" / "novel_memory.db"))
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
    except Exception:
        return None


def get_chapters(
    conn: sqlite3.Connection,
    novel_id: int,
    from_ch: int = 1,
    to_ch: int | None = None,
) -> list[dict]:
    """Get chapters for a novel, ordered by chapter_no."""
    try:
        if to_ch is not None:
            cur = conn.execute(
                """SELECT chapter_no, title, content, word_count, status
                   FROM chapters
                   WHERE novel_id = ? AND chapter_no >= ? AND chapter_no <= ?
                   ORDER BY chapter_no ASC""",
                (novel_id, from_ch, to_ch),
            )
        else:
            cur = conn.execute(
                """SELECT chapter_no, title, content, word_count, status
                   FROM chapters
                   WHERE novel_id = ? AND chapter_no >= ?
                   ORDER BY chapter_no ASC""",
                (novel_id, from_ch),
            )
        return [
            {
                "chapter_no": row[0],
                "title": row[1] or f"第{row[0]}章",
                "content": row[2] or "",
                "word_count": row[3] or 0,
                "status": row[4] or "draft",
            }
            for row in cur.fetchall()
        ]
    except Exception as e:
        print(f"[ERROR] Failed to query chapters: {e}", file=sys.stderr)
        return []


def build_txt(chapters: list[dict], novel_title: str, separator: str = "\n\n---\n\n") -> str:
    """Build a plain-text export."""
    lines = []
    lines.append(novel_title)
    lines.append("=" * len(novel_title))
    lines.append(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"总章节数: {len(chapters)}")
    lines.append(f"总字数:   {sum(ch['word_count'] for ch in chapters):,}")
    lines.append("=" * len(novel_title))
    lines.append("")

    for ch in chapters:
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
        for ch in chapters:
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

    for ch in chapters:
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
) -> dict:
    """Export all chapters of a novel to a single file.

    Returns a dict with status info.
    """
    config = load_config(config_path)
    db_path = get_db_path(config)

    if not Path(db_path).exists():
        return {
            "status": "error",
            "message": f"Database not found: {db_path}",
            "chapters_exported": 0,
        }

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except Exception as e:
        return {
            "status": "error",
            "message": f"Cannot connect to database: {e}",
            "chapters_exported": 0,
        }

    novel = get_novel_info(conn, slug)
    if not novel:
        conn.close()
        return {
            "status": "error",
            "message": f"Novel '{slug}' not found in database.",
            "chapters_exported": 0,
        }

    chapters = get_chapters(conn, novel["id"], from_ch, to_ch)
    conn.close()

    if not chapters:
        return {
            "status": "warning",
            "message": f"No chapters found for '{slug}' (chapter range {from_ch}-{to_ch or 'end'}).",
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

    # Write file
    Path(output_path).write_text(content, encoding="utf-8")

    total_words = sum(ch["word_count"] for ch in chapters)
    file_size = Path(output_path).stat().st_size

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


def main():
    parser = argparse.ArgumentParser(
        description="Export all chapters of a novel to a single file",
    )
    parser.add_argument(
        "--slug", default=DEFAULT_SLUG,
        help=f"Novel slug (default: {DEFAULT_SLUG})",
    )
    parser.add_argument(
        "--config", default=str(PROJECT_ROOT / "config.json"),
        help="Path to config.json",
    )
    parser.add_argument(
        "--format", choices=["txt", "md"], default="md",
        help="Output format (default: md)",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output file path (default: exports/<slug>_full.<format>)",
    )
    parser.add_argument(
        "--novel-title", default=None,
        help="Override novel title from database",
    )
    parser.add_argument(
        "--from-ch", type=int, default=1,
        help="Starting chapter number (default: 1)",
    )
    parser.add_argument(
        "--to-ch", type=int, default=None,
        help="Ending chapter number (default: all)",
    )
    parser.add_argument(
        "--no-toc", action="store_true",
        help="Omit table of contents (markdown only)",
    )
    parser.add_argument(
        "--separator", default="\n\n---\n\n",
        help="Chapter separator (default: double newline + --- + double newline)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output result as JSON",
    )
    args = parser.parse_args()

    result = export_novel(
        slug=args.slug,
        config_path=args.config,
        fmt=args.format,
        output_path=args.output,
        novel_title_override=args.novel_title,
        from_ch=args.from_ch,
        to_ch=args.to_ch,
        include_toc=not args.no_toc,
        separator=args.separator,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result["status"] == "ok":
            print(f"Novel:  {result['novel_title']} ({result['novel_slug']})")
            print(f"Chapters: {result['chapters_exported']} ({result['chapter_range']})")
            print(f"Words:  {result['total_words']:,}")
            print(f"Size:   {result['file_size_bytes']:,} bytes")
            print(f"Output: {result['output_path']}")
        else:
            print(f"[{result['status'].upper()}] {result['message']}")

    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
