#!/usr/bin/env python3
"""
editor_revision_guard.py — 拟人审稿痕迹门禁 v0.4.0

检测章节是"初稿质感"还是"改过稿质感"。
通过段落句长分布、碎片句、句首变化等指标判断：
- 过度解释：段内句长过于均匀（15-25字），缺乏碎片句和长句
- 修改痕迹：段落长度 CV + 句长 CV + 碎片行 + 句首变化

用法:
  python scripts/editor_revision_guard.py \
    --input chapter.txt --chapter-no 1 [--output report.json]
"""
import re, json, sys, argparse, statistics
from pathlib import Path
from typing import List, Dict, Tuple


# ═══════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════

def count_chinese(text: str) -> int:
    return len([c for c in text if '\u4e00' <= c <= '\u9fff'])


def split_sentences(paragraph: str) -> List[str]:
    """按中文标点分句"""
    sents = re.split(r'[。！？；\n]', paragraph)
    return [s.strip() for s in sents if s.strip() and len(s.strip()) >= 2]


def split_paragraphs(text: str, min_chars: int = 20) -> List[str]:
    """按空行分段落"""
    raw = [p.strip() for p in text.split("\n") if p.strip()]
    merged = []
    buf = ""
    for p in raw:
        cn = count_chinese(p)
        if cn < min_chars:
            buf += p
            if count_chinese(buf) >= min_chars:
                merged.append(buf)
                buf = ""
        else:
            if buf:
                merged.append(buf)
                buf = ""
            merged.append(p)
    if buf:
        merged.append(buf)
    return [p for p in merged if count_chinese(p) >= min_chars]


# ═══════════════════════════════════════════════════
# 过度解释检测
# ═══════════════════════════════════════════════════

def detect_over_explained(
    content: str,
    para_min_chars: int = 20,
    over_explained_threshold: float = 0.28
) -> Dict:
    """
    检测"过度解释"段落。
    特征：段内每句都在 15-25 字，无碎片句（<8字），无长句（>35字）。
    """
    paragraphs = split_paragraphs(content, para_min_chars)
    if not paragraphs:
        return {
            "over_explained_count": 0,
            "over_explained_paragraphs": [],
            "total_paragraphs": 0,
            "ratio": 0.0
        }

    over_explained = []

    for i, para in enumerate(paragraphs):
        sents = split_sentences(para)
        if len(sents) < 3:
            continue  # 句数太少不检测

        sent_lengths = [len(s) for s in sents]

        # 检查条件
        all_in_range = all(15 <= sl <= 25 for sl in sent_lengths)
        has_fragment = any(sl < 8 for sl in sent_lengths)
        has_long = any(sl > 35 for sl in sent_lengths)

        # 过度解释：全部在 15-25 且无碎片无长句
        if all_in_range and not has_fragment and not has_long:
            over_explained.append({
                "index": i + 1,
                "sentence_count": len(sents),
                "sentence_lengths": sent_lengths,
                "sample": para[:60]
            })

    ratio = len(over_explained) / max(len(paragraphs), 1)
    return {
        "over_explained_count": len(over_explained),
        "over_explained_paragraphs": over_explained,
        "total_paragraphs": len(paragraphs),
        "ratio": round(ratio, 3)
    }


# ═══════════════════════════════════════════════════
# 修改痕迹（revision texture）
# ═══════════════════════════════════════════════════

def compute_revision_texture(content: str, para_min_chars: int = 20) -> float:
    """
    计算"修改痕迹"分数 0-1，越高越像改过的稿。
    综合：段落长度 CV + 句长 CV + 碎片行比例 + 句首变化度
    """
    paragraphs = split_paragraphs(content, para_min_chars)
    if len(paragraphs) < 2:
        return 0.5

    # ── 1. 段落长度变异系数 ──
    para_lens = [count_chinese(p) for p in paragraphs]
    para_mean = statistics.mean(para_lens)
    para_cv = statistics.stdev(para_lens) / max(para_mean, 1) if len(para_lens) > 1 else 0

    # ── 2. 句长变异系数（全章所有句） ──
    all_sent_lens = []
    fragment_count = 0
    total_sents = 0

    for p in paragraphs:
        sents = split_sentences(p)
        for s in sents:
            sl = len(s)
            all_sent_lens.append(sl)
            total_sents += 1
            if sl < 10:
                fragment_count += 1

    if len(all_sent_lens) < 2:
        sent_cv = 0
    else:
        sent_mean = statistics.mean(all_sent_lens)
        sent_cv = statistics.stdev(all_sent_lens) / max(sent_mean, 1)

    # ── 3. 碎片行比例 ──
    fragment_ratio = fragment_count / max(total_sents, 1)

    # ── 4. 句首变化度：不以"他/她"开头的句比例 ──
    pronoun_starts = 0
    total_for_start = 0
    for p in paragraphs:
        sents = split_sentences(p)
        for s in sents:
            total_for_start += 1
            if s and s[0] in ('他', '她'):
                pronoun_starts += 1

    start_variety = 1.0 - (pronoun_starts / max(total_for_start, 1))

    # ── 综合得分 ──
    # para_cv: 0.3-0.8 正常，sent_cv: 0.3-0.7 正常
    # fragment_ratio: 0.05-0.25 正常
    # start_variety: 0.4-0.9 正常

    cv_score = min(1.0, (para_cv / 0.6) * 0.3 + (sent_cv / 0.5) * 0.3)
    fragment_score = min(1.0, fragment_ratio / 0.2)
    variety_score = min(1.0, start_variety / 0.7)

    texture = cv_score * 0.35 + fragment_score * 0.35 + variety_score * 0.30
    return round(min(1.0, max(0.0, texture)), 3)


# ═══════════════════════════════════════════════════
# 主检查函数
# ═══════════════════════════════════════════════════

def run_editor_revision_check(content: str, chapter_no: int) -> dict:
    """执行编辑审稿痕迹检查，返回报告 dict"""

    # ── 过度解释检测 ──
    over_result = detect_over_explained(content)

    # ── 修改痕迹 ──
    texture_score = compute_revision_texture(content)

    # ── 构建 flags 和 suggestions ──
    flags = []
    suggestions = []

    if over_result["ratio"] > 0.28:
        flags.append({
            "level": "WARNING",
            "type": "OVER_EXPLAINED_PARAGRAPHS",
            "message": (
                f"过度解释段落占比 {over_result['ratio']:.0%} "
                f"({over_result['over_explained_count']}/{over_result['total_paragraphs']})，"
                f"超过阈值 28%。"
            )
        })
        suggestions.append(
            "减少每句解释，增加碎片句（<8字）、对话停顿、省略跳笔。"
        )

    if texture_score < 0.35:
        flags.append({
            "level": "WARNING",
            "type": "LOW_REVISION_TEXTURE",
            "message": f"修改痕迹分数 {texture_score}，文本像初稿（段落/句长过于均匀，缺乏变化）。"
        })
        suggestions.append(
            "变化段落节奏：增加短句（<10字）打破平均，开头多样化避免总用'他/她'。"
        )
    elif texture_score < 0.50:
        flags.append({
            "level": "WARNING",
            "type": "MEDIUM_REVISION_TEXTURE",
            "message": f"修改痕迹分数 {texture_score}，偏低，建议增加段落节奏变化。"
        })
        suggestions.append(
            "适当增加碎片句和句首变化，让文本更有'改过'的质感。"
        )

    # ── 判定状态 ──
    status = "WARNING" if flags else "PASS"

    report = {
        "guard": "editor_revision_guard",
        "version": "v0.4.0",
        "status": status,
        "revision_texture_score": texture_score,
        "over_explained_count": over_result["over_explained_count"],
        "over_explained_paragraphs": over_result["over_explained_paragraphs"],
        "flags": flags,
        "suggestions": suggestions,
        "hard_fail": False,
    }

    return report


# ═══════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Editor Revision Guard — 拟人审稿痕迹门禁"
    )
    parser.add_argument("--input", required=True, help="章节 TXT 文件")
    parser.add_argument("--chapter-no", type=int, default=1)
    parser.add_argument("--output", default=None, help="输出 report JSON 文件")
    args = parser.parse_args()

    content = Path(args.input).read_text(encoding="utf-8")
    report = run_editor_revision_check(content, args.chapter_no)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"\n[OK] Editor revision report saved: {args.output}")

    if report["status"] == "WARNING":
        print(f"\n[WARN] Editor revision: {len(report['flags'])} flags, "
              f"{len(report['suggestions'])} suggestions")
    else:
        print(f"\n[OK] Editor revision passed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
