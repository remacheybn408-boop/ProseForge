#!/usr/bin/env python3
"""
report_builder.py — HTML 报告生成入口脚本 v0.5.0

Thin wrapper around src/report/html_report_builder.py.
Provides a command-line interface for generating the self-contained HTML report.

Usage:
  python scripts/report_builder.py [--config config.json] [--novel-slug demo_novel]
  python scripts/report_builder.py --output reports/index.html
"""

import sys
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Ensure src is importable
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main():
    """Main entry point — delegates to src.report.html_report_builder."""
    try:
        from src.report.html_report_builder import main as report_main
        return report_main()
    except ImportError as e:
        print(f"[ERROR] Cannot import src.report.html_report_builder: {e}")
        print("[INFO] Ensure the src package is properly structured:")
        print(f"       src/report/html_report_builder.py must exist.")
        print("[INFO] Falling back to standalone implementation.")
        return _standalone_main()
    except Exception as e:
        print(f"[ERROR] Report builder failed: {e}")
        return 1


def _standalone_main():
    """Standalone fallback implementation."""
    import argparse
    import json
    import sqlite3
    from datetime import datetime

    parser = argparse.ArgumentParser(
        description="Generate self-contained HTML report",
    )
    parser.add_argument(
        "--config", default=str(PROJECT_ROOT / "config.json"),
        help="Path to config.json",
    )
    parser.add_argument(
        "--novel-slug", default="demo_novel",
        help="Novel slug identifier",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output path (default: reports/index.html)",
    )
    parser.add_argument(
        "--title", default=None,
        help="Report title override",
    )
    args = parser.parse_args()

    # Load config
    config = {}
    config_path = Path(args.config)
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] Cannot parse config: {e}")

    db_path = config.get("db_path", str(PROJECT_ROOT / "data" / "novel_memory.db"))
    db_full = Path(db_path)
    if not db_full.is_absolute():
        db_full = PROJECT_ROOT / db_path

    slug = args.novel_slug

    # Connect to DB
    if db_full.exists():
        try:
            conn = sqlite3.connect(f"file:{db_full}?mode=ro", uri=True)
        except Exception as e:
            print(f"[WARN] Cannot open database: {e}")
            conn = sqlite3.connect(":memory:")
    else:
        print(f"[WARN] Database not found: {db_full}")
        conn = sqlite3.connect(":memory:")

    # Get novel info
    cur = conn.execute("SELECT id, title FROM novels WHERE slug = ?", (slug,))
    row = cur.fetchone()
    novel_title = row[1] if row else slug
    novel_id = row[0] if row else None

    # Get chapter stats
    chapter_count = 0
    total_words = 0
    recent_chapters = []

    if novel_id:
        try:
            cur = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(word_count), 0) FROM chapters WHERE novel_id = ?",
                (novel_id,),
            )
            row = cur.fetchone()
            chapter_count = row[0] or 0
            total_words = row[1] or 0

            cur = conn.execute(
                """SELECT chapter_no, title, word_count, status, updated_at
                   FROM chapters
                   WHERE novel_id = ?
                   ORDER BY chapter_no DESC LIMIT 20""",
                (novel_id,),
            )
            if args.title:
                novel_title = args.title

            recent_chapters = [
                {
                    "chapter_no": r[0],
                    "title": r[1] or f"第{r[0]}章",
                    "word_count": r[2] or 0,
                    "status": r[3] or "draft",
                    "updated_at": r[4] or "",
                }
                for r in cur.fetchall()
            ]
        except Exception as e:
            print(f"[WARN] Chapter query error: {e}")

    conn.close()

    # Build simple HTML
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    from version import get_version; version = get_version()
    project_name = "Novel Forge"

    chapter_rows = ""
    for ch in recent_chapters:
        status_badge = {
            "draft": "草稿",
            "revised": "已改",
            "final": "定稿",
        }.get(ch["status"], ch["status"])
        chapter_rows += f"""
            <tr>
                <td>{ch['chapter_no']}</td>
                <td>{_esc(ch['title'])}</td>
                <td>{ch['word_count']:,}</td>
                <td>{status_badge}</td>
                <td>{ch['updated_at'][:10] if ch['updated_at'] else '-'}</td>
            </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(novel_title)} — 写作报告</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; }}
    .container {{ max-width: 960px; margin: 0 auto; padding: 0 16px; }}
    header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); color: white; padding: 32px 0; margin-bottom: 24px; }}
    header h1 {{ font-size: 24px; font-weight: 600; margin-bottom: 4px; }}
    header .subtitle {{ font-size: 14px; opacity: 0.8; }}
    .section {{ background: white; border-radius: 8px; padding: 24px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
    .section h2 {{ font-size: 18px; font-weight: 600; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #e8e8e8; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; }}
    th {{ background: #fafafa; font-weight: 600; color: #555; font-size: 13px; }}
    tr:hover {{ background: #f8f9ff; }}
    .stat-cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 16px; }}
    .stat-card {{ flex: 1; min-width: 120px; background: #f8f9ff; border-radius: 8px; padding: 16px; text-align: center; }}
    .stat-value {{ font-size: 28px; font-weight: 700; color: #1a1a2e; }}
    .stat-label {{ font-size: 12px; color: #888; margin-top: 4px; }}
    footer {{ text-align: center; padding: 24px 0; color: #999; font-size: 12px; }}
</style>
</head>
<body>
<header>
    <div class="container">
        <h1>{_esc(novel_title)} — 写作报告</h1>
        <div class="subtitle">{project_name} {version} | 生成: {now} | 小说: {_esc(slug)}</div>
    </div>
</header>
<div class="container">
    <div class="section">
        <h2>项目概览</h2>
        <div class="stat-cards">
            <div class="stat-card">
                <div class="stat-value">{chapter_count}</div>
                <div class="stat-label">章节数</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{total_words:,}</div>
                <div class="stat-label">总字数</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(recent_chapters)}</div>
                <div class="stat-label">近期待审</div>
            </div>
        </div>
    </div>
    <div class="section">
        <h2>最近章节</h2>
        <table>
            <thead><tr><th>#</th><th>标题</th><th>字数</th><th>状态</th><th>更新日期</th></tr></thead>
            <tbody>{chapter_rows}
            </tbody>
        </table>
    </div>
</div>
<footer>
    <p>{project_name} {version} &mdash; AI Long-Form Novel Engineering Pipeline</p>
</footer>
</body>
</html>"""

    # Output
    output_path = args.output
    if not output_path:
        output_dir = PROJECT_ROOT / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "index.html"
    else:
        output_path = Path(output_path)

    output_path.write_text(html, encoding="utf-8")
    print(f"Report written to: {output_path}")
    return 0


def _esc(text: str) -> str:
    """Basic HTML escaping."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


if __name__ == "__main__":
    sys.exit(main())
