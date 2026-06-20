"""human_texture package — 人工味质量层 v0.6.6"""
from .voice_diversity_guard import (
    run_voice_diversity_check, list_voice_cards, get_voice_card,
    save_voice_card, delete_voice_card,
)
from .rhythm_guard import run_rhythm_check
from .emotion_summary_guard import run_emotion_summary_check
from .conflict_pressure_guard import run_conflict_check
from .life_texture_guard import run_life_texture_check
from .cliche_sentence_guard import run_cliche_check
from .prompt_specificity_guard import run_prompt_check
from .water_density_guard import run_water_density_check
from .plot_pacing_controller import run_plot_pacing_check


# 题材中文名 ↔ YAML key 映射
GENRE_ALIASES = {
    "修仙": "xianxia", "玄幻": "xuanhuan", "武侠": "wuxia",
    "都市": "urban", "都市异能": "urban_fantasy", "科幻": "sci_fi",
    "末世": "post_apocalyptic", "悬疑": "suspense",
    "推理": "mystery", "恐怖灵异": "horror", "历史": "history", "言情": "romance",
    "爽文": "爽文",
}


def _resolve_genre_key(genre: str) -> str:
    """将中文题材名转为 YAML key，支持复合如 '修仙+爽文' -> 'xianxia+爽文'."""
    parts = [g.strip() for g in genre.split("+") if g.strip()]
    resolved = []
    for p in parts:
        resolved.append(GENRE_ALIASES.get(p, p))
    return "+".join(resolved)


def _load_genre_preset(genre: str = "default") -> dict:
    """Load genre texture thresholds from YAML, support composite genres like 'xianxia+爽文'."""
    try:
        from pathlib import Path
        import yaml
        fp = Path(__file__).resolve().parent.parent.parent.parent / "configs" / "human_texture" / "genre_presets.yaml"
        if not fp.exists():
            return {}
        presets = yaml.safe_load(fp.read_text(encoding="utf-8"))

        # Parse composite genres: "xianxia+爽文" -> ["xianxia", "爽文"]
        genres = [g.strip() for g in _resolve_genre_key(genre).split("+") if g.strip()]
        if not genres:
            genres = ["default"]

        # Single genre: direct lookup
        if len(genres) == 1:
            return presets.get(genres[0], presets.get("default", {}))

        # Composite genres: weighted merge
        weighted = []
        total_w = 0
        for i, g in enumerate(genres):
            p = presets.get(g, presets.get("default", {}))
            if p:
                w = 1.0 / (i + 1)
                weighted.append((w, p))
                total_w += w

        if not weighted:
            return presets.get("default", {})

        # Merge all keys
        all_keys = set()
        for _, p in weighted:
            all_keys.update(p.keys())

        merged = {}
        for key in all_keys:
            if key == "pacing":
                continue  # handled by plot_pacing_controller
            items = [(w / total_w, p.get(key)) for w, p in weighted if p.get(key) is not None]
            if not items:
                continue
            if isinstance(items[0][1], (int, float)):
                merged[key] = round(sum(ratio * val for ratio, val in items), 1)
            elif isinstance(items[0][1], list):
                seen = set()
                result = []
                for _, v in items:
                    for item in v:
                        if item not in seen:
                            result.append(item)
                            seen.add(item)
                merged[key] = result
            else:
                merged[key] = items[0][1]

        return merged
    except Exception:
        return {}


def run_human_texture_guards(content: str, chapter_no: int = 0,
                              project_root=None, task_card: str = "",
                              genre: str = "default", pace_level: str = "normal",
                              prev_paces: list = None) -> dict:
    """Run all human texture quality guards."""
    results = []

    results.append(run_rhythm_check(content, chapter_no))
    results.append(run_emotion_summary_check(content, chapter_no))
    results.append(run_conflict_check(content, chapter_no))
    results.append(run_life_texture_check(content, chapter_no))
    results.append(run_cliche_check(content, chapter_no))
    results.append(run_water_density_check(content, chapter_no, genre=genre))
    results.append(run_plot_pacing_check(content, chapter_no, pace_level=pace_level, genre=genre, prev_paces=prev_paces))
    if project_root:
        results.append(run_voice_diversity_check(content, chapter_no, project_root))
    if task_card:
        results.append(run_prompt_check(task_card, chapter_no))

    # Load genre preset (composite-aware)
    preset = _load_genre_preset(genre)

    # Composite score
    scores = [r.get("score", 100) for r in results]
    overall = sum(scores) // len(scores) if scores else 100
    worst = min(scores)

    findings = []
    for r in results:
        for f in r.get("findings", []):
            f["guard"] = r.get("guard", "?")
            findings.append(f)

    status = "PASS" if worst >= 70 else ("WARNING" if worst >= 55 else "FAIL")

    return {
        "guard": "human_texture",
        "status": status,
        "score": overall,
        "findings": findings,
        "guards": [r.get("guard") for r in results],
        "scores": {r.get("guard"): r.get("score") for r in results},
        "_guards_raw": results,
        "metrics": {"genre": genre, "genre_preset": preset} if preset else {"genre": genre},
        "chapter_no": chapter_no,
    }
