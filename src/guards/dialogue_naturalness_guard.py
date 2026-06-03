#!/usr/bin/env python3
"""
dialogue_naturalness_guard.py — 对白自然度门禁 v0.4.0

防止所有角色像AI一样用完整句子解释事物。
检查每个对白场景中的自然度指标：
1. 打断: 角色是否切断另一个角色？（句中"..." 或 "——"断开）
2. 未完成句: 对白行是否不以 。！？ 结束？
3. 动作节拍: 对白之间的身体动作
4. 称呼变化: 角色对同一人使用不同名字/称呼
5. 句长变化: 各角色对白行长度的 CV > 0.3

只输出 WARNING（不 FAIL），hard_fail 始终为 False。

用法:
  python scripts/dialogue_naturalness_guard.py \
    --input chapter.txt --chapter-no 1 --out report.json
"""
import re, json, sys, argparse, statistics
from pathlib import Path
from collections import Counter


# ═══════════════════════════════════════════════════
# 正则模式
# ═══════════════════════════════════════════════════

# 中英文引号包裹的对白
DIALOGUE_LINE = re.compile(r'[""「」]([^""「」]+)[""「」]')

# 句中打断标记: ... 或 —— 出现在句子中间（不在末尾）
INTERRUPTION_MARKER = re.compile(r'[^。！？\n][…]{2,}|[^。！？\n]——')

# 未完成句: 对白行不以标准句尾标点结束
UNFINISHED_SENTENCE = re.compile(r'[^。！？""」\s]$')

# 常见的句子结束标点
SENTENCE_END = re.compile(r'[。！？]$')

# 动作节拍词
ACTION_BEAT_WORDS = re.compile(
    r'(抬手|放下|拿起|放下|推开|拉开门|转身|回头|蹲下|站起|坐下|走过去|退后|往前|往后退'
    r'|攥|握|捏|掐|按|推|拉|扯|拽|甩|扔|丢|砸|砍|刺|劈|划|点|指|敲|拍|磕|抹|擦'
    r'|拔出|收剑|拔剑|抽刀|掏|取出|放回|塞进|揣|揣进|揣入'
    r'|走|跑|跳|爬|攀|翻|越|跨|踏|踩|踢|踹'
    r'|点头|摇头|叹息|呼|吸|闭眼|睁眼|扫|盯|瞥|望|看'
    r'|沉默|停顿|不语|没有回答|没说话|没有回应|静默)'
)

# 称呼模式的启发式检测
ADDRESS_PATTERN = re.compile(
    r'(周砚|沈师姐|矿头|老张|小月|师兄|师姐|师弟|师妹|师父|师尊|掌门|长老'
    r'|前辈|晚辈|大人|小姐|公子|姑娘|少爷|老爷|夫人|娘子|相公'
    r'|[你您]|[他她它]|我们|你们|他们|咱们)'
)

# 抽象/解释性语言标记（AI腔）
AI_EXPLAIN_MARKER = re.compile(
    r'(也就是说|换言之|换句话说|简而言之|总而言之|总的来看|可以这么说'
    r'|这意味着|这就意味着|这说明|这表明|这代表了|这揭示了|这暗示着)'
)


# ═══════════════════════════════════════════════════
# 检测函数
# ═══════════════════════════════════════════════════

def extract_dialogue_lines(text: str) -> list[str]:
    """从文本中提取所有对白行（引号内容）"""
    return [m.group(1) for m in DIALOGUE_LINE.finditer(text)]


def count_interruptions(dialogue_lines: list[str]) -> int:
    """
    检测打断: 句子中间的 ... 或 ——
    """
    count = 0
    for line in dialogue_lines:
        if INTERRUPTION_MARKER.search(line):
            count += 1
    return count


def count_unfinished_sentences(dialogue_lines: list[str]) -> int:
    """
    检测未完成句: 对白行不以 。！？ 结束
    """
    count = 0
    for line in dialogue_lines:
        stripped = line.strip()
        if stripped and not SENTENCE_END.search(stripped):
            count += 1
    return count


def count_action_beats(text: str) -> int:
    """
    检测动作节拍: 对白之外的身体动作描述
    """
    # 去掉引号内容后，数动作词
    narration = re.sub(r'[""「」][^""「」]+[""「」]', '', text)
    return len(ACTION_BEAT_WORDS.findall(narration))


def compute_address_variation_score(text: str, dialogue_lines: list[str]) -> float:
    """
    计算称呼变化分数 0-1。
    检测同一角色是否使用多种称呼方式。
    启发式方法: 统计所有称呼词的频率分布。
    """
    # 提取旁白中的称呼
    narration = re.sub(r'[""「」][^""「」]+[""「」]', '', text)
    addresses = ADDRESS_PATTERN.findall(narration)

    # 对白中的称呼
    dialogue_text = ' '.join(dialogue_lines)
    addresses.extend(ADDRESS_PATTERN.findall(dialogue_text))

    if not addresses:
        return 0.5

    counter = Counter(addresses)
    unique = len(counter)
    total = sum(counter.values())

    # 多样性越高越好
    diversity = unique / max(total, 1)
    # 映射到更合理的 0-1 范围
    return round(min(1.0, diversity * 5), 3)


def compute_speaker_length_cv(text: str) -> tuple[float, int]:
    """
    计算各"说话人"对白句长的变异系数。
    启发式: 交替的引号内容视为不同说话人。
    """
    dialogue_lines = extract_dialogue_lines(text)
    if len(dialogue_lines) < 2:
        return 0.0, 0

    # 简单启发: 交替引号内容视为两人对话
    # 将奇数位和偶数位分到两组
    speaker_a = []
    speaker_b = []

    for i, line in enumerate(dialogue_lines):
        stripped = line.strip()
        if not stripped:
            continue
        if i % 2 == 0:
            speaker_a.append(len(stripped))
        else:
            speaker_b.append(len(stripped))

    all_lengths = speaker_a + speaker_b
    if len(all_lengths) < 3:
        return 0.0, 2

    mean_val = statistics.mean(all_lengths)
    std_val = statistics.stdev(all_lengths) if len(all_lengths) > 1 else 0
    cv = std_val / max(mean_val, 1)

    return round(cv, 3), (2 if speaker_a and speaker_b else 1)


def detect_ai_explanation_patterns(dialogue_lines: list[str]) -> int:
    """检测AI解释性语言"""
    count = 0
    for line in dialogue_lines:
        if AI_EXPLAIN_MARKER.search(line):
            count += 1
    return count


# ═══════════════════════════════════════════════════
# 主评分
# ═══════════════════════════════════════════════════

def compute_dialogue_naturalness_score(
    dialogue_lines: list[str],
    text: str
) -> float:
    """
    计算对话自然度综合分数 0-1。
    各维度加权: 打断(0.2), 未完成句(0.15), 动作节拍(0.25),
    称呼变化(0.2), 长度CV(0.1), AI解释(0.1)
    """
    if not dialogue_lines:
        return 0.5

    total_lines = max(len(dialogue_lines), 1)

    # 打断率: 合理的打断表明自然对话
    interruption_ratio = count_interruptions(dialogue_lines) / total_lines
    interruption_score = min(1.0, interruption_ratio * 8)  # ~12.5% 打断给满分

    # 未完成句率: 一定比例是自然的
    unfinished_ratio = count_unfinished_sentences(dialogue_lines) / total_lines
    unfinished_score = min(1.0, unfinished_ratio * 5)  # ~20% 未完成句给满分

    # 动作节拍率: 按总中文字符数归一化
    cn_count = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
    action_beats = count_action_beats(text)
    action_ratio = action_beats / max(cn_count / 50, 1)  # 每50字一个动作节拍
    action_score = min(1.0, action_ratio * 2)

    # 称呼变化
    address_score = compute_address_variation_score(text, dialogue_lines)

    # 句长CV
    length_cv, _ = compute_speaker_length_cv(text)
    cv_score = min(1.0, length_cv / 0.5)  # CV=0.5 给满分

    # AI解释模式（反向: 越少越好）
    ai_explain_count = detect_ai_explanation_patterns(dialogue_lines)
    ai_explain_ratio = ai_explain_count / total_lines
    ai_score = max(0.0, 1.0 - ai_explain_ratio * 10)

    # 加权
    score = (
        interruption_score * 0.20 +
        unfinished_score * 0.15 +
        action_score * 0.25 +
        address_score * 0.20 +
        cv_score * 0.10 +
        ai_score * 0.10
    )

    return round(min(1.0, max(0.0, score)), 3)


# ═══════════════════════════════════════════════════
# 报告构建
# ═══════════════════════════════════════════════════

def build_report(text: str, chapter_no: int = 1) -> dict:
    """构建对白自然度门禁报告"""
    dialogue_lines = extract_dialogue_lines(text)

    if not dialogue_lines:
        return {
            "guard": "dialogue_naturalness_guard",
            "version": "v0.4.0",
            "status": "PASS",
            "chapter_no": chapter_no,
            "dialogue_naturalness_score": 1.0,
            "interruption_count": 0,
            "unfinished_count": 0,
            "action_beat_count": 0,
            "address_variation_score": 0.5,
            "speaker_count": 0,
            "speaker_length_cv": 0.0,
            "flags": [],
            "suggestions": ["本章无对白内容，无需检测。"],
            "hard_fail": False,
        }

    # 各项指标
    interruption_count = count_interruptions(dialogue_lines)
    unfinished_count = count_unfinished_sentences(dialogue_lines)
    action_beat_count = count_action_beats(text)
    address_score = compute_address_variation_score(text, dialogue_lines)
    length_cv, speaker_count = compute_speaker_length_cv(text)
    naturalness_score = compute_dialogue_naturalness_score(dialogue_lines, text)
    ai_explain_count = detect_ai_explanation_patterns(dialogue_lines)

    # 构建 flags 和建议
    flags = []
    suggestions = []

    total_lines = len(dialogue_lines)

    # 打断检查
    if total_lines > 5 and interruption_count == 0:
        flags.append({
            "level": "WARNING",
            "type": "NO_INTERRUPTIONS",
            "message": "对话中没有任何打断，所有角色都在等待对方说完，可能不够自然。"
        })
        suggestions.append('加入角色打断对方的场景，用\u201c\u2026\u2026\u201d或\u201c\u2014\u2014\u201d表示话语中断。')

    # 未完成句检查
    unfinished_ratio = unfinished_count / total_lines
    if unfinished_ratio < 0.1 and total_lines > 5:
        flags.append({
            "level": "WARNING",
            "type": "ALL_COMPLETE_SENTENCES",
            "message": f"对白行 {unfinished_ratio:.0%} 未完成，几乎每句都是完整句，像书面语。"
        })
        suggestions.append("让角色说话时偶尔不说完，模拟真实交谈中的被打断或犹豫。")

    # 动作节拍检查
    cn_count = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
    beat_ratio = action_beat_count / max(cn_count / 100, 1)
    if beat_ratio < 1.5 and total_lines > 3:
        flags.append({
            "level": "WARNING",
            "type": "LOW_ACTION_BEATS",
            "message": f"对白之间的动作节拍偏少 ({action_beat_count} 个)，可能是纯对话。"
        })
        suggestions.append("在对白之间穿插角色的小动作（抬手、攥紧、转身、停顿等）。")

    # 称呼变化检查
    if address_score < 0.3 and total_lines > 5:
        flags.append({
            "level": "WARNING",
            "type": "LOW_ADDRESS_VARIATION",
            "message": f"称呼变化度偏低 ({address_score:.2f})，角色可能只用一种方式称呼彼此。"
        })
        suggestions.append("让角色根据情境变化称呼（正式/亲密/愤怒时用不同称呼）。")

    # 句长CV检查
    if length_cv < 0.3 and speaker_count >= 2 and total_lines > 5:
        flags.append({
            "level": "WARNING",
            "type": "LOW_LENGTH_VARIATION",
            "message": f"对白句长变化系数偏低 ({length_cv:.3f})，不同角色说话长度太均匀。"
        })
        suggestions.append("让不同角色有不同的话癖：有人啰嗦有人沉默，有人用短句有人用长句。")

    # AI解释模式检查
    if ai_explain_count > 0:
        flags.append({
            "level": "WARNING",
            "type": "AI_EXPLANATION_PATTERN",
            "message": f"检测到 {ai_explain_count} 处AI解释腔（'也就是说/这意味着'等）。"
        })
        suggestions.append("删除对白中的解释性连接词，让信息通过对话中的动作和情绪传递。")

    # 综合自然度不足
    if naturalness_score < 0.4 and flags:
        flags.insert(0, {
            "level": "WARNING",
            "type": "LOW_NATURALNESS",
            "message": f"对白自然度综合评分偏低 ({naturalness_score:.2f})，建议全面检查。"
        })

    status = "WARNING" if flags else "PASS"

    return {
        "guard": "dialogue_naturalness_guard",
        "version": "v0.4.0",
        "status": status,
        "chapter_no": chapter_no,
        "dialogue_naturalness_score": naturalness_score,
        "interruption_count": interruption_count,
        "unfinished_count": unfinished_count,
        "action_beat_count": action_beat_count,
        "address_variation_score": address_score,
        "speaker_count": speaker_count,
        "speaker_length_cv": length_cv,
        "ai_explain_count": ai_explain_count,
        "total_dialogue_lines": total_lines,
        "flags": flags,
        "suggestions": suggestions,
        "hard_fail": False,
    }


# ═══════════════════════════════════════════════════
# Guard Registry entry point (v0.4.5)
# ═══════════════════════════════════════════════════

def run_dialogue_naturalness_check(content: str, chapter_no: int = 0,
                                   *args, **kwargs) -> dict:
    """Guard Registry entry point. Wraps build_report()."""
    return build_report(content, chapter_no)


# ═══════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Dialogue Naturalness Guard")
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
        print(f"\n[WARN] Dialogue naturalness: {len(report['flags'])} issues found")
    else:
        print(f"\n[OK] Dialogue naturalness check passed")


if __name__ == "__main__":
    main()
