"""ROLE_HANDLERS 注册表契约与 Artifact schema 校验的纯内存测试（无 db、无网络）。"""

from __future__ import annotations

import pytest

from proseforge.application.agents.role_handlers import (
    ARTIFACT_SCHEMAS,
    ARTIFACT_TYPES,
    ROLE_HANDLERS,
    RoleResult,
    allowed_artifact_types,
    default_artifact_type,
    default_role_handler,
    handler_for,
    register_role,
    validate_artifact_payload,
)
from proseforge.domain.ports.model_provider import GenerationEvent


def test_artifact_contract_covers_ten_types():
    assert len(ARTIFACT_TYPES) == 10
    assert set(ARTIFACT_TYPES) == set(ARTIFACT_SCHEMAS)
    assert validate_artifact_payload("SceneDraft", {"title": "t"}) is not None  # 缺 content
    assert validate_artifact_payload("SceneDraft", {"title": "t", "content": "c"}) is None
    assert validate_artifact_payload("candidate", {"anything": 1}) is None  # legacy 类型只要求非空对象
    assert validate_artifact_payload("candidate", {}) is not None
    assert validate_artifact_payload("NoSuchType", {"a": 1}) is not None


def test_role_allowlist_comes_from_domain_policy():
    # roles.py 未改动：普通角色只允许 report/candidate，world_builder 只允许 story_fact
    assert allowed_artifact_types("chief_planner") == frozenset({"report", "candidate"})
    assert allowed_artifact_types("world_builder") == frozenset({"story_fact"})
    assert allowed_artifact_types("no_such_role") == frozenset()
    assert default_artifact_type("chief_planner") == "candidate"
    assert default_artifact_type("world_builder") == "story_fact"


def test_register_role_overrides_default_and_restores():
    # scene_writer 无专家注册（merge_editor 等已由 WS-D 专家模块接管），用于验证默认解析路径
    assert handler_for("scene_writer") is default_role_handler

    async def specialist(_context):
        return RoleResult(artifact_type="candidate", payload={"ok": True})

    saved = ROLE_HANDLERS.get("scene_writer")
    try:
        register_role("scene_writer")(specialist)
        assert handler_for("scene_writer") is specialist
    finally:
        if saved is None:
            ROLE_HANDLERS.pop("scene_writer", None)
        else:
            ROLE_HANDLERS["scene_writer"] = saved
    assert handler_for("scene_writer") is default_role_handler


class _RecordingProvider:
    provider_id = "fake"

    def __init__(self):
        self.requests = []

    async def stream(self, request):
        self.requests.append(request)
        yield GenerationEvent("content.delta", text='{"summary": "ok"}')
        yield GenerationEvent("response.completed", data={"usage": {"input_tokens": 7, "output_tokens": 3, "total_tokens": 10}})

    async def list_models(self):
        return []

    async def validate_credentials(self):
        return {"valid": True}

    async def count_tokens(self, _request):
        return 1


@pytest.mark.asyncio
async def test_default_handler_parses_json_and_reports_usage():
    provider = _RecordingProvider()
    context = {
        "run": {"id": "run-1", "goal_hash": "g" * 64},
        "task": {"id": "task-1", "role": "scene_writer", "task_key": "scene-a"},
        "provider": provider,
        "provider_id": "openai",
        "model": "gpt-4.1-mini",
        "artifacts": [{"artifact_type": "candidate", "task_key": "planner", "preview": "chief_planner candidate"}],
    }

    result = await default_role_handler(context)

    assert result.artifact_type == "candidate"
    assert result.payload == {"summary": "ok"}
    assert (result.input_tokens, result.output_tokens, result.used_tokens) == (7, 3, 10)
    request = provider.requests[0]
    # metadata 带 role/task_key，mock provider 后续可按角色分支
    assert request.metadata["role"] == "scene_writer"
    assert request.metadata["task_key"] == "scene-a"
    assert request.response_schema is not None  # 触发结构化 JSON 输出


@pytest.mark.asyncio
async def test_default_handler_raises_on_non_json_output():
    class GarbageProvider(_RecordingProvider):
        async def stream(self, request):
            yield GenerationEvent("content.delta", text="not json at all")

    import json as _json

    context = {
        "run": {"id": "run-1", "goal_hash": "g" * 64},
        "task": {"id": "task-1", "role": "chief_planner", "task_key": "planner"},
        "provider": GarbageProvider(),
        "provider_id": "openai",
        "model": "gpt-4.1-mini",
        "artifacts": [],
    }
    with pytest.raises(_json.JSONDecodeError):
        await default_role_handler(context)
