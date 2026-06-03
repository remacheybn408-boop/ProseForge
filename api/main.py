import io
import sys
import json
import subprocess
from pathlib import Path
from typing import Optional
from contextlib import redirect_stdout
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, Body, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
SRC_GUARDS_DIR = PROJECT_ROOT / "src" / "guards"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(SRC_GUARDS_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_GUARDS_DIR))

app = FastAPI(
    title="Novel Forge - 小说引擎 API",
    version="0.6.5",
    description="长篇小说 AI 辅助写作流水线的 REST API 封装",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _capture(fn, *args, **kwargs):
    buf = io.StringIO()
    code = 0
    try:
        with redirect_stdout(buf):
            code = fn(*args, **kwargs)
    except SystemExit as e:
        code = e.code if e.code is not None else 0
    return buf.getvalue().strip(), code

def _subprocess(cmd_parts, cwd=None, timeout=300):
    cwd = cwd or str(PROJECT_ROOT)
    r = subprocess.run(cmd_parts, cwd=cwd, timeout=timeout, capture_output=True, text=True)
    return {"returncode": r.returncode, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}

def _load_cfg():
    from config_utils import load_json_config, resolve_path
    p = PROJECT_ROOT / "config.json"
    if p.exists():
        return load_json_config(p, PROJECT_ROOT)
    return load_json_config(PROJECT_ROOT / "config.example.json", PROJECT_ROOT)

def _slot_info():
    ws = PROJECT_ROOT / "workspace"
    reg = ws / "registry.json"
    if not reg.exists():
        return None
    try:
        data = json.loads(reg.read_text(encoding="utf-8"))
        active = data.get("active_slot", "")
        if not active:
            return None
        slot_dir = ws / active
        db = slot_dir / "novel.db"
        if not db.exists():
            return {"active_slot": active, "db_path": None, "slug": None, "title": None}
        import sqlite3
        conn = sqlite3.connect(str(db))
        try:
            row = conn.execute("SELECT slug, title FROM novels LIMIT 1").fetchone()
            slug = row[0] if row else None
            title = row[1] if row else None
        finally:
            conn.close()
        return {
            "active_slot": active,
            "db_path": str(db),
            "slug": slug,
            "title": title,
            "chapters_dir": str(slot_dir / "chapters"),
        }
    except Exception:
        return None

def _ok(data=None, output=""):
    return {"success": True, "data": data, "output": output}

def _err(msg, output=""):
    return {"success": False, "error": msg, "output": output}

def _menu_status():
    from hermes_menu import get_project_status
    return get_project_status()

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.6.5", "timestamp": datetime.now().isoformat()}

@app.get("/api/status")
def get_status(detail: bool = False):
    try:
        from doctor import main as doctor_main
        out, code = _capture(doctor_main, detail=detail)
        return _ok(data={"exit_code": code, "healthy": code == 0}, output=out)
    except ImportError:
        checks = {}
        import platform
        checks["os"] = f"{platform.system()} {platform.release()}"
        checks["python"] = f"{sys.version_info.major}.{sys.version_info.minor}"
        checks["python_ok"] = sys.version_info >= (3, 10)
        checks["config_exists"] = (PROJECT_ROOT / "config.json").exists()
        checks["voice_packs"] = (PROJECT_ROOT / "voice_packs").exists()
        all_ok = all(v for v in checks.values() if isinstance(v, bool))
        return _ok(data={"exit_code": 0 if all_ok else 1, "healthy": all_ok, "checks": checks})

@app.post("/api/init")
def init_project():
    cmd = [sys.executable, str(PROJECT_ROOT / "novel.py"), "init"]
    r = _subprocess(cmd, timeout=60)
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"] + "\n" + r["stderr"])

@app.post("/api/demo")
def run_demo():
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "demo"],
        timeout=600
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.post("/api/setup")
def setup_novels_root(novels_root: str = Body(..., embed=True)):
    from pathlib import Path as P
    path = P(novels_root)
    if not path.is_absolute():
        raise HTTPException(400, "请使用绝对路径（如 D:\\小说）")

    cfg_file = PROJECT_ROOT / "config.json"
    try:
        cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    except Exception:
        cfg = {}

    path.mkdir(parents=True, exist_ok=True)
    cfg["novels_root"] = str(path)
    if "paths" not in cfg:
        cfg["paths"] = {}
    cfg["paths"]["novels_root"] = str(path)
    cfg_file.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    return _ok(data={"novels_root": str(path), "exists": path.exists()})

@app.post("/api/pre/{chapter_no}")
def pre_write(chapter_no: int, slug: Optional[str] = None, volume_no: Optional[int] = None):
    cmd = [
        sys.executable, str(SCRIPTS_DIR / "chapter_pipeline.py"), "pre", str(chapter_no),
        "--config", str(PROJECT_ROOT / "config.json"),
    ]
    slot = _slot_info()
    s = slug or (slot["slug"] if slot else "demo_novel")
    cmd.extend(["--novel-slug", s])
    if volume_no:
        cmd.extend(["--volume-no", str(volume_no)])

    r = _subprocess(cmd, timeout=120)
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"] + "\n" + r["stderr"])

@app.post("/api/post/{chapter_no}")
def post_write(
    chapter_no: int,
    slug: Optional[str] = None,
    volume_no: Optional[int] = None,
    file_path: Optional[str] = None,
    story: bool = False,
):
    """写后检查：字数门禁 → 连续性 → 场景 → 反AI腔 → 防幻觉 → 入库。"""
    slot = _slot_info()
    s = slug or (slot["slug"] if slot else "demo_novel")
    chapters_dir = file_path if file_path else (slot["chapters_dir"] if slot else None)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / "chapter_pipeline.py"), "post", str(chapter_no),
        "--config", str(PROJECT_ROOT / "config.json"),
        "--novel-slug", s,
    ]
    if volume_no:
        cmd.extend(["--volume-no", str(volume_no)])
    if chapters_dir:
        cmd.extend(["--chapters-dir", chapters_dir])
    if slot and slot.get("db_path"):
        cmd.extend(["--db-path", slot["db_path"]])

    r = _subprocess(cmd, timeout=300)
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"] + "\n" + r["stderr"])

@app.post("/api/review/{chapter_no}")
def review_chapter(chapter_no: int, slug: Optional[str] = None, volume_no: Optional[int] = None):
    s = slug or (_slot_info() or {}).get("slug", "demo_novel")
    cmd = [
        sys.executable, str(SCRIPTS_DIR / "chapter_pipeline.py"), "review", str(chapter_no),
        "--config", str(PROJECT_ROOT / "config.json"),
        "--novel-slug", s,
    ]
    if volume_no:
        cmd.extend(["--volume-no", str(volume_no)])
    r = _subprocess(cmd, timeout=300)
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"] + "\n" + r["stderr"])

@app.post("/api/check")
def check_file(file_path: str = Body(..., embed=True)):
    fp = Path(file_path)
    if not fp.exists():
        raise HTTPException(404, f"文件不存在: {file_path}")

    cmd = [sys.executable, str(PROJECT_ROOT / "novel.py"), "check", file_path]
    r = _subprocess(cmd, timeout=120)
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.get("/api/wc")
def word_count(file_path: str = Query(..., description="章节 TXT 文件路径")):
    fp = Path(file_path)
    if not fp.exists():
        raise HTTPException(404, f"文件不存在: {file_path}")
    content = fp.read_text(encoding="utf-8")
    cn = sum(1 for c in content if '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf')
    total = len(content.replace('\n', '').replace('\r', '').replace(' ', ''))
    return _ok(data={"chinese_chars": cn, "total_chars_no_whitespace": total, "file": file_path})

@app.get("/api/agents")
def list_agents():
    try:
        from agents.orchestrator import list_agents as _la
        agents = _la()
        return _ok(data={"agents": agents})
    except Exception as e:
        agents = [
            "chief_editor", "voice_agent", "plot_agent", "setting_agent",
            "continuity_agent", "reader_pull_agent", "context_agent", "anti_ai_agent"
        ]
        return _ok(data={"agents": agents})

@app.post("/api/agents/review/{chapter_no}")
def agents_review(
    chapter_no: int,
    mode: str = Query("light", description="light | full"),
    slug: Optional[str] = None,
):
    """多 Agent 并行审稿（8 个 Agent + Chief Editor）。"""
    s = slug or (_slot_info() or {}).get("slug", "demo_novel")
    cfg = _load_cfg()
    from config_utils import resolve_path
    novels_root = resolve_path(PROJECT_ROOT, cfg.get("novels_root", "./novels"))
    ch_dir = Path(novels_root) / s / "第01卷"
    candidates = list(ch_dir.glob(f"第{chapter_no}章*.txt"))

    content = ""
    if candidates:
        content = candidates[0].read_text(encoding="utf-8")

    from agents.orchestrator import run_agent_review
    result = run_agent_review(content, chapter_no, mode=mode)
    return _ok(data=result)

@app.get("/api/reports")
def get_reports(limit: int = 20):
    cfg = _load_cfg()
    from config_utils import resolve_path
    reports_dir = resolve_path(PROJECT_ROOT, cfg.get("reports_root", "./exports/reports"))

    if not reports_dir.exists():
        return _ok(data={"reports": [], "count": 0})

    all_reports = sorted(reports_dir.rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    items = []
    for rp in all_reports[:limit]:
        mtime = datetime.fromtimestamp(rp.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        size = rp.stat().st_size
        status = "?"
        try:
            data = json.loads(rp.read_text(encoding="utf-8"))
            status = data.get("status", data.get("overall_status", "?"))
        except Exception:
            pass
        items.append({
            "path": str(rp.relative_to(reports_dir)),
            "mtime": mtime,
            "size": size,
            "status": status,
        })

    return _ok(data={"reports": items, "count": len(items), "total": len(all_reports)})

@app.get("/api/reports/{filename:path}")
def get_report_content(filename: str):
    cfg = _load_cfg()
    from config_utils import resolve_path
    reports_dir = resolve_path(PROJECT_ROOT, cfg.get("reports_root", "./exports/reports"))
    fp = reports_dir / filename
    if not fp.exists() or not fp.is_relative_to(reports_dir):
        raise HTTPException(404, f"报告不存在: {filename}")
    content = json.loads(fp.read_text(encoding="utf-8"))
    return _ok(data=content)

@app.get("/api/guards")
def get_guards():
    guards = {}
    try:
        from guard_registry import GUARD_RUNNERS, GUARD_LEVELS, MODE_GUARDS
        core = {}
        for name in sorted(GUARD_RUNNERS):
            core[name] = {"level": GUARD_LEVELS.get(name, "?")}
        guards["core"] = core
        guards["modes"] = {}
        for mode, g_list in MODE_GUARDS.items():
            guards["modes"][mode] = g_list
    except ImportError:
        guards["core"] = {"error": "guard_registry not importable"}

    v050 = {}
    for name in ["reader_pull_guard", "voice_pack_guard", "meme_pack_guard"]:
        v050[name] = (SRC_GUARDS_DIR / f"{name}.py").exists()
    guards["v050"] = v050

    return _ok(data=guards)

@app.get("/api/export")
def export_novel(slug: Optional[str] = None, fmt: str = "md"):
    s = slug or (_slot_info() or {}).get("slug", "demo_novel")
    cmd = [sys.executable, str(PROJECT_ROOT / "novel.py"), "export", "--slug", s, "--format", fmt]
    r = _subprocess(cmd, timeout=60)
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.get("/api/db/list")
def db_list():
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "db", "list"],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.get("/api/db/current")
def db_current():
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "db", "current"],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.get("/api/db/info")
def db_info():
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "db", "info"],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.post("/api/db/new")
def db_new(name: str = Body(..., embed=True), description: str = Body("")):
    cmd = [sys.executable, str(PROJECT_ROOT / "novel.py"), "db", "new", "--name", name]
    if description:
        cmd.extend(["--description", description])
    r = _subprocess(cmd, timeout=30)
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.post("/api/db/switch/{slot_id}")
def db_switch(slot_id: str):
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "db", "use", slot_id],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.post("/api/db/backup")
def db_backup(slot_id: Optional[str] = None):
    cmd = [sys.executable, str(PROJECT_ROOT / "novel.py"), "db", "backup"]
    if slot_id:
        cmd.extend(["--slot", slot_id])
    r = _subprocess(cmd, timeout=30)
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.delete("/api/db/{slot_id}")
def db_delete(slot_id: str, confirm: bool = Query(False)):
    cmd = [sys.executable, str(PROJECT_ROOT / "novel.py"), "db", "delete", slot_id]
    if confirm:
        cmd.append("--yes")
    r = _subprocess(cmd, timeout=30)
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.get("/api/db/trash")
def db_trash():
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "db", "trash"],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.post("/api/db/restore/{slot_id}")
def db_restore(slot_id: str, from_trash: bool = Query(False), backup_id: Optional[str] = None):
    cmd = [sys.executable, str(PROJECT_ROOT / "novel.py"), "db", "restore", slot_id]
    if from_trash:
        cmd.append("--from-trash")
    if backup_id:
        cmd.extend(["--backup-id", backup_id])
    r = _subprocess(cmd, timeout=30)
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.get("/api/outlines")
def outlines_list():
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "outline", "list"],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.get("/api/outlines/current")
def outlines_current():
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "outline", "current"],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.post("/api/outlines/add")
def outline_add(
    outline_file: str = Body(..., embed=True),
    title: str = Body(""),
    genre: str = Body(""),
    style: str = Body(""),
    replace_current: bool = Body(False),
    keep_inactive: bool = Body(False),
    dry_run: bool = Body(False),
):
    """添加大纲（自动相似度检测）。"""
    cmd = [sys.executable, str(PROJECT_ROOT / "novel.py"), "outline", "add", outline_file]
    if title:
        cmd.extend(["--title", title])
    if genre:
        cmd.extend(["--genre", genre])
    if style:
        cmd.extend(["--style", style])
    if replace_current:
        cmd.append("--replace-current")
    if keep_inactive:
        cmd.append("--keep-inactive")
    if dry_run:
        cmd.append("--dry-run")
    r = _subprocess(cmd, timeout=60)
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.post("/api/outlines/switch/{outline_id}")
def outline_switch(outline_id: str):
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "outline", "switch", outline_id],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.post("/api/outlines/import")
def outline_import(
    outline_file: str = Body(..., embed=True),
    title: str = Body(..., embed=True),
    genre: str = Body(""),
    style: str = Body(""),
):
    """导入大纲（指定标题）。"""
    cmd = [sys.executable, str(PROJECT_ROOT / "novel.py"), "outline", "import", outline_file, "--title", title]
    if genre:
        cmd.extend(["--genre", genre])
    if style:
        cmd.extend(["--style", style])
    r = _subprocess(cmd, timeout=60)
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.post("/api/outlines/diff/{id1}/{id2}")
def outline_diff(id1: str, id2: str):
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "outline", "diff", id1, id2],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.post("/api/outlines/rollback/{outline_id}")
def outline_rollback(outline_id: str):
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "outline", "rollback", outline_id],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.post("/api/outlines/compare")
def outline_compare(compare_file: str = Body(..., embed=True)):
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "outline", "compare", compare_file],
        timeout=60
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.delete("/api/outlines/{outline_id}")
def outline_delete(outline_id: str):
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "outline", "delete", outline_id],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.post("/api/outlines/undo")
def outline_undo():
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "outline", "undo"],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.get("/api/board")
def get_board():
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "board"],
        timeout=30
    )
    return _ok(output=r["stdout"])

@app.get("/api/menu/status")
def get_menu_status():
    status = _menu_status()
    return _ok(data=status)

@app.get("/api/chapters")
def get_chapters():
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "chapters"],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.get("/api/genres")
def list_genres():
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "genre", "list"],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.get("/api/genres/{genre_id}")
def show_genre(genre_id: str):
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "genre", "show", genre_id],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.get("/api/styles")
def list_styles():
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "style", "list"],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.get("/api/styles/{style_id}")
def show_style(style_id: str):
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "style", "show", style_id],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.post("/api/story/init")
def story_init():
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "story", "init"],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.post("/api/story/contract/{chapter_no}")
def story_contract(chapter_no: int):
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "story", "contract", str(chapter_no)],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.post("/api/story/commit/{chapter_no}")
def story_commit(chapter_no: int):
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "story", "commit", str(chapter_no)],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.get("/api/story/health")
def story_health():
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "story", "health"],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.post("/api/query")
def query_memory(question: str = Body(..., embed=True)):
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "query", question],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.get("/api/learn")
def learn_rules(action: str = Query("list"), rule: Optional[str] = None):
    cmd = [sys.executable, str(PROJECT_ROOT / "novel.py"), "learn", action]
    if rule:
        cmd.append(rule)
    r = _subprocess(cmd, timeout=30)
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.get("/api/rag/status")
def rag_status():
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "rag", "status"],
        timeout=30
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.post("/api/rag/query")
def rag_query(question: str = Body(..., embed=True)):
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "rag", "query", question],
        timeout=60
    )
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.post("/api/stability-check")
def stability_check(full: bool = Query(False)):
    cmd = [sys.executable, str(PROJECT_ROOT / "novel.py"), "stability-check"]
    if full:
        cmd.append("--full")
    r = _subprocess(cmd, timeout=300 if full else 60)
    return _ok(data={"exit_code": r["returncode"]}, output=r["stdout"])

@app.post("/api/chapters/upload")
async def upload_chapter(
    file: UploadFile = File(...),
    chapter_no: Optional[int] = None,
    slug: Optional[str] = None,
):
    """上传章节 TXT 文件到指定小说目录。"""
    slot = _slot_info()
    s = slug or (slot["slug"] if slot else "demo_novel")

    cfg = _load_cfg()
    from config_utils import resolve_path
    novels_root = resolve_path(PROJECT_ROOT, cfg.get("novels_root", "./novels"))
    vol_dir = Path(novels_root) / s / "第01卷"
    vol_dir.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    text = content.decode("utf-8")

    if chapter_no:
        candidates = list(vol_dir.glob(f"第{chapter_no}章*.txt"))
        if candidates:
            dest = candidates[0]
        else:
            dest = vol_dir / f"第{chapter_no}章_{file.filename}"
    else:
        dest = vol_dir / file.filename

    dest.write_text(text, encoding="utf-8")
    cn = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')

    return _ok(data={
        "path": str(dest),
        "chinese_chars": cn,
        "novel_slug": s,
    })

@app.get("/api/chapters/{chapter_no}/content")
def get_chapter_content(chapter_no: int, slug: Optional[str] = None):
    slot = _slot_info()
    s = slug or (slot["slug"] if slot else "demo_novel")

    cfg = _load_cfg()
    from config_utils import resolve_path
    novels_root = resolve_path(PROJECT_ROOT, cfg.get("novels_root", "./novels"))
    ch_dir = Path(novels_root) / s / "第01卷"

    candidates = list(ch_dir.glob(f"第{chapter_no}章*.txt"))
    if not candidates:
        raise HTTPException(404, f"未找到第{chapter_no}章的章节文件")

    content = candidates[0].read_text(encoding="utf-8")
    cn = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')

    return _ok(data={
        "chapter_no": chapter_no,
        "filename": candidates[0].name,
        "content": content,
        "word_count": cn,
        "novel_slug": s,
    })

@app.get("/api/help")
def api_help():
    r = _subprocess(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "scc-help"],
        timeout=30
    )
    return _ok(output=r["stdout"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
