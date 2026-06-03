#!/usr/bin/env python3
"""
patch_planner.py — 改稿补丁规划器 v0.4.0

根据 revision_tasks.json 决定改哪里、锁定哪里。
默认锁定章节开头、结尾、伏笔段。改动比例 ≤ 35%。

用法:
  python scripts/patch_planner.py \\
    --input chapter.txt --tasks tasks.json --out patch_plan.json
"""
import re, json, sys, argparse
from pathlib import Path
from typing import List


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n") if p.strip()]


def count_chinese(text: str) -> int:
    return len([c for c in text if '\u4e00' <= c <= '\u9fff'])


def detect_locked_ranges(paragraphs: List[str]) -> list[dict]:
    """自动检测需要锁定的段落"""
    locked = []
    n = len(paragraphs)

    if n == 0:
        return locked

    # 开头 2 段：承接上章
    locked.append({
        "paragraph_start": 1,
        "paragraph_end": min(2, n),
        "reason": "开头承接上一章，不允许改动",
    })

    # 结尾 2 段：章节钩子
    if n >= 2:
        locked.append({
            "paragraph_start": max(1, n - 1),
            "paragraph_end": n,
            "reason": "章节结尾钩子，不允许默认改动",
        })

    # 伏笔段：含"伏笔/线索/揭露/真相/原来"等关键词
    for i, p in enumerate(paragraphs):
        if re.search(r'(伏笔|线索|揭露|真相|原来|其实是|真正的身份)', p):
            locked.append({
                "paragraph_start": i + 1,
                "paragraph_end": i + 1,
                "reason": "伏笔相关段落，不允许改动",
            })

    # 角色口癖强相关：含明确称呼+口癖标记
    for i, p in enumerate(paragraphs):
        if re.search(r'(甭|俺|咋|啥|嘛|哩|咧|呗)', p) and re.search(r'[""「」]', p):
            already = any(l["paragraph_start"] <= i+1 <= l["paragraph_end"] for l in locked)
            if not already:
                locked.append({
                    "paragraph_start": i + 1,
                    "paragraph_end": i + 1,
                    "reason": "角色口癖强相关段落，不允许改动",
                })

    return locked


def build_patch_plan(chapter_text: str, tasks: dict,
                     max_changed_ratio: float = 0.35) -> dict:
    """根据任务生成补丁计划"""
    paragraphs = split_paragraphs(chapter_text)
    n = len(paragraphs)
    locked = detect_locked_ranges(paragraphs)
    task_list = tasks.get("tasks", [])

    patch_ops = []
    for task in task_list:
        tr = task.get("target_range", {})
        start = max(1, tr.get("paragraph_start", 0))
        end = min(n, tr.get("paragraph_end", start))

        # 检查是否与锁定区域冲突
        conflict = False
        for lock in locked:
            if not (end < lock["paragraph_start"] or start > lock["paragraph_end"]):
                conflict = True
                break

        if conflict:
            # 移到锁定区域之外
            start = max(1, min([l["paragraph_end"] + 1 for l in locked
                               if l["paragraph_end"] < n], default=n//2))
            end = min(n, start + 3)

        patch_ops.append({
            "task_id": task["task_id"],
            "operation": "rewrite_range",
            "paragraph_start": start,
            "paragraph_end": end,
            "rewrite_goal": task.get("instruction", ""),
            "preserve_before": True,
            "preserve_after": True,
        })

    # 计算改动比例
    changed_paras = set()
    for op in patch_ops:
        for i in range(op["paragraph_start"], op["paragraph_end"] + 1):
            changed_paras.add(i)
    changed_ratio = len(changed_paras) / max(n, 1)

    warnings = []
    if changed_ratio > max_changed_ratio:
        warnings.append(
            f"改动比例 {changed_ratio:.0%} 超过上限 {max_changed_ratio:.0%}，"
            f"建议减少任务或人工确认。")

    return {
        "version": "v0.4.0",
        "source_file": "",
        "total_paragraphs": n,
        "patch_plan": patch_ops,
        "locked_ranges": locked,
        "changed_paragraphs": len(changed_paras),
        "changed_ratio": round(changed_ratio, 3),
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(description="Patch Planner")
    parser.add_argument("--input", required=True, help="章节 TXT")
    parser.add_argument("--tasks", required=True, help="revision_tasks.json")
    parser.add_argument("--out", required=True, help="输出 patch_plan.json")
    parser.add_argument("--max-changed-ratio", type=float, default=0.35)
    args = parser.parse_args()

    chapter = Path(args.input).read_text(encoding="utf-8")
    tasks = json.loads(Path(args.tasks).read_text(encoding="utf-8"))

    plan = build_patch_plan(chapter, tasks, args.max_changed_ratio)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] patch_plan: {len(plan['patch_plan'])} ops, "
          f"{plan['changed_ratio']:.0%} changed → {args.out}")
    if plan["warnings"]:
        for w in plan["warnings"]:
            print(f"  [WARN] {w}")


if __name__ == "__main__":
    main()
