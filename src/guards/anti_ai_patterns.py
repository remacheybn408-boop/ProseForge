#!/usr/bin/env python3
"""
anti_ai_patterns.py — Unified AI腔 Pattern Library v0.4.5

ALL anti_ai rules live here. No other file may copy-paste patterns.
post and orchestrator share the same matching logic through this module.

Key change from v0.4.0:
  - "不是A而是B" is now scored by density, not single-match WARN.
  - Sentences with physical evidence (动作/实验/物件) get reduced weight.
  - Punctuation-normalised matching catches separator variants.
"""

import re
from typing import Tuple


# ═══════════════════════════════════════════════════
# Pattern definitions
# ═══════════════════════════════════════════════════

def normalize_punct(text: str) -> str:
    """Normalize Chinese punctuation for pattern matching."""
    # Collapse varied separators to space
    text = re.sub(r"[，、；;：:\\s]+", " ", text)
    text = re.sub(r"[—–-]+", " ", text)
    return text


# "不是A而是B" patterns (with flexible separator)
NOT_A_B_PATTERNS = [
    (r"不是.{1,40}而是", "NOT_A_ER_SHI"),
    (r"并非.{1,40}而是", "BING_FEI_A_ER_SHI"),
    (r"不是.{1,40}是(?!说|想|问|不|没|在|会|能)", "NOT_A_SHI"),
    (r"与其说.{1,40}不如说", "YU_QI_SHUO"),
]

# Forbidden AI phrases
AI_CLICHE_PATTERNS = [
    (r"那一刻[，,]?[^。]{0,20}(终于|忽然|突然)", "NA_YI_KE"),
    (r"她?终于明白[了]?", "ZHONG_YU_MING_BAI"),
    (r"她?从未想过", "CONG_WEI_XIANG_GUO"),
    (r"她?终于意识到", "ZHONG_YU_YI_SHI_DAO"),
    (r"沉默了几秒", "CHEN_MO_JI_MIAO"),
    (r"像一座废墟", "XIANG_FEI_XU"),
    (r"是她的救赎", "SHI_JIU_SHU"),
    (r"像一尊雕像", "XIANG_DIAO_XIANG"),
]

# Hard-science lecture patterns (scientific jargon in narration)
HARD_SCIENCE_PATTERNS = [
    (r"根据.{1,30}(方程|公式|定理)", "HARD_SCIENCE_REF"),
    (r"(傅里叶|拓扑|微分方程|偏转方程|量子态|波函数|哈密顿)", "HARD_SCIENCE_TERM"),
]

# False Agency — inanimate things doing human actions (stop-slop)
FALSE_AGENCY_PATTERNS = [
    (r"(灵气|灵力|魔气|真气|元气|煞气|妖气).{1,10}(活跃|躁动|沸腾|暴动|狂暴|苏醒|涌动)", "FALSE_AGENCY"),
    (r"(空气|气氛|氛围|气场).{1,10}(凝重|凝固|紧张|压抑|窒息|诡异|微妙)", "FALSE_AGENCY"),
    (r"(决定|答案|选择|命运|结局).{1,10}(浮现|降临|到来|出现|涌出)", "FALSE_AGENCY"),
    (r"(时间|历史|岁月|天道|规则).{0,5}(给出了|做出了|证明了)", "FALSE_AGENCY"),
]

# Throat-clearing openers — announcement phrases (stop-slop)
THROAT_CLEARING_PATTERNS = [
    (r"(说白了|实话实说|坦白讲|坦白说|讲真|说真的|说实在的)", "THROAT_CLEARING"),
    (r"(不得不说|不得不承认|不能不承认|不能不说)", "THROAT_CLEARING"),
    (r"(说到底|归根结底|从某种意义上说|毫不夸张地说)", "THROAT_CLEARING"),
]

# Dramatic fragmentation — staccato drama (stop-slop)
DRAMATIC_FRAGMENTATION_PATTERNS = [
    (r"[^。]{2,8}。\s*就(这样|那样|这么|那么)。\s*[^。]{2,10}。", "DRAMATIC_FRAGMENT"),
    (r"[^。]{2,8}。\s*[^。]{2,8}。\s*那就是[^。]{2,15}。", "DRAMATIC_FRAGMENT"),
]

# Narrator-from-a-distance — disembodied observation (stop-slop)
NARRATOR_DISTANCE_PATTERNS = [
    (r"没人(注意|察觉|发现|意识到|知道|看见)", "NARRATOR_DISTANCE"),
    (r"人们(总是|往往|常常|似乎|好像|都|都以为)", "NARRATOR_DISTANCE"),
    (r"在这个(世界|时代|时刻|瞬间|地方|角落)", "NARRATOR_DISTANCE"),
]

# Lazy extremes — false authority through absolutes (stop-slop)
LAZY_EXTREME_PATTERNS = [
    (r"一切(都|似乎|好像|仿佛|已经|全都|全部)", "LAZY_EXTREME"),
    (r"所有(人都|的人|的一切|的这些)", "LAZY_EXTREME"),
    (r"从未(有过|见过|想过|感受过|体验过|遇到)", "LAZY_EXTREME"),
    (r"永远(都|无法|不会|改变|值得|不可能)", "LAZY_EXTREME"),
]


# ═══════════════════════════════════════════════════
# Evidence-aware scoring
# ═══════════════════════════════════════════════════

# Physical evidence keywords that reduce AI penalty
EVIDENCE_KEYWORDS = [
    "水缸", "柴刀", "石", "矿", "碗", "树皮", "木牌", "役牌",
    "青苔", "止血丸", "油纸", "草鞋", "炭笔", "馒头", "粥",
    "劈", "砍", "推", "搬", "抬", "抓", "按", "压", "砸",
    "画", "刻", "磨", "擦", "洗", "煮", "烧",
    "裂开", "渗血", "破皮", "流鼻血", "肿包",
    "痉挛", "铁锈味", "水沫子", "手抖", "腿软", "冷汗",
]


def has_physical_evidence(sentence: str) -> bool:
    """Check if a sentence contains physical action or object evidence."""
    return any(kw in sentence for kw in EVIDENCE_KEYWORDS)


# ═══════════════════════════════════════════════════
# Main check function
# ═══════════════════════════════════════════════════

def check_anti_ai(content: str) -> Tuple[int, list[dict]]:
    """
    Run all anti-AI pattern checks on content.

    Returns:
      (score, findings): score 0-100 (higher = more AI-like),
      findings is a list of {code, message, sentence, location, evidence_weight}
    """
    findings = []
    lines = content.split("\n")
    normalized = normalize_punct(content)

    # 1. Check "不是A而是B" patterns
    not_a_b_count = 0
    for pattern, code in NOT_A_B_PATTERNS:
        for m in re.finditer(pattern, normalized):
            # Find approximate line
            pos = m.start()
            line_idx = normalized[:pos].count("\n") if "\n" in normalized else 0
            snippet = content[max(0, pos-40):pos+80].replace("\n", " ")

            evidence_weight = 0.5 if has_physical_evidence(snippet) else 1.0

            findings.append({
                "code": code,
                "message": f"AI句式: '{m.group()[:40]}'",
                "sentence": snippet.strip()[:120],
                "location": f"~第{line_idx+1}行",
                "evidence_weight": evidence_weight,
                "confidence": 0.5 * evidence_weight,  # Lower confidence if evidence present
            })
            not_a_b_count += 1

    # 2. Check AI cliche phrases
    for pattern, code in AI_CLICHE_PATTERNS:
        for m in re.finditer(pattern, content):
            snippet = content[max(0, m.start()-20):m.end()+40].replace("\n", " ")
            findings.append({
                "code": code,
                "message": f"AI套话: '{m.group()[:40]}'",
                "sentence": snippet.strip()[:120],
                "location": "",
                "evidence_weight": 1.0,
                "confidence": 0.9,
            })

    # 3. Check hard science patterns
    for pattern, code in HARD_SCIENCE_PATTERNS:
        for m in re.finditer(pattern, content):
            snippet = content[max(0, m.start()-20):m.end()+40].replace("\n", " ")
            findings.append({
                "code": code,
                "message": f"硬科普: '{m.group()[:40]}'",
                "sentence": snippet.strip()[:120],
                "location": "",
                "evidence_weight": 0.5,
                "confidence": 0.4,
            })

    # 4. Check False Agency (事物的拟人动作 — stop-slop)
    for pattern, code in FALSE_AGENCY_PATTERNS:
        for m in re.finditer(pattern, content):
            snippet = content[max(0, m.start()-10):m.end()+30].replace("\n", " ")
            findings.append({
                "code": code,
                "message": f"假人动作: '{m.group()[:40]}'",
                "sentence": snippet.strip()[:120],
                "location": "",
                "evidence_weight": 0.8,
                "confidence": 0.7,
            })

    # 5. Check Throat-clearing (白话开头 — stop-slop)
    for pattern, code in THROAT_CLEARING_PATTERNS:
        for m in re.finditer(pattern, content):
            snippet = content[max(0, m.start()-10):m.end()+20].replace("\n", " ")
            findings.append({
                "code": code,
                "message": f"AI套话: '{m.group()[:40]}'",
                "sentence": snippet.strip()[:120],
                "location": "",
                "evidence_weight": 0.9,
                "confidence": 0.8,
            })

    # 6. Check Dramatic Fragmentation (碎片化戏剧 — stop-slop)
    for pattern, code in DRAMATIC_FRAGMENTATION_PATTERNS:
        for m in re.finditer(pattern, content):
            snippet = m.group()[:80].replace("\n", " ")
            findings.append({
                "code": code,
                "message": f"碎片化句式: '{snippet[:50]}'",
                "sentence": snippet.strip()[:120],
                "location": "",
                "evidence_weight": 1.0,
                "confidence": 0.6,
            })

    # 7. Check Narrator Distance (旁白距离感 — stop-slop)
    for pattern, code in NARRATOR_DISTANCE_PATTERNS:
        for m in re.finditer(pattern, content):
            snippet = content[max(0, m.start()-10):m.end()+30].replace("\n", " ")
            findings.append({
                "code": code,
                "message": f"旁白距离: '{m.group()[:40]}'",
                "sentence": snippet.strip()[:120],
                "location": "",
                "evidence_weight": 0.7,
                "confidence": 0.5,
            })

    # 8. Check Lazy Extremes (绝对化表述 — stop-slop)
    for pattern, code in LAZY_EXTREME_PATTERNS:
        for m in re.finditer(pattern, content):
            snippet = content[max(0, m.start()-10):m.end()+20].replace("\n", " ")
            findings.append({
                "code": code,
                "message": f"绝对化: '{m.group()[:40]}'",
                "sentence": snippet.strip()[:120],
                "location": "",
                "evidence_weight": 0.6,
                "confidence": 0.5,
            })

    # Compute weighted score
    weighted = sum(f["confidence"] * f["evidence_weight"] for f in findings)
    not_a_b_weighted = sum(
        f["confidence"] * f["evidence_weight"]
        for f in findings if f["code"] in ("NOT_A_ER_SHI", "BING_FEI_A_ER_SHI",
                                            "NOT_A_SHI", "YU_QI_SHUO"))

    # Score rules:
    # - Single "不是A而是B" with evidence: no penalty
    # - Single without evidence: mild
    # - 2+ in chapter: WARN
    # - 4+: strong WARN
    ai_cliche_count = sum(1 for f in findings
                          if f["code"] in ("NA_YI_KE", "ZHONG_YU_MING_BAI",
                                           "CONG_WEI_XIANG_GUO", "ZHONG_YU_YI_SHI_DAO",
                                           "CHEN_MO_JI_MIAO", "XIANG_FEI_XU",
                                           "SHI_JIU_SHU", "XIANG_DIAO_XIANG"))

    score = min(100, int(weighted * 25))

    return score, findings


# ═══════════════════════════════════════════════════
# Guard-compatible entry point
# ═══════════════════════════════════════════════════

def run_anti_ai_check(content: str, chapter_no: int = 0) -> dict:
    """
    Guard-compatible entry point. Returns legacy dict format.
    Also used by guard_registry via _adapt_legacy_dict.
    """
    score, findings = find_anti_ai_issues(content)
    return run_anti_ai_check_result(content, chapter_no)


def find_anti_ai_issues(content: str):
    """Shorthand alias used by existing code."""
    return check_anti_ai(content)


def run_anti_ai_check_result(content: str, chapter_no: int = 0) -> dict:
    """Returns dict compatible with both legacy and GuardResult adapter."""
    score, raw_findings = check_anti_ai(content)

    # Convert to guard-compatible flags
    flags = []
    for f in raw_findings:
        if f["evidence_weight"] < 1.0 and f["confidence"] < 0.5:
            # Low-confidence with evidence: informational only
            continue
        flags.append({
            "code": f["code"],
            "message": f["message"],
            "snippet": f["sentence"],
            "confidence": f["confidence"],
            "location": f.get("location", ""),
        })

    not_a_b_count = sum(1 for f in raw_findings
                        if f["code"] in ("NOT_A_ER_SHI", "BING_FEI_A_ER_SHI",
                                         "NOT_A_SHI", "YU_QI_SHUO"))
    cliche_count = sum(1 for f in raw_findings
                       if f["code"] in ("NA_YI_KE", "ZHONG_YU_MING_BAI",
                                        "CONG_WEI_XIANG_GUO", "ZHONG_YU_YI_SHI_DAO",
                                        "CHEN_MO_JI_MIAO", "XIANG_FEI_XU",
                                        "SHI_JIU_SHU", "XIANG_DIAO_XIANG"))
    hard_sci_count = sum(1 for f in raw_findings
                         if f["code"] in ("HARD_SCIENCE_REF", "HARD_SCIENCE_TERM"))
    false_agency_count = sum(1 for f in raw_findings
                              if f["code"] == "FALSE_AGENCY")
    throat_clearing_count = sum(1 for f in raw_findings
                                 if f["code"] == "THROAT_CLEARING")
    dramatic_frag_count = sum(1 for f in raw_findings
                               if f["code"] == "DRAMATIC_FRAGMENT")
    narrator_dist_count = sum(1 for f in raw_findings
                               if f["code"] == "NARRATOR_DISTANCE")
    lazy_extreme_count = sum(1 for f in raw_findings
                              if f["code"] == "LAZY_EXTREME")

    # Determine status
    status = "PASS"
    if cliche_count >= 2:
        status = "WARNING"
    elif not_a_b_count >= 5:
        status = "WARNING"
    elif not_a_b_count >= 2 and hard_sci_count >= 2:
        status = "WARNING"
    elif throat_clearing_count >= 2:
        status = "WARNING"
    elif false_agency_count >= 5:
        status = "WARNING"
    elif dramatic_frag_count >= 2:
        status = "WARNING"
    elif lazy_extreme_count >= 4:
        status = "WARNING"

    return {
        "guard": "anti_ai_guard",
        "status": status,
        "score": score,
        "flags": flags,
        "metrics": {
            "not_a_b_count": not_a_b_count,
            "cliche_count": cliche_count,
            "hard_science_count": hard_sci_count,
            "false_agency_count": false_agency_count,
            "throat_clearing_count": throat_clearing_count,
            "dramatic_frag_count": dramatic_frag_count,
            "narrator_dist_count": narrator_dist_count,
            "lazy_extreme_count": lazy_extreme_count,
            "total_flags": len(raw_findings),
            "weighted_score": score,
        },
        "hard_fail": False,
    }
