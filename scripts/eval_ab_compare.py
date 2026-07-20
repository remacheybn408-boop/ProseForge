"""A/B 评估对比（蓝图 V3-008 release rule）。

用法::

    python scripts/eval_ab_compare.py --run-a <run_id> --run-b <run_id>

从数据库载入两个 run 的 Artifact/评审/已批准记忆，归一化对比范围后对两边
各算一次确定性 rubric（v3-rubric-1），应用发布规则：V3 优于基线当且仅当
continuity/character/plot_causality 三维均值 ≥ run A 且无一维低 > 0.5，
同时 cost 增幅 ≤ 40%、latency 增幅 ≤ 60%。只输出哈希与分数（绝不打印正文），
并把对比结果写入/更新一行 ``agent_evaluations``（run_id = run B）。

导入本模块无副作用：重量级 proseforge 依赖全部在 ``_compare`` 内延迟导入，
``--help`` 不触碰数据库与 settings。
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

CORE_DIMENSIONS: tuple[str, ...] = ("continuity", "character", "plot_causality")
COST_TOLERANCE = 1.4  # 发布规则：cost 增幅 ≤ 40%
LATENCY_TOLERANCE = 1.6  # 发布规则：latency 增幅 ≤ 60%


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two agent runs with the deterministic V3 rubric (redacted aggregates only).")
    parser.add_argument("--run-a", required=True, help="Baseline run id (run A).")
    parser.add_argument("--run-b", required=True, help="Candidate run id (run B / V3).")
    return parser.parse_args(argv)


def _extract_text(payload: object) -> list[str]:
    """确定性抽取 Artifact payload 内的文本片段（排序键、递归）；只用于打分，绝不输出。"""
    if isinstance(payload, str):
        return [payload]
    if isinstance(payload, dict):
        parts: list[str] = []
        for key in sorted(payload):
            parts.extend(_extract_text(payload[key]))
        return parts
    if isinstance(payload, list):
        parts = []
        for item in payload:
            parts.extend(_extract_text(item))
        return parts
    return []


async def _load_bundle(session, run_id: str) -> dict[str, object]:
    from sqlalchemy import select

    from proseforge.application.agents.memory_service import decode_value
    from proseforge.infrastructure.database.models.agents import (
        AgentArtifactModel,
        AgentEvaluationModel,
        AgentMemoryModel,
        AgentReviewModel,
        AgentRunModel,
    )

    run = await session.scalar(select(AgentRunModel).where(AgentRunModel.id == run_id))
    if run is None:
        raise SystemExit(f"run not found: {run_id}")
    artifacts = list(await session.scalars(select(AgentArtifactModel).where(AgentArtifactModel.run_id == run_id).order_by(AgentArtifactModel.id)))
    reviews = list(await session.scalars(select(AgentReviewModel).where(AgentReviewModel.run_id == run_id).order_by(AgentReviewModel.id)))
    memories = list(
        await session.scalars(
            select(AgentMemoryModel).where(AgentMemoryModel.project_id == run.project_id, AgentMemoryModel.status == "ACCEPTED").order_by(AgentMemoryModel.id)
        )
    )
    evaluations = list(await session.scalars(select(AgentEvaluationModel).where(AgentEvaluationModel.run_id == run_id).order_by(AgentEvaluationModel.id)))
    return {
        "run": run,
        "artifacts": [
            {"id": row.id, "artifact_type": row.artifact_type, "sha256": row.sha256, "text": "\n".join(_extract_text(json.loads(row.payload)))}
            for row in artifacts
        ],
        "reviews": [
            {"finding": row.conflict_group or row.status, "evidence": json.loads(row.evidence)}
            for row in reviews
        ],
        "facts": [f"{row.memory_key}:{decode_value(row)['value']}" for row in memories],
        "evaluation_ids": [row.id for row in evaluations],
        "budget_used": int(run.budget_used),
        # 偏差说明：事件/任务表无时间戳列，无法取 p95；以 run 墙钟时长作延迟样本
        "duration_ms": max(0, int((run.updated_at - run.created_at).total_seconds() * 1000)),
    }


def _normalize_scope(bundle_a: dict[str, object], bundle_b: dict[str, object]) -> None:
    """只对比两边都存在的 Artifact 类型（原地过滤，顺序按 id 确定）。"""
    types_a = {artifact["artifact_type"] for artifact in bundle_a["artifacts"]}  # type: ignore[index]
    types_b = {artifact["artifact_type"] for artifact in bundle_b["artifacts"]}  # type: ignore[index]
    shared = types_a & types_b
    bundle_a["artifacts"] = [artifact for artifact in bundle_a["artifacts"] if artifact["artifact_type"] in shared]  # type: ignore[index]
    bundle_b["artifacts"] = [artifact for artifact in bundle_b["artifacts"] if artifact["artifact_type"] in shared]  # type: ignore[index]


def _score_bundle(bundle: dict[str, object], *, baseline: dict[str, object] | None) -> dict[str, object]:
    from proseforge.application.agents.evaluation import score_rubric

    text = "\n".join(str(artifact["text"]) for artifact in bundle["artifacts"])  # type: ignore[index]
    cost = {"budget_used": bundle["budget_used"], "duration_ms": bundle["duration_ms"]}
    if baseline is not None:
        cost["baseline_budget_used"] = baseline["budget_used"]
        cost["baseline_duration_ms"] = baseline["duration_ms"]
    return score_rubric(
        text,
        facts=bundle["facts"],  # type: ignore[arg-type]
        reviews=bundle["reviews"],  # type: ignore[arg-type]
        cost=cost,
    )


def _verdict(scores_a: dict[str, object], scores_b: dict[str, object], bundle_a: dict[str, object], bundle_b: dict[str, object]) -> dict[str, object]:
    dims_a, dims_b = scores_a["dimensions"], scores_b["dimensions"]  # type: ignore[assignment]
    mean_a = sum(dims_a[name] for name in CORE_DIMENSIONS) / len(CORE_DIMENSIONS)  # type: ignore[index]
    mean_b = sum(dims_b[name] for name in CORE_DIMENSIONS) / len(CORE_DIMENSIONS)  # type: ignore[index]
    cost_ratio = float(bundle_b["budget_used"]) / max(1, float(bundle_a["budget_used"]))
    latency_ratio = float(bundle_b["duration_ms"]) / max(1, float(bundle_a["duration_ms"]))
    checks = {
        "core_mean_not_lower": mean_b >= mean_a,
        "no_dimension_lower_by_over_half_point": all(dims_b[name] >= dims_a[name] - 0.5 for name in dims_a),  # type: ignore[index]
        "cost_increase_within_40_percent": cost_ratio <= COST_TOLERANCE,
        "latency_increase_within_60_percent": latency_ratio <= LATENCY_TOLERANCE,
    }
    return {
        "v3_better_than_baseline": all(checks.values()),
        "checks": checks,
        "core_mean_a": round(mean_a, 4),
        "core_mean_b": round(mean_b, 4),
        "cost_ratio": round(cost_ratio, 4),
        "latency_ratio": round(latency_ratio, 4),
    }


async def _compare(args: argparse.Namespace) -> int:
    from sqlalchemy import select

    from proseforge.infrastructure.database.models.agents import AgentEvaluationModel
    from proseforge.infrastructure.database.session import create_engine_and_sessionmaker
    from proseforge.settings import get_settings

    engine, session_factory = create_engine_and_sessionmaker(get_settings())
    try:
        async with session_factory() as session:
            bundle_a = await _load_bundle(session, args.run_a)
            bundle_b = await _load_bundle(session, args.run_b)
            _normalize_scope(bundle_a, bundle_b)
            scores_a = _score_bundle(bundle_a, baseline=None)
            scores_b = _score_bundle(bundle_b, baseline=bundle_a)
            verdict = _verdict(scores_a, scores_b, bundle_a, bundle_b)

            artifact_hashes = {
                "run_a": [artifact["sha256"] for artifact in bundle_a["artifacts"]],  # type: ignore[index]
                "run_b": [artifact["sha256"] for artifact in bundle_b["artifacts"]],  # type: ignore[index]
            }
            comparison_hash = hashlib.sha256(
                json.dumps({"run_a": args.run_a, "run_b": args.run_b, **artifact_hashes}, sort_keys=True).encode()
            ).hexdigest()
            comparison_id = "cmp-" + hashlib.sha256(f"{args.run_a}:{args.run_b}".encode()).hexdigest()[:24]
            payload = json.dumps(
                {
                    "kind": "ab_comparison",
                    "rubric_version": scores_b["rubric_version"],
                    "run_a": args.run_a,
                    "run_b": args.run_b,
                    "dimensions_a": scores_a["dimensions"],
                    "dimensions_b": scores_b["dimensions"],
                    "overall_a": scores_a["overall"],
                    "overall_b": scores_b["overall"],
                    "artifact_hashes": artifact_hashes,
                    "verdict": verdict,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            row = await session.scalar(select(AgentEvaluationModel).where(AgentEvaluationModel.id == comparison_id))
            if row is None:
                session.add(AgentEvaluationModel(id=comparison_id, run_id=args.run_b, fixture_hash=comparison_hash, score=int(scores_b["overall"]), payload=payload))
            else:
                row.run_id, row.fixture_hash, row.score, row.payload = args.run_b, comparison_hash, int(scores_b["overall"]), payload
            await session.commit()

            print(json.dumps({"comparison_id": comparison_id, "fixture_hash": comparison_hash, **json.loads(payload)}, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
    finally:
        await engine.dispose()


def main() -> int:
    return asyncio.run(_compare(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
