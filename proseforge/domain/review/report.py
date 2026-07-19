from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Severity = Literal["blocking", "suggestion", "nit"]


@dataclass(frozen=True)
class ReviewFinding:
    severity: Severity
    message: str
    evidence: list[dict[str, int]]


@dataclass(frozen=True)
class ReviewReport:
    scope: str
    subject_type: str
    subject_id: str
    findings: list[ReviewFinding]
    scores: dict[str, float]
    model_snapshot: dict[str, object]
    context_snapshot_id: str | None = None
    usage_call_id: str | None = None
