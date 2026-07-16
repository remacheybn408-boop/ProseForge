"""Compatibility import for the migrated prose analyzer."""

from proseforge.domain.quality.analyzers.prose_analyzer import ProseAnalyzer

ProseAgent = ProseAnalyzer

__all__ = ["ProseAgent", "ProseAnalyzer"]
