#!/usr/bin/env python3
"""genre_rules.py — Apply genre-specific rules to chapter text."""
from typing import Dict, List


def check_genre_rules(text: str, genre_pack: Dict, style_pack: Dict, word_count: int = 0) -> List[Dict]:
    """Run genre-specific checks and return findings."""
    findings = []
    genre_id = genre_pack.get("genre_id", "generic")

    # Generic checks (always run)
    _check_generic(text, findings, word_count)

    # Genre-specific dispatch
    dispatchers = {
        "xianxia": _check_xianxia,
        "mystery": _check_mystery,
        "apocalypse": _check_apocalypse,
        "fantasy": _check_fantasy,
        "historical": _check_historical,
        "wuxia": _check_wuxia,
        "romance": _check_romance,
        "horror": _check_horror,
        "sci_fi": _check_sci_fi,
    }

    if genre_id in dispatchers:
        dispatchers[genre_id](text, findings, word_count)

    return findings


def _check_generic(text: str, findings: List[Dict], wc: int):
    """Universal checks."""
    # Check for AI-pattern overuse
    ai_patterns = ["不是A而是B", "这意味着", "像一座废墟", "像一尊雕像",
                   "仿佛在说", "仿佛在告诉", "似乎预示着"]
    for pat in ai_patterns:
        count = text.count(pat)
        if count >= 2:
            findings.append({
                "level": "WARNING", "type": "AI腔模式",
                "message": f"检测到AI模板句式'{pat}'出现{count}次",
                "suggestion": f"手工改写{pat}出现的句子，去除模板感",
            })

    # Empty text
    if wc < 100:
        findings.append({
            "level": "WARNING", "type": "文本过短",
            "message": f"字数不足100，无法进行有效题材检查",
            "suggestion": "请确保章节有足够内容后再审稿",
        })


def _check_xianxia(text: str, findings: List[Dict], wc: int):
    """修仙/玄幻专项检查."""
    # Sudden enlightenment patterns
    import re
    sudden = re.findall(r'顿悟|突然.*突破|瞬间.*升级|忽然.*明悟', text)
    if sudden and "代价" not in text and "后果" not in text and "反噬" not in text:
        findings.append({
            "level": "WARNING", "type": "修仙:无代价突破",
            "message": f"出现顿悟/突破相关词汇({sudden[0]})，但未检测到代价或反噬描写",
            "suggestion": "为突破增加代价：经脉受损、丹药消耗、心魔反噬、寿命折损等",
        })

    # Excessive cultivation explanation
    cult_terms = ["灵气", "灵力", "真元", "丹田", "经脉", "功法", "境界"]
    cult_count = sum(text.count(t) for t in cult_terms)
    if cult_count > 15 and wc > 0:
        findings.append({
            "level": "WARNING", "type": "修仙:修炼解释过量",
            "message": f"修炼相关术语出现{cult_count}次，可能解释过多",
            "suggestion": "减少设定解释，用人物行动和代价展示修炼体系",
        })


def _check_mystery(text: str, findings: List[Dict], wc: int):
    """悬疑推理专项检查."""
    clue_words = ["线索", "证据", "证物", "痕迹", "指纹", "脚印", "目击"]
    clue_count = sum(text.count(w) for w in clue_words)
    if clue_count == 0 and wc > 500:
        findings.append({
            "level": "WARNING", "type": "悬疑:缺少线索",
            "message": "本章未检测到任何线索或证据描写",
            "suggestion": "每章至少埋一个可观察线索，供读者复盘",
        })


def _check_apocalypse(text: str, findings: List[Dict], wc: int):
    """末世生存专项检查."""
    resource_words = ["食物", "水", "药品", "弹药", "物资", "补给", "燃料"]
    resource_count = sum(text.count(w) for w in resource_words)
    if resource_count == 0 and wc > 500:
        findings.append({
            "level": "WARNING", "type": "末世:缺少资源意识",
            "message": "本章未提及任何生存资源",
            "suggestion": "末世题材应时刻体现资源压力，至少提及食物/水源状况",
        })


def _check_fantasy(text: str, findings: List[Dict], wc: int):
    """奇幻/西幻专项检查."""
    magic_words = ["魔法", "咒语", "法术", "魔力", "元素"]
    magic_count = sum(text.count(w) for w in magic_words)
    if magic_count > 10:
        findings.append({
            "level": "WARNING", "type": "奇幻:魔法密度高",
            "message": f"魔法相关词汇出现{magic_count}次",
            "suggestion": "确保每次施法有代价，避免魔法万能化",
        })


def _check_historical(text: str, findings: List[Dict], wc: int):
    """历史小说专项检查."""
    modern_words = ["OK", "牛逼", "社恐", "内卷", "套路", "硬核", "get到",
                    "打call", "破防", "躺平", "无语", "高端"]
    for mw in modern_words:
        if mw in text:
            findings.append({
                "level": "WARNING", "type": "历史:现代用语",
                "message": f"检测到现代网络用语'{mw}'",
                "suggestion": f"将'{mw}'替换为符合时代背景的表达",
            })


def _check_wuxia(text: str, findings: List[Dict], wc: int):
    """武侠小说专项检查."""
    import re
    lucky_finds = re.findall(r'奇遇|捡到|意外.*发现|突然.*得到|机缘', text)
    hard_work = re.findall(r'苦练|修炼|磨炼|练习|打坐|练功', text)
    if lucky_finds and not hard_work:
        findings.append({
            "level": "WARNING", "type": "武侠:奇遇无代价",
            "message": f"出现奇遇描写但无相应磨炼",
            "suggestion": "武侠成长应强调苦练和代价，奇遇只是契机不应替代努力",
        })


def _check_romance(text: str, findings: List[Dict], wc: int):
    """言情专项检查."""
    templates = ["霸道总裁", "冰山美人", "傻白甜", "高冷男神", "软萌妹子"]
    for t in templates:
        if t in text:
            findings.append({
                "level": "WARNING", "type": "言情:标签化角色",
                "message": f"出现标签化形容'{t}'",
                "suggestion": "用具体行为描写替代标签化形容",
            })


def _check_horror(text: str, findings: List[Dict], wc: int):
    """恐怖专项检查."""
    jumpscare = text.count("突然") + text.count("忽然")
    if jumpscare >= 5:
        findings.append({
            "level": "WARNING", "type": "恐怖:依赖突然惊吓",
            "message": f"'突然/忽然'出现{jumpscare}次，可能过度依赖突然惊吓",
            "suggestion": "用氛围递进和规则压力替代频繁突然惊吓",
        })


def _check_sci_fi(text: str, findings: List[Dict], wc: int):
    """科幻专项检查."""
    hard_terms = ["量子", "熵", "维度", "奇点", "暗物质", "反物质", "超光速"]
    used = [t for t in hard_terms if t in text]
    explain_words = ["因为", "原理是", "意思是", "也就是说", "简单来说"]
    explained = any(ew in text for ew in explain_words)
    if used and not explained and wc > 500:
        findings.append({
            "level": "WARNING", "type": "科幻:硬术语未解释",
            "message": f"检测到硬科幻术语{used}但未在上下文中解释",
            "suggestion": "在对话或叙述中自然嵌入术语的通俗理解",
        })
