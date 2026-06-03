"""
test_end_to_end_demo.py — v0.3.0 端到端流程测试
"""
import pytest, sqlite3, tempfile, os, sys, json, shutil
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import init_db
from chapter_pipeline import App, DEFAULT_CONFIG


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
def e2e_env():
    """Set up temp env with DB + skeleton + chapter files."""
    tmp = tempfile.mkdtemp()
    os.chdir(tmp)

    # Config
    cfg = {
        "db_path": str(Path(tmp) / "data" / "test.db"),
        "novels_root": str(Path(tmp) / "novels"),
        "exports_root": str(Path(tmp) / "exports"),
        "word_count": {"hard_min": 3300, "ideal_min": 3500, "ideal_max": 3900, "normal_max": 4200, "special_max": 5000},
        "scene_quality": {"min_effective_scenes": 4},
    }
    Path(tmp, "data").mkdir(parents=True, exist_ok=True)
    with open(Path(tmp, "config.json"), 'w', encoding='utf-8') as f:
        json.dump(cfg, f)

    # Init DB
    schema = Path(__file__).parent.parent / "database" / "schema.sql"
    init_db.init_db(cfg["db_path"], str(schema), [])

    # Import skeleton
    skeleton_path = Path(__file__).parent.parent / "examples" / "demo_novel" / "outline_skeleton.json"
    with open(skeleton_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

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
    chapters_dir = Path(tmp) / "novels" / slug / "第01卷"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    app = App(cfg, slug, data["novel_outline"]["title"], 1, str(chapters_dir))

    return {"tmp": tmp, "cfg": cfg, "app": app, "chapters_dir": chapters_dir, "slug": slug}


class TestEndToEndFlow:
    def test_full_ch1_cycle(self, e2e_env):
        """Complete ch1: pre → write TXT → post → verify brief + DB state"""
        import chapter_pipeline as cp
        env = e2e_env
        app = env["app"]
        cp.app = app

        # Step 1: pre ch1
        result = cp.pre_write_gate(1, "normal")
        assert result is not None
        assert result["chapter_no"] == 1

        # Step 2: write chapter TXT
        ch1_text = _make_chapter_text(1, "山村的清晨")
        ch1_file = env["chapters_dir"] / "第1章_山村的清晨.txt"
        ch1_file.write_text(ch1_text, encoding='utf-8')

        # Step 3: post ch1
        cp.app = app
        post_result = cp.ingest(1, "normal")
        assert post_result is not None
        assert post_result["word_count"] > 0

        # Verify DB
        conn = sqlite3.connect(env["cfg"]["db_path"])
        conn.row_factory = sqlite3.Row

        # chapter_plans status
        cp_row = conn.execute("SELECT title_status, plan_status, actual_word_count FROM chapter_plans WHERE chapter_no=1").fetchone()
        assert cp_row["title_status"] == "written"
        assert cp_row["plan_status"] == "ingested"
        assert cp_row["actual_word_count"] > 0

        # chapters entry
        ch = conn.execute("SELECT * FROM chapters WHERE chapter_no=1").fetchone()
        assert ch is not None
        assert ch["word_count"] > 0

        # chapter_versions
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
        import chapter_pipeline as cp
        env = e2e_env
        app = env["app"]
        cp.app = app

        # Need at least one chapter in DB for volume_post
        ch1_text = _make_chapter_text(1, "山村的清晨")
        (env["chapters_dir"] / "第1章_山村的清晨.txt").write_text(ch1_text, encoding='utf-8')
        cp.app = app
        cp.ingest(1, "normal")

        # Run volume_post
        cp.app = app
        cp.volume_post()

        # Verify report
        report_path = app.exports_root / "volume_reports" / "volume_01_report.json"
        assert report_path.exists()
        report = json.loads(report_path.read_text(encoding='utf-8'))
        assert report["total_chapters"] >= 1
        assert "unresolved_hooks_to_next" in report
