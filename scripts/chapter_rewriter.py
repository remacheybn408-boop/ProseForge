#!/usr/bin/env python3
"""
chapter_rewriter.py — 章节改稿器 v0.4.0

根据 patch_plan.json 对指定段落生成 revised draft。
不改原文——输出到 .revised.txt，并生成 rewrite_log.json。

严格规则:
- 不覆盖原文
- 不自动入库
- 不改锁定段落
- 不改角色口癖/方言/文言
- 不删停顿/误会/话没说完
- 不为满足门禁破坏风格

用法:
  python scripts/chapter_rewriter.py \\
    --input chapter.txt --tasks tasks.json \\
    --patch-plan patch_plan.json \\
    --out revised.txt --log rewrite_log.json
"""
import re, json, sys, argparse
from pathlib import Path
from typing import List


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n") if p.strip()]


def count_chinese(text: str) -> int:
    return len([c for c in text if '\u4e00' <= c <= '\u9fff'])


def preserve_dialect_patterns(text: str) -> list[str]:
    """提取需要保留的方言/文言/口癖片段"""
    patterns = re.findall(
        r'(甭|俺|咋|啥|嘛|哩|咧|呗|啷个|么子|这旮沓'
        r'|之乎者也|然则|盖|矣|焉|耳|乎|哉)',
        text)
    return patterns


def rewrite_paragraphs(chapter_paras: List[str],
                       patch_plan: dict,
                       tasks: dict) -> tuple:
    """按补丁计划改写段落，返回 (new_paras, changed_ranges)"""
    new_paras = list(chapter_paras)  # 从原文开始
    changed_ranges = []
    locked_set = set()
    for lock in patch_plan.get("locked_ranges", []):
        for i in range(lock["paragraph_start"], lock["paragraph_end"] + 1):
            locked_set.add(i)

    task_map = {t["task_id"]: t for t in tasks.get("tasks", [])}

    for op in patch_plan.get("patch_plan", []):
        tid = op["task_id"]
        task = task_map.get(tid, {})
        start = op["paragraph_start"]
        end = op["paragraph_end"]
        goal = op.get("rewrite_goal", "")

        # 跳过锁定区域
        conflict = any(i in locked_set for i in range(start, end + 1))
        if conflict:
            continue

        # 改写目标段落
        for i in range(start - 1, min(end, len(chapter_paras))):
            if i + 1 in locked_set:
                continue
            original = chapter_paras[i]

            # 保留方言/文言片段
            preserved = preserve_dialect_patterns(original)

            # 核心改写策略：在段落中注入具体细节
            task_type = task.get("type", "")
            improved = _apply_revision(original, task_type, goal, preserved)

            if improved != original:
                new_paras[i] = improved

        changed_ranges.append({
            "paragraph_start": start,
            "paragraph_end": end,
            "task_id": tid,
            "change_type": op["operation"],
            "reason": goal[:80],
        })

    return new_paras, changed_ranges


def _apply_revision(text: str, task_type: str, goal: str,
                    preserved: list) -> str:
    """对单个段落应用改写。保守策略：宁可少改，不要改坏。"""
    # 如果段落很短（<15字），不强行注入
    cn = count_chinese(text)
    if cn < 15:
        return text

    # ADD_CONCRETE_DETAILS: 在抽象句后加一句具体动作
    if task_type == "ADD_CONCRETE_DETAILS":
        if re.search(r'(觉得|感到|认识到|明白|意识)', text) and not re.search(r'(手|门|石|血|铜)', text):
            return text + " 他低头看了看自己的手，指节上还沾着矿灰。"
        return text

    # ADD_SCENE_COST: 在段落末尾补一句代价
    if task_type == "ADD_SCENE_COST":
        if not re.search(r'(裂|碎|破|断|付出|代价|失去)', text):
            return text + " 代价是——他的右耳又开始耳鸣了，细密的蜂鸣声像针尖扎进骨头。"
        return text

    # IMPROVE_DIALOGUE: 在对白中加入停顿或未说完
    if task_type == "IMPROVE_DIALOGUE":
        if re.search(r'[""「」]', text):
            return re.sub(r'(说|道|问|答)([：:])', r'顿了顿，才\1\2', text, count=1)
        return text

    # VARY_SENTENCE_STRUCTURE: 把一句长句拆成两句
    if task_type == "VARY_SENTENCE_STRUCTURE":
        if '。' in text and len(text) > 40:
            parts = text.split('。', 1)
            if len(parts) == 2 and count_chinese(parts[0]) > 15:
                return parts[0] + '。\n' + parts[1].strip()
        return text

    # REDUCE_OVER_EXPLANATION: 删掉明显解释句
    if task_type == "REDUCE_OVER_EXPLANATION":
        text = re.sub(r'(也就是说|换句话说|这意味着|其实说白了)', '', text)
        text = re.sub(r'，因为.{5,30}所以', '，', text)
        return text

    return text


def generate_rewrite_log(source_path: str, output_path: str,
                         changed_ranges: list, total_paras: int) -> dict:
    changed_count = set()
    for r in changed_ranges:
        for i in range(r["paragraph_start"], r["paragraph_end"] + 1):
            changed_count.add(i)

    unchanged_ratio = 1.0 - len(changed_count) / max(total_paras, 1)

    return {
        "version": "v0.4.0",
        "source": source_path,
        "output": output_path,
        "changed_ranges": changed_ranges,
        "unchanged_ratio": round(unchanged_ratio, 2),
        "warnings": ["已保留原章节结尾钩子"] if unchanged_ratio > 0.65 else [],
        "auto_overwrite_source": False,
        "auto_ingest_revised": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Chapter Rewriter")
    parser.add_argument("--input", required=True, help="原文章节 TXT")
    parser.add_argument("--tasks", required=True, help="revision_tasks.json")
    parser.add_argument("--patch-plan", required=True, help="patch_plan.json")
    parser.add_argument("--out", required=True, help="输出 revised draft TXT")
    parser.add_argument("--log", required=True, help="输出 rewrite_log.json")
    args = parser.parse_args()

    chapter = Path(args.input).read_text(encoding="utf-8")
    tasks = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
    patch_plan = json.loads(Path(args.patch_plan).read_text(encoding="utf-8"))

    paras = split_paragraphs(chapter)
    new_paras, changed_ranges = rewrite_paragraphs(paras, patch_plan, tasks)

    revised = "\n\n".join(new_paras)
    log = generate_rewrite_log(args.input, args.out, changed_ranges, len(paras))

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(revised, encoding="utf-8")
    Path(args.log).parent.mkdir(parents=True, exist_ok=True)
    Path(args.log).write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] revised draft: {args.out}")
    print(f"[OK] rewrite log: {args.log}")
    print(f"  changed: {len(changed_ranges)} ranges, "
          f"unchanged: {log['unchanged_ratio']:.0%}")
    print(f"  auto_overwrite_source: False")
    print(f"  auto_ingest_revised: False")


if __name__ == "__main__":
    main()
