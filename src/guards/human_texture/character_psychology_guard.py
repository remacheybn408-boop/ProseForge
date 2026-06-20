"""character_psychology_guard.py — 角色心理状态审核 v1.0

历史: 由 mental_state_guard 重命名而来（v0.7.3 全量重命名）。

4 条规则检查角色心理状态描写是否过度/一致/合理/连续追踪。

注册名: character_psychology_guard
函数:   run_character_psychology_check
"""

import re
import json
from pathlib import Path
from typing import Optional

# ── 过度检测词库 ──
OVERPLAY_KEYWORDS = [
    "崩溃", "失控", "幻觉", "妄想", "癫狂", "精神错乱",
    "疯了", "发疯", "疯掉", "疯癫", "疯狂", "歇斯底里",
    "神经病", "精神病", "心理变态", "扭曲", "失常",
]

# 情绪极端词（用于偏离检测）
EXTREME_EMOTION_WORDS = [
    "极度", "非常", "无比", "万分", "极其", "绝顶",
    "撕心裂肺", "痛不欲生", "生不如死", "肝肠寸断",
    "欣喜若狂", "暴跳如雷", "怒不可遏", "惊恐万状",
    "毛骨悚然", "魂飞魄散", "肝胆俱裂",
]

# 章节追踪关键词
TRACKING_VERBS = [
    "表现", "体现", "描写", "展现", "出现", "显示",
    "情绪", "心理", "反应", "状态", "症状",
]


def _load_genre_preset(genre: str = "default") -> dict:
    """加载题材弹性阈值（不存在时返回默认值）.

    优先读 character_psychology key，向后兼容 mental_state key.
    """
    try:
        import yaml
        project_root = Path(__file__).resolve().parents[3]
        gf = project_root / "configs" / "human_texture" / "genre_presets.yaml"
        if not gf.exists():
            return {}
        data = yaml.safe_load(gf.read_text(encoding="utf-8"))
        section = data.get("character_psychology") or data.get("mental_state") or {}
        preset = section.get(genre, section.get("default", {}))
        return preset
    except Exception:
        return {}


def _get_elastic_threshold(key: str, genre: str = "default") -> int:
    """获取弹性阈值，不存在时返回默认值."""
    preset = _load_genre_preset(genre)
    defaults = {"overplay_density_warn": 3, "overplay_density_block": 8,
                "deviation_tolerance": 2, "chapter_tracking_gap": 3}
    return preset.get(key, defaults.get(key, 3))


def _get_character_text_segments(content: str, name: str, window: int = 200) -> str:
    """提取角色名附近文本段，用于 per-character 分析。"""
    segments = []
    pos = 0
    while True:
        idx = content.find(name, pos)
        if idx == -1:
            break
        start = max(0, idx - window)
        end = min(len(content), idx + len(name) + window)
        segments.append(content[start:end])
        pos = end
    return " ".join(segments)


def run_character_psychology_check(
    content: str,
    chapter_no: int = 0,
    project_root: Optional[Path] = None,
    character_name: Optional[str] = None,
    genre: str = "default",
) -> dict:
    """心理状态审核主入口 — 4 条规则.

    Args:
        content: 章节文本
        chapter_no: 章节号
        project_root: 项目根目录（用于加载角色卡）
        character_name: 指定角色（None = 检查所有有 psychology 的角色）
        genre: 题材（用于弹性阈值）

    Returns:
        {"status": "PASS"|"WARN"|"FAIL", "issues": [...]}
    """
    issues = []
    chinese_chars = len(re.findall(r'[一-鿿]', content))
    thousand_words = max(chinese_chars / 1000, 1)

    # ── 通用检查（不需要角色卡）──

    # Rule 1: 过度检测 — 心理病理词汇密度
    overplay_count = sum(content.count(kw) for kw in OVERPLAY_KEYWORDS)
    density = overplay_count / thousand_words
    block_threshold = _get_elastic_threshold("overplay_density_block", genre)
    warn_threshold = _get_elastic_threshold("overplay_density_warn", genre)

    if density > block_threshold:
        issues.append({
            "code": "PSYCHOLOGY_OVERPLAY_BLOCK",
            "severity": "FAIL",
            "message": f"心理病理词汇密度 {density:.1f}/千字，超过拦截阈值 {block_threshold}",
            "suggestion": f"减少「{'/'.join(OVERPLAY_KEYWORDS[:5])}」等词汇的使用频率",
            "confidence": 0.85,
        })
    elif density > warn_threshold:
        issues.append({
            "code": "PSYCHOLOGY_OVERPLAY_WARN",
            "severity": "WARN",
            "message": f"心理病理词汇密度 {density:.1f}/千字，超过警告阈值 {warn_threshold}",
            "suggestion": "检查是否有过度渲染心理状态的段落",
            "confidence": 0.80,
        })

    # ── 角色心理状态数据读取 ──
    if not project_root:
        project_root = Path(__file__).resolve().parents[3]

    try:
        from src.guards.human_texture.character_psychology_crud import list_character_psychologies
    except ImportError:
        # 无模块时仅返回过度检测结果
        status = "PASS"
        if any(i.get("severity") == "FAIL" for i in issues):
            status = "FAIL"
        elif issues:
            status = "WARN"
        return {"status": status, "issues": issues}

    # 获取所有角色的心理状态数据
    cards = list_character_psychologies(project_root)
    if character_name:
        cards = [c for c in cards if c.get("name") == character_name]

    deviation_tolerance = _get_elastic_threshold("deviation_tolerance", genre)
    tracking_gap = _get_elastic_threshold("chapter_tracking_gap", genre)

    for mc in cards:
        name = mc.get("name", "")
        ps = mc.get("character_psychology") or mc.get("mental_state") or {}
        if not ps:
            continue

        for cat, data in ps.items():
            if data is None:
                continue
            severity = data.get("severity", 0)
            triggers = data.get("triggers", [])
            manifestations = data.get("manifestations", [])
            chapter_notes = data.get("chapter_notes", {})

            # Rule 2: 一致性检测 — 触发词出现但未见表现
            if triggers:
                active_triggers = [t for t in triggers if t in content]
                if active_triggers:
                    active_manifests = [m for m in manifestations if m in content]
                    if not active_manifests:
                        issues.append({
                            "code": "PSYCHOLOGY_CONSISTENCY",
                            "severity": "WARN",
                            "message": f"「{name}」的「{cat}」触发词「{'/'.join(active_triggers[:3])}」在章节中出现，但未见对应表现",
                            "suggestion": f"添加对「{name}」的「{cat}」症状描写: {', '.join(manifestations[:3]) if manifestations else '参考角色卡设置表现'}",
                            "confidence": 0.75,
                            "character": name,
                            "category": cat,
                        })

            # Rule 3: 偏离检测 — 情绪极端词密度 vs severity
            if severity > 0:
                char_text = _get_character_text_segments(content, name)
                char_chars = len(re.findall(r'[一-鿿]', char_text))
                char_thousand = max(char_chars / 1000, 1)
                extreme_count = sum(char_text.count(w) for w in EXTREME_EMOTION_WORDS)
                extreme_density = extreme_count / char_thousand
                expected_density = severity * 0.3
                deviation = abs(extreme_density - expected_density)

                if deviation > deviation_tolerance:
                    if deviation > deviation_tolerance + 1:
                        issues.append({
                            "code": "PSYCHOLOGY_DEVIATION_BLOCK",
                            "severity": "FAIL",
                            "message": f"「{name}」情绪极端词密度 {extreme_density:.1f}/千字，"
                                       f"与设定 severity={severity} 的预期 {expected_density:.1f}/千字偏差过大",
                            "suggestion": "调整情绪极端词密度，或更新角色卡的 severity",
                            "confidence": 0.70,
                            "character": name,
                            "category": cat,
                        })
                    else:
                        issues.append({
                            "code": "PSYCHOLOGY_DEVIATION_WARN",
                            "severity": "WARN",
                            "message": f"「{name}」情绪极端词密度 {extreme_density:.1f}/千字，"
                                       f"与 setting severity={severity} 略有偏差",
                            "suggestion": "检查该章节情绪描写是否与设定严重度匹配",
                            "confidence": 0.65,
                            "character": name,
                            "category": cat,
                        })

            # Rule 4: 章节追踪 — chapter_notes 是否更新
            if severity > 0 and chapter_no > 0:
                ch_str = str(chapter_no)
                if ch_str not in chapter_notes:
                    tracked_chapters = sorted(
                        (int(k) for k in chapter_notes.keys() if k.isdigit()),
                        reverse=True,
                    )
                    if tracked_chapters:
                        gap = chapter_no - tracked_chapters[0]
                    else:
                        gap = chapter_no

                    if gap >= tracking_gap:
                        issues.append({
                            "code": "PSYCHOLOGY_TRACKING_GAP",
                            "severity": "WARN",
                            "message": f"「{name}」的「{cat}」已连续 {gap} 章无 chapter_note 更新（上次: 第{tracked_chapters[0] if tracked_chapters else '?'}章）",
                            "suggestion": f"使用 nf_审稿 或 nf_改写 工具查看/修改",
                            "confidence": 0.90,
                            "character": name,
                            "category": cat,
                        })

    # ── 汇总 ──
    if any(i.get("severity") == "FAIL" for i in issues):
        status = "FAIL"
    elif issues:
        status = "WARN"
    else:
        status = "PASS"

    return {
        "status": status,
        "issues": issues,
    }


# ═════════════════════════════════════════════════════════════════
# Backward-compat alias — 旧函数名继续工作
# ═════════════════════════════════════════════════════════════════

run_mental_state_check = run_character_psychology_check
