"""Compatibility import for the migrated chief editor analyzer."""

from proseforge.domain.quality.analyzers.chief_editor_analyzer import ChiefEditorAnalyzer

ChiefEditor = ChiefEditorAnalyzer

__all__ = ["ChiefEditor", "ChiefEditorAnalyzer"]
