#!/usr/bin/env python3
"""
consequence_lexicon.py — Visible Consequence Lexicon v0.4.5

Problem: scene_causality_guard only recognizes literal keywords like "裂开",
"渗血", "破皮" — missing narrative cost expressions like "肺痉挛", "铁锈味",
"水沫子", "手抖".

This lexicon provides four categories of visible consequence:
  physical_cost, object_cost, social_cost, rule_cost
"""

from typing import List, Dict, Tuple


# ═══════════════════════════════════════════════════
# PHYSICAL COST — body-level visible consequences
# ═══════════════════════════════════════════════════

PHYSICAL_COST = [
    # Internal organ / respiratory
    "痉挛", "肺痉挛", "胸口发闷", "喉咙发紧", "喘不过气", "憋气",
    # Sensory (taste/smell/sound in body)
    "铁锈味", "血腥味", "苦味", "腥甜",
    # Respiratory output
    "咳嗽", "咳出血", "水沫", "水沫子", "带血沫",
    # Motor control loss
    "手抖", "腿软", "站不稳", "跪倒", "摔倒", "踉跄", "趔趄",
    # Pain responses
    "冷汗", "冒汗", "指节发白", "咬紧牙", "嘴唇发白", "脸白",
    # Vision / hearing
    "眼前发黑", "耳鸣", "眼冒金星", "视线模糊",
    # Sensation
    "麻", "发麻", "刺痛", "灼痛", "抽痛", "一跳一跳地痛", "钝痛",
    # Swelling / bleeding
    "肿包", "肿块", "淤青", "血痂", "破皮", "渗血", "流鼻血",
    "刮出.*印子", "刮出.*血", "裂了一角", "渗.*血",
    # Internal cost
    "经脉灼伤", "经脉刺痛", "神魂刺痛", "神魂消耗",
    # Old injury tracking
    "旧伤", "肋骨.*痛", "骨膜.*痛", "伤.*跳.*痛",
]

# ═══════════════════════════════════════════════════
# OBJECT COST — visible changes to objects
# ═══════════════════════════════════════════════════

OBJECT_COST = [
    "裂纹", "裂开", "碎裂", "崩裂",
    "卷刃", "卷口", "豁口",
    "凹陷", "缺口", "缺角", "缺了一块角",
    "碎屑", "木屑", "铁屑", "石粉",
    "水纹", "涟漪", "震颤", "晃动",
    "倾斜", "松动", "崩开", "磨损",
    "折断", "断.*截", "散.*一地",
    "刀口.*崩", "刀.*弹起",
    "炭笔.*断", "笔尖.*断",
]

# ═══════════════════════════════════════════════════
# SOCIAL COST — status/relationship consequences
# ═══════════════════════════════════════════════════

SOCIAL_COST = [
    "记名", "记在簿子", "记上一笔",
    "扣饭", "扣.*饭", "罚工", "罚.*工",
    "加活", "加量", "加.*捆", "多劈",
    "盯上", "盯住", "盯.*看",
    "排挤", "孤立", "被孤立",
    "哄笑", "嘲笑", "笑.*最大声",
    "沉默", "不吭声", "没人.*出声",
    "避开", "退开", "让开", "不敢靠近",
    "被赶", "被拦", "被推开", "被拉走",
    "怀疑", "质疑", "不信",
    "以下犯上", "冒犯",
]

# ═══════════════════════════════════════════════════
# RULE COST — institutional/system consequences
# ═══════════════════════════════════════════════════

RULE_COST = [
    "坏了规矩", "不合规矩", "按规矩",
    "欠账", "欠.*账",
    "补上", "补考", "补.*考",
    "不得", "不准", "不允许",
    "罚", "扣", "限时", "过时不候",
    "考核.*不合格", "不合格",
    "执事堂", "灰纸", "官文",
    "以下犯上",
]


# ═══════════════════════════════════════════════════
# Search functions
# ═══════════════════════════════════════════════════

import re


def find_all_consequences(content: str) -> Dict[str, List[Dict]]:
    """
    Scan content for all four types of consequences.

    Returns:
      {"physical_cost": [...], "object_cost": [...],
       "social_cost": [...], "rule_cost": [...]}
    Each item: {"type": ..., "keyword": ..., "snippet": ...}
    """
    results = {
        "physical_cost": [],
        "object_cost": [],
        "social_cost": [],
        "rule_cost": [],
    }

    for kw in PHYSICAL_COST:
        for m in re.finditer(kw, content):
            start = max(0, m.start() - 20)
            end = min(len(content), m.end() + 40)
            snippet = content[start:end].replace("\n", " ").strip()
            results["physical_cost"].append({
                "type": "physical_cost",
                "keyword": m.group(),
                "snippet": snippet[:120],
            })

    for kw in OBJECT_COST:
        for m in re.finditer(kw, content):
            start = max(0, m.start() - 20)
            end = min(len(content), m.end() + 40)
            snippet = content[start:end].replace("\n", " ").strip()
            results["object_cost"].append({
                "type": "object_cost",
                "keyword": m.group(),
                "snippet": snippet[:120],
            })

    for kw in SOCIAL_COST:
        for m in re.finditer(kw, content):
            start = max(0, m.start() - 20)
            end = min(len(content), m.end() + 40)
            snippet = content[start:end].replace("\n", " ").strip()
            results["social_cost"].append({
                "type": "social_cost",
                "keyword": m.group(),
                "snippet": snippet[:120],
            })

    for kw in RULE_COST:
        for m in re.finditer(kw, content):
            start = max(0, m.start() - 20)
            end = min(len(content), m.end() + 40)
            snippet = content[start:end].replace("\n", " ").strip()
            results["rule_cost"].append({
                "type": "rule_cost",
                "keyword": m.group(),
                "snippet": snippet[:120],
            })

    return results


def count_visible_consequences(content: str) -> int:
    """
    Count unique visible consequences of all four types.
    Deduplicates by snippet to avoid counting the same occurrence twice.
    """
    all_costs = find_all_consequences(content)
    seen = set()
    for cost_type, items in all_costs.items():
        for item in items:
            # Deduplicate by snippet start to avoid overlap
            key = item["snippet"][:40]
            seen.add(key)
    return len(seen)


def has_minimum_visible_cost(content: str, min_cost: int = 2) -> Tuple[bool, int, dict]:
    """
    Check if content has at least `min_cost` visible consequences.

    Returns:
      (passed, count, details)
    """
    all_costs = find_all_consequences(content)
    unique = set()
    for cost_type, items in all_costs.items():
        for item in items:
            unique.add(item["snippet"][:40])

    count = len(unique)
    passed = count >= min_cost

    return passed, count, {
        "physical_count": len(all_costs["physical_cost"]),
        "object_count": len(all_costs["object_cost"]),
        "social_count": len(all_costs["social_cost"]),
        "rule_count": len(all_costs["rule_cost"]),
        "unique_visible_count": count,
    }
