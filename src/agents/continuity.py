"""Compatibility import for the migrated continuity analyzer."""

from proseforge.domain.quality.analyzers.continuity_analyzer import ContinuityAnalyzer

ContinuityAgent = ContinuityAnalyzer

__all__ = ["ContinuityAgent", "ContinuityAnalyzer"]
