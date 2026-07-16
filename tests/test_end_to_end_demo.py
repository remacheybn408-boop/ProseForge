"""
test_end_to_end_demo.py — v0.3.0 端到端流程测试

v0.8.3 (M11): tempfile.mkdtemp + 裸 os.chdir → tmp_path + monkeypatch.chdir。
DB 路径直接拼在 tmp_path 下，让 pytest 自动清理。
"""
import pytest
import sqlite3
import json

from src.db import init_db
from src.pipeline._base import App
from src.pipeline.pre import run_pre
from src.pipeline.ingest import ingest
from src.pipeline import ingest as ingest_module
from src.pipeline.volume import volume_post


def _make_chapter_text(chapter_no, title, word_target=3700):
    """生成模拟章节文本（含多场景/对话/动作）"""
    scenes = [
        f"清晨的阳光穿过窗棂。这是第{chapter_no}章的开始。\n" + "他站了很久，久到脚底传来一阵麻意。\n" * 3,
        f'"第{chapter_no}章的事情，你想好了吗？"她问。\n' * 3 + "他摇了摇头。\n",
        "傍晚时分，他回到了住处。\n" + "推开门，屋里空无一人。\n" * 2,
        '"你终于来了。"黑暗中有人说话。\n' * 2 + "他握紧了拳头。\n" * 3,
    ]
    text = ("\n\n".join(scenes) + "\n") * (word_target // 260)
    return f"{text}\n本章自检:字数约{len(text)}字"


@pytest.fixture
def e2e_env(tmp_path, project_root, monkeypatch):
    """Set up temp env with DB + skeleton + chapter files."""
    monkeypatch.chdir(tmp_path)

    # Config
    cfg = {
        "db_path": str(tmp_path / "data" / "test.db"),
        "novels_root": str(tmp_path / "novels"),
        "exports_root": str(tmp_path / "exports"),
        "word_count": {"hard_min": 3300, "ideal_min": 3500, "ideal_max": 3900, "normal_max": 4200, "special_max": 5000},
        "scene_quality": {"min_effective_scenes": 4},
    }
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # Init DB
    schema = project_root / "database" / "schema.sql"
    init_db.init_db(cfg["db_path"], str(schema), [])

    # Import skeleton
    skeleton_path = project_root / "examples" / "demo_novel" / "outline_skeleton.json"
    data = json.loads(skeleton_path.read_text(encoding="utf-8"))

    conn = sqlite3.connect(cfg["db_path"])
    conn.row_factory = sqlite3.Row
    slug = data["novel_outline"]["slug"]
    conn.execute("INSERT INTO novels(slug, title, genre, status) VALUES(?,?,?,?)",
        (slug, data["novel_outline"]["title"], data["novel_outline"]["genre"], "writing"))
    nid = conn.execute("SELECT id FROM novels WHERE slug=?", (slug,)).fetchone()[0]
    ts = "2025-01-01 00:00:00"

    for vp in data["volume_plans"]:
        conn.execute("""INSERT INTO volume_plans(novel_id, volume_no, planned_title, volume_goal,
            opening_state, ending_target, must_complete, suggested_chapters, updated_at)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (nid, vp["volume_no"], vp["planned_title"], vp["volume_goal"],
             vp.get("opening_state",""), vp.get("ending_target",""),
             vp.get("must_complete",""), vp.get("suggested_chapters",25), ts))

    for cp in data["chapter_plans"][:3]:  # Only first 3 for speed
        conn.execute("""INSERT INTO chapter_plans(novel_id, volume_no, chapter_no,
            planned_title, chapter_goal, conflict_point, ending_hook_direction, updated_at)
            VALUES(?,?,?,?,?,?,?,?)""",
            (nid, cp["volume_no"], cp["chapter_no"],
             cp.get("planned_title",""), cp.get("chapter_goal",""),
             cp.get("conflict_point",""), cp.get("ending_hook_direction",""), ts))
    conn.commit()
    conn.close()

    # Chapter TXT files dir
    chapters_dir = tmp_path / "novels" / slug / "第01卷"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    app = App(cfg, slug, data["novel_outline"]["title"], 1, str(chapters_dir))

    return {"tmp": tmp_path, "cfg": cfg, "app": app, "chapters_dir": chapters_dir, "slug": slug}


class TestEndToEndFlow:
    def test_ingest_marks_partial_failure_when_enrichment_crashes(self, e2e_env, monkeypatch):
        app = e2e_env["app"]
        chapter_file = e2e_env["chapters_dir"] / "第1章_测试.txt"
        chapter_file.write_text("有效正文。\n" * 20, encoding="utf-8")

        def fail_brief(*args, **kwargs):
            raise RuntimeError("brief generator unavailable")

        monkeypatch.setattr(ingest_module, "generate_chapter_brief", fail_brief)

        with pytest.raises(RuntimeError, match="brief generator unavailable"):
            ingest_module.ingest(1, "normal", app_inst=app)

        state_path = app.state_dir / "chapter_001_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["status"] == "PARTIAL_FAILURE"
        assert "brief generator unavailable" in state["error"]
        conn = sqlite3.connect(app.db_path)
        assert conn.execute("SELECT COUNT(*) FROM chapters WHERE chapter_no=1").fetchone()[0] == 0
        conn.close()

    def test_full_ch1_cycle(self, e2e_env):
        """Complete ch1: pre → write TXT → post → verify brief + DB state"""
        env = e2e_env
        app = env["app"]

        # Step 1: pre ch1
        result = run_pre(
            1, novel_slug=app.novel_slug, novel_title=app.novel_title,
            volume_no=app.volume_no, db_path=str(app.db_path),
            chapters_dir=str(app.chapters_dir),
        )
        assert result is not None
        assert result["chapter_no"] == 1

        # Step 2: write chapter TXT
        ch1_text = _make_chapter_text(1, "山村的清晨")
        ch1_file = env["chapters_dir"] / "第1章_山村的清晨.txt"
        ch1_file.write_text(ch1_text, encoding='utf-8')

        # Step 3: ingest ch1
        post_result = ingest(1, "normal", app_inst=app)
        assert post_result is not None
        assert post_result["word_count"] > 0

        # Verify DB
        conn = sqlite3.connect(env["cfg"]["db_path"])
        conn.row_factory = sqlite3.Row

        cp_row = conn.execute("SELECT title_status, plan_status, actual_word_count FROM chapter_plans WHERE chapter_no=1").fetchone()
        assert cp_row["title_status"] == "written"
        assert cp_row["plan_status"] == "ingested"
        assert cp_row["actual_word_count"] > 0

        ch = conn.execute("SELECT * FROM chapters WHERE chapter_no=1").fetchone()
        assert ch is not None
        assert ch["word_count"] > 0

        v = conn.execute("SELECT COUNT(*) as cnt FROM chapter_versions WHERE chapter_no=1").fetchone()
        assert v["cnt"] >= 1

        conn.close()

        # Verify chapter_brief file
        brief_path = app.exports_root / "chapter_briefs" / "chapter_001_brief.json"
        assert brief_path.exists()
        brief = json.loads(brief_path.read_text(encoding='utf-8'))
        assert "ending_state" in brief
        assert "next_chapter_hooks" in brief
        assert brief["actual_word_count"] > 0

    def test_volume_post_generates_report(self, e2e_env):
        """Volume post should create volume_report.json"""
        env = e2e_env
        app = env["app"]

        # Need at least one chapter in DB for volume_post
        ch1_text = _make_chapter_text(1, "山村的清晨")
        (env["chapters_dir"] / "第1章_山村的清晨.txt").write_text(ch1_text, encoding='utf-8')
        ingest(1, "normal", app_inst=app)

        # Run volume_post
        volume_post(
            novel_slug=app.novel_slug,
            novel_title=app.novel_title,
            volume_no=app.volume_no,
            db_path=str(app.db_path),
            chapters_dir=str(app.chapters_dir),
        )

        # Verify report
        report_path = app.exports_root / "volume_reports" / "volume_01_report.json"
        assert report_path.exists()
        report = json.loads(report_path.read_text(encoding='utf-8'))
        assert report["total_chapters"] >= 1
        assert "unresolved_hooks_to_next" in report
