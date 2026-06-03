#!/usr/bin/env python3
"""style_rules.py — Apply style-specific rules to chapter text."""
from typing import Dict, List


def check_style_rules(text: str, style_pack: Dict, word_count: int = 0) -> List[Dict]:
    """Run style-specific checks and return findings."""
    findings = []
    style_id = style_pack.get("style_id", "generic")

    # Generic always
    _check_generic_style(text, findings)

    dispatchers = {
        "webnovel": _check_webnovel,
        "stream_of_consciousness": _check_stream,
        "black_humor": _check_black_humor,
        "postmodern": _check_postmodern,
        "children_lit": _check_children,
        "youth_lit": _check_youth,
    }

    if style_id in dispatchers:
        dispatchers[style_id](text, findings, word_count)

    return findings


def _check_generic_style(text: str, findings: List[Dict]):
    """Base style quality."""
    # Excessive adverbs
    import re
    adverbs = re.findall(r'[\u4e00-\u9fff]{1,2}地', text)
    if len(adverbs) > 15:
        findings.append({
            "level": "WARNING", "type": "风格:副词过多",
            "message": f"检测到{len(adverbs)}个'XX地'副词结构",
            "suggestion": "用具体动作替代副词修饰",
        })


def _check_webnovel(text: str, findings: List[Dict], wc: int):
    """Web novel style checks."""
    paras = [p for p in text.split('\n') if p.strip()]
    last_para = paras[-1] if paras else ""
    hook_words = ["突然", "然而", "但是", "没想到", "就在这", "正在这"]
    if not any(hw in last_para for hw in hook_words):
        findings.append({
            "level": "WARNING", "type": "网文:章尾无钩子",
            "message": "章尾段落未检测到追读钩子信号",
            "suggestion": "章尾加入转折/悬念/危机/新发现吸引读者翻页",
        })


def _check_stream(text: str, findings: List[Dict], wc: int):
    """Stream of consciousness checks."""
    if text.count("。") / max(wc, 1) < 0.02:
        findings.append({
            "level": "WARNING", "type": "意识流:句号过少",
            "message": "句号密度极低，可能为超长句流",
            "suggestion": "意识流也需要呼吸点，适度用句号分节",
        })


def _check_black_humor(text: str, findings: List[Dict], wc: int):
    """Black humor: must have darkness + humor, not just jokes."""
    dark_words = ["死", "痛苦", "绝望", "失败", "荒诞", "讽刺"]
    funny_words = ["笑", "滑稽", "幽默", "荒诞"]
    has_dark = any(w in text for w in dark_words)
    has_funny = any(w in text for w in funny_words)
    if wc > 500 and not (has_dark and has_funny):
        findings.append({
            "level": "WARNING", "type": "黑色幽默:欠缺黑色或幽默",
            "message": "黑色幽默应在痛苦/荒诞中产生笑，检测到只有单一色调",
            "suggestion": "在严肃场景中插入荒诞反差，或给悲剧加一层冷嘲视角",
        })


def _check_postmodern(text: str, findings: List[Dict], wc: int):
    """Postmodern: should show structural experimentation."""
    pass  # Postmodern is definitionally hard to check automatically


def _check_children(text: str, findings: List[Dict], wc: int):
    """Children's literature: no dark/violent content."""
    violent = ["杀", "死", "血", "尸", "虐"]
    count = sum(text.count(w) for w in violent)
    if count > 3:
        findings.append({
            "level": "WARNING", "type": "儿童文学:暴力内容",
            "message": f"检测到暴力词汇{count}次",
            "suggestion": "儿童文学应避免血腥暴力描写",
        })


def _check_youth(text: str, findings: List[Dict], wc: int):
    """Youth literature: age-appropriate voice."""
    lecture_words = ["应该", "必须", "一定要", "不能", "不可以"]
    count = sum(text.count(w) for w in lecture_words)
    if count > 8:
        findings.append({
            "level": "WARNING", "type": "青年文学:说教倾向",
            "message": f"强制性词汇出现{count}次，可能有说教倾向",
            "suggestion": "用人物经历和选择展示道理，而非直接说教",
        })
