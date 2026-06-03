#!/usr/bin/env python3
"""
base_agent.py — Multi-Agent Review Board Base Class v0.5.5

All review agents inherit from BaseAgent.
Agents only review — they do NOT modify the original text.
They output structured reports with findings, scores, and status.
"""

import re
from typing import Optional


class BaseAgent:
    """Base class for all review agents.

    Subclasses must implement review() and return a standardized result dict.
    """

    def __init__(self, name: str, config: dict = None):
        self.name = name
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)

    def review(self, content: str, chapter_no: int = 0,
               context: dict = None) -> dict:
        """Review content and return findings.

        Args:
            content: Full text of the chapter to review.
            chapter_no: Chapter number.
            context: Optional context dict (prev_chapter, hooks, profiles, etc.)

        Returns:
            dict with keys: agent, chapter, score, status, findings
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.review() must be implemented"
        )

    def _build_result(self, score: int, status: str,
                      findings: list) -> dict:
        """Construct standardized result dict.

        Args:
            score: 0-100, higher = more issues (lower quality).
            status: 'PASS', 'WARNING', or 'FAIL'.
            findings: list of {level, message, evidence, suggestion} dicts.

        Returns:
            Standardized result dict.
        """
        status = status.upper()
        if status not in ("PASS", "WARNING", "FAIL"):
            status = "WARNING"

        return {
            "agent": self.name,
            "chapter": 0,  # filled by orchestrator
            "score": min(100, max(0, score)),
            "status": status,
            "findings": findings or [],
        }

    def _make_finding(self, level: str, message: str,
                      evidence: str = "", suggestion: str = "") -> dict:
        """Shorthand for creating a finding dict.

        Args:
            level: 'PASS', 'WARN', or 'FAIL'.
            message: Human-readable issue description.
            evidence: Snippet or line range showing the issue.
            suggestion: Optional fix suggestion.

        Returns:
            Finding dict.
        """
        level = level.upper()
        if level not in ("PASS", "WARN", "FAIL"):
            level = "WARN"
        return {
            "level": level,
            "message": message,
            "evidence": evidence,
            "suggestion": suggestion,
        }

    @staticmethod
    def _count_chinese(text: str) -> int:
        """Count Chinese characters in text."""
        return len([c for c in text if '\u4e00' <= c <= '\u9fff'])

    @staticmethod
    def _get_paragraphs(content: str, tail_chars: int = 0) -> list:
        """Split content into non-empty paragraphs.

        Args:
            content: Full text.
            tail_chars: If >0, only process the last N chars.

        Returns:
            List of paragraph strings.
        """
        if tail_chars > 0:
            content = content[-tail_chars:] if len(content) > tail_chars else content
        return [p.strip() for p in content.split('\n') if p.strip()]
