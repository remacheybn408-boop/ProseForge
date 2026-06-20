#!/usr/bin/env python3
"""opening_hook_guard.py — 开篇吸引力检测 v0.7.2

检查章节开篇是否能抓住读者。
维度: 开头类型、信息钩子、速度评分、前100字质量。
"""

import re

WEAK_OPENINGS = [
    r'^这一天', r'^那[一]天', r'^今天', r'^昨天', r'^明天',
    r'^这时', r'^这时候', r'^此时', r'^此刻',
    r'^他[们]?说', r'^她[们]?说',
    r'^[就][在这时]', r'^[于][是]',
    r'^[窗门]外', r'^[远在]处',
]

STRONG_OPENINGS = [
    r'^[突][然]', r'^[砰撞砸响哭喊叫]', r'^[不]好',
    r'^[最][后]', r'^[只][是]', r'^[他][没]',
    r'^[为][什]么', r'^[如][果]',
    r'[\?？!！]',  # 以问号/感叹号开头的行
]


def _analyze_opening_lines(text: str, max_lines: int = 5) -> dict:
    """分析开篇前N行的质量"""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if not lines:
        return {"total_lines": 0, "weak_count": 0, "strong_count": 0, "first_line": ""}

    first_line = lines[0][:80]
    openings = lines[:max_lines]

    weak_count = sum(1 for l in openings if any(re.match(p, l) for p in WEAK_OPENINGS))
    strong_count = sum(1 for l in openings if any(re.match(p, l) for p in STRONG_OPENINGS))

    # 开篇是否有具体物件
    has_object = bool(re.search(r'[\u4e00-\u9fff]{2}[\u3001\s]*[\u4e00-\u9fff]{0,4}(?:了|着|过)', first_line)) if first_line else False

    # 是否有时间/地点锚点
    has_time = bool(re.search(r'[\d一二三四五六七八九十]+[点时分年天月周]', first_line)) if first_line else False
    has_place = bool(re.search(r'[在到于从]', first_line)) if first_line else False

    # 是否有动作（动词开头）
    has_action = bool(re.match(r'[^的了我你他她它是在有被把让给为]', first_line[:2])) if first_line else False

    return {
        "total_lines": len(openings),
        "weak_count": weak_count,
        "strong_count": strong_count,
        "first_line": first_line[:60],
        "has_object": has_object,
        "has_time": has_time,
        "has_place": has_place,
        "has_action": has_action,
    }


def run_opening_hook_check(text: str, chapter_no: int = 0) -> dict:
    """Run opening hook guard on a chapter."""
    analysis = _analyze_opening_lines(text)

    issues = []
    warnings = []

    # 1. 弱开头检测
    if analysis["weak_count"] >= 2:
        issues.append({
            "code": "WEAK_OPENING",
            "severity": "WARN",
            "message": f"开篇{analysis['weak_count']}行使用了弱开头模式（'这一天''此时'等）",
            "suggestion": "用具体动作、物件、对话或反常场景替代：不要'这一天天气很好'，而要'阳光晒在吧台的裂缝上'",
            "confidence": 0.7,
            "details": {"weak_count": analysis["weak_count"]},
        })
        warnings.append(issues[-1]["message"])

    # 2. 开篇缺少动作
    if not analysis["has_action"] and len(analysis.get("first_line", "")) > 5:
        issues.append({
            "code": "NO_OPENING_ACTION",
            "severity": "INFO",
            "message": "开篇以静态描述开始，缺少推动读者继续读的动作或悬念",
            "suggestion": "试试以角色的一个动作或反常细节开头：'她把第三遍核对完的数字又加了一遍'比'苏晚晴在核对账目'更有力道",
            "confidence": 0.55,
            "details": {"first_line": analysis["first_line"]},
        })

    # 3. 强钩子奖励
    if analysis["strong_count"] >= 1:
        issues.append({
            "code": "STRONG_OPENING",
            "severity": "PASS",
            "message": f"开篇有{analysis['strong_count']}个强力钩子标记（问句/冲突/意外）",
            "suggestion": "",
            "confidence": 0.9,
            "details": {"strong_count": analysis["strong_count"]},
        })

    has_warn = any(i["severity"] == "WARN" for i in issues)
    has_fail = any(i["severity"] == "FAIL" for i in issues)

    return {
        "guard": "opening_hook_guard",
        "status": "PASS" if not has_warn else ("FAIL" if has_fail else "WARN"),
        "chapter_no": chapter_no,
        "issues": issues,
        "warnings": warnings,
        "scores": {
            "opening_quality": max(0, 10 - analysis["weak_count"] * 3 + analysis["strong_count"] * 4),
            "weak_openings": analysis["weak_count"],
            "strong_openings": analysis["strong_count"],
            "has_action_start": analysis["has_action"],
        },
    }
