"""评审簇角色 handler（蓝图 V3-006）：continuity/adversarial/style 评审 + merge_editor。

职责：
- 评审 handler 调模型产出带证据区间的 findings（JSON），并把评审结论持久化为
  AgentReviewModel 行（此前 review_swarm 只有内存语义，本模块负责接线落库）；
- 两条评审在同一证据上给出不同结论时，按 review_swarm.detect_conflicts 语义共享
  确定性 conflict_group（cg-<sha256(run_id|证据) 前 12 位>），双方状态置 CONFLICT；
- merge_editor 只对本 run 已落库评审做四桶分类，绝不改写作者正文、不调模型。

Artifact 类型说明：现行 RolePolicy（domain/agents/roles.py）对上述角色的 allowlist
只有 report/candidate，类型化 Artifact（ContinuityReport 等）会被 executor 的
allowlist 校验拒绝。因此评审报告以 artifact_type="report" 提交，payload 携带
report_type 与类型化 schema 的 required keys（ContinuityReport→summary+issues，
AdversarialReport→summary+risks，StyleReview→summary+issues）；policy 放开
allowlist 后，该 payload 可直接通过 validate_artifact_payload 的类型化校验。

存储评审状态 → 合并桶映射（merge_editor 与 chief_editor 共用，见 categorize_reviews）：
- payload.resolution == "accepted"（任意状态，含已裁定的冲突）→ accepted
- status == "CONFLICT" 且带 conflict_group 且未裁定 → conflicts（按组聚合，resolution=null）
- status == "UNSUPPORTED" → unsupported
- 其余（PASS/WARNING：有证据支持且无对抗结论）→ agreements
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select

from proseforge.application.agents.review_swarm import Finding, detect_conflicts
from proseforge.application.agents.role_handlers import RoleResult, TaskContext, register_role
from proseforge.domain.agents import policy
from proseforge.domain.common.ids import new_id
from proseforge.infrastructure.database.models.agents import AgentReviewModel

# 评审角色 → (类型化报告名, findings 在 payload 中的键名)；键名对齐 ARTIFACT_SCHEMAS required keys
REVIEWER_REPORT_TYPES: dict[str, tuple[str, str]] = {
    "continuity_reviewer": ("ContinuityReport", "issues"),
    "adversarial_reviewer": ("AdversarialReport", "risks"),
    "style_editor": ("StyleReview", "issues"),
}

MAX_EVIDENCE_SPANS = 32  # 与 api/routes/agent_runs.py ReviewRequest 的 evidence 上限一致
_STATUS_RANK = {"PASS": 0, "UNSUPPORTED": 1, "WARNING": 2, "CONFLICT": 3}
_MERGE_BUCKETS: tuple[str, ...] = ("agreements", "conflicts", "unsupported", "accepted")


# --- 模型调用与输出归一（chief_handler 复用 stream_model_json） ---


async def stream_model_json(context: TaskContext, *, system_prompt: str, user_prompt: str) -> tuple[dict[str, Any], tuple[int, int, int]]:
    """流式调模型并解析单个 JSON 对象；返回 (payload, (input, output, total) tokens)。

    输出非合法 JSON 时抛 JSONDecodeError，由 executor 按 malformed_json 语义重试；
    模型调用不持有任何数据库事务。
    """
    from proseforge.domain.ports.model_provider import GenerationRequest
    from proseforge.providers.usage import normalize_provider_usage

    task = context["task"]
    run = context["run"]
    assert isinstance(task, dict) and isinstance(run, dict)
    provider = context["provider"]
    provider_id = str(context.get("provider_id", "unknown"))
    request = GenerationRequest(
        model=str(context["model"]),
        system_blocks=({"role": "system", "text": system_prompt},),
        input_blocks=({"role": "user", "text": user_prompt},),
        response_schema={"type": "object"},
        metadata={"workflow": "agent-run", "run_id": str(run.get("id", "")), "role": str(task["role"]), "task_key": str(task["task_key"])},
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
    payload = json.loads("".join(parts).strip())
    if not isinstance(payload, dict):
        raise ValueError("role output must be a JSON object")
    tokens = (usage.input_tokens, usage.output_tokens, usage.total_tokens) if usage else (0, 0, 0)
    return payload, tokens


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalize_findings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """把模型输出归一为 findings 列表；兼容 issues/risks 纯字符串清单（无证据区间）。"""
    items: list[Any] = []
    raw = payload.get("findings")
    if isinstance(raw, list):
        items.extend(raw)
    if not items:
        for key in ("issues", "risks"):
            legacy = payload.get(key)
            if isinstance(legacy, list):
                items.extend(legacy)
    findings: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, str):
            findings.append({"finding": item[:500], "severity": "medium", "target_artifact_id": None, "evidence_spans": []})
        elif isinstance(item, dict):
            raw_spans = item.get("evidence_spans")
            spans = [span for span in raw_spans if isinstance(span, dict)] if isinstance(raw_spans, list) else []
            findings.append({
                "finding": str(item.get("finding", ""))[:500],
                "severity": str(item.get("severity", "medium")),
                "target_artifact_id": str(item["target_artifact_id"]) if item.get("target_artifact_id") else None,
                "evidence_spans": [
                    {"artifact_id": str(span.get("artifact_id", "")), "start": _safe_int(span.get("start", 0)), "end": _safe_int(span.get("end", 0)), "quote": str(span.get("quote", ""))[:500]}
                    for span in spans
                ][:MAX_EVIDENCE_SPANS],
            })
    return [finding for finding in findings if finding["finding"]]


def _span_key(span: dict[str, Any]) -> str:
    """证据标识：优先 quote（detect_conflicts 按 evidence 相等判同靶），否则 artifact:start:end。"""
    quote = str(span.get("quote", "")).strip()
    if quote:
        return quote
    artifact_id = str(span.get("artifact_id", "")).strip()
    return f"{artifact_id}:{span.get('start', 0)}:{span.get('end', 0)}" if artifact_id else ""


# --- 评审快照与四桶分类（merge_editor / chief_editor / chief-proposal 端点共用） ---


def snapshot_review(row: AgentReviewModel) -> dict[str, Any]:
    """事务内快照评审行（会话关闭后 ORM 实例过期，分类/合并只读快照 dict）。"""
    try:
        payload = json.loads(row.payload or "{}")
    except ValueError:
        payload = {}
    try:
        evidence = json.loads(row.evidence or "[]")
    except ValueError:
        evidence = []
    claims = payload.get("claims") if isinstance(payload, dict) else None
    return {
        "id": row.id,
        "artifact_id": row.artifact_id,
        "reviewer_role": row.reviewer_role,
        "status": row.status,
        "conflict_group": row.conflict_group,
        "evidence": evidence if isinstance(evidence, list) else [],
        "claims": claims if isinstance(claims, list) else [],
        "resolution": payload.get("resolution") if isinstance(payload, dict) else None,
    }


def categorize_reviews(reviews: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """存储评审快照 → agreement/conflict/unsupported/accepted 四桶（映射见模块 docstring）；纯函数。"""
    buckets: dict[str, list[dict[str, Any]]] = {key: [] for key in _MERGE_BUCKETS}
    conflict_groups: dict[str, list[dict[str, Any]]] = {}
    for review in reviews:
        entry = {
            "review_id": review["id"],
            "artifact_id": review["artifact_id"],
            "reviewer_role": review["reviewer_role"],
            "status": review["status"],
            "claims": list(review["claims"]),
        }
        if review["resolution"] == "accepted":
            buckets["accepted"].append(entry)
        elif review["status"] == "CONFLICT" and review["conflict_group"]:
            conflict_groups.setdefault(str(review["conflict_group"]), []).append(entry)
        elif review["status"] == "UNSUPPORTED":
            buckets["unsupported"].append(entry)
        else:
            buckets["agreements"].append(entry)
    buckets["conflicts"] = [
        {
            "conflict_group": group,
            "parties": sorted(str(item["review_id"]) for item in items),
            "claims": [claim for item in items for claim in item["claims"]],
            "resolution": None,  # 冲突记录保留双方主张；裁定只能来自用户审批
        }
        for group, items in sorted(conflict_groups.items())
    ]
    return buckets


def build_merge_payload(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    """MergeCandidate payload（summary+sources 对齐 validate_artifact_payload 的 required keys）。"""
    buckets = categorize_reviews(reviews)
    summary = (
        f"Merge of {len(reviews)} reviews: "
        f"{len(buckets['agreements'])} agreement, {len(buckets['conflicts'])} conflict group, "
        f"{len(buckets['unsupported'])} unsupported, {len(buckets['accepted'])} accepted."
    )
    return {
        "summary": summary,
        "sources": sorted(str(review["id"]) for review in reviews),
        "artifact_ids": sorted({str(review["artifact_id"]) for review in reviews}),
        **buckets,
    }


# --- 冲突接线：review_swarm.detect_conflicts 语义的持久化 ---


def _conflict_slug(run_id: str, evidence_key: str) -> str:
    """确定性冲突组 slug：同一 run 同一证据的矛盾评审复用同组（重跑幂等）。"""
    return f"cg-{hashlib.sha256(f'{run_id}|{evidence_key}'.encode()).hexdigest()[:12]}"


def _row_findings(row: AgentReviewModel) -> list[Finding]:
    """评审行 → detect_conflicts 输入（无主张或无证据的行不参与，PASS 行天然不冲突）。"""
    snapshot = snapshot_review(row)
    findings: list[Finding] = []
    for claim in snapshot["claims"]:
        message = str(claim.get("finding", "")).strip() if isinstance(claim, dict) else ""
        if not message:
            continue
        for span in snapshot["evidence"]:
            if isinstance(span, dict):
                key = _span_key(span)
                if key:
                    findings.append(Finding(reviewer=row.reviewer_role, message=message, evidence=key))
    return findings


def wire_conflicts(run_id: str, rows: list[AgentReviewModel]) -> None:
    """对一批评审行（既有 + 新增）执行冲突接线：同证据不同结论 → 双方 CONFLICT + 共享 slug。"""
    tagged = [(finding, row) for row in rows for finding in _row_findings(row)]
    row_by_finding = {id(finding): row for finding, row in tagged}
    for left, right in detect_conflicts([finding for finding, _ in tagged]):
        pair = {row_by_finding[id(left)], row_by_finding[id(right)]}
        if len(pair) < 2:
            continue  # 同一评审内部矛盾不成组（避免单方冲突组）
        slug = _conflict_slug(run_id, str(left.evidence))
        for row in pair:
            row.conflict_group = slug
            row.status = "CONFLICT"


# --- 评审 handler ---


def _review_user_prompt(role: str, task_key: str, run: dict[str, Any], artifacts: list[dict[str, Any]]) -> str:
    from proseforge.application.agents.prompts import JSON_OUTPUT_INSTRUCTION

    lines = [
        f"任务：{task_key}（角色 {role}）",
        f"写作目标摘要：{str(run.get('goal_hash', ''))[:12]}",
        "评审对象（上游 Artifact；evidence_spans 的 artifact_id 必须取自下列 id）：",
    ]
    for item in artifacts:
        lines.append(f"- artifact_id={item.get('id', '')} [{item.get('artifact_type', '')}] {item.get('task_key', '')}: {item.get('preview', '')}")
    lines.append("逐条输出 findings：每条给出 verdict；有证据时填 evidence_spans（quote 对应原文片段），无证据时 verdict=UNSUPPORTED 且 evidence_spans 为空。")
    lines.append(JSON_OUTPUT_INSTRUCTION)
    return "\n".join(lines)


async def _run_reviewer(role: str, context: TaskContext) -> RoleResult:
    policy.authorize(role, "create_artifact")  # fail-closed；PolicyDenied 由 executor 置任务 FAILED 并留 policy.denied
    task = context["task"]
    run = context["run"]
    assert isinstance(task, dict) and isinstance(run, dict)
    run_id, task_key = str(run["id"]), str(task["task_key"])
    artifacts = [item for item in context.get("artifacts", []) if isinstance(item, dict)]
    report_type, findings_key = REVIEWER_REPORT_TYPES[role]

    # 模型调用在任何数据库事务之外
    from proseforge.application.agents.prompts import prompt_for_role

    output, (input_tokens, output_tokens, used_tokens) = await stream_model_json(
        context,
        system_prompt=prompt_for_role(role),
        user_prompt=_review_user_prompt(role, task_key, run, artifacts),
    )
    findings = _normalize_findings(output)
    summary = str(output.get("summary", ""))[:2000]

    # findings 按目标 artifact 归组；幻觉 id / 无目标的归入第一个上游 artifact（确定性，通常即唯一被审稿）
    by_artifact: dict[str, list[dict[str, Any]]] = {str(item.get("id", "")): [] for item in artifacts}
    fallback_id = str(artifacts[0].get("id", "")) if artifacts else ""
    for finding in findings:
        target = finding["target_artifact_id"]
        if not target:
            target = next((str(span["artifact_id"]) for span in finding["evidence_spans"] if span.get("artifact_id") in by_artifact), None)
        if target not in by_artifact:
            target = fallback_id
        if target:
            by_artifact[target].append(finding)

    per_artifact: list[dict[str, Any]] = []
    for item in artifacts:
        artifact_id = str(item.get("id", ""))
        related = by_artifact.get(artifact_id, [])
        spans = [span for finding in related for span in finding["evidence_spans"]][:MAX_EVIDENCE_SPANS]
        if not related:
            # PASS 也必须带证据（服务端规则：仅 UNSUPPORTED 允许空证据）——引用被审 artifact 本身
            status, evidence = "PASS", [{"artifact_id": artifact_id, "start": 0, "end": 0, "quote": str(item.get("preview", ""))[:120], "note": "no findings"}]
        elif spans:
            status, evidence = "WARNING", spans
        else:
            status, evidence = "UNSUPPORTED", []
        per_artifact.append({
            "artifact_id": artifact_id,
            "status": status,
            "evidence": evidence,
            "claims": [{"finding": finding["finding"], "severity": finding["severity"]} for finding in related],
        })

    uow_factory = context["uow_factory"]
    assert callable(uow_factory)
    async with uow_factory() as uow:
        existing = list(await uow.session.scalars(select(AgentReviewModel).where(AgentReviewModel.run_id == run_id)))
        by_key = {(row.artifact_id, row.reviewer_role): row for row in existing}
        new_rows: list[AgentReviewModel] = []
        for entry in per_artifact:
            if (entry["artifact_id"], role) in by_key:
                continue  # 幂等：同 (artifact, reviewer) 复用已落库行，任务重试/重投不重复建行
            row = AgentReviewModel(
                id=new_id(),
                run_id=run_id,
                artifact_id=entry["artifact_id"],
                reviewer_role=role,
                status=entry["status"],
                evidence=json.dumps(entry["evidence"], ensure_ascii=False),
                payload=json.dumps({"claims": entry["claims"], "resolution": None}, ensure_ascii=False),
            )
            uow.session.add(row)
            by_key[(entry["artifact_id"], role)] = row
            new_rows.append(row)
        wire_conflicts(run_id, [*existing, *new_rows])
        await uow.commit()

    review_rows = [by_key[(entry["artifact_id"], role)] for entry in per_artifact]
    verdict = max((row.status for row in review_rows), key=lambda item: _STATUS_RANK.get(item, 0), default="UNSUPPORTED")
    return RoleResult(
        artifact_type="report",  # RolePolicy allowlist 仅 report/candidate；report_type 承载类型化报告名
        payload={
            "report_type": report_type,
            "summary": summary or f"{role} reviewed {len(artifacts)} artifacts.",
            findings_key: findings,
            "review_ids": [row.id for row in review_rows],
            "verdict": verdict,
        },
        used_tokens=used_tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        extra_events=[
            {"event": "review.committed", "review_id": row.id, "artifact_id": row.artifact_id, "reviewer_role": role, "status": row.status, "conflict_group": row.conflict_group}
            for row in new_rows
        ],
    )


def _make_reviewer_handler(role: str) -> Callable[[TaskContext], Awaitable[RoleResult]]:
    async def handler(context: TaskContext) -> RoleResult:
        return await _run_reviewer(role, context)

    handler.__name__ = f"{role}_handler"
    return handler


for _role in REVIEWER_REPORT_TYPES:
    register_role(_role)(_make_reviewer_handler(_role))


@register_role("merge_editor")
async def merge_editor_handler(context: TaskContext) -> RoleResult:
    """merge_editor：本 run 已落库评审 → 四桶分类 MergeCandidate；不改写作者正文，不调模型。"""
    policy.authorize("merge_editor", "create_artifact")
    run = context["run"]
    assert isinstance(run, dict)
    run_id = str(run["id"])
    uow_factory = context["uow_factory"]
    assert callable(uow_factory)
    async with uow_factory() as uow:
        reviews = [snapshot_review(row) for row in await uow.session.scalars(select(AgentReviewModel).where(AgentReviewModel.run_id == run_id))]
    payload = build_merge_payload(reviews)
    return RoleResult(
        artifact_type="candidate",
        payload=payload,
        extra_events=[{"event": "merge.committed", "run_id": run_id, "review_count": len(reviews), **{key: len(payload[key]) for key in _MERGE_BUCKETS}}],
    )
