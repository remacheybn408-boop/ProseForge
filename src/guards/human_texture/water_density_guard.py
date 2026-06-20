"""water_density_guard.py — 水文密度检测 v0.6.6

检测字数增加但有效事件没有增加的章节。
接入现有 human_texture 体系，不新建 CLI。
"""
import re

# 有效事件标记词
EVENT_MARKERS = [
    "决定", "发现", "失去", "改变", "打破", "推开", "冲进", "转身走",
    "说了一句", "拿定主意", "不再", "终于", "第一次", "承认", "坦白",
    "揭穿", "暴露", "追上", "阻止", "抢在", "挡在", "落入",
    "签订", "同意", "拒绝", "答应", "妥协", "翻脸",
]

# 低信息对话模式
LOW_INFO_DIALOGUE = [
    "我不知道", "你到底想", "你听我", "你冷静", "你相信我",
    "不是你想的那样", "事情不是", "你不明白", "我也没办法",
    "你先听我说", "我没什么好说的",
]

# 重复情绪模式
REPEATED_EMOTION = [
    "心里一沉", "心里一紧", "说不上来", "复杂", "纷乱",
    "某种", "仿佛", "无法形容",
]


def run_water_density_check(content: str, chapter_no: int = 0,
                            genre: str = "default") -> dict:
    """水文密度检测主入口。"""
    total_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
    if total_chars < 600:
        return {"guard": "water_density_guard", "status": "PASS",
                "score": 100, "findings": [],
                "metrics": {"word_count": total_chars, "event_count": 0,
                           "density": 0, "note": "章节偏短，跳过水文检测"},
                "chapter_no": chapter_no}

    # 检测有效事件
    event_count = sum(1 for m in EVENT_MARKERS if m in content)
    # 场景变化检测
    scene_markers = len(re.findall(r'\n\n', content)) + 1
    # 低信息对话
    low_info = sum(1 for p in LOW_INFO_DIALOGUE if p in content)
    # 重复情绪
    repeated_emotion = sum(1 for p in REPEATED_EMOTION if p in content)

    density = round(event_count / (total_chars / 1000), 2)

    findings = []
    score = 100

    # 事件密度评分
    threshold = _get_density_threshold(genre, total_chars)
    if density < threshold[0]:
        findings.append({
            "level": "FAIL",
            "message": f"事件密度过低 ({density}/千字)，本章含 {event_count} 个有效事件",
            "suggestion": f"每千字至少 {threshold[1]} 个有效事件——增加决定/发现/冲突变化"
        })
        score -= 30
    elif density < threshold[1]:
        findings.append({
            "level": "WARN",
            "message": f"事件密度偏低 ({density}/千字)，{event_count} 个事件/{total_chars}字",
            "suggestion": "检查是否有大量非推进性描写"
        })
        score -= 15

    # 低信息对话
    if low_info >= 3:
        findings.append({
            "level": "WARN",
            "message": f"低信息对话 {low_info} 处",
            "suggestion": "避免对话原地绕圈，让每次对话推进信息或关系"
        })
        score -= 10

    # 重复情绪
    if repeated_emotion >= 4:
        findings.append({
            "level": "WARN",
            "message": f"重复情绪模式 {repeated_emotion} 处",
            "suggestion": "同一情绪不要反复用不同词语总结"
        })
        score -= 10

    status = "PASS" if score >= 70 else ("WARNING" if score >= 55 else "FAIL")
    return {
        "guard": "water_density_guard",
        "status": status,
        "score": max(0, score),
        "findings": findings,
        "metrics": {
            "word_count": total_chars,
            "event_count": event_count,
            "density": density,
            "low_info_dialogue": low_info,
            "repeated_emotion": repeated_emotion,
        },
        "chapter_no": chapter_no,
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


def _get_density_threshold(genre: str, word_count: int) -> tuple:
    """按题材返回密度阈值 (warn, fail)。支持复合题材如 xianxia+爽文。"""
    try:
        from pathlib import Path
        import yaml
        fp = Path(__file__).resolve().parent.parent.parent.parent / "configs" / "human_texture" / "genre_presets.yaml"
        if fp.exists():
            presets = yaml.safe_load(fp.read_text(encoding="utf-8"))
            genres = [g.strip() for g in _resolve_genre(genre).split("+") if g.strip()]
            if not genres:
                genres = ["default"]
            total_w = 0
            weighted_val = 0
            for i, g in enumerate(genres):
                p = presets.get(g, presets.get("default", {}))
                val = p.get("water_density_min")
                if val is not None:
                    w = 1.0 / (i + 1)
                    weighted_val += val * w
                    total_w += w
            if total_w > 0:
                avg = weighted_val / total_w
                warn_th = max(0.4, avg / 100)
                fail_th = max(0.2, warn_th - 0.2)
                return (warn_th, fail_th)
    except Exception:
        pass
    return (0.8, 0.5)
