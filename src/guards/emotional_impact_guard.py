#!/usr/bin/env python3
"""emotional_impact_guard.py — 情感渲染力检测 v0.7.2

检查章节是否能引发读者情感共鸣。
维度: 情感词汇密度、情感变化曲线、高光时刻标记、情感真实感评分。
"""

import re
from typing import List, Dict

EMOTION_WORDS = {
    "喜悦": ["笑", "开心", "高兴", "喜", "甜", "暖", "温柔", "幸福", "满足", "欣慰",
             "安心", "释然", "感动", "感激", "期待", "兴奋", "痛快", "舒畅", "踏实"],
    "悲伤": ["哭", "泪", "伤", "痛", "悲", "哀", "难受", "心碎", "哽咽", "鼻酸",
             "眼眶", "红", "湿", "酸", "沉重", "压抑", "苦涩", "失落", "绝望", "怀念"],
    "愤怒": ["怒", "恨", "气", "恼", "火", "愤", "咬牙", "握拳", "颤抖", "涨红",
             "青筋", "砸", "摔", "骂", "吼", "冷", "瞪", "怼", "忍", "憋屈"],
    "恐惧": ["怕", "慌", "恐", "惧", "惊", "冷汗", "发抖", "缩", "躲", "跑",
             "心跳", "加速", "窒息", "苍白", "哆嗦", "不安", "焦", "躁", "失眠"],
    "平静": ["静", "淡", "平", "稳", "沉", "缓", "慢", "闭", "放松", "呼吸",
             "安", "宁", "定", "清", "醒", "空", "沉默", "放空", "发呆", "坐"],
}

SERIOUS_SCENE_PATTERNS = [
    r'(死[了亡去掉]|犧牲|殉|葬[礼])',
    r'(重[伤创]|濒[死]|垂[危])',
    r'(诀[别]|永[别]|再也|永远[不没])',
    r'(分[手]|离[别婚]|散[了]|失[去恋踪])',
    r'(哭[泣诉]|泪[水流]|哽咽|泣不成声)',
]


def _detect_emotion_density(text: str) -> Dict[str, float]:
    """检测情感词汇密度（每千字各情感类别次数）"""
    total_chars = max(len(re.findall(r'[\u4e00-\u9fff]', text)), 1)
    result = {}
    for category, words in EMOTION_WORDS.items():
        count = sum(text.count(w) for w in words)
        density = count / total_chars * 1000
        result[category] = round(density, 2)
    return result


def _detect_emotion_curve(text: str) -> List[Dict]:
    """按段落检测情感变化，看是否有起伏"""
    paras = [p for p in text.split('\n') if p.strip() and len(p) > 10]
    curve = []
    for i, para in enumerate(paras[:20]):  # 最多20段
        scores = {}
        for cat, words in EMOTION_WORDS.items():
            scores[cat] = sum(para.count(w) for w in words)
        dominant = max(scores, key=scores.get) if max(scores.values()) > 0 else "无"
        curve.append({"para": i, "dominant": dominant, "intensity": max(scores.values())})
    return curve


def _detect_highlights(text: str) -> int:
    """检测高光情感时刻（连续高强度情感描写）"""
    paras = [p for p in text.split('\n') if p.strip()]
    highlight_count = 0
    for para in paras:
        total_hits = sum(para.count(w) for words in EMOTION_WORDS.values() for w in words)
        para_len = max(len(re.findall(r'[\u4e00-\u9fff]', para)), 1)
        density = total_hits / para_len
        if density > 0.15 and para_len > 30:  # 高密度情感段落
            highlight_count += 1
    return highlight_count


def _check_flat_emotion(text: str, density: Dict[str, float]) -> List[Dict]:
    """检查是否全章情感平淡"""
    issues = []
    max_density = max(density.values()) if density else 0
    if max_density < 0.3:
        issues.append({
            "code": "FLAT_EMOTION",
            "severity": "WARN",
            "message": "全章情感词汇密度偏低，读者可能难以产生情感共鸣",
            "suggestion": "增加角色情感反应描写（不仅是'难过''开心'，而是通过动作、物件、环境间接传达）",
            "confidence": 0.6,
            "details": {"max_emotion_density": max_density},
        })
    return issues


def _check_emotion_gap(curve: List[Dict]) -> List[Dict]:
    """检查情感曲线是否单一一成不变"""
    issues = []
    if not curve:
        return issues
    unique_emotions = set(c["dominant"] for c in curve if c["dominant"] != "无")
    if len(unique_emotions) <= 1 and len(curve) >= 5:
        issues.append({
            "code": "FLAT_EMOTION_CURVE",
            "severity": "WARN",
            "message": f"情感曲线单一（仅{unique_emotions}），缺少起伏变化",
            "suggestion": "在一章内设计至少1次情感转折或情绪递进",
            "confidence": 0.7,
            "details": {"emotions_found": list(unique_emotions), "paragraphs_analyzed": len(curve)},
        })
    return issues


def _check_serious_emotion_gap(text: str, density: Dict[str, float]) -> List[Dict]:
    """严肃场景下缺乏应有的情感反应"""
    issues = []
    has_serious = any(re.search(p, text) for p in SERIOUS_SCENE_PATTERNS)
    if has_serious:
        sad_density = density.get("悲伤", 0)
        fear_density = density.get("恐惧", 0)
        if sad_density < 0.5 and fear_density < 0.5:
            issues.append({
                "code": "SERIOUS_EMOTION_GAP",
                "severity": "WARN",
                "message": "严肃场景（死亡/离别/重伤）但情感反应词汇不足，读者可能无感",
                "suggestion": "在关键情节处增加角色情感反应：通过颤抖的手指、发红的眼眶、说不下去的话来传递",
                "confidence": 0.65,
                "details": {"sad_density": sad_density, "fear_density": fear_density},
            })
    return issues


def run_emotional_impact_check(text: str, chapter_no: int = 0) -> dict:
    """Run emotional impact guard on a chapter."""
    density = _detect_emotion_density(text)
    curve = _detect_emotion_curve(text)

    all_issues = []
    all_issues.extend(_check_flat_emotion(text, density))
    all_issues.extend(_check_emotion_gap(curve))
    all_issues.extend(_check_serious_emotion_gap(text, density))

    highlights = _detect_highlights(text)

    has_warn = any(i["severity"] == "WARN" for i in all_issues)
    has_fail = any(i["severity"] == "FAIL" for i in all_issues)

    return {
        "guard": "emotional_impact_guard",
        "status": "PASS" if not has_warn else ("FAIL" if has_fail else "WARN"),
        "chapter_no": chapter_no,
        "issues": all_issues,
        "warnings": [i["message"] for i in all_issues],
        "scores": {
            "joy": density.get("喜悦", 0),
            "sadness": density.get("悲伤", 0),
            "anger": density.get("愤怒", 0),
            "fear": density.get("恐惧", 0),
            "calm": density.get("平静", 0),
            "highlights": highlights,
        },
    }
