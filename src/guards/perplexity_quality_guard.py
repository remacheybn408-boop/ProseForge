#!/usr/bin/env python3
"""
perplexity_quality_guard.py — QGP 困惑度质量门禁 v0.3.1-qgp

通过 ngram 惊讶度、句长节奏、重复短语、抽象总结密度、
具体锚点密度、对白变化度等指标，检测章节是否：
1. 过度模板化 / 过度平滑
2. 节奏过平
3. 异常混乱 / 断裂

QGP 不是 AI 检测器，只做 WARNING，不硬拦章节入库。
默认 ngram 后端，纯 Python 标准库，无需 GPU，无需联网。

用法:
  python scripts/perplexity_quality_guard.py \\
    --input chapter.txt --chapter-no 1 --novel-slug demo \\
    --config config.json --out report.json
"""
import re, json, sys, argparse, math, statistics
from pathlib import Path
from collections import Counter
from typing import Optional


# ═══════════════════════════════════════════════════
# 默认配置
# ═══════════════════════════════════════════════════

DEFAULT_QGP_CONFIG = {
    "enabled": True,
    "mode": "warning_only",
    "backend": "ngram",
    "baseline_enabled": False,
    "baseline_path": "",
    "paragraph_min_chars": 40,
    "low_surprise_z_threshold": -1.2,
    "high_surprise_z_threshold": 1.8,
    "template_risk_threshold": 0.35,
    "rhythm_flatness_threshold": 0.72,
    "dialogue_variation_min": 0.18,
    "max_warning_paragraphs": 8,
    "transformers": {
        "enabled": False,
        "model_path": "",
        "device": "cpu",
        "stride": 256,
        "max_length": 512
    }
}

# ═══════════════════════════════════════════════════
# 文本分割
# ═══════════════════════════════════════════════════

def split_paragraphs(text: str, min_chars: int = 40) -> list[str]:
    """按空行分段落，过滤过短段落"""
    raw = [p.strip() for p in text.split("\n") if p.strip()]
    merged = []
    buf = ""
    for p in raw:
        cn = len([c for c in p if '\u4e00' <= c <= '\u9fff'])
        if cn < min_chars:
            buf += p
            if len([c for c in buf if '\u4e00' <= c <= '\u9fff']) >= min_chars:
                merged.append(buf)
                buf = ""
        else:
            if buf:
                merged.append(buf)
                buf = ""
            merged.append(p)
    if buf:
        merged.append(buf)
    return [p for p in merged if len([c for c in p if '\u4e00' <= c <= '\u9fff']) >= min_chars]


def split_sentences(paragraph: str) -> list[str]:
    """按中文标点分句"""
    sents = re.split(r'[。！？；\n]', paragraph)
    return [s.strip() for s in sents if s.strip() and len(s.strip()) >= 3]


def count_chinese(text: str) -> int:
    return len([c for c in text if '\u4e00' <= c <= '\u9fff'])


# ═══════════════════════════════════════════════════
# N-gram 分析
# ═══════════════════════════════════════════════════

def char_ngram_counts(text: str, n: int = 3) -> dict[str, int]:
    """字符级 n-gram 计数（仅中文字符）"""
    chinese_only = ''.join(c for c in text if '\u4e00' <= c <= '\u9fff')
    if len(chinese_only) < n:
        return {}
    grams = [chinese_only[i:i+n] for i in range(len(chinese_only) - n + 1)]
    return dict(Counter(grams))


def compute_ngram_surprise(paragraph: str, corpus_counts: dict,
                            n: int = 3) -> float:
    """
    计算段落的 ngram 罕见度分数。
    罕见度越高 → 文本越不模板 → 分数越高。
    罕见度越低 → 可能是常见模板组合 → 分数越低。
    """
    if not corpus_counts:
        return 50.0  # 无参考时默认中庸

    para_counts = char_ngram_counts(paragraph, n)
    if not para_counts:
        return 50.0

    total_corpus = sum(corpus_counts.values()) or 1
    surprises = []
    for gram, count in para_counts.items():
        corpus_freq = corpus_counts.get(gram, 0) / total_corpus
        # 越罕见越惊讶: -log(freq+epsilon)
        surprise = -math.log(max(corpus_freq, 1e-6))
        surprises.append(surprise)

    if not surprises:
        return 50.0
    avg_surprise = statistics.mean(surprises)
    # 映射到 0-100 尺度
    return min(100, max(0, avg_surprise * 8))


def compute_ngram_surprise_no_corpus(paragraph: str, n: int = 3) -> float:
    """
    无参考语料时的自惊讶度：用段落自身的 ngram 多样性。
    高多样性 = 高惊讶度，低多样性 = 模板化。
    """
    counts = char_ngram_counts(paragraph, n)
    if not counts:
        return 50.0
    unique = len(counts)
    total = sum(counts.values())
    ratio = unique / max(total, 1)
    # 映射到 0-100
    return min(100, max(0, ratio * 20 + 30))


# ═══════════════════════════════════════════════════
# 重复短语检测
# ═══════════════════════════════════════════════════

def repeated_phrase_ratio(text: str, min_len: int = 4,
                          max_len: int = 8) -> float:
    """
    检测重复短语比例。
    返回 0.0-1.0，越高越严重。
    """
    chinese_only = ''.join(c for c in text if '\u4e00' <= c <= '\u9fff')
    if len(chinese_only) < min_len * 2:
        return 0.0

    phrases = Counter()
    total_phrases = 0
    for L in range(min_len, max_len + 1):
        for i in range(len(chinese_only) - L + 1):
            phrase = chinese_only[i:i+L]
            phrases[phrase] += 1
            total_phrases += 1

    if total_phrases == 0:
        return 0.0
    repeated = sum(1 for c in phrases.values() if c >= 3)
    return min(1.0, repeated / max(len(phrases), 1))


# ═══════════════════════════════════════════════════
# 句长统计
# ═══════════════════════════════════════════════════

def sentence_length_stats(paragraph: str) -> dict:
    """句长变化统计"""
    sents = split_sentences(paragraph)
    if len(sents) < 2:
        return {"mean": 0, "std": 0, "cv": 0, "count": len(sents)}
    lengths = [len(s) for s in sents]
    mean_val = statistics.mean(lengths)
    std_val = statistics.stdev(lengths) if len(lengths) > 1 else 0
    cv = std_val / max(mean_val, 1)
    return {"mean": round(mean_val, 1), "std": round(std_val, 1),
            "cv": round(cv, 3), "count": len(lengths)}


# ═══════════════════════════════════════════════════
# 抽象总结 / 具体锚点
# ═══════════════════════════════════════════════════

ABSTRACT_WORDS = re.compile(
    r'(突然|仿佛|似乎|意识|明白|觉悟|顿悟|命运|危机|压迫|威胁'
    r'|无法形容|难以言喻|五味杂陈|百感交集|前所未有'
    r'|真正的|所谓|本质上|说到底|实际上|事实上|终于)'
)

CONCRETE_ANCHORS = re.compile(
    r'(手|脚|眼|耳|口|鼻|头|肩|背|腰|腿|臂|指|掌|拳'
    r'|门|窗|墙|地|天|桌|椅|床|碗|杯|壶|炉|灯|烛|火|水|土|石|木|金'
    r'|剑|刀|枪|棍|鞭|弓|箭|盾|甲|袍|衣|袖|鞋|靴|帽|巾|带|环|镯'
    r'|血|汗|泪|唾|痰|尿|屎|灰|尘|泥|沙|雾|烟|光|影|痕|纹|线|点'
    r'|玉|铜|铁|银|金|纸|竹|布|皮|绳|链|锁|钥|印|符|丹|药|针|线'
    r'|矿|洞|坑|井|路|道|桥|河|湖|海|山|峰|谷|林|树|草|花|叶'
    r'|铜钱|玉牌|令牌|竹简|袖口|石阶|窗纸|井沿|门槛|屋檐|案几)'
)


def abstract_summary_ratio(paragraph: str) -> float:
    """抽象总结词密度"""
    matches = len(ABSTRACT_WORDS.findall(paragraph))
    cn = count_chinese(paragraph)
    return matches / max(cn / 100, 1)


def concrete_anchor_ratio(paragraph: str) -> float:
    """具体锚点密度"""
    matches = len(CONCRETE_ANCHORS.findall(paragraph))
    cn = count_chinese(paragraph)
    return matches / max(cn / 100, 1)


# ═══════════════════════════════════════════════════
# 对白变化度
# ═══════════════════════════════════════════════════

def dialogue_variation_score(text: str) -> float:
    """
    对白句长、语气词、停顿变化度。
    0.0-1.0，越高越好。
    """
    dialogues = re.findall(r'[""「」]([^""「」]{5,})[""「」]', text)
    if len(dialogues) < 2:
        return 0.5

    lengths = [len(d) for d in dialogues]
    len_std = statistics.stdev(lengths) if len(lengths) > 1 else 0

    # 语气词多样性
    particles = re.findall(r'(呢|吗|吧|啊|呀|哦|嗯|哼|哈|呵|嘛|哩|咧|呗|罢|啦|呐)',
                           ' '.join(dialogues))
    particle_diversity = len(set(particles)) / max(len(particles), 1)

    # 停顿: 省略号 / 破折号
    pauses = len(re.findall(r'(……|\\.{3,}|——|—)', ' '.join(dialogues)))
    pause_ratio = min(1.0, pauses / max(len(dialogues), 1))

    score = (min(1.0, len_std / 20) * 0.4 +
             particle_diversity * 0.3 +
             pause_ratio * 0.3)
    return round(score, 3)


# ═══════════════════════════════════════════════════
# 节奏平坦度
# ═══════════════════════════════════════════════════

def compute_rhythm_flatness(paragraphs: list[str]) -> float:
    """
    段落长度 + 句长过于稳定 → 节奏平。
    0.0-1.0，越高越平。
    """
    if len(paragraphs) < 2:
        return 0.5

    para_lens = [count_chinese(p) for p in paragraphs]
    all_sent_lens = []
    for p in paragraphs:
        sents = split_sentences(p)
        all_sent_lens.extend([len(s) for s in sents])

    if not all_sent_lens:
        return 0.5

    para_cv = statistics.stdev(para_lens) / max(statistics.mean(para_lens), 1) if len(para_lens) > 1 else 0
    sent_cv = statistics.stdev(all_sent_lens) / max(statistics.mean(all_sent_lens), 1) if len(all_sent_lens) > 1 else 0

    # 越稳定 → 越平 → 分数越高
    flatness = 1.0 - (para_cv * 0.4 + sent_cv * 0.6)
    return round(min(1.0, max(0.0, flatness)), 3)


# ═══════════════════════════════════════════════════
# 段落分类
# ═══════════════════════════════════════════════════

def classify_paragraph(metrics: dict, baseline: Optional[dict],
                       config: dict) -> dict:
    """根据指标对段落做出风险评估"""
    qgp = metrics["qgp_score"]
    risk = "normal"
    reasons = []

    # 基线对比
    if baseline and baseline.get("metrics"):
        bm = baseline["metrics"]
        if bm.get("avg_qgp_score_std", 0) > 0:
            z = (qgp - bm.get("avg_qgp_score_mean", 50)) / bm["avg_qgp_score_std"]
        else:
            z = 0
    else:
        z = 0

    low_thresh = config.get("low_surprise_z_threshold", -1.2)
    high_thresh = config.get("high_surprise_z_threshold", 1.8)

    if z < low_thresh:
        risk = "low_surprise"
        reasons.append("n-gram惊讶度过低，可能模板化")
    elif z > high_thresh:
        risk = "high_surprise"
        reasons.append("n-gram惊讶度过高，可能混乱/方言/文言突兀")

    if metrics.get("template_risk", 0) > config.get("template_risk_threshold", 0.35):
        if risk == "normal":
            risk = "low_surprise"
        reasons.append("重复短语比例偏高")

    return {"qgp_score": qgp, "z_score": round(z, 2), "risk": risk,
            "reasons": reasons}


# ═══════════════════════════════════════════════════
# 主报告构建
# ═══════════════════════════════════════════════════

def build_report(text: str, config: dict, novel_slug: str,
                 chapter_no: int, baseline: Optional[dict] = None) -> dict:
    """构建完整的 QGP 报告"""
    cfg = {**DEFAULT_QGP_CONFIG, **config}
    min_chars = cfg.get("paragraph_min_chars", 40)

    paragraphs = split_paragraphs(text, min_chars)
    if not paragraphs:
        return _empty_report(novel_slug, chapter_no)

    # 构建语料参考（整章作为自参考）
    corpus_ngrams = char_ngram_counts(text, 3)
    use_corpus = len(corpus_ngrams) > 10

    # 逐段分析
    para_results = []
    all_qgp = []
    all_template = []
    abstract_ratios = []
    concrete_ratios = []

    for i, para in enumerate(paragraphs):
        cn = count_chinese(para)

        if use_corpus:
            qgp_score = compute_ngram_surprise(para, corpus_ngrams, 3)
        else:
            qgp_score = compute_ngram_surprise_no_corpus(para, 3)

        sent_stats = sentence_length_stats(para)
        phrase_ratio = repeated_phrase_ratio(para)
        abstract_r = abstract_summary_ratio(para)
        concrete_r = concrete_anchor_ratio(para)

        all_qgp.append(qgp_score)
        all_template.append(phrase_ratio)
        abstract_ratios.append(abstract_r)
        concrete_ratios.append(concrete_r)

        metrics = {
            "qgp_score": round(qgp_score, 1),
            "chars": cn,
            "sentence_count": sent_stats["count"],
            "sentence_len_mean": sent_stats["mean"],
            "sentence_len_cv": sent_stats["cv"],
            "template_risk": round(phrase_ratio, 3),
            "abstract_ratio": round(abstract_r, 3),
            "concrete_ratio": round(concrete_r, 3),
        }

        cls = classify_paragraph(metrics, baseline, cfg)
        metrics["risk"] = cls["risk"]
        metrics["reasons"] = cls["reasons"]

        para_results.append({
            "index": i + 1,
            **metrics,
            "sample": para[:60]
        })

    # ── 汇总指标 ──
    avg_qgp = statistics.mean(all_qgp) if all_qgp else 50
    qgp_std = statistics.stdev(all_qgp) if len(all_qgp) > 1 else 0
    avg_template = statistics.mean(all_template) if all_template else 0
    avg_abstract = statistics.mean(abstract_ratios) if abstract_ratios else 0
    avg_concrete = statistics.mean(concrete_ratios) if concrete_ratios else 0

    low_surprise_count = sum(1 for p in para_results if p["risk"] == "low_surprise")
    high_surprise_count = sum(1 for p in para_results if p["risk"] == "high_surprise")
    rhythm = compute_rhythm_flatness(paragraphs)
    dia_var = dialogue_variation_score(text)

    # ── 基线对比 ──
    baseline_status = "missing"
    z_score = 0
    baseline_mean = 50
    baseline_std = 10
    if baseline and baseline.get("metrics"):
        baseline_status = "loaded"
        bm = baseline["metrics"]
        baseline_mean = bm.get("avg_qgp_score_mean", 50)
        baseline_std = bm.get("avg_qgp_score_std", 10)
        if baseline_std > 0:
            z_score = round((avg_qgp - baseline_mean) / baseline_std, 2)

    # ── WARNING 触发 ──
    flags = []
    suggestions = []

    low_ratio = low_surprise_count / max(len(para_results), 1)
    high_ratio = high_surprise_count / max(len(para_results), 1)

    if low_ratio > 0.3:
        flags.append({"level": "WARNING", "type": "LOW_SURPRISE_TEMPLATE_RISK",
                      "message": f"低惊讶段落 {low_ratio:.0%}，可能存在模板化叙述。"})
        suggestions.append("把抽象总结句改成具体动作、物件、停顿、误会或代价。")

    if avg_template > cfg.get("template_risk_threshold", 0.35):
        flags.append({"level": "WARNING", "type": "REPEATED_PHRASE_RISK",
                      "message": f"重复短语比例 {avg_template:.1%} 偏高。"})
        suggestions.append("减少套话和万能句式，增加具体叙事细节。")

    if rhythm > cfg.get("rhythm_flatness_threshold", 0.72):
        flags.append({"level": "WARNING", "type": "RHYTHM_FLATNESS",
                      "message": f"节奏平坦度 {rhythm:.2f}，段落和句长过于平均。"})
        suggestions.append("变化段落长度，长短句交替，打破平均节奏。")

    if avg_abstract > 0.25 and avg_concrete < 0.30:
        flags.append({"level": "WARNING", "type": "ABSTRACT_OVER_CONCRETE",
                      "message": f"抽象总结密度偏高 ({avg_abstract:.2f})，具体锚点偏低 ({avg_concrete:.2f})。"})
        suggestions.append("每 3-5 段至少加入一个可触摸的场景物件。")

    if dia_var < cfg.get("dialogue_variation_min", 0.18):
        flags.append({"level": "WARNING", "type": "LOW_DIALOGUE_VARIATION",
                      "message": f"对白变化度 {dia_var:.2f} 偏低，角色口吻可能过于相似。"})
        suggestions.append("让角色对白出现句长差异、称呼差异和口头禅差异。")

    if high_ratio > 0.2:
        flags.append({"level": "WARNING", "type": "HIGH_SURPRISE_CHAOS",
                      "message": f"高惊讶段落 {high_ratio:.0%}，文本可能异常混乱/方言过猛/文言突兀。"})
        if not any("方言" in s for s in suggestions):
            suggestions.append("检查方言/文言浓度是否超出角色设定，减少生僻词堆砌。")

    if baseline_status == "missing":
        suggestions.insert(0, "建议放入 3-5 章作者满意样本建立 QGP 基线。")

    # ── 裁决 ──
    status = "WARNING" if flags else "PASS"

    # 截取建议段落（最多 max_warning_paragraphs 个）
    warning_paras = [p for p in para_results if p["risk"] != "normal"]
    warning_paras = warning_paras[:cfg.get("max_warning_paragraphs", 8)]

    report = {
        "guard": "perplexity_quality_guard",
        "version": "v0.3.1-qgp",
        "status": status,
        "mode": "warning_only",
        "backend": cfg["backend"],
        "novel_slug": novel_slug,
        "chapter_no": chapter_no,
        "baseline_status": baseline_status,
        "summary": {
            "avg_qgp_score": round(avg_qgp, 1),
            "baseline_mean": round(baseline_mean, 1),
            "baseline_std": round(baseline_std, 1),
            "z_score": z_score,
            "paragraph_count": len(paragraphs),
            "low_surprise_ratio": round(low_ratio, 3),
            "high_surprise_ratio": round(high_ratio, 3),
            "template_risk_ratio": round(avg_template, 3),
            "rhythm_flatness": rhythm,
            "dialogue_variation_score": dia_var,
            "concrete_anchor_ratio": round(avg_concrete, 3),
            "abstract_summary_ratio": round(avg_abstract, 3),
        },
        "flags": flags,
        "suggestions": suggestions,
        "paragraphs": warning_paras,
        "hard_fail": False,
    }

    return report


def _empty_report(novel_slug, chapter_no):
    return {
        "guard": "perplexity_quality_guard",
        "version": "v0.3.1-qgp",
        "status": "PASS",
        "mode": "warning_only",
        "backend": "ngram",
        "novel_slug": novel_slug,
        "chapter_no": chapter_no,
        "baseline_status": "missing",
        "summary": {
            "avg_qgp_score": 0, "baseline_mean": 0, "baseline_std": 0,
            "z_score": 0, "paragraph_count": 0,
            "low_surprise_ratio": 0, "high_surprise_ratio": 0,
            "template_risk_ratio": 0, "rhythm_flatness": 0,
            "dialogue_variation_score": 0,
            "concrete_anchor_ratio": 0, "abstract_summary_ratio": 0,
        },
        "flags": [], "suggestions": [], "paragraphs": [], "hard_fail": False,
    }


# ═══════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="QGP Perplexity Quality Guard")
    parser.add_argument("--input", required=True, help="章节 TXT 文件")
    parser.add_argument("--chapter-no", type=int, default=1)
    parser.add_argument("--novel-slug", default="demo_novel")
    parser.add_argument("--config", default=None, help="config.json")
    parser.add_argument("--baseline", default=None, help="QGP baseline JSON")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    # 加载配置
    qgp_cfg = dict(DEFAULT_QGP_CONFIG)
    if args.config and Path(args.config).exists():
        full_cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
        if "qgp" in full_cfg:
            qgp_cfg = {**DEFAULT_QGP_CONFIG, **full_cfg["qgp"]}

    if not qgp_cfg.get("enabled", True):
        print(json.dumps({"status": "PASS", "mode": "disabled"}, ensure_ascii=False))
        return 0

    content = Path(args.input).read_text(encoding="utf-8")

    # 加载基线
    baseline = None
    if args.baseline and Path(args.baseline).exists():
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))

    report = build_report(content, qgp_cfg, args.novel_slug,
                          args.chapter_no, baseline)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"\n[OK] QGP report saved: {args.out}")

    if report["status"] == "WARNING":
        print(f"\n[WARN] QGP: {len(report['flags'])} flags, "
              f"{len(report['suggestions'])} suggestions")
    else:
        print(f"\n[OK] QGP passed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
