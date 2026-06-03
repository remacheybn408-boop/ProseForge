"""/story/contract — Generate chapter writing contract."""
import json
from pathlib import Path
from datetime import datetime

STORY_DIR = ".story"


def _resolve_story(project_root):
    try:
        ws_dir = project_root / 'workspace'
        reg_file = ws_dir / 'registry.json'
        if reg_file.exists():
            import json
            reg = json.loads(reg_file.read_text(encoding='utf-8'))
            active = reg.get('active_slot', '')
            if active:
                sd = ws_dir / active / '.story'
                if sd.exists():
                    return sd
    except Exception:
        pass
    return project_root / '.story'

def build_contract(project_root: Path, chapter_no: int, chapter_title: str = "",
                   prev_contract: dict = None, prev_commit: dict = None) -> dict:
    """Build a chapter contract from previous context and master settings."""
    story = _resolve_story(project_root)

    # Load master setting
    ms = json.loads((story / "master_setting.json").read_text(encoding="utf-8"))

    # Load memory
    characters = json.loads((story / "memory" / "characters.json").read_text(encoding="utf-8"))
    promises = json.loads((story / "memory" / "promises.json").read_text(encoding="utf-8"))
    world_facts = json.loads((story / "memory" / "world_facts.json").read_text(encoding="utf-8"))
    rules = json.loads((story / "memory" / "learned_rules.json").read_text(encoding="utf-8"))

    # Inherit from previous
    required_context = []
    open_promises = []
    if prev_commit:
        required_context = prev_commit.get("next_chapter_hooks", [])
    if promises:
        open_promises = [p for p in promises if not p.get("resolved")]

    contract = {
        "chapter_no": chapter_no,
        "chapter_title": chapter_title,
        "created_at": datetime.now().isoformat(),
        "required_previous_context": required_context,
        "open_promises_to_keep": [p["promise"] for p in open_promises],
        "active_characters": [c for c in characters if c.get("active", True)],
        "active_world_facts": world_facts[-10:] if world_facts else [],
        "required_scene_goal": (prev_commit.get("next_chapter_hooks") or [""])[0] if prev_commit else "",
        "style_constraints": [r["rule"] for r in rules],
        "forbidden_changes": [
            "不要违反已建立的世界观规则",
            "不要让角色做出不符合性格的决定",
            "不要忽略前文已建立的伏笔",
        ],
        "minimum_quality_rules": {
            "min_words": 1300,
            "must_have_dialogue": False,
            "must_advance_plot": True,
        },
    }

    # Find existing and extend
    existing_promises = [p for p in promises if p.get("resolved")]
    contract["previously_resolved_promises"] = [p["promise"] for p in existing_promises[-5:]]

    return contract


def save_contract(project_root: Path, chapter_no: int, contract: dict):
    """Save a chapter contract to .story/chapters/chapter_XXX_contract.json"""
    story = _resolve_story(project_root)
    (story / "chapters").mkdir(exist_ok=True)
    fp = story / "chapters" / f"chapter_{chapter_no:03d}_contract.json"
    fp.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(fp)
