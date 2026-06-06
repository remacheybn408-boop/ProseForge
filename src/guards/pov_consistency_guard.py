#!/usr/bin/env python3
"""pov_consistency_guard.py — 视角一致性检测 v0.7.2

检查章节是否保持一致的叙述视角。
检测: 视角代词一致性、非本角色内心活动、跨段视角跳跃。
"""

import re


def _detect_pov_shift(text: str, chapter_no: int = 0) -> list:
    """检测可能的视角跳跃"""
    issues = []
    paras = [p for p in text.split('\n') if p.strip() and len(p) > 20]

    if len(paras) < 3:
        return issues

    # 统计 "他" 和 "她" 的比例
    ta_count = len(re.findall(r'\b他', text))
    ta_female = len(re.findall(r'\b她', text))

    # 如果两者都大量出现，可能是双视角
    if ta_count > 5 and ta_female > 5:
        # 检查是否频繁交替
        para_he = [1 for p in paras if re.search(r'\b他', p) and not re.search(r'\b她', p)]
        para_she = [1 for p in paras if re.search(r'\b她', p) and not re.search(r'\b他', p)]
        if len(para_he) > 3 and len(para_she) > 3:
            # 检查切换次数
            switches = 0
            last_pov = None
            for p in paras:
                has_he = bool(re.search(r'\b他', p))
                has_she = bool(re.search(r'\b她', p))
                current = None
                if has_he and not has_she:
                    current = "他"
                elif has_she and not has_he:
                    current = "她"
                if current and current != last_pov:
                    switches += 1
                    last_pov = current
            if switches > 4:
                issues.append({
                    "code": "POV_SHIFT",
                    "severity": "WARN",
                    "message": f"叙述视角在本章内切换{switches}次（他↔她），读者可能迷失",
                    "suggestion": "每章保持单一视角。如需切换视角，用空行或分节符明确标记，并确保切换有叙事目的",
                    "confidence": 0.7,
                    "details": {"switches": switches, "he_count": ta_count, "she_count": ta_female},
                })

    # 检测"心想""内心暗道"之类的标记后是否跟随内心独白
    thought_markers = re.findall(r'[心想暗道暗忖琢磨盘算思忖][：:，,]', text)
    if len(thought_markers) > 3:
        markers_per_1000 = len(thought_markers) / max(len(re.findall(r'[\u4e00-\u9fff]', text)), 1) * 1000
        if markers_per_1000 > 2:
            issues.append({
                "code": "EXCESSIVE_INTERIOR",
                "severity": "INFO",
                "message": f"内心独白标记出现{len(thought_markers)}次（{markers_per_1000:.1f}/千字），可能过度解释角色想法",
                "suggestion": "让读者的通过角色的动作、表情、沉默来判断心理，不要全靠'心想''暗道'来告诉读者",
                "confidence": 0.6,
                "details": {"thought_markers": len(thought_markers), "density": round(markers_per_1000, 1)},
            })

    return issues


def run_pov_consistency_check(text: str, chapter_no: int = 0) -> dict:
    """Run POV consistency guard on a chapter."""
    issues = _detect_pov_shift(text, chapter_no)
    warnings = [i["message"] for i in issues if i["severity"] in ("WARN", "FAIL")]

    has_warn = any(i["severity"] == "WARN" for i in issues)
    has_fail = any(i["severity"] == "FAIL" for i in issues)

    return {
        "guard": "pov_consistency_guard",
        "status": "PASS" if not has_warn else ("FAIL" if has_fail else "WARN"),
        "chapter_no": chapter_no,
        "issues": issues,
        "warnings": warnings,
        "scores": {
            "pov_stability": max(0, 10 - len([i for i in issues if i["code"] == "POV_SHIFT"]) * 3),
            "interior_density": len(issues),
        },
    }
