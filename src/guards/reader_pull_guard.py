#!/usr/bin/env python3
"""
reader_pull_guard.py — 读者追读力门禁 v0.5.0

Pure rule-based, no LLM. Checks whether a chapter has reader retention power (追读力).

Input:
    chapter_text (str)
    previous_chapter_summary (dict or None)
    chapter_no (int)

Output:
    dict with status, hook_present, previous_hook_payoff, micro_payoff,
    new_debt, debt_overload, cool_point_grounded, ending_pull, issues list
"""

import re
from typing import Optional


# ═══════════════════════════════════════════════════
# Keyword / regex patterns
# ═══════════════════════════════════════════════════

# Cliffhanger / question / unresolved action at chapter end
HOOK_PATTERNS = [
    # Direct questions
    r'[？?]',
    # Unresolved action — things just happening or about to happen
    r'(突然|忽然|就在这时|正在此时|话音未落|猛地|骤然|倏地)',
    # Someone appearing / arriving unexpectedly
    r'([一一个人人影]?[道个条抹阵]?(?:人影|身影|黑[影芒]|光[芒影]|气息|声音|脚步声)[出闪现传涌走靠逼])',
    # Door / barrier opening
    r'(门|石门|洞[口府]|[门闸]口|[屏结界]障)[缓猛轰骤]?[然]?(?:开了|[打推拉震冲撞]开|缓[缓慢]打[开]|洞开)',
    # Revelation / discovery hook
    r'(竟然|居然|怎么[会能]|原来|难[难道怪]|这[是就]|那[是就])',
    # Urgency / threat hook (last 200 chars)
    r'(危险|危机|威胁|[杀追]意|杀气|寒[意气芒]|[死死]亡)',
    # Betrayal / twist hook
    r'(背叛|出卖|[叛背]徒|倒戈|反水|翻脸)',
    # Power / upgrade about to happen
    r'(突破|晋[升级]|蜕[变]|觉[醒]|涌[现入出]|[灵真仙神]力)',
]

# Micro payoff — small victory / reveal / progress
MICRO_PAYOFF_PATTERNS = [
    # Progress markers
    r'(成功|终于|总算是|算是|好歹|至少|起码)',
    # Discovery / insight
    r'(发现|明白[了]?|恍然|原来如此|懂了|理解[了]?|意识到)',
    # Small victory
    r'(赢了?|战胜|通过|过了|撑过|扛过|顶住|守住了?)',
    # Skill/ability gain
    r'(学会了?|掌握了?|领悟|顿悟|领会|感受到)',
    # Object/item gain
    r'(得到[了]?|获得了?|拿到了?|捡到|找到[了]?)',
    # Resolution of a minor thread
    r'(解决|摆平|处理[好完掉]|搞定|收[拾好])',
    # Character growth
    r'(成长|进步|变强[了]?|提[升高]了?|增[强长加])',
    # Relationship progress
    r'(信任|认可|承认|看[好重]|改观|刮目)',
]

# New debt — introduces new question/thread
NEW_DEBT_PATTERNS = [
    # Questions raised
    r'(什么[意思]?|为什么|怎么[回会]|究竟|到底)',
    # Mystery / unknown
    r'(不知[道晓]|未[知解明]|谜[团题底]|秘密|隐[情秘瞒藏])',
    # New character / faction introduced
    r'(新[来的]?|陌生|从未见|头一次|第一[次回个])',
    # New location mentioned
    r'(听说[过]?|传说[中]?|据[说称传闻]|古老|禁[地忌区域])',
    # Foreshadowing
    r'(日后|将来|以后|迟早|终[有将]|总有一天)',
    # Pending threat
    r'(盯上[了]?|暗中|暗[处地里中]|潜[伏藏]|窥[视探伺])',
    # Unresolved conflict
    r'(还[没未]|尚未|[尚仍]未|依旧|依然|仍[然旧])',
]

# Cool point — concrete action/object-based cool moment
COOL_POINT_PATTERNS = [
    # Concrete action
    r'(一剑|[一拳一刀一掌一指一枪一棍一斧]|反手|回身|侧身)',
    # Object-based
    r'(灵石|法器|丹药|[刀剑枪斧][光锋芒刃]|阵[法盘眼]|符[箓篆纸])',
    # Physical description + action
    r'(纹丝不动|稳如泰山|快如闪电|[火光寒雷]光|残影|虚影)',
    # Concrete result
    r'(碎[裂了]|炸[开了裂]|裂[开了]|塌[了陷]|崩[开毁])',
    # Measured/quantified (science-monk style)
    r'([一二三四五六七八九十百千万]+[倍成尺丈斤石斗升丈])',
    # Spatial awareness
    r'(三[尺丈步寸]|一[尺丈步寸]|数[尺丈步寸]|半[尺丈步寸])',
]

# Ending pull — does ending make reader want next chapter
ENDING_PULL_PATTERNS = [
    r'[？?]',                                    # Question
    r'未完待续|欲知后事|下回分解',                  # Explicit continuation
    r'(突然|忽然|就在这时|正在此时|话音未落)',        # Sudden interruption
    r'(他怎么也|[没未]想到|出乎意料|意想不到)',       # Surprise
    r'(危险|危机|威胁|[杀追]意|杀气)',               # Danger
    r'(下一[步个关章回]|接[下来着]|即将|马上|立刻)',   # Next step
]


# ═══════════════════════════════════════════════════
# Core checking functions
# ═══════════════════════════════════════════════════

def _count_patterns(text: str, patterns: list[str]) -> int:
    """Count how many distinct patterns match in the given text."""
    count = 0
    for pat in patterns:
        if re.search(pat, text):
            count += 1
    return count


def _check_hook_present(text: str) -> dict:
    """Check if chapter ends with a cliffhanger/question/unresolved action.
    
    Focuses on the last ~300 characters (final paragraph/ending).
    """
    ending = text.rstrip()
    # Take last ~300 chars for ending analysis
    ending_chunk = ending[-300:] if len(ending) > 300 else ending
    
    hook_count = _count_patterns(ending_chunk, HOOK_PATTERNS)
    present = hook_count >= 1
    
    return {
        "present": present,
        "confidence": min(hook_count / 4.0, 1.0),
        "matched_count": hook_count,
    }


def _check_previous_hook_payoff(
    text: str,
    previous_chapter_summary: Optional[dict],
) -> dict:
    """Check if previous chapter's hook was addressed."""
    if not previous_chapter_summary:
        return {"payoff": True, "reason": "no_previous_hook_data", "confidence": 1.0}
    
    prev_hook = previous_chapter_summary.get("ending_hook", "")
    prev_content = previous_chapter_summary.get("content_preview", "")
    
    if not prev_hook and not prev_content:
        return {"payoff": True, "reason": "no_previous_hook_found", "confidence": 1.0}
    
    # Simple continuity: check if key terms from prev hook appear in current
    search_text = prev_hook + " " + prev_content
    # Extract meaningful words (2-4 chars Chinese phrases)
    keywords = re.findall(r'[\u4e00-\u9fff]{2,4}', search_text)
    keywords = [k for k in keywords if len(k) >= 2 and k not in 
                ('一个', '这个', '那个', '他们', '我们', '没有', '已经', '所以', '因为', '但是',
                 '不过', '而且', '然后', '可以', '如果', '虽然', '一定', '这里', '那里')]
    
    if not keywords:
        return {"payoff": True, "reason": "no_extractable_keywords", "confidence": 1.0}
    
    matched = 0
    for kw in keywords[:8]:  # Check top 8 keywords
        if kw in text:
            matched += 1
    
    ratio = matched / min(len(keywords), 8) if keywords else 0
    payoff = ratio >= 0.25  # At least 25% of keywords appear
    
    return {
        "payoff": payoff,
        "reason": f"matched {matched}/{min(len(keywords), 8)} keywords from prev hook",
        "confidence": ratio,
    }


def _check_micro_payoff(text: str) -> dict:
    """Check for at least one small victory/reveal/progress."""
    count = _count_patterns(text, MICRO_PAYOFF_PATTERNS)
    has_payoff = count >= 1
    
    return {
        "present": has_payoff,
        "matched_count": count,
        "confidence": min(count / 3.0, 1.0),
    }


def _check_new_debt(text: str) -> dict:
    """Check how many new questions/threads are introduced."""
    # Count distinct patterns matched
    matched = []
    for pat in NEW_DEBT_PATTERNS:
        if re.search(pat, text):
            matched.append(pat)
    
    debt_count = len(matched)
    
    return {
        "count": debt_count,
        "overloaded": debt_count > 2,
    }


def _check_cool_point_grounded(text: str) -> dict:
    """Check for concrete action/object-based cool moment (not just shouting)."""
    count = _count_patterns(text, COOL_POINT_PATTERNS)
    grounded = count >= 2  # Need at least 2 concrete elements
    
    # Also check for "shouting-only" cool moments (bad)
    shout_patterns = [
        r'(哈{2,})',                # Laughing
        r'([大高暴怒]喝|[大高]吼|怒[吼喝喊])',  # Shouting
        r'(狂妄|猖狂|嚣[张]|大[笑])',   # Arrogant
    ]
    shout_count = _count_patterns(text, shout_patterns)
    
    return {
        "grounded": grounded,
        "concrete_count": count,
        "shout_count": shout_count,
        "confidence": min(count / 4.0, 1.0),
    }


def _check_ending_pull(text: str) -> dict:
    """Check if the ending makes reader want to read the next chapter."""
    ending = text.rstrip()
    ending_chunk = ending[-400:] if len(ending) > 400 else ending
    
    # Check for concluding/ending language (anti-pull)
    conclusion_patterns = [
        r'(这就[是样]|到此为止|结束[了]?|告[一]?段落|落下帷幕)',
        r'(安[心稳全]|平静|宁静|祥和|安稳|满足)',
    ]
    has_conclusion = _count_patterns(ending_chunk, conclusion_patterns) > 0
    
    pull_count = _count_patterns(ending_chunk, ENDING_PULL_PATTERNS)
    has_pull = pull_count >= 1 and not has_conclusion
    
    return {
        "present": has_pull,
        "matched_count": pull_count,
        "has_conclusion": has_conclusion,
        "confidence": min(pull_count / 4.0, 1.0) if has_pull else 0.0,
    }


# ═══════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════

def run_reader_pull_check(
    chapter_text: str,
    chapter_no: int = 0,
    previous_chapter_summary: Optional[dict] = None,
) -> dict:
    """
    Run reader pull (追读力) guard on a chapter.
    
    Args:
        chapter_text: Full text of the chapter.
        chapter_no: Chapter number.
        previous_chapter_summary: Optional dict with 'ending_hook' and 
            'content_preview' from the previous chapter.
    
    Returns:
        dict with status (WARN/PASS), all check results, and issues list.
        Never returns FAIL.
    """
    hook = _check_hook_present(chapter_text)
    prev_payoff = _check_previous_hook_payoff(chapter_text, previous_chapter_summary)
    micro = _check_micro_payoff(chapter_text)
    debt = _check_new_debt(chapter_text)
    cool = _check_cool_point_grounded(chapter_text)
    ending = _check_ending_pull(chapter_text)
    
    issues = []
    
    # Build issue list
    if not hook["present"]:
        issues.append({
            "code": "NO_HOOK",
            "severity": "WARN",
            "message": "章节结尾缺少悬念/问题/未完成动作，读者可能不会追读下一章",
            "suggestion": "在结尾处增加：未解答的问题、突然的打断、新威胁的出现、或一个引人好奇的发现",
            "confidence": 1.0 - hook["confidence"],
        })
    
    if not prev_payoff["payoff"]:
        issues.append({
            "code": "UNRESOLVED_PREV_HOOK",
            "severity": "WARN",
            "message": f"上一章的悬念似乎未被回应: {prev_payoff['reason']}",
            "suggestion": "确保本章回应上一章结尾留下的问题或悬念，不要让读者等太久",
            "confidence": 1.0 - prev_payoff["confidence"],
        })
    
    if not micro["present"]:
        issues.append({
            "code": "NO_MICRO_PAYOFF",
            "severity": "WARN",
            "message": "章节缺少微小回报：没有发现/胜利/进步/成长——纯铺垫章节读者容易流失",
            "suggestion": "每章至少给读者一个'获得感'：小胜利、新发现、能力提升、或关系进展",
            "confidence": 0.85,
        })
    
    if debt["overloaded"]:
        issues.append({
            "code": "DEBT_OVERLOAD",
            "severity": "WARN",
            "message": f"本章引入过多新线索({debt['count']}个)而无足够回报，读者会感到混乱",
            "suggestion": "控制每章新线索在2个以内，未解决的旧线索优先处理",
            "confidence": 0.75,
        })
    elif debt["count"] == 0:
        issues.append({
            "code": "NO_NEW_DEBT",
            "severity": "WARN",
            "message": "本章没有引入任何新疑问/线索，剧情可能缺乏推进感",
            "suggestion": "适当引入新的疑问或伏笔，让读者保持好奇心",
            "confidence": 0.55,
        })
    
    if not cool["grounded"]:
        issues.append({
            "code": "COOL_POINT_UNGROUNDED",
            "severity": "WARN",
            "message": f"缺少具体动作/物件锚点的'帅'时刻({cool['concrete_count']}个具体元素)",
            "suggestion": "用具体动作和物件代替空洞的喊叫——'他一剑劈开石门'比'他大喝一声'更酷",
            "confidence": 0.70,
        })
    
    if not ending["present"]:
        issues.append({
            "code": "WEAK_ENDING",
            "severity": "WARN",
            "message": "结尾缺乏追读拉力——读者可能在此放下",
            "suggestion": "结尾用悬念/问题/突发打断来制造'必须看下一章'的冲动",
            "confidence": 0.80,
        })
    elif ending.get("has_conclusion"):
        issues.append({
            "code": "CONCLUSIVE_ENDING",
            "severity": "WARN",
            "message": "结尾有完结感语言，可能削弱追读拉力",
            "suggestion": "即使本章故事告一段落，结尾仍应埋入新的好奇点",
            "confidence": 0.65,
        })
    
    status = "WARN" if issues else "PASS"
    
    return {
        "guard": "reader_pull_guard",
        "version": "v0.5.0",
        "status": status,
        "final_decision": status,
        "chapter_no": chapter_no,
        "hook_present": hook,
        "previous_hook_payoff": prev_payoff,
        "micro_payoff": micro,
        "new_debt": debt,
        "debt_overload": debt["overloaded"],
        "cool_point_grounded": cool,
        "ending_pull": ending,
        "issues": issues,
        "warnings": [i["message"] for i in issues],
        "violations": [i["message"] for i in issues],
    }


# ═══════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse, json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Reader Pull Guard v0.5.0")
    parser.add_argument("content_file", help="Chapter TXT file path")
    parser.add_argument("--chapter-no", type=int, default=1, help="Chapter number")
    parser.add_argument("--prev-summary", default=None, help="Previous chapter summary JSON file")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    args = parser.parse_args()

    text = Path(args.content_file).read_text(encoding="utf-8")
    
    prev = None
    if args.prev_summary and Path(args.prev_summary).exists():
        prev = json.loads(Path(args.prev_summary).read_text(encoding="utf-8"))
    
    report = run_reader_pull_check(text, args.chapter_no, prev)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    
    if args.output:
        p = Path(args.output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    
    status = report["status"]
    if status == "WARN":
        print(f"\n[WARN] Reader pull: {len(report['issues'])} issues")
    else:
        print(f"\n[OK] Reader pull check passed")
