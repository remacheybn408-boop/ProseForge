#!/usr/bin/env python3
"""dialogue_structure_guard.py — 对白结构门禁 v1.0

防止所有角色像背稿子一样用规整的完整句对话。检查 5 个结构维度：
1. 打断: 角色是否切断另一个角色？（句中"..." 或 "——"断开）
2. 未完成句: 对白行是否不以 。！？ 结束？
3. 动作节拍: 对白之间的身体动作
4. 称呼变化: 角色对同一人使用不同名字/称呼
5. 句长变化: 各角色对白行长度的 CV > 0.3

不再涵盖 AI_EXPLAIN_MARKER（"也就是说/换言之/这意味着"等）——
该维度已迁移到 anti_ai_guard 的 AI_EXPLAIN_PATTERNS。

只输出 WARNING（不 FAIL），hard_fail 始终为 False。

历史: 由 dialogue_naturalness_guard 重构而来（v0.7.3 起拆分）。
"""
import re, json, argparse
from pathlib import Path
from collections import Counter
from src.utils.text_metrics import length_cv

try:
    from version import get_version
except ImportError:
    def get_version() -> str:
        return "v1.0"


# ═══════════════════════════════════════════════════
# 正则模式
# ═══════════════════════════════════════════════════

# 中英文引号包裹的对白
DIALOGUE_LINE = re.compile(r'[""「」]([^""「」]+)[""「」]')

# 句中打断标记: ... 或 —— 出现在句子中间（不在末尾）
INTERRUPTION_MARKER = re.compile(r'[^。！？\n][…]{2,}|[^。！？\n]——')

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


# ═══════════════════════════════════════════════════
# 检测函数
# ═══════════════════════════════════════════════════

def extract_dialogue_lines(text: str) -> list[str]:
    """从文本中提取所有对白行（引号内容）"""
    return [m.group(1) for m in DIALOGUE_LINE.finditer(text)]


def count_interruptions(dialogue_lines: list[str]) -> int:
    """检测打断: 句子中间的 ... 或 ——"""
    return sum(1 for line in dialogue_lines if INTERRUPTION_MARKER.search(line))


def count_unfinished_sentences(dialogue_lines: list[str]) -> int:
    """检测未完成句: 对白行不以 。！？ 结束"""
    count = 0
    for line in dialogue_lines:
        stripped = line.strip()
        if stripped and not SENTENCE_END.search(stripped):
            count += 1
    return count


def count_action_beats(text: str) -> int:
    """检测动作节拍: 对白之外的身体动作描述"""
    narration = re.sub(r'[""「」][^""「」]+[""「」]', '', text)
    return len(ACTION_BEAT_WORDS.findall(narration))


def compute_address_variation_score(text: str, dialogue_lines: list[str]) -> float:
    """计算称呼变化分数 0-1。多样性越高越好。"""
    narration = re.sub(r'[""「」][^""「」]+[""「」]', '', text)
    addresses = ADDRESS_PATTERN.findall(narration)
    dialogue_text = ' '.join(dialogue_lines)
    addresses.extend(ADDRESS_PATTERN.findall(dialogue_text))

    if not addresses:
        return 0.5

    counter = Counter(addresses)
    unique = len(counter)
    total = sum(counter.values())
    diversity = unique / max(total, 1)
    return round(min(1.0, diversity * 5), 3)


def compute_speaker_length_cv(text: str) -> tuple[float, int]:
    """计算各"说话人"对白句长的变异系数。
    启发式: 交替的引号内容视为不同说话人。
    """
    dialogue_lines = extract_dialogue_lines(text)
    if len(dialogue_lines) < 2:
        return 0.0, 0

    speaker_a, speaker_b = [], []
    for i, line in enumerate(dialogue_lines):
        stripped = line.strip()
        if not stripped:
            continue
        (speaker_a if i % 2 == 0 else speaker_b).append(len(stripped))

    all_lengths = speaker_a + speaker_b
    if len(all_lengths) < 3:
        return 0.0, 2
    return length_cv(all_lengths), (2 if speaker_a and speaker_b else 1)


# ═══════════════════════════════════════════════════
# 主评分
# ═══════════════════════════════════════════════════

def compute_dialogue_structure_score(
    dialogue_lines: list[str],
    text: str,
) -> float:
    """计算对话结构综合分数 0-1。
    各维度加权: 打断(0.22), 未完成句(0.17), 动作节拍(0.28),
    称呼变化(0.22), 长度CV(0.11)
    """
    if not dialogue_lines:
        return 0.5

    total_lines = max(len(dialogue_lines), 1)

    interruption_ratio = count_interruptions(dialogue_lines) / total_lines
    interruption_score = min(1.0, interruption_ratio * 8)

    unfinished_ratio = count_unfinished_sentences(dialogue_lines) / total_lines
    unfinished_score = min(1.0, unfinished_ratio * 5)

    cn_count = len([c for c in text if '一' <= c <= '鿿'])
    action_beats = count_action_beats(text)
    action_ratio = action_beats / max(cn_count / 50, 1)
    action_score = min(1.0, action_ratio * 2)

    address_score = compute_address_variation_score(text, dialogue_lines)

    cv, _ = compute_speaker_length_cv(text)
    cv_score = min(1.0, cv / 0.5)

    score = (
        interruption_score * 0.22 +
        unfinished_score * 0.17 +
        action_score * 0.28 +
        address_score * 0.22 +
        cv_score * 0.11
    )

    return round(min(1.0, max(0.0, score)), 3)


# ═══════════════════════════════════════════════════
# 报告构建
# ═══════════════════════════════════════════════════

def build_report(text: str, chapter_no: int = 1) -> dict:
    """构建对话结构门禁报告"""
    dialogue_lines = extract_dialogue_lines(text)

    if not dialogue_lines:
        return {
            "guard": "dialogue_structure_guard",
            "version": get_version(),
            "status": "PASS",
            "chapter_no": chapter_no,
            "dialogue_structure_score": 1.0,
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

    interruption_count = count_interruptions(dialogue_lines)
    unfinished_count = count_unfinished_sentences(dialogue_lines)
    action_beat_count = count_action_beats(text)
    address_score = compute_address_variation_score(text, dialogue_lines)
    cv, speaker_count = compute_speaker_length_cv(text)
    structure_score = compute_dialogue_structure_score(dialogue_lines, text)

    flags = []
    suggestions = []
    total_lines = len(dialogue_lines)

    if total_lines > 5 and interruption_count == 0:
        flags.append({
            "level": "WARNING",
            "type": "NO_INTERRUPTIONS",
            "message": "对话中没有任何打断，所有角色都在等待对方说完，可能不够自然。",
        })
        suggestions.append('加入角色打断对方的场景，用“……”或“——”表示话语中断。')

    unfinished_ratio = unfinished_count / total_lines
    if unfinished_ratio < 0.1 and total_lines > 5:
        flags.append({
            "level": "WARNING",
            "type": "ALL_COMPLETE_SENTENCES",
            "message": f"对白行 {unfinished_ratio:.0%} 未完成，几乎每句都是完整句，像书面语。",
        })
        suggestions.append("让角色说话时偶尔不说完，模拟真实交谈中的被打断或犹豫。")

    cn_count = len([c for c in text if '一' <= c <= '鿿'])
    beat_ratio = action_beat_count / max(cn_count / 100, 1)
    if beat_ratio < 1.5 and total_lines > 3:
        flags.append({
            "level": "WARNING",
            "type": "LOW_ACTION_BEATS",
            "message": f"对白之间的动作节拍偏少 ({action_beat_count} 个)，可能是纯对话。",
        })
        suggestions.append("在对白之间穿插角色的小动作（抬手、攥紧、转身、停顿等）。")

    if address_score < 0.3 and total_lines > 5:
        flags.append({
            "level": "WARNING",
            "type": "LOW_ADDRESS_VARIATION",
            "message": f"称呼变化度偏低 ({address_score:.2f})，角色可能只用一种方式称呼彼此。",
        })
        suggestions.append("让角色根据情境变化称呼（正式/亲密/愤怒时用不同称呼）。")

    if cv < 0.3 and speaker_count >= 2 and total_lines > 5:
        flags.append({
            "level": "WARNING",
            "type": "LOW_LENGTH_VARIATION",
            "message": f"对白句长变化系数偏低 ({cv:.3f})，不同角色说话长度太均匀。",
        })
        suggestions.append("让不同角色有不同的话癖：有人啰嗦有人沉默，有人用短句有人用长句。")

    if structure_score < 0.4 and flags:
        flags.insert(0, {
            "level": "WARNING",
            "type": "LOW_STRUCTURE",
            "message": f"对话结构综合评分偏低 ({structure_score:.2f})，建议全面检查。",
        })

    status = "WARNING" if flags else "PASS"

    return {
        "guard": "dialogue_structure_guard",
        "version": get_version(),
        "status": status,
        "chapter_no": chapter_no,
        "dialogue_structure_score": structure_score,
        "interruption_count": interruption_count,
        "unfinished_count": unfinished_count,
        "action_beat_count": action_beat_count,
        "address_variation_score": address_score,
        "speaker_count": speaker_count,
        "speaker_length_cv": cv,
        "total_dialogue_lines": total_lines,
        "flags": flags,
        "suggestions": suggestions,
        "hard_fail": False,
    }


# ═══════════════════════════════════════════════════
# Guard Registry entry point
# ═══════════════════════════════════════════════════

def run_dialogue_structure_check(content: str, chapter_no: int = 0,
                                  *args, **kwargs) -> dict:
    """Guard Registry entry point."""
    return build_report(content, chapter_no)


# ═══════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════

