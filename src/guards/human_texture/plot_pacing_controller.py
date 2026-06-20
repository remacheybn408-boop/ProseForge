"""plot_pacing_controller.py — 剧情进度控制器 v0.6.6

支持复合题材（如 "xianxia+爽文"），弹性加权评分而非刚硬阈值。
"""
import re
import json
from pathlib import Path

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
# pace 别名映射
PACE_ALIASES = {
    "slow": "breathing",
    "relaxed": "setup",
    "fast": "accelerate",
    "intense": "climax",
}


def _resolve_pace(pace: str) -> str:
    """Resolve pace aliases (slow→breathing, fast→accelerate)."""
    return PACE_ALIASES.get(pace, pace)


PACE_LEVELS = {
    "breathing":   {"name": "慢章/休整",     "min_deltas": 1},
    "setup":       {"name": "铺垫/信息",     "min_deltas": 2},
    "normal":      {"name": "正常推进",      "min_deltas": 3},
    "accelerate":  {"name": "加速/冲突升级",  "min_deltas": 4},
    "climax":      {"name": "高潮/转折",     "min_deltas": 5},
}



# 题材中文名 ↔ YAML key 映射
GENRE_ALIASES = {
    "修仙": "xianxia", "玄幻": "xuanhuan", "武侠": "wuxia",
    "都市": "urban", "都市异能": "urban_fantasy", "科幻": "sci_fi",
    "末世": "post_apocalyptic", "悬疑": "suspense",
    "推理": "mystery", "恐怖灵异": "horror", "历史": "history", "言情": "romance",
    "爽文": "爽文",
}


def _resolve_genre(genre: str) -> str:
    """Resolve Chinese genre names to YAML keys."""
    parts = [g.strip() for g in genre.split("+") if g.strip()]
    return "+".join(GENRE_ALIASES.get(p, p) for p in parts)


def _load_genre_pacing(genre: str) -> dict:
    """从 genre_presets.yaml 加载某个题材的 pacing 规则，支持复合题材如 xianxia+爽文."""
    try:
        fp = Path(__file__).resolve().parent.parent.parent.parent / "configs" / "human_texture" / "genre_presets.yaml"
        if not fp.exists():
            return _default_pacing()
        import yaml
        presets = yaml.safe_load(fp.read_text(encoding="utf-8"))

        # 解析复合题材：xianxia+爽文 → ["xianxia", "爽文"]
        genres = [g.strip() for g in _resolve_genre(genre).split("+") if g.strip()]
        if not genres:
            genres = ["default"]

        weights = []
        total_weight = 0
        for i, g in enumerate(genres):
            preset = presets.get(g, presets.get("default", {}))
            pacing = preset.get("pacing", {})
            if pacing:
                # 主题材权重 1.0，副题材递减
                w = 1.0 / (i + 1)
                weights.append((w, pacing))
                total_weight += w

        if not weights:
            return _default_pacing()

        # 合并加权 rule
        merged = _default_pacing()
        for w, pacing in weights:
            ratio = w / total_weight
            merged["min_deltas"] = max(1, round(sum(
                _default_pacing()["min_deltas"] * (1 - ratio) + pacing.get("min_deltas", 2) * ratio
                for _ in range(1)
            )))
            # 合并加权 delta
            for delta_key in PROGRESS_DELTAS:
                base_weight = _default_pacing()["weighted_deltas"].get(delta_key, 1.0)
                genre_weight = pacing.get("weighted_deltas", {}).get(delta_key, 1.0)
                merged["weighted_deltas"][delta_key] = round(base_weight * (1 - ratio) + genre_weight * ratio, 2)
            # 合并 focus_deltas（取并集）
            merged["focus_deltas"] = list(dict.fromkeys(
                merged["focus_deltas"] + pacing.get("focus_deltas", [])
            ))

        return merged
    except Exception:
        return _default_pacing()


def _default_pacing() -> dict:
    return {
        "min_deltas": 2,
        "weighted_deltas": {k: 1.0 for k in PROGRESS_DELTAS},
        "focus_deltas": ["event_delta", "conflict_delta", "hook_delta", "decision_delta"],
    }


def detect_deltas(content: str) -> dict:
    """检测章节文本中有哪些进度增量被触发（带程度评分）。"""
    results = {}
    for delta, keywords in DELTA_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in content)
        # 程度评分：1个关键词=1分，3+个=满分
        intensity = min(count / max(len(keywords) * 0.3, 1), 1.0)
        results[delta] = {
            "count": count,
            "present": count > 0,
            "intensity": round(intensity, 2),
        }
    return results


def detect_pace_from_content(content: str) -> str:
    """根据文本特征推断实际 pace level。"""
    total_chars = len(content)
    action_words = len(re.findall(r'[跑跳冲抓打踢拔砸扔推挡躲闪]', content))
    dialogue_ratio = len(re.findall(r'说|问|答|喊|叫|骂|嘀咕|解释', content)) / max(total_chars, 1)

    if action_words >= 10:
        return "accelerate" if dialogue_ratio < 0.1 else "climax"
    if dialogue_ratio > 0.08:
        return "normal"
    if action_words <= 3 and dialogue_ratio < 0.04:
        return "breathing"
    return "normal"


def run_plot_pacing_check(content: str, chapter_no: int = 0,
                          pace_level: str = "normal", genre: str = "default",
                          prev_paces: list = None) -> dict:
    """剧情进度控制器主入口。支持复合题材：--genre 'xianxia+爽文'"""
    total_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
    if total_chars < 300:
        return {"guard": "plot_pacing_controller", "status": "PASS",
                "score": 100, "findings": [], "chapter_no": chapter_no}

    # 加载题材规则（支持复合）
    pacing_rule = _load_genre_pacing(genre)
    weighted_deltas = pacing_rule["weighted_deltas"]
    focus_deltas = pacing_rule["focus_deltas"]
    min_deltas = pacing_rule.get("min_deltas", PACE_LEVELS.get(pace_level, {}).get("min_deltas", 2))

    # 检测增量
    deltas = detect_deltas(content)
    actual_pace = detect_pace_from_content(content)
    pace_level = _resolve_pace(pace_level)
    pace_cfg = PACE_LEVELS.get(pace_level, PACE_LEVELS["normal"])

    findings = []
    score = 100

    # ── 弹性加权评分 ──
    # 计算加权进度分：每类增量按题材权重加权
    weighted_score = 0
    max_possible = sum(weighted_deltas.values())
    for delta_key, weight in weighted_deltas.items():
        info = deltas.get(delta_key, {})
        present = info.get("present", False)
        intensity = info.get("intensity", 0)
        if present:
            weighted_score += weight * max(intensity, 0.5)  # 有触发至少给一半分

    # 弹性进度充足度
    progress_ratio = weighted_score / max_possible
    expected = max(0.2, min_deltas / len(PROGRESS_DELTAS))  # 弹性期望值

    if progress_ratio < expected * 0.6:
        findings.append({
            "level": "FAIL" if progress_ratio < expected * 0.3 else "WARN",
            "message": f"进度不足：加权分 {weighted_score:.1f}/{max_possible:.0f} (期望≥{expected:.0%}, 实际{progress_ratio:.0%})",
            "suggestion": f"复合题材「{genre}」侧重: {', '.join(sorted(weighted_deltas, key=weighted_deltas.get, reverse=True)[:4])}"
        })
        score -= 35 if progress_ratio < expected * 0.3 else 20

    # 增量数量检查（弹性）
    present_count = sum(1 for d in deltas.values() if d["present"])
    if present_count < min_deltas and progress_ratio < 0.4:
        findings.append({
            "level": "WARN" if present_count >= min_deltas - 1 else "FAIL",
            "message": f"增量类型偏少：{present_count} 类 (建议 ≥{min_deltas}类，复合题材要求更高)",
            "suggestion": f"当前 pace={pace_level}，增加事件或冲突推进"
        })
        score -= 15

    # 题材焦点检查（弹性）
    focused_present = sum(1 for d in focus_deltas if deltas.get(d, {}).get("present"))
    min_focus = max(1, len(focus_deltas) // 3)
    if focused_present < min_focus:
        findings.append({
            "level": "WARN",
            "message": f"题材「{genre}」关键推进偏少：{focused_present}/{len(focus_deltas)}",
            "suggestion": f"建议包含: {', '.join(focus_deltas[:4])}"
        })
        score -= 15

    # 慢章弹性规则
    if pace_level in ("breathing", "setup"):
        rel_present = deltas.get("relationship_delta", {}).get("present", False)
        dec_present = deltas.get("decision_delta", {}).get("present", False)
        if not rel_present and not dec_present:
            findings.append({
                "level": "INFO" if present_count >= 1 else "WARN",
                "message": "慢章允许放慢，但需至少一种人物关系或决定推进",
                "suggestion": "加入人物互动细节或内心决定"
            })
            score -= 8

    # 章末钩子（弹性：爽文类钩子权重更高）
    hook_present = deltas.get("hook_delta", {}).get("present", False)
    hook_weight = weighted_deltas.get("hook_delta", 1.0)
    if not hook_present and hook_weight >= 1.0:
        findings.append({
            "level": "WARN" if hook_weight >= 1.3 else "INFO",
            "message": f"章末无新钩子 (该题材钩子权重={hook_weight})",
            "suggestion": "结尾留下未解决的问题或新压力"
        })
        score -= 15 if hook_weight >= 1.3 else 5

    # 连续慢章债
    if prev_paces:
        slow_streak = sum(1 for p in (prev_paces[-3:] if prev_paces else []) if p in ("breathing", "setup"))
        if slow_streak >= 2 and pace_level in ("breathing", "setup"):
            findings.append({
                "level": "WARN",
                "message": f"连续 {slow_streak + 1} 章偏慢 (含本章)，建议下章加速",
                "suggestion": "慢章可以存在，但爽文/修仙类不宜超过2章"
            })
            score -= 12
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
            "genre": genre,
            "genres_parsed": [g.strip() for g in genre.split("+") if g.strip()],
            "weighted_score": round(weighted_score, 1),
            "max_possible": round(max_possible, 1),
            "progress_ratio": round(progress_ratio, 2),
            "deltas": {k: v["present"] for k, v in deltas.items()},
            "delta_intensities": {k: v["intensity"] for k, v in deltas.items()},
            "present_count": present_count,
            "focused_present": focused_present,
            "focus_total": len(focus_deltas),
            "min_deltas": min_deltas,
        },
        "chapter_no": chapter_no,
    }
