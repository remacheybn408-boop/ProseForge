#!/usr/bin/env python3
"""Merged 6-agent review board."""

from version import get_version

from .base_agent import BaseAgent
from .character import CharacterAgent, load_voice_context
from .chief_editor_agent import ChiefEditor
from .continuity import ContinuityAgent
from .detail import DetailAgent
from .orchestrator import AgentOrchestrator, run_agent_review
from .plot import PlotAgent
from .prose import ProseAgent
from .reader import ReaderAgent

__version__ = get_version()

__all__ = [
    "BaseAgent",
    "ContinuityAgent",
    "CharacterAgent",
    "load_voice_context",
    "ProseAgent",
    "PlotAgent",
    "ReaderAgent",
    "DetailAgent",
    "ChiefEditor",
    "AgentOrchestrator",
    "run_agent_review",
]
