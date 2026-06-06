#!/usr/bin/env python3
"""sensory_detail_guard.py — 感官描写浓度检测 v0.7.2

检查章节是否缺乏让读者沉浸的五感描写。
维度: 视觉、听觉、触觉、嗅觉、味觉、动觉（身体感受）词汇密度。
"""

import re

SENSORY_PATTERNS = {
    "视觉": [
        r'[看][见到]', r'[眼]', r'[颜]色', r'[光][线芒亮暗阴]', r'[明][亮暗]',
        r'[红黄蓝绿白黑青紫金灰]', r'[窗]外', r'[映][照出]', r'[漆][黑]',
        r'[朦][胧]', r'[闪][烁耀]', r'[透][明过]',
    ],
    "听觉": [
        r'[声][音响]', r'[听][见到]', r'[耳][边旁]', r'[静][下]', r'[沉][默]',
        r'[咚][的]', r'[哐][当]', r'[咔][嚓]', r'[吱][呀]', r'[嗡][嗡]',
        r'[轰][隆]', r'[哗][啦]', r'[铃][声]', r'[呼][吸]', r'[脚][步]',
    ],
    "触觉": [
        r'[冰][凉冷]', r'[温][暖热]', r'[烫]', r'[寒][意]', r'[凉][意]',
        r'[触][碰到]', r'[摸][了着]', r'[握][住紧着]', r'[拉][扯拽]',
        r'[刺][痛骨]', r'[滑][腻]', r'[粗][糙]', r'[柔][软嫩]', r'[硬][邦]',
        r'[肌][肤]', r'[皮][肤]', r'[手][心掌]',
    ],
    "嗅觉": [
        r'[香][味气]', r'[臭][味]', r'[闻][到]', r'[气][味]', r'[腥][味]',
        r'[焦][味糊]', r'[烟][味]', r'[清][香]', r'[浓][郁]', r'[腐][臭烂]',
        r'[咖啡][的香气]', r'[墨][香]', r'[花][香]',
    ],
    "味觉": [
        r'[味][道]', r'[尝][了]', r'[苦][涩]', r'[甜]', r'[酸]', r'[辣]',
        r'[咸]', r'[淡]', r'[喝][了一口]', r'[吃][了一口]', r'[嚼]',
        r'[回][味]', r'[涩]',
    ],
    "动觉": [
        r'[浑][身]', r'[全][身]', r'[身][体]', r'[肩][膀]', r'[背][部]',
        r'[腿]', r'[腰]', r'[酸][痛]', r'[累][了]', r'[疼]', r'[痛]',
        r'[发][抖颤]', r'[僵][硬直]', r'[冒][汗]', r'[呼][吸]',
        r'[心][跳]', r'[血][液]', r'[肌][肉]',
    ],
}


def _count_sensory(text: str) -> dict:
    """统计各感官类别的命中次数"""
    total_chars = max(len(re.findall(r'[\u4e00-\u9fff]', text)), 1)
    result = {}
    for sense, patterns in SENSORY_PATTERNS.items():
        count = 0
        for pat in patterns:
            count += len(re.findall(pat, text))
        density = round(count / total_chars * 1000, 2)
        result[sense] = {"count": count, "density": density}
    return result


def _check_sensory_gaps(sensory: dict) -> list:
    """检查缺失的感官维度"""
    issues = []
    missing = [s for s, d in sensory.items() if d["density"] < 0.3]
    threshold = 3

    for s in missing:
        if s in ("味觉", "嗅觉"):
            continue  # 不强求每章都有味道描写

    if len(missing) >= threshold:
        issues.append({
            "code": "SENSORY_GAP",
            "severity": "WARN",
            "message": f"感官描写缺失{len(missing)}个维度({', '.join(missing)})，读者沉浸感不足",
            "suggestion": "每章至少覆盖3种感官：视觉+听觉是基础，再加触觉或动觉。用物件和环境传递感官，不要直接说'他感到'",
            "confidence": 0.7,
            "details": {"missing": missing},
        })

    return issues


def _check_visual_dominance(sensory: dict) -> list:
    """检查是否过度依赖视觉描写"""
    issues = []
    visual = sensory.get("视觉", {}).get("density", 0)
    non_visual = sum(v["density"] for k, v in sensory.items() if k != "视觉")
    if visual > 0 and non_visual > 0 and visual > non_visual * 3:
        issues.append({
            "code": "VISUAL_OVERDOMINANCE",
            "severity": "INFO",
            "message": "视觉描写占比过高，缺少其他感官层次",
            "suggestion": "在关键场景加入听觉（环境音、沉默）、触觉（温度、质感）、动觉（身体反应）",
            "confidence": 0.55,
            "details": {"visual_density": visual, "non_visual_density": round(non_visual, 2)},
        })
    return issues


def run_sensory_detail_check(text: str, chapter_no: int = 0) -> dict:
    """Run sensory detail guard on a chapter."""
    sensory = _count_sensory(text)

    all_issues = []
    all_issues.extend(_check_sensory_gaps(sensory))
    all_issues.extend(_check_visual_dominance(sensory))

    has_warn = any(i["severity"] == "WARN" for i in all_issues)
    has_fail = any(i["severity"] == "FAIL" for i in all_issues)

    # Score (0-100): more sensory dimensions with reasonable density = higher
    dims_above_threshold = sum(1 for d in sensory.values() if d["density"] >= 0.3)
    score = min(100, dims_above_threshold * 16 + 4)

    return {
        "guard": "sensory_detail_guard",
        "status": "PASS" if not has_warn else ("FAIL" if has_fail else "WARN"),
        "chapter_no": chapter_no,
        "issues": all_issues,
        "warnings": [i["message"] for i in all_issues],
        "scores": {k: v["density"] for k, v in sensory.items()},
        "summary": {
            "dimensions_covered": dims_above_threshold,
            "total_score": score,
        },
    }
