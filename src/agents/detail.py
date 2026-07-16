"""Compatibility import for the migrated detail analyzer."""

from proseforge.domain.quality.analyzers.detail_analyzer import DetailAnalyzer

DetailAgent = DetailAnalyzer

__all__ = ["DetailAgent", "DetailAnalyzer"]
