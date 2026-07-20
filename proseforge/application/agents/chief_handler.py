"""chief_editor handler（蓝图 V3-007）：MergeCandidate → V2 RevisionProposal，替换 executor 占位路径。

流程：graph 输出 manifest（TaskContext artifacts）+ 本 run 已落库评审 + run.chapter_id/
base_version_id → 先按 merge_editor 同一四桶分类产出 MergeCandidate，再创建 V2
RevisionProposal：after = base.content + "\\n\\n" + 合并附录（模型撰写；输出不可用回退
候选摘要，保证 v3-execution-proposal 链路可达）。

guard gating：存在未裁定（resolution is None）CONFLICT 评审时 proposal.guard_status
置 "blocked"，V2 approve 走 ApprovalBlocked → 422（application/revision/
approve_proposal.py），冲突裁定前不可批准。RevisionRepository.create 不接收
guard_status 参数，在返回行上赋值后随调用方事务一并提交。

run 无 chapter_id/base_version_id 时只产 MergeCandidate，不建 proposal。
proposal 创建幂等：run.proposal_id 已设置且行存在 → 复用，不重复创建/发事件。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from proseforge.application.agents.prompts import prompt_for_role
from proseforge.application.agents.review_handlers import build_merge_payload, snapshot_review, stream_model_json
from proseforge.application.agents.role_handlers import RoleResult, TaskContext, register_role
from proseforge.domain.agents import policy
from proseforge.domain.common.ids import new_id
from proseforge.infrastructure.database.models.agents import AgentEventModel, AgentReviewModel, AgentRunModel
from proseforge.infrastructure.database.models.revision import RevisionProposalModel

_MERGE_BUCKETS: tuple[str, ...] = ("agreements", "conflicts", "unsupported", "accepted")


def unresolved_conflict_groups(reviews: list[dict[str, Any]]) -> list[str]:
    """未裁定（resolution is None）CONFLICT 评审的 conflict_group（去重升序）。"""
    return sorted({str(review["conflict_group"]) for review in reviews if review["status"] == "CONFLICT" and review["conflict_group"] and review["resolution"] is None})


def fallback_appendix(merge_payload: dict[str, Any]) -> str:
    """模型输出不可用时的确定性附录：候选摘要 + 桶计数（保证提案链路可达）。"""
    counts = ", ".join(f"{key}={len(merge_payload.get(key, []))}" for key in _MERGE_BUCKETS)
    return f"{merge_payload.get('summary', '')}\n[MergeCandidate] {counts}".strip()


async def _lock_run(uow, run_id: str) -> AgentRunModel:
    locked = await uow.session.scalar(
        select(AgentRunModel).where(AgentRunModel.id == run_id).with_for_update().execution_options(populate_existing=True)
    )
    if locked is None:
        raise LookupError("agent run not found")
    return locked


def _append_event(uow, run: AgentRunModel, event_type: str, data: dict[str, Any]) -> None:
    """在调用方事务内追加 run 事件（调用方已持有 run 行锁，sequence 单调递增）。"""
    sequence = int(run.event_cursor) + 1
    uow.session.add(AgentEventModel(id=new_id(), run_id=run.id, sequence=sequence, event_type=event_type, payload=json.dumps(data, ensure_ascii=False, sort_keys=True)))
    run.event_cursor = sequence
    run.updated_at = datetime.now(UTC)


async def create_chief_proposal(uow, run_id: str, reviews: list[dict[str, Any]], *, appendix: str) -> dict[str, Any]:
    """在调用方事务内创建（或幂等复用）V2 RevisionProposal；不自行 commit。

    返回 {"proposal_id", "guard_status", "created"}；base version 缺失抛 LookupError。
    """
    locked = await _lock_run(uow, run_id)
    if locked.proposal_id:
        existing = await uow.session.get(RevisionProposalModel, locked.proposal_id)
        if existing is not None:
            return {"proposal_id": existing.id, "guard_status": existing.guard_status, "created": False}
    base = await uow.chapters.get_version_owned(str(locked.chapter_id), str(locked.base_version_id), str(locked.user_id))
    if base is None:
        raise LookupError("chief editor base version not found")
    blocked = unresolved_conflict_groups(reviews)
    proposal = await uow.revisions.create(
        chapter_id=str(locked.chapter_id),
        base_version_id=base.id,
        before=base.content,
        after=f"{base.content}\n\n{appendix}",
        rationale=f"Chief Editor merge of agent run {run_id}: {len(reviews)} reviews, {len(blocked)} unresolved conflict group.",
    )
    # revisions.create 不接收 guard_status：在返回行上赋值，随调用方事务一并提交
    proposal.guard_status = "blocked" if blocked else "clear"
    locked.proposal_id = proposal.id
    _append_event(uow, locked, "proposal.created", {"proposal_id": proposal.id, "guard_status": proposal.guard_status})
    if blocked:
        _append_event(uow, locked, "proposal.blocked", {"proposal_id": proposal.id, "conflict_groups": blocked})
    return {"proposal_id": proposal.id, "guard_status": proposal.guard_status, "created": True}


async def run_chief_proposal(uow, run_id: str, reviews: list[dict[str, Any]]) -> dict[str, Any]:
    """端点路径（POST .../chief-proposal）：无 run 凭据可用，附录用确定性回退；在端点事务内执行。"""
    return await create_chief_proposal(uow, run_id, reviews, appendix=fallback_appendix(build_merge_payload(reviews)))


async def _compose_appendix(context: TaskContext, merge_payload: dict[str, Any]) -> tuple[str, tuple[int, int, int]]:
    """模型撰写合并附录；输出不可用（异常/非 JSON/缺 appendix）回退候选摘要，不阻断提案链路。"""
    task = context["task"]
    run = context["run"]
    assert isinstance(task, dict) and isinstance(run, dict)
    artifacts = [item for item in context.get("artifacts", []) if isinstance(item, dict)]
    lines = [
        f"任务：{task.get('task_key', '')}（角色 chief_editor）",
        f"写作目标摘要：{str(run.get('goal_hash', ''))[:12]}",
        "graph 输出 manifest：",
        *[f"- artifact_id={item.get('id', '')} [{item.get('artifact_type', '')}] {item.get('task_key', '')}: {item.get('preview', '')}" for item in artifacts],
        f"一致发现（agreements）：{json.dumps(merge_payload.get('agreements', []), ensure_ascii=False)[:2000]}",
        f"已接受发现（accepted）：{json.dumps(merge_payload.get('accepted', []), ensure_ascii=False)[:2000]}",
        "撰写追加在正文后的合并附录（appendix），落实一致与已接受发现；不得改写原文。",
    ]
    try:
        output, tokens = await stream_model_json(context, system_prompt=prompt_for_role("chief_editor"), user_prompt="\n".join(lines))
    except Exception:
        return fallback_appendix(merge_payload), (0, 0, 0)
    appendix = output.get("appendix")
    if not isinstance(appendix, str) or not appendix.strip():
        return fallback_appendix(merge_payload), tokens
    return appendix.strip(), tokens


@register_role("chief_editor")
async def chief_editor_handler(context: TaskContext) -> RoleResult:
    """chief_editor：MergeCandidate → V2 RevisionProposal（guard 阻塞语义见模块 docstring）。"""
    policy.authorize("chief_editor", "create_artifact")
    policy.authorize("chief_editor", "create_revision_proposal")
    run = context["run"]
    assert isinstance(run, dict)
    run_id = str(run["id"])
    uow_factory = context["uow_factory"]
    assert callable(uow_factory)

    # 读阶段：短事务内快照 run 行与评审（会话关闭后 ORM 实例过期，后续只用快照 dict）
    async with uow_factory() as uow:
        row = await uow.session.get(AgentRunModel, run_id)
        if row is None:
            raise LookupError("agent run not found")
        chapter_id, base_version_id = row.chapter_id, row.base_version_id
        reviews = [snapshot_review(item) for item in await uow.session.scalars(select(AgentReviewModel).where(AgentReviewModel.run_id == run_id))]

    payload = build_merge_payload(reviews)
    input_tokens = output_tokens = used_tokens = 0
    if chapter_id and base_version_id:
        appendix, (input_tokens, output_tokens, used_tokens) = await _compose_appendix(context, payload)  # 模型调用在事务外
        async with uow_factory() as uow:
            info = await create_chief_proposal(uow, run_id, reviews, appendix=appendix)
            await uow.commit()
        payload["proposal_id"] = info["proposal_id"]
        payload["guard_status"] = info["guard_status"]
    return RoleResult(
        artifact_type="candidate",
        payload=payload,
        used_tokens=used_tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        extra_events=[{"event": "merge.committed", "run_id": run_id, "review_count": len(reviews), **{key: len(payload[key]) for key in _MERGE_BUCKETS}}],
    )
