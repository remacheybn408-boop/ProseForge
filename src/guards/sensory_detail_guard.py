#!/usr/bin/env python3
"""sensory_detail_guard.py — 感官描写浓度检测 v0.7.3

检查章节是否缺乏让读者沉浸的五感描写。
维度: 视觉、听觉、触觉、嗅觉、味觉、动觉（身体感受）词汇密度。

词表统一从 src.utils.sensory_lexicon 引入，与 concrete_anchor_guard 共用。
"""

from src.utils.sensory_lexicon import count_sensory_dimensions as _count_sensory


def _check_sensory_gaps(sensory: dict) -> list:
    """检查缺失的感官维度"""
    issues = []
    missing = [s for s, d in sensory.items() if d["density"] < 0.3]
    threshold = 3

    for s in missing:
        if s in ("味觉", "嗅觉"):
            continue  # 不强求每章都有味道描写

    if len(missing) >= threshold:
        issues.append({
            "code": "SENSORY_GAP",
            "severity": "WARN",
            "message": f"感官描写缺失{len(missing)}个维度({', '.join(missing)})，读者沉浸感不足",
            "suggestion": "每章至少覆盖3种感官：视觉+听觉是基础，再加触觉或动觉。用物件和环境传递感官，不要直接说'他感到'",
            "confidence": 0.7,
            "details": {"missing": missing},
        })

    return issues


def _check_visual_dominance(sensory: dict) -> list:
    """检查是否过度依赖视觉描写"""
    issues = []
    visual = sensory.get("视觉", {}).get("density", 0)
    non_visual = sum(v["density"] for k, v in sensory.items() if k != "视觉")
    if visual > 0 and non_visual > 0 and visual > non_visual * 3:
        issues.append({
            "code": "VISUAL_OVERDOMINANCE",
            "severity": "INFO",
            "message": "视觉描写占比过高，缺少其他感官层次",
            "suggestion": "在关键场景加入听觉（环境音、沉默）、触觉（温度、质感）、动觉（身体反应）",
            "confidence": 0.55,
            "details": {"visual_density": visual, "non_visual_density": round(non_visual, 2)},
        })
    return issues


def run_sensory_detail_check(text: str, chapter_no: int = 0) -> dict:
    """Run sensory detail guard on a chapter."""
    sensory = _count_sensory(text)

    all_issues = []
    all_issues.extend(_check_sensory_gaps(sensory))
    all_issues.extend(_check_visual_dominance(sensory))

    has_warn = any(i["severity"] == "WARN" for i in all_issues)
    has_fail = any(i["severity"] == "FAIL" for i in all_issues)

    # Score (0-100): more sensory dimensions with reasonable density = higher
    dims_above_threshold = sum(1 for d in sensory.values() if d["density"] >= 0.3)
    score = min(100, dims_above_threshold * 16 + 4)

    return {
        "guard": "sensory_detail_guard",
        "status": "PASS" if not has_warn else ("FAIL" if has_fail else "WARN"),
        "chapter_no": chapter_no,
        "issues": all_issues,
        "warnings": [i["message"] for i in all_issues],
        "scores": {k: v["density"] for k, v in sensory.items()},
        "summary": {
            "dimensions_covered": dims_above_threshold,
            "total_score": score,
        },
    }
