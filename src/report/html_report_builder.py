#!/usr/bin/env python3
"""
html_report_builder.py — Generate self-contained HTML report v0.5.0

Builds reports/index.html from SQLite data. No external CDN, inline CSS only.

Usage:
  python -m src.report.html_report_builder [--config config.json] [--novel-slug demo_novel]
  nf_续写 / nf_审稿 工具 (Hermes plugin)
"""

import json
import sqlite3
import sys
import argparse
import os
from pathlib import Path
from datetime import datetime

from src.utils.config_utils import load_json_config, resolve_path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SLUG = "demo_novel"
DEFAULT_CONFIG = PROJECT_ROOT / "config.json"
from pathlib import Path; import sys; _vdir = Path(__file__).parent.parent.parent
from version import get_version; VERSION = get_version()
PROJECT_NAME = "Novel Forge"


def load_config(config_path: str | None) -> dict:
    return load_json_config(config_path, PROJECT_ROOT)


def get_db_path(config: dict) -> str:
    return str(resolve_path(PROJECT_ROOT, config.get("db_path", "./data/novel_memory.db")))


def get_novel_id(conn: sqlite3.Connection, slug: str) -> int | None:
    try:
        cur = conn.execute("SELECT id, title FROM novels WHERE slug = ?", (slug,))
        row = cur.fetchone()
        return row if row else None
    except Exception:
        return None


def get_chapter_stats(conn: sqlite3.Connection, novel_id: int) -> dict:
    """Get chapter count and total words."""
    try:
        cur = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(word_count), 0) FROM chapters WHERE novel_id = ?",
            (novel_id,),
        )
        row = cur.fetchone()
        return {"count": row[0] or 0, "total_words": row[1] or 0}
    except Exception:
        return {"count": 0, "total_words": 0}


def get_recent_chapters(conn: sqlite3.Connection, novel_id: int, limit: int = 20) -> list[dict]:
    """Get recent chapters list."""
    try:
        cur = conn.execute(
            """SELECT chapter_no, title, word_count, status, updated_at
               FROM chapters
               WHERE novel_id = ?
               ORDER BY chapter_no DESC
               LIMIT ?""",
            (novel_id, limit),
        )
        return [
            {
                "chapter_no": row[0],
                "title": row[1] or f"第{row[0]}章",
                "word_count": row[2] or 0,
                "status": row[3] or "draft",
                "updated_at": row[4] or "",
            }
            for row in cur.fetchall()
        ]
    except Exception:
        return []


def get_guard_summary(conn: sqlite3.Connection, novel_id: int) -> dict | None:
    """Try to load guard summary from exports."""
    exports_root = PROJECT_ROOT / "exports"
    candidates = sorted(exports_root.glob("guard_summary*.json"), reverse=True)
    if candidates:
        try:
            data = json.loads(candidates[0].read_text(encoding="utf-8"))
            return data
        except Exception:
            pass
    return None


def get_voice_pack_status() -> dict:
    """Check packs/voice/ directory status."""
    vp = PROJECT_ROOT / "packs" / "voice"
    if not vp.exists():
        return {"exists": False, "categories": [], "total_files": 0}
    try:
        categories = []
        total = 0
        for item in vp.iterdir():
            if item.is_dir():
                sub_count = len(list(item.glob("*.yaml"))) + len(list(item.glob("*.yml"))) + len(list(item.glob("*.json")))
                categories.append({"name": item.name, "file_count": sub_count})
                total += sub_count
            elif item.suffix in (".yaml", ".yml", ".md"):
                total += 1
        return {"exists": True, "categories": categories, "total_files": total}
    except Exception:
        return {"exists": True, "categories": [], "total_files": 0}


def get_warnings_summary(conn: sqlite3.Connection, novel_id: int) -> list[dict]:
    """Get continuity_checks as warnings."""
    try:
        cur = conn.execute(
            """SELECT check_type, issue, severity, status
               FROM continuity_checks
               WHERE novel_id = ? AND severity >= 1
               ORDER BY severity DESC, id DESC
               LIMIT 30""",
            (novel_id,),
        )
        return [
            {
                "type": row[0],
                "issue": row[1],
                "severity": row[2],
                "status": row[3],
            }
            for row in cur.fetchall()
        ]
    except Exception:
        return []


def build_html(
    slug: str,
    novel_title: str,
    chapter_stats: dict,
    recent_chapters: list[dict],
    guard_summary: dict | None,
    voice_status: dict,
    warnings: list[dict],
) -> str:
    """Build complete HTML document."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Chapter rows
    chapter_rows = ""
    for ch in recent_chapters:
        status_badge = {
            "draft": '<span class="badge badge-draft">草稿</span>',
            "revised": '<span class="badge badge-revised">已改</span>',
            "final": '<span class="badge badge-final">定稿</span>',
        }.get(ch["status"], f'<span class="badge">{ch["status"]}</span>')

        chapter_rows += f"""
                <tr>
                    <td>{ch['chapter_no']}</td>
                    <td>{_esc(ch['title'])}</td>
                    <td>{ch['word_count']:,}</td>
                    <td>{status_badge}</td>
                    <td>{ch['updated_at'][:10] if ch['updated_at'] else '-'}</td>
                </tr>"""

    # Guard summary section
    if guard_summary:
        executed = guard_summary.get("executed_guards", [])
        final = guard_summary.get("final_status", "UNKNOWN")
        warn_count = guard_summary.get("warning_count", 0)
        blocked = guard_summary.get("blocked_by", [])
        run_mode = guard_summary.get("run_mode", "")

        guard_final_class = {
            "PASS": "pass",
            "WARN": "warn",
            "BLOCKED": "fail",
            "FAIL": "fail",
        }.get(final, "warn")

        guard_rows = ""
        for g in executed:
            gname = g.get("guard", g.get("name", "?"))
            gstatus = g.get("status", "?")
            gclass = {"PASS": "pass", "WARN": "warn", "FAIL": "fail"}.get(gstatus, "warn")
            findings = g.get("findings", [])
            fcount = len(findings) if findings else 0
            guard_rows += f"""
                <tr>
                    <td>{_esc(str(gname))}</td>
                    <td><span class="badge badge-{gclass}">{gstatus}</span></td>
                    <td>{fcount}</td>
                </tr>"""

        guard_section = f"""
        <div class="section">
            <h2>门禁总览 (Guard Summary)</h2>
            <div class="stat-cards">
                <div class="stat-card">
                    <div class="stat-value">{len(executed)}</div>
                    <div class="stat-label">执行门禁</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{warn_count}</div>
                    <div class="stat-label">WARNING</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{len(blocked)}</div>
                    <div class="stat-label">BLOCKED</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value stat-{guard_final_class}">{final}</div>
                    <div class="stat-label">最终结果</div>
                </div>
            </div>
            <table>
                <thead><tr><th>门禁</th><th>状态</th><th>发现</th></tr></thead>
                <tbody>{guard_rows}
                </tbody>
            </table>
            <p class="meta">模式: {run_mode} | 最新门禁摘要 (JSON)</p>
        </div>"""
    else:
        guard_section = """
        <div class="section">
            <h2>门禁总览 (Guard Summary)</h2>
            <div class="empty-state">
                <div class="empty-icon">&#9888;</div>
                <p>暂无门禁数据。请运行 <code>nf_审稿</code> 生成门禁报告。</p>
            </div>
        </div>"""

    # Voice pack section
    if voice_status["exists"]:
        vp_cats = ""
        for cat in voice_status.get("categories", []):
            vp_cats += f"""
                <tr>
                    <td>{_esc(cat['name'])}</td>
                    <td>{cat['file_count']}</td>
                </tr>"""
        voice_section = f"""
        <div class="section">
            <h2>声纹包状态 (Voice Packs)</h2>
            <div class="stat-cards">
                <div class="stat-card">
                    <div class="stat-value">{voice_status['total_files']}</div>
                    <div class="stat-label">总文件数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{len(voice_status.get('categories', []))}</div>
                    <div class="stat-label">分类目录</div>
                </div>
            </div>
            <table>
                <thead><tr><th>分类</th><th>文件数</th></tr></thead>
                <tbody>{vp_cats}
                </tbody>
            </table>
        </div>"""
    else:
        voice_section = """
        <div class="section">
            <h2>声纹包状态 (Voice Packs)</h2>
            <div class="empty-state">
                <div class="empty-icon">&#128227;</div>
                <p>packs/voice/ 目录未找到。请运行 <code>install.bat</code> 初始化声纹包。</p>
            </div>
        </div>"""

    # Warnings section
    if warnings:
        warn_rows = ""
        for w in warnings:
            sev_class = {1: "warn", 2: "warn", 3: "fail"}.get(w["severity"], "warn")
            warn_rows += f"""
                <tr>
                    <td>{_esc(w['type'])}</td>
                    <td>{_esc(w['issue'][:80])}{'...' if len(w.get('issue','')) > 80 else ''}</td>
                    <td><span class="badge badge-{sev_class}">L{w['severity']}</span></td>
                    <td>{_esc(w['status'])}</td>
                </tr>"""
        warnings_section = f"""
        <div class="section">
            <h2>警告摘要 (Warnings)</h2>
            <table>
                <thead><tr><th>类型</th><th>问题</th><th>严重度</th><th>状态</th></tr></thead>
                <tbody>{warn_rows}
                </tbody>
            </table>
        </div>"""
    else:
        warnings_section = """
        <div class="section">
            <h2>警告摘要 (Warnings)</h2>
            <div class="empty-state">
                <div class="empty-icon">&#10003;</div>
                <p>暂无警告记录。一切看起来不错！</p>
            </div>
        </div>"""

    # Build full HTML
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(novel_title)} — 写作报告</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Microsoft YaHei", sans-serif;
        background: #f5f5f5;
        color: #333;
        line-height: 1.6;
    }}
    .container {{
        max-width: 960px;
        margin: 0 auto;
        padding: 0 16px;
    }}
    header {{
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        color: white;
        padding: 32px 0;
        margin-bottom: 24px;
    }}
    header h1 {{
        font-size: 24px;
        font-weight: 600;
        margin-bottom: 4px;
    }}
    header .subtitle {{
        font-size: 14px;
        opacity: 0.8;
    }}
    .section {{
        background: white;
        border-radius: 8px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }}
    .section h2 {{
        font-size: 18px;
        font-weight: 600;
        margin-bottom: 16px;
        padding-bottom: 8px;
        border-bottom: 2px solid #e8e8e8;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
    }}
    th, td {{
        padding: 10px 12px;
        text-align: left;
        border-bottom: 1px solid #eee;
    }}
    th {{
        background: #fafafa;
        font-weight: 600;
        color: #555;
        font-size: 13px;
        text-transform: uppercase;
    }}
    tr:hover {{ background: #f8f9ff; }}
    .stat-cards {{
        display: flex;
        gap: 16px;
        flex-wrap: wrap;
        margin-bottom: 16px;
    }}
    .stat-card {{
        flex: 1;
        min-width: 120px;
        background: #f8f9ff;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }}
    .stat-value {{
        font-size: 28px;
        font-weight: 700;
        color: #1a1a2e;
    }}
    .stat-value.stat-pass {{ color: #22c55e; }}
    .stat-value.stat-warn {{ color: #f59e0b; }}
    .stat-value.stat-fail {{ color: #ef4444; }}
    .stat-label {{
        font-size: 12px;
        color: #888;
        margin-top: 4px;
    }}
    .badge {{
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
    }}
    .badge-pass {{ background: #dcfce7; color: #166534; }}
    .badge-warn {{ background: #fef3c7; color: #92400e; }}
    .badge-fail {{ background: #fee2e2; color: #991b1b; }}
    .badge-draft {{ background: #e0e7ff; color: #3730a3; }}
    .badge-revised {{ background: #fef3c7; color: #92400e; }}
    .badge-final {{ background: #dcfce7; color: #166534; }}
    .empty-state {{
        text-align: center;
        padding: 40px 16px;
        color: #999;
    }}
    .empty-icon {{
        font-size: 48px;
        margin-bottom: 12px;
    }}
    .meta {{
        font-size: 12px;
        color: #999;
        margin-top: 12px;
    }}
    footer {{
        text-align: center;
        padding: 24px 0;
        color: #999;
        font-size: 12px;
    }}
    code {{
        background: #f0f0f0;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 13px;
    }}
</style>
</head>
<body>

<header>
    <div class="container">
        <h1>{_esc(novel_title)} — 写作报告</h1>
        <div class="subtitle">{PROJECT_NAME} {VERSION} | 生成时间: {now} | 小说: {_esc(slug)}</div>
    </div>
</header>

<div class="container">

    <div class="section">
        <h2>项目概览</h2>
        <div class="stat-cards">
            <div class="stat-card">
                <div class="stat-value">{chapter_stats['count']}</div>
                <div class="stat-label">章节数</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{chapter_stats['total_words']:,}</div>
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

{guard_section}

{voice_section}

{warnings_section}

</div>

<footer>
    <p>{PROJECT_NAME} {VERSION} &mdash; AI Long-Form Novel Engineering Pipeline</p>
</footer>

</body>
</html>"""
    return html


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

