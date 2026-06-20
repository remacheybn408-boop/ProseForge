#!/usr/bin/env python3
"""genre_agent.py — Genre Agent: applies genre/style rules to chapter review."""
import json
from pathlib import Path
from typing import Dict, Optional

from .genre_loader import load_genre_pack
from .style_loader import load_style_pack
from .genre_rules import check_genre_rules
from .style_rules import check_style_rules

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def run_genre_agent(
    content: str,
    chapter_no: int = 1,
    genre_id: Optional[str] = None,
    style_id: Optional[str] = None,
    word_count: int = 0,
) -> Dict:
    """Run genre/style review on chapter content.

    Returns a dict compatible with the agent review report format.
    """
    genre_pack = load_genre_pack(genre_id)
    style_pack = load_style_pack(style_id)

    wc = word_count or _count_chinese(content)

    genre_findings = check_genre_rules(content, genre_pack, style_pack, wc)
    style_findings = check_style_rules(content, style_pack, wc)

    all_findings = genre_findings + style_findings

    status = "PASS"
    for f in all_findings:
        if f["level"] == "FAIL":
            status = "FAIL"
            break
        elif f["level"] in ("WARNING", "STRONG_WARNING"):
            status = "WARN"

    score = max(0, 100 - len(all_findings) * 8)

    return {
        "agent": "genre_agent",
        "chapter_no": chapter_no,
        "genre": genre_pack.get("genre_id", "generic"),
        "style": style_pack.get("style_id", "generic"),
        "score": score,
        "status": status,
        "findings": all_findings,
        "genre_pack_name": genre_pack.get("name", ""),
        "style_pack_name": style_pack.get("name", ""),
    }


def _count_chinese(text: str) -> int:
    import re
    return len(re.findall(r'[\u4e00-\u9fff]', text))
