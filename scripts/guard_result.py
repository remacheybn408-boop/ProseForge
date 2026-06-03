#!/usr/bin/env python3
"""
guard_result.py — Unified guard result data structures for v0.4.5

Guard Finding: individual issue found by a guard
Guard Result:   one guard's complete output
Guard Summary:  all guards' combined result — THE single truth source
"""

from dataclasses import dataclass, field, asdict
from typing import Literal, Optional
import json


Severity = Literal["PASS", "WARN", "FAIL"]
GuardStatus = Literal["PASS", "WARN", "FAIL"]
SummaryStatus = Literal["PASS", "WARN", "FAIL"]


@dataclass
class GuardFinding:
    """One specific issue found by a guard."""
    guard: str                          # guard name, e.g. "anti_ai_guard"
    severity: Severity                  # PASS / WARN / FAIL
    code: str                           # unique error code, e.g. "NOT_A_B_PATTERN"
    message: str                        # human-readable description
    evidence: list[str] = field(default_factory=list)  # snippet evidence
    suggestion: str = ""                # optional fix suggestion
    confidence: float = 0.65            # 0.0–1.0, how sure the guard is
    location: str = ""                  # approximate location in text (line range)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GuardResult:
    """Output of a single guard execution."""
    guard: str                          # guard name
    status: GuardStatus                 # overall status for this guard
    findings: list[GuardFinding] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)   # guard-specific metrics
    report_path: Optional[str] = None             # if report saved to disk
    error: str = ""                               # if guard crashed

    @property
    def warn_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "WARN")

    @property
    def fail_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "FAIL")

    def to_dict(self) -> dict:
        return {
            "guard": self.guard,
            "status": self.status,
            "findings": [f.to_dict() for f in self.findings],
            "metrics": self.metrics,
            "report_path": self.report_path,
            "error": self.error,
            "warn_count": self.warn_count,
            "fail_count": self.fail_count,
        }


@dataclass
class GuardSummary:
    """Combined result of all guards for one chapter — THE truth source."""
    chapter_no: int
    overall_status: SummaryStatus = "PASS"
    fail_count: int = 0
    warn_count: int = 0
    pass_count: int = 0
    results: list[GuardResult] = field(default_factory=list)
    executed_guards: list[str] = field(default_factory=list)
    skipped_guards: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    fts_health: dict = field(default_factory=dict)
    title_diff: Optional[str] = None
    version: str = "v0.4.5"

    def compute(self):
        """Recompute derived fields from results."""
        self.fail_count = 0
        self.warn_count = 0
        self.pass_count = 0
        for r in self.results:
            if r.status == "FAIL":
                self.fail_count += 1
            elif r.status == "WARN":
                self.warn_count += 1
            else:
                self.pass_count += 1

        self.executed_guards = [r.guard for r in self.results]
        self.blocked_by = [r.guard for r in self.results if r.status == "FAIL"]

        if self.fail_count > 0:
            self.overall_status = "FAIL"
        elif self.warn_count > 0:
            self.overall_status = "WARN"
        else:
            self.overall_status = "PASS"

    def add_result(self, result: GuardResult):
        self.results.append(result)
        self.compute()

    def get_warnings(self) -> list[dict]:
        """Flat list of all WARN+FAIL findings for deduplication/revision."""
        all_warnings = []
        for r in self.results:
            for f in r.findings:
                if f.severity in ("WARN", "FAIL"):
                    all_warnings.append(f.to_dict())
        return all_warnings

    def to_dict(self) -> dict:
        return {
            "chapter_no": self.chapter_no,
            "overall_status": self.overall_status,
            "fail_count": self.fail_count,
            "warn_count": self.warn_count,
            "pass_count": self.pass_count,
            "results": [r.to_dict() for r in self.results],
            "executed_guards": self.executed_guards,
            "skipped_guards": self.skipped_guards,
            "blocked_by": self.blocked_by,
            "fts_health": self.fts_health,
            "title_diff": self.title_diff,
            "version": self.version,
        }

    def save(self, path: str):
        """Save to JSON file."""
        from pathlib import Path
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "GuardSummary":
        from pathlib import Path
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        summary = cls(chapter_no=data["chapter_no"])
        summary.overall_status = data.get("overall_status", "PASS")
        summary.fail_count = data.get("fail_count", 0)
        summary.warn_count = data.get("warn_count", 0)
        summary.pass_count = data.get("pass_count", 0)
        summary.executed_guards = data.get("executed_guards", [])
        summary.skipped_guards = data.get("skipped_guards", [])
        summary.blocked_by = data.get("blocked_by", [])
        summary.fts_health = data.get("fts_health", {})
        summary.title_diff = data.get("title_diff")
        summary.version = data.get("version", "v0.4.5")
        for r in data.get("results", []):
            findings = [GuardFinding(**f) for f in r.get("findings", [])]
            gr = GuardResult(
                guard=r["guard"], status=r["status"], findings=findings,
                metrics=r.get("metrics", {}), report_path=r.get("report_path"),
                error=r.get("error", ""))
            summary.results.append(gr)
        return summary


def finding(guard: str, severity: Severity, code: str, message: str,
            evidence: list[str] = None, suggestion: str = "",
            confidence: float = 0.65, location: str = "") -> GuardFinding:
    """Shorthand constructor."""
    return GuardFinding(guard=guard, severity=severity, code=code,
                        message=message, evidence=evidence or [],
                        suggestion=suggestion, confidence=confidence,
                        location=location)


def result_pass(guard: str, metrics: dict = None) -> GuardResult:
    return GuardResult(guard=guard, status="PASS", metrics=metrics or {})


def result_warn(guard: str, f: GuardFinding, metrics: dict = None) -> GuardResult:
    return GuardResult(guard=guard, status="WARN", findings=[f],
                       metrics=metrics or {})


def result_fail(guard: str, f: GuardFinding, metrics: dict = None) -> GuardResult:
    return GuardResult(guard=guard, status="FAIL", findings=[f],
                       metrics=metrics or {})
