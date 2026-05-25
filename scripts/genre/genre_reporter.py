#!/usr/bin/env python3
"""genre_reporter.py — Generate genre review reports in JSON and Markdown."""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_REPORT_DIR = _PROJECT_ROOT / "reports" / "genre"


def save_genre_report(report: Dict, chapter_no: int):
    """Save genre agent report as JSON and Markdown."""
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = _REPORT_DIR / f"chapter_{chapter_no:03d}_genre_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Markdown
    md_path = _REPORT_DIR / f"chapter_{chapter_no:03d}_genre_report.md"
    md = _build_markdown(report)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    return str(json_path), str(md_path)


def _build_markdown(report: Dict) -> str:
    lines = []
    lines.append(f"# Genre Agent 审稿报告")
    lines.append(f"")
    lines.append(f"- **章节**: 第{report['chapter_no']}章")
    lines.append(f"- **题材**: {report.get('genre_pack_name', report['genre'])} ({report['genre']})")
    lines.append(f"- **风格**: {report.get('style_pack_name', report['style'])} ({report['style']})")
    lines.append(f"- **评分**: {report['score']}/100")
    lines.append(f"- **状态**: {report['status']}")
    lines.append(f"- **时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"")

    findings = report.get("findings", [])
    if findings:
        lines.append(f"## Findings ({len(findings)})")
        lines.append(f"")
        for i, f in enumerate(findings, 1):
            lines.append(f"### {i}. [{f['level']}] {f['type']}")
            lines.append(f"")
            lines.append(f"**问题**: {f['message']}")
            lines.append(f"")
            lines.append(f"**建议**: {f.get('suggestion', '无')}")
            lines.append(f"")
    else:
        lines.append(f"## Findings")
        lines.append(f"")
        lines.append(f"✅ 未发现题材/风格相关问题。")
        lines.append(f"")

    return "\n".join(lines)
