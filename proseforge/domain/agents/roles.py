from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class AgentRole(str, Enum):
    CHIEF_PLANNER = "chief_planner"
    STORY_ARCHITECT = "story_architect"
    WORLD_BUILDER = "world_builder"
    CHARACTER_DESIGNER = "character_designer"
    TIMELINE_ANALYST = "timeline_analyst"
    SCENE_WRITER = "scene_writer"
    STYLE_EDITOR = "style_editor"
    CONTINUITY_REVIEWER = "continuity_reviewer"
    ADVERSARIAL_REVIEWER = "adversarial_reviewer"
    MERGE_EDITOR = "merge_editor"
    CHIEF_EDITOR = "chief_editor"

@dataclass(frozen=True)
class RolePolicy:
    role: AgentRole
    artifact_types: frozenset[str]
    tools: frozenset[str]
    max_tokens: int
    max_children: int
    can_activate_facts: bool = False
    can_create_revision: bool = False
    can_create_chapter_version: bool = False
    policy_version: str = "v1"

CATALOG = {role: RolePolicy(role, frozenset({"report", "candidate"}), frozenset(), 12000, 4, can_create_revision=role is AgentRole.CHIEF_EDITOR) for role in AgentRole}
CATALOG[AgentRole.WORLD_BUILDER] = RolePolicy(AgentRole.WORLD_BUILDER, frozenset({"story_fact"}), frozenset(), 8000, 3)
