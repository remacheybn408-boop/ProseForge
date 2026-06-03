"""/story/init — Initialize .story/ directory with master_setting and memory files."""
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

def init_story(project_root: Path = None, novel_title: str = "未命名小说"):
    """Initialize .story/ directory with empty memory files."""
    root = project_root or Path.cwd()
    story = _resolve_story(root)
    story.mkdir(parents=True, exist_ok=True)

    created = []

    # Ensure subdirs
    for sub in ["memory", "chapters", "commits", "events"]:
        (story / sub).mkdir(exist_ok=True)

    # master_setting.json
    ms = story / "master_setting.json"
    if not ms.exists():
        ms.write_text(json.dumps({
            "title": novel_title,
            "genre": "",
            "style": "",
            "total_volumes": 0,
            "target_chapters": 0,
            "core_theme": "",
            "world_summary": "",
            "created_at": datetime.now().isoformat()
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        created.append("master_setting.json")

    # memory files
    memory = story / "memory"
    memory.mkdir(exist_ok=True)

    mem_files = {
        "characters.json": [],
        "promises.json": [],
        "world_facts.json": [],
        "style_rules.json": [],
        "learned_rules.json": [],
    }
    for fname, default in mem_files.items():
        fp = memory / fname
        if not fp.exists():
            fp.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
            created.append(f"memory/{fname}")

    # subdirs
    for d in ["volumes", "chapters", "commits", "events"]:
        (story / d).mkdir(exist_ok=True)

    # event ledger (JSONL)
    el = story / "events" / "event_ledger.jsonl"
    if not el.exists():
        el.write_text("", encoding="utf-8")

    return {"ok": True, "story_dir": str(story), "created": created}
