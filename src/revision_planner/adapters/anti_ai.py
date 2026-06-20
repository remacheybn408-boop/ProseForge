"""anti_ai adapter — prose_agent.review() output -> list[Finding].

Expected anti-AI finding shape:
    {level: "WARN", message: "AI套话 [NA_YI_KE]: '...'", evidence: "...", suggestion: "..."}
    {level: "WARN", message: "AI套话过多: 6处", evidence: "", suggestion: "..."}
"""

from __future__ import annotations

import re
from typing import Any

from src.revision_planner.schema import Finding, locate_in_text, normalize_severity


_CODED_HEAD = re.compile(r"^(?:AI套话|AI句式|硬科普)\s*\[([A-Z_0-9]+)\]")
_MATCHED_PHRASE = re.compile(r":\s*'([^']+)'\s*$")
_SYNTHETIC: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^水文段落"), "WATER_LOOK_REPEAT"),
    (re.compile(r"^对话标记重复"), "WATER_SAY_REPEAT"),
    (re.compile(r"^总结腔"), "SUMMARY_TONE"),
    (re.compile(r"^AI套话过多"), "AI_CLICHE_OVERFLOW"),
    (re.compile(r"^AI句式泛滥"), "NOT_A_B_OVERFLOW"),
]


def _extract_code(message: str) -> str:
    match = _CODED_HEAD.match(message)
    if match:
        return match.group(1)
    for pattern, code in _SYNTHETIC:
        if pattern.match(message):
            return code
    return "UNKNOWN"


def adapt(agent_output: dict[str, Any], *, text: str) -> list[Finding]:
    """Convert anti-AI/prose findings into normalized planner findings."""
    out: list[Finding] = []
    phrase_cursor: dict[str, int] = {}

    for raw in agent_output.get("findings", []) or []:
        message = raw.get("message", "") or ""
        wide_evidence = raw.get("evidence", "") or ""

        phrase_match = _MATCHED_PHRASE.search(message)
        matched_phrase = phrase_match.group(1) if phrase_match else ""

        location = None
        evidence_for_finding = matched_phrase or wide_evidence
        if matched_phrase:
            start_pos = phrase_cursor.get(matched_phrase, 0)
            location = locate_in_text(text, matched_phrase, start_pos=start_pos)
            if location is not None:
                phrase_cursor[matched_phrase] = location.char_end
        if location is None and wide_evidence:
            location = locate_in_text(text, wide_evidence)

        merged_raw = dict(raw)
        if matched_phrase and wide_evidence and wide_evidence != matched_phrase:
            merged_raw["_snippet"] = wide_evidence

        out.append(
            Finding(
                source="prose_agent",
                code=_extract_code(message),
                severity=normalize_severity(raw.get("level", "WARN")),
                message=message,
                evidence=evidence_for_finding,
                location=location,
                suggestion=raw.get("suggestion", "") or "",
                raw=merged_raw,
            )
        )
    return out
