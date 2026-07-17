from __future__ import annotations
from proseforge.domain.agents.roles import CATALOG, AgentRole

class PolicyDenied(PermissionError): pass

def authorize(role: AgentRole | str, capability: str, *, policy_version: str = "v1") -> None:
    selected = AgentRole(role); policy = CATALOG[selected]
    if policy.policy_version != policy_version: raise PolicyDenied("policy version mismatch")
    allowed = {"activate_fact": policy.can_activate_facts, "create_revision": policy.can_create_revision, "create_chapter_version": policy.can_create_chapter_version}
    if capability in allowed and not allowed[capability]: raise PolicyDenied(f"{selected.value} cannot {capability}")

def check_children(role: AgentRole | str, child_count: int) -> None:
    policy = CATALOG[AgentRole(role)]
    if child_count > policy.max_children: raise PolicyDenied("maximum child count exceeded")
