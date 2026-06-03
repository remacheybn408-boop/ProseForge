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


def _load_genre_preset(genre: str = "default") -> dict:
    """Load genre texture thresholds from YAML, fallback to default."""
    try:
        from pathlib import Path
        import yaml
        fp = Path(__file__).resolve().parent.parent.parent.parent / "configs" / "human_texture" / "genre_presets.yaml"
        if fp.exists():
            presets = yaml.safe_load(fp.read_text(encoding="utf-8"))
            return presets.get(genre, presets.get("default", {}))
    except Exception:
        pass
    return {}


def run_human_texture_guards(content: str, chapter_no: int = 0,
                              project_root=None, task_card: str = "",
                              genre: str = "default", pace_level: str = "normal",
                              prev_paces: list = None) -> dict:
    """运行全部人工味质量层检测，返回综合报告。"""
    results = []

    # 各 guard 独立运行
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

    # 加载题材预设
    preset = _load_genre_preset(genre)

    # 综合评分（权重按题材调整）
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
