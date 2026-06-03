#!/usr/bin/env python3
"""
style_variation_guard.py — 句式变化门禁 v0.4.0

防止章节内句式过于统一、模式化。
检查项：
1. 句子开头重复: >25% 的句子以相同词开头 → WARNING
2. 句长 CV: < 0.35 → 太均匀 → WARNING
3. 段落长度 CV: 同上
4. 抽象词滥用: 命运/危机/似乎/仿佛/终于/本质/真正 > 12 次 → WARNING
5. 转折词重复: 但是/然而/所以/于是/然后/接着/之后/因为 过度重复

只输出 WARNING（不 FAIL），hard_fail 始终为 False。

用法:
  python scripts/style_variation_guard.py \
    --input chapter.txt --chapter-no 1 --out report.json
"""
import re, json, sys, argparse, statistics
from pathlib import Path
from collections import Counter


# ═══════════════════════════════════════════════════
# 正则模式
# ═══════════════════════════════════════════════════

# 分句: 按中文标点切分
SENTENCE_SPLIT = re.compile(r'[。！？；\n]+')

# 句子开头（取出前两个字用于统计，跳过引号等）
SENTENCE_OPENING = re.compile(r'^[\s""「」\'"‘’]*([\u4e00-\u9fff]{1,2})')

# 抽象词列表
ABSTRACT_WORDS = re.compile(
    r'(命运|危机|似乎|仿佛|终于|本质|真正|注定|宿命|天意|必然|归宿'
    r'|绝望|深渊|黑暗|光明|希望|轮回|永恒|终极|无尽)'
)

# 转折/连接词列表
TRANSITION_WORDS = re.compile(
    r'(但是|然而|所以|于是|然后|接着|之后|因为|因此|不过|可是|况且|而且'
    r'|虽然|尽管|即使|即便|无论|不论|不管|只有|只要|除非|否则)'
)

# 高频开头词列表（用于检测重复）
COMMON_OPENERS = {'他', '她', '这', '那', '但', '我', '你', '一', '在',
                  '不', '可', '就', '还', '也', '又', '而', '却', '便'}


# ═══════════════════════════════════════════════════
# 文本分割
# ═══════════════════════════════════════════════════

def split_sentences(text: str) -> list[str]:
    """按中文标点分割句子"""
    raw = SENTENCE_SPLIT.split(text)
    return [s.strip() for s in raw if len(s.strip()) >= 2]


def split_paragraphs(text: str) -> list[str]:
    """按空行/换行分割段落"""
    raw = [p.strip() for p in text.split('\n') if p.strip()]
    return [p for p in raw if len(p) >= 5]


def count_chinese(text: str) -> int:
    """计算中文字符数"""
    return len([c for c in text if '\u4e00' <= c <= '\u9fff'])


# ═══════════════════════════════════════════════════
# 检测函数
# ═══════════════════════════════════════════════════

def compute_sentence_opening_repetition(sentences: list[str]) -> dict:
    """
    统计句子开头词的分布。
    返回: opening_repetition_ratio, most_common_opener, top_openings
    """
    if not sentences:
        return {
            "opening_repetition_ratio": 0.0,
            "most_common_opener": "",
            "opener_count": 0,
            "total_sentences": 0,
        }

    openers = []
    for s in sentences:
        m = SENTENCE_OPENING.match(s)
        if m:
            openers.append(m.group(1))

    if not openers:
        return {
            "opening_repetition_ratio": 0.0,
            "most_common_opener": "",
            "opener_count": 0,
            "total_sentences": len(sentences),
        }

    counter = Counter(openers)
    most_common = counter.most_common(1)[0]
    ratio = most_common[1] / len(openers)

    return {
        "opening_repetition_ratio": round(ratio, 3),
        "most_common_opener": most_common[0],
        "opener_count": most_common[1],
        "total_sentences": len(sentences),
        "top_openings": counter.most_common(5),
    }


def compute_sentence_length_cv(sentences: list[str]) -> float:
    """计算句子长度的变异系数"""
    if len(sentences) < 2:
        return 0.0
    lengths = [len(s) for s in sentences if len(s) >= 1]
    if len(lengths) < 2:
        return 0.0
    mean_val = statistics.mean(lengths)
    std_val = statistics.stdev(lengths)
    return round(std_val / max(mean_val, 1), 3)


def compute_paragraph_length_cv(paragraphs: list[str]) -> float:
    """计算段落长度的变异系数（按中文字符数）"""
    if len(paragraphs) < 2:
        return 0.0
    lengths = [count_chinese(p) for p in paragraphs]
    if len(lengths) < 2:
        return 0.0
    mean_val = statistics.mean(lengths)
    std_val = statistics.stdev(lengths)
    return round(std_val / max(mean_val, 1), 3)


def count_abstract_words(text: str) -> int:
    """统计抽象词出现次数"""
    return len(ABSTRACT_WORDS.findall(text))


def count_transition_words(text: str) -> int:
    """统计转折/连接词出现次数"""
    return len(TRANSITION_WORDS.findall(text))


def compute_transition_density(text: str) -> float:
    """转折词密度（每100中文字符）"""
    cn_count = count_chinese(text)
    if cn_count == 0:
        return 0.0
    return round(count_transition_words(text) / (cn_count / 100), 2)


# ═══════════════════════════════════════════════════
# 报告构建
# ═══════════════════════════════════════════════════

def build_report(text: str, chapter_no: int = 1) -> dict:
    """构建句式变化门禁报告"""
    sentences = split_sentences(text)
    paragraphs = split_paragraphs(text)

    if not sentences:
        return {
            "guard": "style_variation_guard",
            "version": "v0.4.0",
            "status": "PASS",
            "chapter_no": chapter_no,
            "sentence_opening_variety": 1.0,
            "sentence_len_cv": 0.0,
            "paragraph_len_cv": 0.0,
            "abstract_word_count": 0,
            "transition_word_count": 0,
            "opening_repetition_ratio": 0.0,
            "flags": [],
            "suggestions": ["本章无有效句子，无需检测。"],
            "hard_fail": False,
        }

    # 各项指标
    opening_info = compute_sentence_opening_repetition(sentences)
    sent_len_cv = compute_sentence_length_cv(sentences)
    para_len_cv = compute_paragraph_length_cv(paragraphs)
    abstract_count = count_abstract_words(text)
    transition_count = count_transition_words(text)
    opening_ratio = opening_info["opening_repetition_ratio"]

    # 构建 flags 和建议
    flags = []
    suggestions = []

    # 1. 句子开头重复
    if opening_ratio > 0.25:
        most_common = opening_info["most_common_opener"]
        flags.append({
            "level": "WARNING",
            "type": "SENTENCE_OPENING_REPETITION",
            "message": (
                f"超过 {opening_ratio:.0%} 的句子以"
                f"{most_common}{opening_info['opener_count']}/{opening_info['total_sentences']}"
                f"开头，句式过于单一。"
            )
        })
        suggestions.append(
            f"减少以{most_common}开头的句子，用时间/地点/动作/环境描写开头，打破单调。"
        )

    # 2. 句长 CV 过低
    if sent_len_cv < 0.35:
        flags.append({
            "level": "WARNING",
            "type": "LOW_SENTENCE_LENGTH_VARIATION",
            "message": f"句长变异系数偏低 ({sent_len_cv:.3f})，句子长度过于均匀。"
        })
        suggestions.append("长短句交替使用：重要信息用短句强调，描写用稍长句铺陈。")

    # 3. 段落长度 CV 过低
    if para_len_cv < 0.35 and paragraphs:
        flags.append({
            "level": "WARNING",
            "type": "LOW_PARAGRAPH_LENGTH_VARIATION",
            "message": f"段落长度变异系数偏低 ({para_len_cv:.3f})，段落长度过于均匀。"
        })
        suggestions.append("段落长短结合：动作场景用短段落，心理/描写用中长段落。")

    # 4. 抽象词滥用
    if abstract_count > 12:
        flags.append({
            "level": "WARNING",
            "type": "ABSTRACT_WORD_OVERUSE",
            "message": f"抽象关键词出现 {abstract_count} 次（超过阈值 12），叙述可能过于空泛。"
        })
        suggestions.append(
            f"将命运/危机/似乎/仿佛类词汇替换为具体的人物行动、物件或场景变化。"
        )

    # 5. 转折词重复
    cn_count = count_chinese(text)
    transition_density = transition_count / max(cn_count / 100, 1)
    if transition_density > 2.5:
        flags.append({
            "level": "WARNING",
            "type": "TRANSITION_WORD_OVERUSE",
            "message": (
                f"转折/连接词出现 {transition_count} 次 "
                f"（密度 {transition_density:.1f}/百字），可能过度使用衔接词。"
            )
        })
        suggestions.append("减少但是/然而/所以/于是等连接词，用动作或场景转换自然过渡。")

    status = "WARNING" if flags else "PASS"

    return {
        "guard": "style_variation_guard",
        "version": "v0.4.0",
        "status": status,
        "chapter_no": chapter_no,
        "sentence_opening_variety": opening_info,
        "sentence_len_cv": sent_len_cv,
        "paragraph_len_cv": para_len_cv,
        "abstract_word_count": abstract_count,
        "transition_word_count": transition_count,
        "opening_repetition_ratio": opening_ratio,
        "total_sentences": len(sentences),
        "total_paragraphs": len(paragraphs),
        "flags": flags,
        "suggestions": suggestions,
        "hard_fail": False,
    }


# ═══════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Style Variation Guard")
    parser.add_argument("--input", required=True, help="章节 TXT 文件路径")
    parser.add_argument("--chapter-no", type=int, default=1)
    parser.add_argument("--out", default=None, help="输出 JSON 报告路径")
    args = parser.parse_args()

    content = Path(args.input).read_text(encoding="utf-8")
    report = build_report(content, args.chapter_no)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    if report["status"] == "WARNING":
        print(f"\n[WARN] Style variation: {len(report['flags'])} issues found")
    else:
        print(f"\n[OK] Style variation check passed")


if __name__ == "__main__":
    main()
