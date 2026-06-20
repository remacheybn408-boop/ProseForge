"""/story/init — Initialize .story/ directory with master_setting and memory files."""
import json
from pathlib import Path
from datetime import datetime

from src.story import resolve_story_dir
from src.story.contract_builder import load_characters

def _migrate_existing_commits(story: Path) -> dict:
    """Auto-generate contracts for commits that lack matching contracts.

    Called when .story/ already exists (e.g. post saved commits before init was run).
    Reads each chapter_NNN_commit.json and generates a corresponding contract
    in chapters/chapter_NNN_contract.json if one doesn't already exist.
    """
    commits_dir = story / "commits"
    chapters_dir = story / "chapters"
    chapters_dir.mkdir(exist_ok=True)

    created = []
    skipped = []

    commit_files = sorted(commits_dir.glob("chapter_*_commit.json"))
    if not commit_files:
        return {"migrated": 0, "created": [], "skipped": []}

    for cf in commit_files:
        ch_num_str = cf.stem.split("_")[1]
        contract_path = chapters_dir / f"chapter_{ch_num_str}_contract.json"
        if contract_path.exists():
            skipped.append(ch_num_str)
            continue

        # Build contract from commit data
        try:
            commit = json.loads(cf.read_text(encoding="utf-8"))
        except Exception:
            skipped.append(f"{ch_num_str}(parse_err)")
            continue

        ch_no = commit.get("chapter_no", int(ch_num_str))
        ch_title = commit.get("title", f"第{ch_no}章")

        # Extract active characters from character_state_changes
        char_changes = commit.get("character_state_changes", {})
        active_chars = []
        if char_changes:
            for name, change in char_changes.items():
                active_chars.append({
                    "name": name,
                    "first_appearance": change.get("chapter", ch_no),
                    "last_state": change.get("after", ""),
                    "last_chapter": change.get("chapter", ch_no),
                    "active": True,
                })
        # Also check memory/characters.json
        if not active_chars:
            try:
                mem_chars = load_characters(story)
                active_chars = [c for c in mem_chars if c.get("active", True)]
            except Exception:
                pass

        # Extract promises
        open_promises = []
        prom_mem = story / "memory" / "promises.json"
        if prom_mem.exists():
            try:
                all_promises = json.loads(prom_mem.read_text(encoding="utf-8"))
                open_promises = [
                    p.get("promise", str(p))
                    for p in all_promises if not p.get("resolved")
                ]
            except Exception:
                pass
        if not open_promises and commit.get("new_promises"):
            open_promises = commit["new_promises"]

        # Build minimal contract
        hooks = commit.get("next_chapter_hooks", [])
        contract = {
            "chapter_no": ch_no,
            "chapter_title": ch_title,
            "created_at": datetime.now().isoformat(),
            "generated_from": "commit_migration",
            "required_previous_context": hooks,
            "open_promises_to_keep": open_promises,
            "active_characters": active_chars,
            "active_world_facts": [],
            "required_scene_goal": hooks[0] if hooks else "",
            "style_constraints": [],
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
            "word_count": commit.get("word_count", 0),
            "target_scenes": 1,
        }
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
        created.append(ch_num_str)

    return {"migrated": len(created), "created": created, "skipped": skipped}


def init_story(project_root: Path = None, novel_title: str = "未命名小说"):
    """Initialize .story/ directory with empty memory files.

    If .story/ already exists (e.g. post saved commits but init was never run),
    auto-migrate existing commits into contracts so story health passes cleanly.
    """
    root = project_root or Path.cwd()
    story = resolve_story_dir(root)
    already_existed = story.exists()
    story.mkdir(parents=True, exist_ok=True)

    created = []
    migrated = {}

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

    # ── v0.7.1: migrate existing commits → contracts ──
    if already_existed:
        migrated = _migrate_existing_commits(story)
        if migrated.get("migrated", 0) > 0:
            created.append(f"contracts (migrated from {migrated['migrated']} commits)")

    return {
        "ok": True,
        "story_dir": str(story),
        "created": created,
        "migrated": migrated,
    }
