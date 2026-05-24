#!/usr/bin/env python3
"""
qgp_baseline.py — QGP 风格基线构建 v0.3.1-qgp

从作者认可的章节样本中提取 ngram 统计和风格指标，
后续章节只和自己的 baseline 对比。

用法:
  python scripts/qgp_baseline.py build \\
    --input-dir examples/demo_novel/baseline_chapters \\
    --novel-slug demo_novel \\
    --out data/qgp_baselines/demo_novel.qgp_baseline.json
"""
import json, sys, argparse, statistics
from pathlib import Path
from collections import Counter


def count_chinese(text: str) -> int:
    return len([c for c in text if '\u4e00' <= c <= '\u9fff'])


def char_ngram_counts(text: str, n: int = 3) -> dict[str, int]:
    chinese_only = ''.join(c for c in text if '\u4e00' <= c <= '\u9fff')
    if len(chinese_only) < n:
        return {}
    grams = [chinese_only[i:i+n] for i in range(len(chinese_only) - n + 1)]
    return dict(Counter(grams))


def split_paragraphs(text: str, min_chars: int = 40) -> list[str]:
    raw = [p.strip() for p in text.split("\n") if p.strip()]
    merged, buf = [], ""
    for p in raw:
        cn = count_chinese(p)
        if cn < min_chars:
            buf += p
            if count_chinese(buf) >= min_chars:
                merged.append(buf); buf = ""
        else:
            if buf:
                merged.append(buf); buf = ""
            merged.append(p)
    if buf:
        merged.append(buf)
    return [p for p in merged if count_chinese(p) >= min_chars]


def split_sentences(paragraph: str) -> list[str]:
    sents = re.split(r'[。！？；\n]', paragraph)
    return [s.strip() for s in sents if s.strip() and len(s.strip()) >= 3]

import re


def analyze_text(text: str) -> dict:
    """单篇文本的风格指标"""
    paras = split_paragraphs(text)
    para_lens = [count_chinese(p) for p in paras]

    # 句长
    all_sent_lens = []
    for p in paras:
        all_sent_lens.extend([len(s) for s in split_sentences(p)])

    # 对白比例
    dialogues = re.findall(r'[""「」]([^""「」]+)[""「」]', text)
    dia_chars = sum(count_chinese(d) for d in dialogues)
    total_chars = count_chinese(text) or 1
    dialogue_ratio = dia_chars / total_chars

    # 唯一字符比
    chinese_only = ''.join(c for c in text if '\u4e00' <= c <= '\u9fff')
    unique_chars = len(set(chinese_only))
    unique_ratio = unique_chars / max(len(chinese_only), 1)

    return {
        "total_chars": total_chars,
        "paragraph_count": len(paras),
        "para_len_mean": statistics.mean(para_lens) if para_lens else 0,
        "sentence_len_mean": statistics.mean(all_sent_lens) if all_sent_lens else 0,
        "dialogue_ratio": round(dialogue_ratio, 3),
        "unique_char_ratio": round(unique_ratio, 3),
    }


def compute_baseline_from_files(file_paths: list[Path]) -> dict:
    """从多个文件计算基线"""
    all_metrics = []
    merged_text = ""

    for fp in file_paths:
        text = fp.read_text(encoding="utf-8")
        merged_text += text
        all_metrics.append(analyze_text(text))

    # 合并 ngram 统计
    merged_ngrams = char_ngram_counts(merged_text, 3)

    # 汇总指标
    para_counts = [m["paragraph_count"] for m in all_metrics]
    sent_lens = [m["sentence_len_mean"] for m in all_metrics]
    dia_ratios = [m["dialogue_ratio"] for m in all_metrics]
    unique_ratios = [m["unique_char_ratio"] for m in all_metrics]

    # 计算每章的 qgp_score（用整章合并语料的其他章作为参考）
    qgp_scores = []
    for i, fp in enumerate(file_paths):
        text = fp.read_text(encoding="utf-8")
        # 用其他章作为参考语料
        other_text = ""
        for j, fp2 in enumerate(file_paths):
            if i != j:
                other_text += fp2.read_text(encoding="utf-8")
        if not other_text:
            other_text = text

        from perplexity_quality_guard import compute_ngram_surprise
        corpus = char_ngram_counts(other_text, 3)
        score = compute_ngram_surprise(text, corpus, 3)
        qgp_scores.append(score)

    return {
        "source_chapters": [fp.name for fp in file_paths],
        "source_count": len(file_paths),
        "total_chars": sum(m["total_chars"] for m in all_metrics),
        "ngram_vocab_size": len(merged_ngrams),
        "metrics": {
            "avg_qgp_score_mean": round(statistics.mean(qgp_scores), 1) if qgp_scores else 50,
            "avg_qgp_score_std": round(statistics.stdev(qgp_scores), 1) if len(qgp_scores) > 1 else 10,
            "sentence_len_mean": round(statistics.mean(sent_lens), 1) if sent_lens else 0,
            "sentence_len_std": round(statistics.stdev(sent_lens), 1) if len(sent_lens) > 1 else 0,
            "dialogue_ratio_mean": round(statistics.mean(dia_ratios), 3) if dia_ratios else 0,
            "dialogue_ratio_std": round(statistics.stdev(dia_ratios), 3) if len(dia_ratios) > 1 else 0,
            "unique_char_ratio_mean": round(statistics.mean(unique_ratios), 3) if unique_ratios else 0,
            "unique_char_ratio_std": round(statistics.stdev(unique_ratios), 3) if len(unique_ratios) > 1 else 0,
            "qgp_scores": [round(s, 1) for s in qgp_scores],
        },
    }


def main():
    parser = argparse.ArgumentParser(description="QGP Baseline Builder")
    sub = parser.add_subparsers(dest="action")

    build_p = sub.add_parser("build", help="从样本章节建立基线")
    build_p.add_argument("--input-dir", required=True, help="样本章节目录")
    build_p.add_argument("--novel-slug", default="demo_novel")
    build_p.add_argument("--out", required=True, help="输出基线 JSON")
    build_p.add_argument("--pattern", default="*.txt", help="文件匹配 (默认: *.txt)")

    args = parser.parse_args()

    if args.action != "build":
        parser.print_help()
        return 1

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        print(f"[FAIL] 目录不存在: {input_dir}")
        return 1

    files = sorted(input_dir.glob(args.pattern))
    if not files:
        print(f"[FAIL] 目录中无匹配文件: {args.pattern}")
        return 1

    print(f"从 {len(files)} 个文件构建基线...")
    for f in files:
        print(f"  {f.name}")

    baseline = compute_baseline_from_files(files)
    baseline["novel_slug"] = args.novel_slug
    baseline["version"] = "v0.3.1-qgp"
    baseline["backend"] = "ngram"

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    print(f"\n[OK] 基线已保存: {out_path}")
    print(f"  QGP 均值: {baseline['metrics']['avg_qgp_score_mean']} "
          f"±{baseline['metrics']['avg_qgp_score_std']}")
    print(f"  句长均值: {baseline['metrics']['sentence_len_mean']}")
    print(f"  对白比例: {baseline['metrics']['dialogue_ratio_mean']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
