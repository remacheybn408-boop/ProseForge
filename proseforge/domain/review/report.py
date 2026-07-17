from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewFinding:
    severity: str
    message: str
    start: int | None = None
    end: int | None = None


@dataclass(frozen=True)
class ReviewReport:
    scope: str
    findings: tuple[ReviewFinding, ...]
    scores: dict[str, float]
    status: str = "REVIEWED"
