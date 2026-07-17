from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class RevisionProposal:
    base_version_id: str
    before_hash: str
    after_text: str
    rationale: str
    status: str = "PROPOSED"

    @property
    def after_hash(self) -> str: return hashlib.sha256(self.after_text.encode()).hexdigest()

    def approve(self, current_hash: str) -> "RevisionProposal":
        if current_hash != self.before_hash: raise ValueError("stale proposal base")
        return RevisionProposal(self.base_version_id, self.before_hash, self.after_text, self.rationale, "APPROVED")


def content_hash(content: str) -> str: return hashlib.sha256(content.encode()).hexdigest()
