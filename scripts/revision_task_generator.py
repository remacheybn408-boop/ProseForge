#!/usr/bin/env python3
"""
revision_task_generator.py — 修改任务生成器 v0.4.0

把 final_submission_report 或去重报告中的 Top 问题转成可执行改稿任务。
只生成 Top 5，置信度 < 0.70 不进入。

用法:
  python scripts/revision_task_generator.py \\
    --input chapter.txt --report final_report.json --out tasks.json
"""
import re, json, sys, argparse
from pathlib import Path
from typing import Optional


def count_chinese(text: str) -> int:
    return len([c for c in text if '\u4e00' <= c <= '\u9fff'])


def split_paragraphs(text: str) -> list[str]:
    """按空行分段，返回段落列表"""
    return [p.strip() for p in text.split("\n") if p.strip()]


def find_paragraph_range(chapter: str, target_issue: str) -> dict:
    """
    根据问题描述粗略定位段落范围。
    如果无法定位，返回空范围让人类指定。
    """
    paras = split_paragraphs(chapter)
    if not paras:
        return {"paragraph_start": 1, "paragraph_end": 1}

    keywords = re.findall(r'[\u4e00-\u9fff]{2,4}', target_issue)
    for i, p in enumerate(paras):
        matches = sum(1 for kw in keywords if kw in p)
        if matches >= 2:
            return {"paragraph_start": i + 1, "paragraph_end": min(i + 4, len(paras))}

    # Default: middle section
    mid = len(paras) // 2
    return {"paragraph_start": max(1, mid - 1), "paragraph_end": min(len(paras), mid + 2)}


def generate_tasks(chapter_text: str, report: dict,
                   min_confidence: float = 0.70,
                   max_tasks: int = 5) -> dict:
    """从报告中提取 Top 修改任务"""
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

    # 最多取 N 个
    top = filtered[:max_tasks]

    tasks = []
    for idx, issue in enumerate(top):
        problem = issue.get("merged_issue") or issue.get("issue") or issue.get("message", "")
        fix = issue.get("revision_task") or issue.get("fix") or issue.get("suggestion", "")

        # 尝试定位段落
        target_range = find_paragraph_range(chapter_text, problem)

        # 判断任务类型
        task_type = "REWRITE_RANGE"
        if "物件" in problem or "锚点" in problem or "动作" in problem:
            task_type = "ADD_CONCRETE_DETAILS"
        elif "代价" in problem or "损失" in problem or "因果" in problem:
            task_type = "ADD_SCENE_COST"
        elif "对白" in problem or "口吻" in problem or "称呼" in problem:
            task_type = "IMPROVE_DIALOGUE"
        elif "重复" in problem or "句式" in problem or "节奏" in problem:
            task_type = "VARY_SENTENCE_STRUCTURE"
        elif "解释" in problem or "留白" in problem or "初稿" in problem:
            task_type = "REDUCE_OVER_EXPLANATION"

        tasks.append({
            "task_id": f"rev_{idx+1:03d}",
            "priority": idx + 1,
            "type": task_type,
            "confidence": round(issue.get("confidence", 0.7), 2),
            "target_range": target_range,
            "problem": problem[:100],
            "instruction": fix[:200],
            "must_keep": [
                "不改变章节主线",
                "不新增无关角色",
                "不解释世界观",
                "保留作者风格和角色口吻",
                "保留章节结尾钩子",
            ],
            "avoid": [
                "不要空喊危机来了",
                "不要扩写成水文",
                "不要用总结句替代动作",
                "不要为了满足门禁改坏角色口吻",
                "不要删除停顿、误会、话没说完",
            ],
        })

    chapter_no = report.get("chapter_no", 0)
    return {
        "version": "v0.4.0",
        "chapter_no": chapter_no,
        "source_file": "",
        "task_count": len(tasks),
        "tasks": tasks,
        "message": f"生成 {len(tasks)} 个可执行改稿任务。" if tasks
                   else "没有足够高置信度的可执行改稿任务。",
    }


def main():
    parser = argparse.ArgumentParser(description="Revision Task Generator")
    parser.add_argument("--input", required=True, help="章节 TXT")
    parser.add_argument("--report", required=True, help="final_submission_report.json 或 deduplicated_report.json")
    parser.add_argument("--out", required=True, help="输出 revision_tasks.json")
    parser.add_argument("--min-confidence", type=float, default=0.70)
    parser.add_argument("--max-tasks", type=int, default=5)
    args = parser.parse_args()

    chapter = Path(args.input).read_text(encoding="utf-8")
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))

    tasks = generate_tasks(chapter, report, args.min_confidence, args.max_tasks)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] {tasks['task_count']} revision tasks → {args.out}")


if __name__ == "__main__":
    main()
