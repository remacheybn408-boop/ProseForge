"""Compatibility import for the migrated analyzer base class."""

from proseforge.domain.quality.analyzers.base_analyzer import BaseAnalyzer

BaseAgent = BaseAnalyzer

__all__ = ["BaseAgent", "BaseAnalyzer"]
