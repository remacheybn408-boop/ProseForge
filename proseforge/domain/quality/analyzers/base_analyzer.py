#!/usr/bin/env python3
"""
base_agent.py — Multi-Agent Review Board Base Class v0.5.5

All review agents inherit from BaseAnalyzer.
Agents only review — they do NOT modify the original text.
They output structured reports with findings, scores, and status.
"""



class BaseAnalyzer:
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
            "source": self.name,
        }

    @staticmethod
    def _component_result(score: int, status: str, findings: list) -> dict:
        """Build an internal sub-review result for merged agents."""
        status = (status or "WARNING").upper()
        if status not in ("PASS", "WARNING", "FAIL"):
            status = "WARNING"
        return {
            "score": min(100, max(0, score)),
            "status": status,
            "findings": findings or [],
        }

    @staticmethod
    def _merge_statuses(statuses: list[str]) -> str:
        """Merge component statuses with FAIL > WARNING > PASS priority."""
        normalized = [(status or "PASS").upper() for status in statuses]
        if any(status == "FAIL" for status in normalized):
            return "FAIL"
        if any(status == "WARNING" for status in normalized):
            return "WARNING"
        return "PASS"

    def _merge_components(self, components: list[dict]) -> dict:
        """Merge multiple component review results into one agent result."""
        findings = []
        seen = set()
        for component in components:
            for finding in component.get("findings", []) or []:
                key = (
                    finding.get("level", ""),
                    finding.get("message", ""),
                    finding.get("evidence", ""),
                    finding.get("suggestion", ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                findings.append(finding)

        statuses = [component.get("status", "PASS") for component in components]
        merged_status = self._merge_statuses(statuses)

        warning_components = sum(
            1 for component in components
            if component.get("status", "PASS").upper() == "WARNING"
        )
        fail_components = sum(
            1 for component in components
            if component.get("status", "PASS").upper() == "FAIL"
        )
        warning_findings = sum(
            1 for finding in findings
            if finding.get("level", "").upper() == "WARN"
        )
        fail_findings = sum(
            1 for finding in findings
            if finding.get("level", "").upper() == "FAIL"
        )

        score = {"PASS": 0, "WARNING": 45, "FAIL": 75}[merged_status]
        score += max(0, warning_components - 1) * 5
        score += fail_components * 8
        score += warning_findings * 2
        score += fail_findings * 5

        return self._build_result(min(100, score), merged_status, findings)

    @staticmethod
    def _count_chinese(text: str) -> int:
        """Count Chinese characters in text. \u59d4\u6258 utils.text_metrics\uff08\u5168\u4ed3\u552f\u4e00\u53e3\u5f84\uff09\u3002"""
        return sum(
            1
            for char in text
            if "\u3400" <= char <= "\u4dbf" or "\u4e00" <= char <= "\u9fff"
        )

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
