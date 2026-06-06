"""/story/commit — Generate chapter commit record after post."""
import json
from pathlib import Path
from datetime import datetime

from scripts.story.contract_builder import load_characters

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

def build_commit(project_root: Path, chapter_no: int, chapter_title: str = "",
                 word_count: int = 0, guard_summary: dict = None,
                 events: list = None, character_changes: dict = None,
                 new_promises: list = None, resolved_promises: list = None,
                 next_hooks: list = None) -> dict:
    """Build a chapter commit record."""
    commit = {
        "chapter_no": chapter_no,
        "title": chapter_title,
        "word_count": word_count,
        "committed_at": datetime.now().isoformat(),
        "events": events or [],
        "character_state_changes": character_changes or {},
        "new_promises": new_promises or [],
        "resolved_promises": resolved_promises or [],
        "next_chapter_hooks": next_hooks or [],
        "guard_summary": guard_summary or {},
    }
    return commit


def save_commit(project_root: Path, chapter_no: int, commit: dict):
    """Save a chapter commit and update memory files."""
    story = _resolve_story(project_root)
    story.mkdir(parents=True, exist_ok=True)
    (story / "commits").mkdir(parents=True, exist_ok=True)
    fp = story / "commits" / f"chapter_{chapter_no:03d}_commit.json"
    fp.write_text(json.dumps(commit, ensure_ascii=False, indent=2), encoding="utf-8")

    # Update event ledger
    if commit.get("events"):
        update_event_ledger(project_root, chapter_no, commit["events"])

    # Update memory
    update_memory_from_commit(project_root, commit)

    return str(fp)


def update_event_ledger(project_root: Path, chapter_no: int, events: list):
    """Append events to event_ledger.jsonl."""
    story = _resolve_story(project_root)
    events_dir = story / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    ledger = events_dir / "event_ledger.jsonl"
    lines = []
    for evt in events:
        entry = {"chapter": chapter_no, "event": str(evt), "timestamp": datetime.now().isoformat()}
        lines.append(json.dumps(entry, ensure_ascii=False))
    with open(ledger, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def update_memory_from_commit(project_root: Path, commit: dict):
    """Update memory files based on commit data."""
    story = _resolve_story(project_root)
    memory = story / "memory"
    memory.mkdir(parents=True, exist_ok=True)

    # Update promises
    promises_file = memory / "promises.json"
    promises = json.loads(promises_file.read_text(encoding="utf-8")) if promises_file.exists() else []
    for p in commit.get("new_promises", []):
        promises.append({"promise": str(p), "chapter": commit.get("chapter_no"), "resolved": False})
    for p in commit.get("resolved_promises", []):
        for existing in promises:
            if existing["promise"] == str(p):
                existing["resolved"] = True
    promises_file.write_text(json.dumps(promises, ensure_ascii=False, indent=2), encoding="utf-8")

    # Update character states
    chars_file = memory / "characters.json"
    chars = load_characters(_resolve_story(project_root))
    for name, change in commit.get("character_state_changes", {}).items():
        found = False
        for c in chars:
            if c.get("name") == name:
                c["last_state"] = change.get("after", c.get("last_state", ""))
                c["last_chapter"] = commit.get("chapter_no")
                found = True
        if not found:
            chars.append({
                "name": name,
                "first_appearance": commit.get("chapter_no"),
                "last_state": change.get("after", ""),
                "last_chapter": commit.get("chapter_no"),
                "active": True,
            })
    chars_file.write_text(json.dumps(chars, ensure_ascii=False, indent=2), encoding="utf-8")
