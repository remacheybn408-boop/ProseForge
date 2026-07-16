"""
test_skeleton_flow.py — Phase 2 端到端测试

v0.8.3 (M11): DB / chapters_dir / exports_root 改走 pytest tmp_path / tmp_db
fixture（conftest.py），不再用 tempfile.mkdtemp 散落各处。
"""
import pytest
import sqlite3
import json

from src.pipeline._base import App, DEFAULT_CONFIG
from src.pipeline.pre import run_pre
from src.pipeline.ingest import ingest


@pytest.fixture
def db_and_app(tmp_db, project_root):
    """tmp_db 已经跑过 init_db；在它之上塞 demo skeleton + App。"""
    db_path = tmp_db

    # Import demo skeleton
    skeleton_path = project_root / "examples" / "demo_novel" / "outline_skeleton.json"
    with open(skeleton_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    conn = sqlite3.connect(str(db_path))
    slug = data["novel_outline"]["slug"]
    conn.execute("INSERT INTO novels(slug, title, genre, status) VALUES(?,?,?,?)",
        (slug, data["novel_outline"]["title"], data["novel_outline"]["genre"], "planning"))
    nid = conn.execute("SELECT id FROM novels WHERE slug=?", (slug,)).fetchone()[0]
    ts = "2025-01-01 00:00:00"

    # Insert volume plan
    for vp in data["volume_plans"]:
        conn.execute("""INSERT INTO volume_plans(novel_id, volume_no, planned_title, volume_goal,
            opening_state, ending_target, must_complete, suggested_chapters, updated_at)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (nid, vp["volume_no"], vp["planned_title"], vp["volume_goal"],
             vp.get("opening_state",""), vp.get("ending_target",""),
             vp.get("must_complete",""), vp.get("suggested_chapters",25), ts))

    # Insert chapter plans
    for cp in data["chapter_plans"]:
        conn.execute("""INSERT INTO chapter_plans(novel_id, volume_no, chapter_no,
            planned_title, chapter_goal, conflict_point, ending_hook_direction,
            main_event, character_focus, must_include,
            plot_threads_to_advance, reader_promises_to_advance,
            continuity_from_previous, updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (nid, cp["volume_no"], cp["chapter_no"],
             cp.get("planned_title",""), cp.get("chapter_goal",""),
             cp.get("conflict_point",""), cp.get("ending_hook_direction",""),
             cp.get("main_event",""), cp.get("character_focus",""),
             cp.get("must_include",""),
             cp.get("plot_threads_to_advance",""),
             cp.get("reader_promises_to_advance",""),
             cp.get("continuity_from_previous",""), ts))

    conn.commit()
    conn.close()

    cfg = DEFAULT_CONFIG.copy()
    cfg["db_path"] = str(db_path)
    app = App(cfg, slug, data["novel_outline"]["title"], 1)

    return db_path, app


def _run_pre(app, chapter_no, chapter_type="normal"):
    """Helper: call run_pre with parameters derived from a pre-built App."""
    return run_pre(
        chapter_no,
        chapter_type=chapter_type,
        novel_slug=app.novel_slug,
        novel_title=app.novel_title,
        volume_no=app.volume_no,
        db_path=str(app.db_path),
        chapters_dir=str(app.chapters_dir) if app.chapters_dir else None,
    )


class TestSkeletonPre:
    def test_pre_reads_volume_plan(self, db_and_app):
        """pre should display volume plan info."""
        db_path, app = db_and_app
        result = _run_pre(app, 1, "normal")
        assert result is not None
        assert result["chapter_no"] == 1

    def test_pre_reads_chapter_plan(self, db_and_app):
        """pre should read chapter skeleton."""
        db_path, app = db_and_app
        result = _run_pre(app, 5, "normal")
        assert result is not None

    def test_pre_chapter_no_skeleton(self, db_and_app):
        """Chapter 30 has no skeleton - should not crash."""
        db_path, app = db_and_app
        result = _run_pre(app, 30, "normal")
        assert result is not None


class TestVolumeSequenceCheck:
    def test_volume_2_warns_when_volume_1_empty(self, db_and_app):
        """Pre on volume 2 should warn if volume 1 has no chapters."""
        db_path, app = db_and_app
        vol2_app = App(DEFAULT_CONFIG.copy() | {"db_path": str(db_path)},
                       app.novel_slug, app.novel_title, 2)
        result = run_pre(
            1, novel_slug=vol2_app.novel_slug, novel_title=vol2_app.novel_title,
            volume_no=2, db_path=str(db_path),
        )
        assert result is not None


class TestChapterPlansSync:
    def test_ingest_updates_chapter_plans_status(self, db_and_app, tmp_path):
        """After ingest, chapter_plans title_status should be 'written'."""
        db_path, app = db_and_app

        # Create a chapters dir with a dummy TXT
        chapters_dir = tmp_path / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)
        app.chapters_dir = chapters_dir
        app.exports_root = tmp_path / "exports"
        app.exports_root.mkdir(parents=True, exist_ok=True)
        app.state_dir = app.exports_root / "pipeline_state"
        app.state_dir.mkdir(parents=True, exist_ok=True)

        # Write dummy chapter file
        chapter_file = chapters_dir / "第1章_test_title.txt"
        chapter_file.write_text("测试内容" * 1000, encoding='utf-8')

        # Create pre state (so post can run)
        state = {"chapter_no": 1, "chapter_type": "normal", "pre_done": True,
                 "allowed_to_write": True, "timestamp": "2025-01-01"}
        (app.state_dir / "chapter_001_state.json").write_text(json.dumps(state), encoding='utf-8')

        # Check status before
        conn = sqlite3.connect(str(db_path))
        before = conn.execute("SELECT title_status FROM chapter_plans WHERE chapter_no=1").fetchone()
        conn.close()
        assert before[0] == "planned"

        # Run ingest via app_inst
        result = ingest(1, "normal", app_inst=app)
        assert result is not None

        # Check status after
        conn = sqlite3.connect(str(db_path))
        after = conn.execute("SELECT title_status, final_title FROM chapter_plans WHERE chapter_no=1").fetchone()
        conn.close()
        assert after[0] == "written"
        assert after[1] == "test_title"
