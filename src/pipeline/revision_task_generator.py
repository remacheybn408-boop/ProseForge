#!/usr/bin/env python3
"""revision_task_generator.py — 修改任务生成器

把 final_submission_report 或去重报告中的 Top 问题转成 revision_tasks.json。
只生成任务，不改文，也不直接调用改写器。默认只保留 Top 5，置信度 < 0.70 不进入。

任务类型与 must_keep/avoid 优先复用 report_deduplicator.ISSUE_CATEGORIES（按 merged_issue
标签反查类别）；标签不在表中的报告格式（top_revision_tasks/flags）退回中文关键词推断。
这些 merged issue 多为**章节级**风格问题，不再伪造段落定位——改写卡按章节尺度呈现。
"""
import re
from version import get_version
from src.pipeline.report_deduplicator import ISSUE_CATEGORIES


def count_chinese(text: str) -> int:
    return len([c for c in text if '一' <= c <= '鿿'])


def split_paragraphs(text: str) -> list[str]:
    """按空行分段，返回段落列表"""
    return [p.strip() for p in text.split("\n") if p.strip()]


# ── 类别 → task_type / 差异化 guidance（复用 dedup 已有类别，避免再抽中文关键词）──
_LABEL_TO_CAT = {info["label"]: cat for cat, info in ISSUE_CATEGORIES.items()}

_CAT_TO_TASKTYPE = {
    "ABSTRACT_OVERUSE": "ADD_CONCRETE_DETAILS",
    "DIALOGUE_SAMENESS": "IMPROVE_DIALOGUE",
    "RHYTHM_FLATNESS": "VARY_SENTENCE_STRUCTURE",
    "MISSING_COST": "ADD_SCENE_COST",
    "OVER_EXPLAINED": "REDUCE_OVER_EXPLANATION",
    "CLASSICAL_MISUSE": "ADJUST_REGISTER",
}

_BASELINE_KEEP = [
    "不改变章节主线",
    "保留作者风格和角色口吻",
    "保留章节结尾钩子",
]
_BASELINE_AVOID = [
    "不要扩写成水文",
    "不要用总结句替代动作",
    "不要为了满足门禁改坏角色口吻",
]
_CAT_GUIDANCE = {
    "ADD_CONCRETE_DETAILS": {
        "keep": ["保留原有信息密度"],
        "avoid": ["不要空喊情绪或危机", "不要堆砌无意义的细节"],
    },
    "IMPROVE_DIALOGUE": {
        "keep": ["保留对白原意与信息"],
        "avoid": ["不要删除停顿、误会、话没说完"],
    },
    "VARY_SENTENCE_STRUCTURE": {
        "keep": ["保留段落原意"],
        "avoid": ["不要为变化句式牺牲清晰度"],
    },
    "ADD_SCENE_COST": {
        "keep": ["保留情节因果链"],
        "avoid": ["不要空喊代价，要落到具体损失"],
    },
    "REDUCE_OVER_EXPLANATION": {
        "keep": ["只删冗余解释，保留读者必需信息"],
        "avoid": ["不要删掉关键设定或情节信息"],
    },
    "ADJUST_REGISTER": {
        "keep": ["保留人物语体一致性"],
        "avoid": ["不要把文言一刀切删净"],
    },
}


def _infer_type_by_keyword(problem: str) -> str:
    """兜底：标签不在 ISSUE_CATEGORIES 时按中文关键词粗判 task_type。"""
    if "物件" in problem or "锚点" in problem or "动作" in problem:
        return "ADD_CONCRETE_DETAILS"
    if "代价" in problem or "损失" in problem or "因果" in problem:
        return "ADD_SCENE_COST"
    if "对白" in problem or "口吻" in problem or "称呼" in problem:
        return "IMPROVE_DIALOGUE"
    if "重复" in problem or "句式" in problem or "节奏" in problem:
        return "VARY_SENTENCE_STRUCTURE"
    if "解释" in problem or "留白" in problem or "初稿" in problem:
        return "REDUCE_OVER_EXPLANATION"
    return "REWRITE_RANGE"


def _classify(problem: str) -> tuple[str, str]:
    """返回 (category, task_type)。优先标签反查类别，否则关键词兜底（category=UNCATEGORIZED）。"""
    cat = _LABEL_TO_CAT.get(problem.strip())
    if cat:
        return cat, _CAT_TO_TASKTYPE.get(cat, "REWRITE_RANGE")
    return "UNCATEGORIZED", _infer_type_by_keyword(problem)


def _guidance_for(task_type: str) -> tuple[list, list]:
    """组装 must_keep/avoid：baseline + 类别特异项（去重保序）。"""
    extra = _CAT_GUIDANCE.get(task_type, {"keep": [], "avoid": []})
    keep = list(dict.fromkeys(_BASELINE_KEEP + extra["keep"]))
    avoid = list(dict.fromkeys(_BASELINE_AVOID + extra["avoid"]))
    return keep, avoid


def generate_tasks(chapter_text: str, report: dict,
                   min_confidence: float = 0.70,
                   max_tasks: int = 5) -> dict:
    """从报告中提取 Top 修改任务（章节尺度，不带段落定位）。"""
    # 提取问题列表
    issues = []
    if "top_revision_tasks" in report:
        issues = report["top_revision_tasks"]
    elif "merged_issues" in report:
        issues = report["merged_issues"]
    elif "flags" in report:
        issues = report["flags"]

    # 过滤低置信度
    filtered = [i for i in issues
                if i.get("confidence", 0.5) >= min_confidence]
    top = filtered[:max_tasks]

    tasks = []
    for idx, issue in enumerate(top):
        problem = issue.get("merged_issue") or issue.get("issue") or issue.get("message", "")
        fix = issue.get("revision_task") or issue.get("fix") or issue.get("suggestion", "")

        category, task_type = _classify(problem)
        must_keep, avoid = _guidance_for(task_type)

        task = {
            "task_id": f"rev_{idx+1:03d}",
            "priority": idx + 1,
            "type": task_type,
            "category": category,
            "confidence": round(issue.get("confidence", 0.7), 2),
            "problem": problem[:100],
            "instruction": fix[:200],
            "must_keep": must_keep,
            "avoid": avoid,
        }
        # 原始 flag 自带 evidence 例句就透传（有则给，没有不编）
        evidence = issue.get("evidence")
        if evidence:
            task["evidence"] = evidence if isinstance(evidence, list) else [str(evidence)]
        tasks.append(task)

    chapter_no = report.get("chapter_no", 0)
    return {
        "version": get_version(),
        "chapter_no": chapter_no,
        "source_file": "",
        "task_count": len(tasks),
        "tasks": tasks,
        "message": f"生成 {len(tasks)} 个可执行改稿任务。" if tasks
                   else "没有足够高置信度的可执行改稿任务。",
    }
