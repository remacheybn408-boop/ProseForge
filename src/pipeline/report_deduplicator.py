#!/usr/bin/env python3
"""
report_deduplicator.py — 门禁报告去重与合并

把多个门禁报的同类问题合并成一条修改任务。
例如: anti_ai + show_dont_tell + concrete_anchor + qgp
      都指向 "抽象总结过多，具体锚点不足" → 合并为一条。

用法:
  from report_deduplicator import deduplicate_warnings
  merged = deduplicate_warnings(warnings_list)
"""
import json, sys, statistics, argparse
from pathlib import Path
from collections import defaultdict
from typing import List, Dict
from version import get_version


# ═══════════════════════════════════════════════════
# 问题类别定义
# ═══════════════════════════════════════════════════

ISSUE_CATEGORIES = {
    "ABSTRACT_OVERUSE": {
        "keywords": [" ABSTRACT", " SUMMARY", " TELL", " ANCHOR",
                     "LOW_SURPRISE", "TEMPLATE", "抽象", "总结", "锚点",
                     "概念", "情绪"],
        # v0.8.0：含旧子检测名 + 新 L2 聚合名
        "sources": ["anti_ai_guard", "show_dont_tell_guard",
                    "concrete_anchor_guard", "perplexity_quality_guard",
                    "padding_guard",
                    "prose_authenticity_guard", "scene_grounding_guard",
                    "dialogue_quality_guard"],
        "label": "抽象总结过多，具体锚点不足",
        "fix": "把抽象总结改成具体动作、物件、停顿、误会或代价。",
    },
    "DIALOGUE_SAMENESS": {
        "keywords": ["DIALOGUE", "VOICE", " VARIATION", " NATURALNESS",
                     "对白", "角色", "口吻", "称呼"],
        "sources": ["character_voice_guard", "dialogue_structure_guard",
                    "dialogue_beat_guard", "style_variation_guard",
                    "dialogue_quality_guard"],
        "label": "对白缺乏角色辨识度",
        "fix": "让不同角色在句长、称呼、语气词、口头禅上有差异。",
    },
    "RHYTHM_FLATNESS": {
        "keywords": ["FLATNESS", "RHYTHM", "OPENING_REPETITION",
                     "REVISION_TEXTURE", "节奏", "平坦", "重复"],
        "sources": ["style_variation_guard", "editor_revision_guard",
                    "perplexity_quality_guard",
                    "narrative_rhythm_guard", "reader_engagement_guard"],
        "label": "文本节奏偏平，句式缺乏变化",
        "fix": "变化段落长度和句长，加入短句和碎片句打破平均节奏。",
    },
    "MISSING_COST": {
        "keywords": ["COST", "CAUSALITY", " RESULT", "BEAT",
                     "代价", "因果", "损失", "付出"],
        "sources": ["scene_causality_guard", "dialogue_beat_guard",
                    "scene_grounding_guard", "dialogue_quality_guard"],
        "label": "场景缺少明确代价",
        "fix": "每场关键冲突后加入可见损失：物件破损、关系恶化、身体受伤。",
    },
    "CLASSICAL_MISUSE": {
        "keywords": ["WENYAN", "CLASSICAL", "REGISTER",
                     "文言", "古雅", "语体"],
        "sources": ["classical_register_guard", "character_voice_guard",
                    "prose_authenticity_guard", "dialogue_quality_guard"],
        "label": "文言使用不当或密度过高",
        "fix": "检查文言是否在合适的角色/场景中使用，避免影响可读性。",
    },
    "OVER_EXPLAINED": {
        "keywords": ["OVER_EXPLAINED", "REVISION_TEXTURE",
                     "EDITOR_REVISION", "初稿", "解释过满"],
        "sources": ["editor_revision_guard", "anti_ai_guard", "padding_guard",
                    "narrative_rhythm_guard", "prose_authenticity_guard",
                    "reader_engagement_guard"],
        "label": "部分段落解释过满，缺少留白",
        "fix": "删掉部分解释句，让读者自己体会。增加动作和物件代替解释。",
    },
}


def _flag_type(flag: dict) -> str:
    """flag 类型码：兼容旧 'type' 与 v0.8.0 finding 的 'code'"""
    return (flag.get("type") or flag.get("code") or "").upper()


def _flag_source(flag: dict) -> str:
    """flag 来源 guard：兼容 'source_guard' / 'guard' / 'source'

    注意：v0.8.0 走 `GuardSummary.get_warnings()` 时 `guard` 是 L2 聚合名（如
    prose_authenticity_guard），子检测身份在 `_adapt_legacy_dict` 中已经丢了。
    所以 ISSUE_CATEGORIES.sources 必须同时收纳旧子检测名和新聚合名。
    """
    return (flag.get("source_guard")
            or flag.get("guard")
            or flag.get("source")
            or "")


def classify_warning(flag: dict) -> str:
    """根据 flag 的 type/code 和 source/guard 分类

    ftype 同时按原值和"下划线→空格"两种形态匹配，所以 ' ABSTRACT' 这种带前导空格
    的边界关键词能命中 'ABSTRACT_OVERUSE_DETECTED' 这种位于开头的 code。
    """
    raw = _flag_type(flag)
    padded = " " + raw.replace("_", " ") + " "
    msg = (flag.get("message") or "").upper()
    source = _flag_source(flag)

    for cat_name, cat in ISSUE_CATEGORIES.items():
        if source in cat["sources"]:
            for kw in cat["keywords"]:
                if kw in raw or kw in padded or kw in msg:
                    return cat_name
    return "UNCATEGORIZED"


def deduplicate_warnings(warnings: List[dict],
                         min_confidence: float = 0.55) -> List[dict]:
    """合并同类 WARNING，过滤低置信度"""
    if not warnings:
        return []

    # 过滤低置信度
    filtered = [w for w in warnings
                if w.get("confidence", 0.5) >= min_confidence]

    # 按类别分组
    groups = defaultdict(list)
    for w in filtered:
        cat = classify_warning(w)
        groups[cat].append(w)

    merged = []
    for cat, group in groups.items():
        if cat == "UNCATEGORIZED":
            # 未分类的各自保留（去重）
            seen = set()
            for w in group:
                key = _flag_type(w) + _flag_source(w)
                if key not in seen:
                    seen.add(key)
                    src = _flag_source(w) or "unknown"
                    merged.append({
                        "merged_issue": w.get("message", str(w)),
                        "severity": "low",
                        "confidence": w.get("confidence", 0.5),
                        "reported_by": [src],
                        "revision_task": w.get("message", ""),
                        "type": "single",
                    })
        else:
            info = ISSUE_CATEGORIES[cat]
            confidences = [w.get("confidence", 0.5) for w in group]
            avg_conf = statistics.mean(confidences) if confidences else 0.5

            # 需要至少 2 个来源或 confidence > 0.7
            sources = list(set(_flag_source(w) for w in group if _flag_source(w)))
            if len(sources) >= 2 or avg_conf > 0.7:
                merged.append({
                    "merged_issue": info["label"],
                    "severity": "medium" if avg_conf > 0.7 else "low",
                    "confidence": round(avg_conf, 2),
                    "reported_by": sources,
                    "revision_task": info["fix"],
                    "type": "merged",
                })

    # 按置信度排序
    merged.sort(key=lambda x: x["confidence"], reverse=True)
    return merged


def get_top_revision_tasks(merged_issues: List[dict],
                           max_tasks: int = 5) -> List[dict]:
    """取 Top N 修改任务，附 why/fix"""
    top = merged_issues[:max_tasks]
    tasks = []
    for i, issue in enumerate(top):
        tasks.append({
            "rank": i + 1,
            "issue": issue["merged_issue"],
            "why_it_matters": f"{len(issue['reported_by'])} 个门禁共同发现此问题"
                              if len(issue.get("reported_by", [])) > 1
                              else "门禁检测到潜在质量风险",
            "fix": issue["revision_task"],
            "confidence": issue["confidence"],
            "reported_by": issue.get("reported_by", []),
        })
    return tasks


# ═══════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════

