"""Compatibility import for the migrated plot analyzer."""

from proseforge.domain.quality.analyzers.plot_analyzer import PlotAnalyzer

PlotAgent = PlotAnalyzer

__all__ = ["PlotAgent", "PlotAnalyzer"]
