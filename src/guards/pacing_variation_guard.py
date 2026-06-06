#!/usr/bin/env python3
"""pacing_variation_guard.py — 节奏变化检测 v0.7.2

检查章节的节奏是否张弛有度。
维度: 段落长度变化、动作/对话/描写比例、紧张度标记、节奏转折点。
"""

import re


def _analyze_pacing(text: str) -> dict:
    """分析章节节奏特征"""
    paras = [p.strip() for p in text.split('\n') if p.strip()]
    if not paras:
        return {"para_count": 0, "avg_len": 0, "len_std": 0, "action_ratio": 0,
                "dialogue_ratio": 0, "description_ratio": 0, "tension_markers": 0}

    # 段落长度
    lengths = [len(p) for p in paras]
    avg_len = sum(lengths) / len(lengths)
    variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
    std_dev = variance ** 0.5

    # 内容类型比例
    total_chars = sum(lengths)
    action_chars = sum(len(p) for p in paras if re.search(r'[跑跳走冲追抓打砸踢推拉拽背扛提拎抱]', p))
    dialogue_lines = len([p for p in paras if re.search(r'[说问答喊叫吼骂嚷道]', p)])
    # 粗略估计对话段落长度
    dialogue_chars = 0
    for p in paras:
        if re.search(r'[说问答]', p):
            dialogue_chars += len(p)

    # 紧张度标记
    tension_patterns = [
        r'[突][然]', r'[猛][然地]', r'[急][速]', r'[快][步]', r'[冲][进]',
        r'[撞][开]', r'[摔][门]', r'[砸][在]', r'[断][了]', r'[爆][发]',
        r'[危][险]', r'[危][机]', r'[紧][张]', r'[吓][了]', r'[惊][醒]',
    ]
    tension_markers = sum(len(re.findall(p, text)) for p in tension_patterns)

    # 节奏转折点: 短段落出现在长段落之后
    transitions = 0
    for i in range(1, len(lengths)):
        if lengths[i] < avg_len * 0.3 and lengths[i-1] > avg_len * 1.5:
            transitions += 1
        if lengths[i] > avg_len * 1.5 and lengths[i-1] < avg_len * 0.3:
            transitions += 1

    return {
        "para_count": len(paras),
        "avg_len": round(avg_len, 1),
        "len_std": round(std_dev, 1),
        "cv": round(std_dev / avg_len, 2) if avg_len > 0 else 0,  # 变异系数
        "action_ratio": round(action_chars / total_chars, 3) if total_chars > 0 else 0,
        "dialogue_ratio": round(dialogue_chars / total_chars, 3) if total_chars > 0 else 0,
        "tension_markers": tension_markers,
        "rhythm_transitions": transitions,
    }


def run_pacing_variation_check(text: str, chapter_no: int = 0) -> dict:
    """Run pacing variation guard on a chapter."""
    pacing = _analyze_pacing(text)
    issues = []
    warnings = []

    # 1. 段落长度太均匀 (CV < 0.5 且段落数 > 5)
    if pacing["cv"] is not None and pacing["cv"] < 0.5 and pacing["para_count"] > 5:
        issues.append({
            "code": "UNIFORM_PARAGRAPH_LENGTH",
            "severity": "WARN",
            "message": f"段落长度过于均匀（变异系数{pacing['cv']}），节奏缺少变化",
            "suggestion": "紧张场景用短段落加速，抒情/思考用长段落放缓。段落长短交错才能控制读者呼吸",
            "confidence": 0.75,
            "details": {"cv": pacing["cv"], "avg_len": pacing["avg_len"], "std": pacing["len_std"]},
        })
        warnings.append(issues[-1]["message"])

    # 2. 紧张度不足
    if pacing["tension_markers"] < 2 and pacing["para_count"] > 10:
        issues.append({
            "code": "LOW_TENSION",
            "severity": "INFO",
            "message": "紧张标记过少，章节整体节奏偏平",
            "suggestion": "关键冲突处用短句、短段落、动词密集的表达来加速节奏；平静段落用长句拉慢",
            "confidence": 0.5,
            "details": {"tension_markers": pacing["tension_markers"]},
        })

    # 3. 缺乏节奏转折
    if pacing["rhythm_transitions"] < 2 and pacing["para_count"] > 10:
        issues.append({
            "code": "NO_RHYTHM_TRANSITION",
            "severity": "INFO",
            "message": "段落长度没有明显起伏，节奏缺乏转折点",
            "suggestion": "设计至少1次节奏变化：紧张追逐后用短段落收束，安静思考时有突发事件打断",
            "confidence": 0.6,
            "details": {"transitions": pacing["rhythm_transitions"]},
        })

    has_warn = any(i["severity"] == "WARN" for i in issues)
    has_fail = any(i["severity"] == "FAIL" for i in issues)

    # Score (0-100)
    score = 60
    if pacing["cv"] and pacing["cv"] >= 0.6:
        score += 20
    elif pacing["cv"] and pacing["cv"] >= 0.4:
        score += 10
    if pacing["tension_markers"] >= 3:
        score += 10
    if pacing["rhythm_transitions"] >= 3:
        score += 10

    return {
        "guard": "pacing_variation_guard",
        "status": "PASS" if not has_warn else ("FAIL" if has_fail else "WARN"),
        "chapter_no": chapter_no,
        "issues": issues,
        "warnings": warnings,
        "scores": {
            "rhythm_score": min(100, score),
            "paragraph_variation": pacing["cv"] or 0,
            "tension_markers": pacing["tension_markers"],
            "rhythm_transitions": pacing["rhythm_transitions"],
            "action_ratio": pacing["action_ratio"],
            "dialogue_ratio": pacing["dialogue_ratio"],
        },
    }
