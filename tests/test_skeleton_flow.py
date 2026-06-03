"""
test_skeleton_flow.py — Phase 2 端到端测试
"""
import pytest, sqlite3, tempfile, os, sys, json
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from chapter_pipeline import App, DEFAULT_CONFIG
import init_db


@pytest.fixture
def db_and_app():
    """Create temp DB with schema + demo skeleton, return (db_path, app)."""
    tmp = tempfile.mkdtemp()
    db_path = Path(tmp) / "test.db"
    schema_path = Path(__file__).parent.parent / "database" / "schema.sql"

    init_db.init_db(str(db_path), str(schema_path), [])

    # Import demo skeleton
    skeleton_path = Path(__file__).parent.parent / "examples" / "demo_novel" / "outline_skeleton.json"
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


class TestSkeletonPre:
    def test_pre_reads_volume_plan(self, db_and_app):
        """pre should display volume plan info."""
        db_path, app = db_and_app
        import chapter_pipeline as cp
        cp.app = app
        # This will print to stdout - we just verify no exception
        result = cp.pre_write_gate(1, "normal")
        assert result is not None
        assert result["chapter_no"] == 1

    def test_pre_reads_chapter_plan(self, db_and_app):
        """pre should read chapter skeleton."""
        db_path, app = db_and_app
        import chapter_pipeline as cp
        cp.app = app
        result = cp.pre_write_gate(5, "normal")
        assert result is not None

    def test_pre_chapter_no_skeleton(self, db_and_app):
        """Chapter 30 has no skeleton - should not crash."""
        db_path, app = db_and_app
        import chapter_pipeline as cp
        cp.app = app
        result = cp.pre_write_gate(30, "normal")
        assert result is not None


class TestVolumeSequenceCheck:
    def test_volume_2_warns_when_volume_1_empty(self, db_and_app):
        """Pre on volume 2 should warn if volume 1 has no chapters."""
        db_path, app = db_and_app
        app.volume_no = 2
        import chapter_pipeline as cp
        cp.app = app
        # Should not crash, just warn
        result = cp.pre_write_gate(1, "normal")
        assert result is not None


class TestChapterPlansSync:
    def test_ingest_updates_chapter_plans_status(self, db_and_app):
        """After ingest, chapter_plans title_status should be 'written'."""
        db_path, app = db_and_app

        # Create a chapters dir with a dummy TXT
        chapters_dir = Path(tempfile.mkdtemp())
        app.chapters_dir = chapters_dir
        app.exports_root = Path(tempfile.mkdtemp())
        app.state_dir = app.exports_root / "pipeline_state"
        app.state_dir.mkdir(parents=True, exist_ok=True)

        # Write dummy chapter file
        chapter_file = chapters_dir / "第1章_test_title.txt"
        chapter_file.write_text("测试内容" * 1000, encoding='utf-8')

        # Create pre state (so post can run)
        state = {"chapter_no": 1, "chapter_type": "normal", "pre_done": True,
                 "allowed_to_write": True, "timestamp": "2025-01-01"}
        import json
        (app.state_dir / "chapter_001_state.json").write_text(json.dumps(state), encoding='utf-8')

        # Check status before
        conn = sqlite3.connect(str(db_path))
        before = conn.execute("SELECT title_status FROM chapter_plans WHERE chapter_no=1").fetchone()
        conn.close()
        assert before[0] == "planned"

        # Run ingest
        import chapter_pipeline as cp
        cp.app = app
        result = cp.ingest(1, "normal")
        assert result is not None

        # Check status after
        conn = sqlite3.connect(str(db_path))
        after = conn.execute("SELECT title_status, final_title FROM chapter_plans WHERE chapter_no=1").fetchone()
        conn.close()
        assert after[0] == "written"
        assert after[1] == "test_title"
