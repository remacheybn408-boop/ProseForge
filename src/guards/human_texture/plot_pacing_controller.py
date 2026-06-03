"""plot_pacing_controller.py — 剧情进度控制器 v0.6.6

5 档进度速度 × 8 类进度增量 × 题材预设。
检查每章是否产生有效进度，而非仅仅字数达标。
"""
import re

# ── 进度增量定义 ──
PROGRESS_DELTAS = {
    "event_delta":         "新事件发生",
    "conflict_delta":      "冲突升级或转向",
    "relationship_delta":  "人物关系变化",
    "clue_delta":          "线索出现或验证",
    "power_delta":         "能力/资源/修炼变化",
    "cost_delta":          "付出代价或后果",
    "decision_delta":      "人物做出新选择",
    "hook_delta":          "章末新悬念或新压力",
}

# 各增量对应的关键词
DELTA_KEYWORDS = {
    "event_delta":        ["决定", "发现", "找到", "遇到", "收到", "出事", "来了", "出事了", "出现"],
    "conflict_delta":     ["冲突", "争执", "对峙", "翻脸", "对抗", "决裂", "爆发", "打起来", "争吵"],
    "relationship_delta": ["信任", "理解", "怀疑", "靠近", "疏远", "原谅", "道歉", "感谢", "背叛"],
    "clue_delta":         ["线索", "发现", "证据", "查到", "打听到", "知情", "真相", "秘密", "揭穿"],
    "power_delta":        ["突破", "晋升", "升级", "学会", "获得", "得到", "失去", "摧毁", "修炼"],
    "cost_delta":         ["损失", "付出", "代价", "受伤", "牺牲", "失去", "扣", "罚", "赔"],
    "decision_delta":     ["决定", "选择", "答应", "拒绝", "同意", "妥协", "下定决心", "拿定主意"],
    "hook_delta":         ["还没", "即将", "等待", "不知道", "接下来", "明天", "怎么办", "不对", "难道"],
}

# ── 5 档进度速度 ──
PACE_LEVELS = {
    "breathing":   {"name": "慢章/休整",     "min_deltas": 1, "allow_low_action": True},
    "setup":       {"name": "铺垫/信息",     "min_deltas": 2, "allow_low_action": False},
    "normal":      {"name": "正常推进",      "min_deltas": 3, "allow_low_action": False},
    "accelerate":  {"name": "加速/冲突升级",  "min_deltas": 4, "allow_low_action": False},
    "climax":      {"name": "高潮/转折",     "min_deltas": 5, "allow_low_action": False},
}

# ── 题材进度侧重 ──
GENRE_FOCUS = {
    "xianxia":  ["conflict_delta", "power_delta", "cost_delta", "hook_delta"],
    "romance":  ["relationship_delta", "decision_delta", "hook_delta"],
    "urban":    ["relationship_delta", "event_delta", "decision_delta", "hook_delta"],
    "suspense": ["clue_delta", "event_delta", "conflict_delta", "hook_delta"],
    "mystery":  ["clue_delta", "event_delta", "cost_delta", "hook_delta"],
    "horror":   ["conflict_delta", "cost_delta", "hook_delta", "event_delta"],
    "history":  ["event_delta", "cost_delta", "decision_delta", "hook_delta"],
    "default":  ["event_delta", "conflict_delta", "hook_delta", "decision_delta"],
}


def detect_deltas(content: str) -> dict:
    """检测章节文本中有哪些进度增量被触发。"""
    results = {}
    for delta, keywords in DELTA_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in content)
        results[delta] = {"count": count, "present": count > 0}
    return results


def detect_pace_from_content(content: str) -> str:
    """根据文本特征推断实际 pace level。"""
    total_chars = len(content)
    action_words = len(re.findall(r'[跑跳冲抓打踢拔砸扔推挡躲闪]', content))
    dialogue_ratio = len(re.findall(r'说|问|答|喊|叫|骂|嘀咕|解释', content)) / max(total_chars, 1)

    # 动作多 → 加速/高潮
    if action_words >= 10:
        return "accelerate" if dialogue_ratio < 0.1 else "climax"
    # 对话多 → 推进
    if dialogue_ratio > 0.08:
        return "normal"
    # 动作少对话少 → 慢章
    if action_words <= 3 and dialogue_ratio < 0.04:
        return "breathing"
    return "normal"


def check_subject_mismatch(content: str, delta_results: dict) -> list:
    """检查题材进度侧重是否被满足。"""
    issues = []
    for genre, required in GENRE_FOCUS.items():
        if genre == "default":
            continue
        missing = [d for d in required if not delta_results.get(d, {}).get("present")]
        if missing:
            issues.append({"genre": genre, "missing": missing})
    return issues


def run_plot_pacing_check(content: str, chapter_no: int = 0,
                          pace_level: str = "normal", genre: str = "default",
                          prev_paces: list = None) -> dict:
    """剧情进度控制器主入口。"""
    total_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
    if total_chars < 300:
        return {"guard": "plot_pacing_controller", "status": "PASS",
                "score": 100, "findings": [], "chapter_no": chapter_no}

    # 检测增量
    deltas = detect_deltas(content)
    actual_pace = detect_pace_from_content(content)

    # 获取等级要求
    pace_cfg = PACE_LEVELS.get(pace_level, PACE_LEVELS["normal"])
    min_deltas = pace_cfg["min_deltas"]
    allow_low = pace_cfg["allow_low_action"]

    findings = []
    score = 100

    # 1. 检查增量数量
    present_count = sum(1 for d in deltas.values() if d["present"])
    genre_focus = GENRE_FOCUS.get(genre, GENRE_FOCUS["default"])
    focused_present = sum(1 for d in genre_focus if deltas.get(d, {}).get("present"))

    if present_count < min_deltas:
        findings.append({
            "level": "FAIL" if abs(present_count - min_deltas) >= 2 else "WARN",
            "message": f"进度增量不足：要求 {min_deltas} 类，实际 {present_count} 类 (pace={pace_level})",
            "suggestion": f"增加 {', '.join(list(PROGRESS_DELTAS.keys())[:3])} 中的一种"
        })
        score -= 30 if present_count < min_deltas - 1 else 15

    # 2. 检查题材关键增量
    if focused_present < max(1, len(genre_focus) // 2):
        findings.append({
            "level": "WARN",
            "message": f"题材「{genre}」关键进度不足：{focused_present}/{len(genre_focus)}",
            "suggestion": f"题材侧重: {', '.join(genre_focus)}"
        })
        score -= 15

    # 3. 慢章检查：动作少可以，但必须有进度
    if pace_level in ("breathing", "setup") and allow_low and "relationship_delta" not in [d for d in deltas if deltas[d]["present"]]:
        findings.append({
            "level": "INFO" if present_count >= 1 else "WARN",
            "message": "慢章允许动作少，但需至少一种进度：关系/信息/代价/决定",
            "suggestion": "当前检测到无关系变化，可加入人物关系或情感决定"
        })
        score -= 10

    # 4. 章末钩子检查
    if "hook_delta" not in [d for d in deltas if deltas[d]["present"]]:
        findings.append({
            "level": "WARN",
            "message": "章末缺少新钩子",
            "suggestion": "结尾留下未解决的问题或新的外部压力"
        })
        score -= 15

    # 5. 进度债检查（连续慢章）
    if prev_paces:
        slow_streak = sum(1 for p in (prev_paces[-3:] if prev_paces else []) if p in ("breathing", "setup"))
        if slow_streak >= 2 and pace_level in ("breathing", "setup"):
            findings.append({
                "level": "WARN",
                "message": f"连续 {slow_streak + 1} 章偏慢，建议下一章加速",
                "suggestion": "慢章可以存在，但不能连续原地踏步"
            })
            score -= 10
        elif slow_streak >= 2 and pace_level not in ("accelerate", "climax"):
            findings.append({
                "level": "INFO",
                "message": f"已连续 {slow_streak} 章慢速，下章建议加速",
            })

    # 综合
    status = "PASS" if score >= 70 else ("WARNING" if score >= 55 else "FAIL")
    return {
        "guard": "plot_pacing_controller",
        "status": status,
        "score": max(0, score),
        "findings": findings,
        "metrics": {
            "pace_level": pace_level,
            "actual_pace": actual_pace,
            "deltas": {k: v["present"] for k, v in deltas.items()},
            "present_count": present_count,
            "required_min": min_deltas,
            "genre_focus_hit": f"{focused_present}/{len(genre_focus)}",
        },
        "chapter_no": chapter_no,
    }
