import io
import sys
import json
import subprocess
from pathlib import Path
from contextlib import redirect_stdout
from functools import lru_cache

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
SRC_GUARDS_DIR = PROJECT_ROOT / "src" / "guards"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(SRC_GUARDS_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_GUARDS_DIR))

def capture_stdout(fn, *args, **kwargs):
    buf = io.StringIO()
    code = 0
    try:
        with redirect_stdout(buf):
            code = fn(*args, **kwargs)
    except SystemExit as e:
        code = e.code if e.code is not None else 0
    return buf.getvalue(), code

def run_subprocess(cmd_parts, cwd=None, timeout=300):
    cwd = cwd or str(PROJECT_ROOT)
    result = subprocess.run(
        cmd_parts, cwd=cwd, timeout=timeout,
        capture_output=True, text=True
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }

@lru_cache()
def load_config():
    from config_utils import load_json_config, resolve_path

    cfg_path = PROJECT_ROOT / "config.json"
    if cfg_path.exists():
        return load_json_config(cfg_path, PROJECT_ROOT)
    return load_json_config(PROJECT_ROOT / "config.example.json", PROJECT_ROOT)

def get_python_exe():
    return sys.executable

def get_novel_py():
    return str(PROJECT_ROOT / "novel.py")

def resolve_active_slot():
    ws = PROJECT_ROOT / "workspace"
    reg_file = ws / "registry.json"
    if not reg_file.exists():
        return {"active_slot": "", "db_path": None, "chapters_dir": None, "slug": "demo_novel", "title": "Demo Novel"}

    try:
        import sqlite3
        reg = json.loads(reg_file.read_text(encoding="utf-8"))
        active = reg.get("active_slot", "")
        if not active:
            return {"active_slot": "", "db_path": None, "chapters_dir": None, "slug": "demo_novel", "title": "Demo Novel"}

        slot_dir = ws / active
        db_path = slot_dir / "novel.db"
        chapters_dir = slot_dir / "chapters"

        slug = "demo_novel"
        title = "Demo Novel"
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            try:
                row = conn.execute("SELECT slug, title FROM novels LIMIT 1").fetchone()
                if row:
                    slug = row[0]
                    title = row[1] or slug
            except Exception:
                pass
            finally:
                conn.close()

        return {
            "active_slot": active,
            "db_path": str(db_path) if db_path.exists() else None,
            "chapters_dir": str(chapters_dir) if chapters_dir.exists() else None,
            "slug": slug,
            "title": title,
        }
    except Exception:
        return {"active_slot": "", "db_path": None, "chapters_dir": None, "slug": "demo_novel", "title": "Demo Novel"}
