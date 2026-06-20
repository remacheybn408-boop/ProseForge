#!/usr/bin/env python3
"""
_cluster_aggregator.py — L2 聚合 guard 共享逻辑 v0.8.0

5 个新 L2 聚合 guard（scene_grounding / narrative_rhythm / dialogue_quality /
prose_authenticity / reader_engagement）的公共聚合器。

设计仿照 src/guards/human_texture/__init__.py:run_human_texture_guards：
- 子检测顺序调用、各自独立返回
- 输出保留每个子项的 status/score/findings
- 对外暴露 _guards_raw 供 final_submission_report 下钻
"""

from typing import Callable, List, Tuple


def _status_to_score(status: str) -> int:
    """没有 score 字段时的 fallback：把 status 映射成数字。"""
    s = (status or "PASS").upper()
    if s == "PASS":
        return 100
    if s in ("WARN", "WARNING", "NEED_REVISION"):
        return 60
    if s in ("FAIL", "BLOCK", "BLOCKED"):
        return 30
    return 80


def _normalize_status(s: str) -> str:
    """把混乱的 status 字符串收敛到 PASS / WARNING / FAIL。"""
    s = (s or "PASS").upper()
    if s == "PASS":
        return "PASS"
    if s in ("FAIL", "BLOCK", "BLOCKED"):
        return "FAIL"
    return "WARNING"


def _run_subcheck(name: str, fn: Callable, *args, **kwargs) -> dict:
    """安全调用子检测：异常包成 WARNING，不让一颗老鼠屎拖垮整盘。"""
    try:
        raw = fn(*args, **kwargs)
        if isinstance(raw, tuple):
            raw = raw[0]
        if not isinstance(raw, dict):
            raw = {"status": "PASS"}
        raw.setdefault("guard", name)
        return raw
    except Exception as e:
        return {
            "guard": name,
            "status": "WARNING",
            "error": str(e),
            "findings": [{
                "code": f"{name}_CRASH",
                "message": f"子检测 {name} 异常: {e}",
                "severity": "WARN",
            }],
            "score": 60,
        }


def aggregate_cluster(
    cluster_name: str,
    sub_results: List[dict],
    chapter_no: int,
    metrics: dict = None,
) -> dict:
    """
    把多个子检测的结果聚合成一个 L2 guard 的对外 dict。

    返回字段：
    - guard: 聚合 guard 名（如 "scene_grounding_guard"）
    - status: PASS / WARNING（L2 不出 FAIL）
    - score: 子项分数平均
    - flags: 收拢的 flag 列表（每条带 source 子名）
    - issues: 收拢的 issue 列表（同上）
    - sub_scores: {子名: 分数}
    - sub_statuses: {子名: status}
    - _guards_raw: 原始子结果，供 final_submission_report 下钻
    - chapter_no, metrics
    """
    sub_results = [r for r in sub_results if r is not None]

    sub_scores = {}
    sub_statuses = {}
    flags = []
    issues = []

    for r in sub_results:
        name = r.get("guard", "?")
        status = _normalize_status(r.get("status"))
        sub_statuses[name] = status

        score = r.get("score")
        if score is None:
            score = _status_to_score(status)
        sub_scores[name] = score

        # 收拢 flags（兼容 findings/flags/issues 三种字段名）
        for f in r.get("flags", []) or []:
            if isinstance(f, dict):
                f = dict(f)
                f.setdefault("source", name)
                flags.append(f)

        for f in r.get("findings", []) or []:
            if isinstance(f, dict):
                f = dict(f)
                f.setdefault("source", name)
                flags.append(f)

        for i in r.get("issues", []) or []:
            if isinstance(i, dict):
                i = dict(i)
                i.setdefault("source", name)
                issues.append(i)

    # 聚合 status：任一 FAIL→FAIL（L2 会被 registry 强降级），任一 WARNING→WARNING
    if any(s == "FAIL" for s in sub_statuses.values()):
        overall_status = "FAIL"
    elif any(s == "WARNING" for s in sub_statuses.values()):
        overall_status = "WARNING"
    else:
        overall_status = "PASS"

    overall_score = (sum(sub_scores.values()) // len(sub_scores)) if sub_scores else 100

    out = {
        "guard": cluster_name,
        "status": overall_status,
        "score": overall_score,
        "flags": flags,
        "issues": issues,
        "sub_scores": sub_scores,
        "sub_statuses": sub_statuses,
        "_guards_raw": sub_results,
        "chapter_no": chapter_no,
    }
    if metrics:
        out["metrics"] = metrics
    return out


def safe_run(name: str, fn: Callable, *args, **kwargs) -> dict:
    """导出名，供 5 个聚合 guard 调用。"""
    return _run_subcheck(name, fn, *args, **kwargs)
