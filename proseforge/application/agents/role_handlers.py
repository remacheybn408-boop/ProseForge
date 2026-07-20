"""ROLE_HANDLERS 注册表契约（蓝图 V3-004/005，后续 workstream 的挂载点）。

executor（proseforge/workflows/agent_executor.py）只 import 本模块的注册表与
校验函数。专家 handler（评审簇、主编等后续 workstream）在自己的模块里用
``@register_role("continuity_reviewer")`` 注册，**通过模块 import 副作用生效**：
把模块路径加入 ``SPECIALIST_MODULES``，``handler_for`` 首次解析时由
``load_specialists()`` 惰性 import 一次（避免循环 import 与启动成本）。

TaskContext 约定键：
- ``run``: dict——id/goal_hash/graph_revision/project_id/chapter_id/base_version_id 快照
- ``task``: dict——id/task_key/role 快照
- ``provider``: ModelProvider 实例（已按 run owner 凭据构建）
- ``provider_id`` / ``model``: str
- ``uow_factory``: 无参 callable，返回新的 SqlAlchemyUnitOfWork（handler 自持短事务用）
- ``artifacts``: list[dict]——截至认领时已提交 Artifact 的摘要
  （id/task_key/artifact_type/preview；preview 已脱敏限长，不含正文全文）

默认 handler（``default_role_handler``）：按角色提示词调模型 → 解析 JSON →
产出 artifact_type/payload/usage；模型调用发生在任何数据库事务之外。
Artifact 的服务端校验（allowlist + schema）由 executor 在提交时统一执行。
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from proseforge.domain.agents.roles import CATALOG, AgentRole

TaskContext = dict[str, object]


@dataclass
class RoleResult:
    """角色 handler 的执行结果；executor 据此提交 Artifact 与结算预算。"""

    artifact_type: str
    payload: dict[str, object]
    used_tokens: int = 0
    extra_events: list[dict[str, object]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


RoleHandler = Callable[[TaskContext], Awaitable[RoleResult]]

ROLE_HANDLERS: dict[str, RoleHandler] = {}

# 专家模块路径（后续 workstream 在此登记自己的模块，import 副作用完成注册）
SPECIALIST_MODULES: tuple[str, ...] = ()

_specialists_loaded = False


def register_role(role: str) -> Callable[[RoleHandler], RoleHandler]:
    """注册某角色的专家 handler（后注册覆盖先注册）。"""

    def decorator(handler: RoleHandler) -> RoleHandler:
        ROLE_HANDLERS[role] = handler
        return handler

    return decorator


def load_specialists() -> None:
    """惰性 import SPECIALIST_MODULES 一次；幂等。"""
    global _specialists_loaded
    if _specialists_loaded:
        return
    _specialists_loaded = True
    import importlib

    for module_path in SPECIALIST_MODULES:
        importlib.import_module(module_path)


def handler_for(role: str) -> RoleHandler:
    """解析角色 handler：专家注册优先，否则用默认通用 handler。"""
    load_specialists()
    return ROLE_HANDLERS.get(role, default_role_handler)


# --- Artifact 类型契约（蓝图 V3-005：10 种类型 + 最小 required-keys 校验） ---

ARTIFACT_TYPES: tuple[str, ...] = (
    "OutlineCandidate",
    "CharacterCard",
    "WorldRuleCandidate",
    "TimelineReport",
    "SceneDraft",
    "StyleReview",
    "ContinuityReport",
    "AdversarialReport",
    "MergeCandidate",
    "RevisionProposal",
)

ARTIFACT_SCHEMAS: dict[str, tuple[str, ...]] = {
    "OutlineCandidate": ("title", "chapters"),
    "CharacterCard": ("name", "role", "traits"),
    "WorldRuleCandidate": ("rule", "scope"),
    "TimelineReport": ("events", "issues"),
    "SceneDraft": ("title", "content"),
    "StyleReview": ("summary", "issues"),
    "ContinuityReport": ("summary", "issues"),
    "AdversarialReport": ("summary", "risks"),
    "MergeCandidate": ("summary", "sources"),
    "RevisionProposal": ("summary", "changes"),
}

# 现行 RolePolicy 允许的非类型化 legacy 类型（roles.py 由 policy workstream 演进）
GENERIC_ARTIFACT_TYPES: frozenset[str] = frozenset({"report", "candidate", "story_fact"})


def allowed_artifact_types(role: str) -> frozenset[str]:
    """角色 Artifact 类型 allowlist（domain/agents/roles.py RolePolicy，只读）。"""
    try:
        return CATALOG[AgentRole(role)].artifact_types
    except (KeyError, ValueError):
        return frozenset()


def default_artifact_type(role: str) -> str:
    """默认 handler 的产出类型：优先 candidate，其次 report，再次 allowlist 首项。"""
    allowed = allowed_artifact_types(role)
    for preferred in ("candidate", "report"):
        if preferred in allowed:
            return preferred
    return sorted(allowed)[0] if allowed else "candidate"


def validate_artifact_payload(artifact_type: str, payload: object) -> str | None:
    """最小 schema 校验：返回 None 通过，否则返回错误原因（不抛异常）。

    10 种类型化 Artifact 校验 required keys；legacy 类型只要求非空 JSON 对象。
    """
    if artifact_type not in ARTIFACT_TYPES and artifact_type not in GENERIC_ARTIFACT_TYPES:
        return f"unknown artifact type: {artifact_type}"
    if not isinstance(payload, dict) or not payload:
        return "artifact payload must be a non-empty JSON object"
    missing = [key for key in ARTIFACT_SCHEMAS.get(artifact_type, ()) if key not in payload]
    if missing:
        return f"artifact payload missing required keys: {','.join(missing)}"
    return None


async def default_role_handler(context: TaskContext) -> RoleResult:
    """默认通用 handler：角色提示词 → 模型 → 解析 JSON → RoleResult。

    模型输出非合法 JSON 时抛 JSONDecodeError，由 executor 按 malformed_json
    语义重试（max_attempts 内重置 PENDING，否则任务 FAILED）。
    """
    from proseforge.application.agents.prompts import build_task_prompt, prompt_for_role
    from proseforge.domain.ports.model_provider import GenerationRequest
    from proseforge.providers.usage import normalize_provider_usage

    task = context["task"]
    run = context["run"]
    assert isinstance(task, dict) and isinstance(run, dict)
    role, task_key = str(task["role"]), str(task["task_key"])
    provider_id = str(context.get("provider_id", "unknown"))
    provider = context["provider"]
    request = GenerationRequest(
        model=str(context["model"]),
        system_blocks=({"role": "system", "text": prompt_for_role(role)},),
        input_blocks=({"role": "user", "text": build_task_prompt(role=role, task_key=task_key, goal_hint=str(run.get("goal_hash", ""))[:12], artifacts=list(context.get("artifacts", [])))},),
        response_schema={"type": "object"},
        metadata={"workflow": "agent-run", "run_id": str(run.get("id", "")), "role": role, "task_key": task_key},
    )
    parts: list[str] = []
    usage = None
    async for event in provider.stream(request):
        if event.event == "content.delta":
            parts.append(event.text)
        elif event.event == "usage.updated":
            usage = normalize_provider_usage(provider_id, event.data)
        elif event.event == "response.completed" and event.data.get("usage"):
            usage = normalize_provider_usage(provider_id, event.data, final=True)
    raw = "".join(parts).strip()
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("role output must be a JSON object")
    declared = payload.get("artifact_type")
    artifact_type = str(declared) if isinstance(declared, str) and declared else default_artifact_type(role)
    return RoleResult(
        artifact_type=artifact_type,
        payload=payload,
        used_tokens=usage.total_tokens if usage else 0,
        input_tokens=usage.input_tokens if usage else 0,
        output_tokens=usage.output_tokens if usage else 0,
    )
