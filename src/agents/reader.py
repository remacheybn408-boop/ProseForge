"""Compatibility import for the migrated reader analyzer."""

from proseforge.domain.quality.analyzers.reader_analyzer import ReaderAnalyzer

ReaderAgent = ReaderAnalyzer

__all__ = ["ReaderAgent", "ReaderAnalyzer"]
