"""test_rewrite_pipeline.py — rewrite/accept 改写闭环测试

覆盖 src/pipeline/rewrite.py：
- run_rewrite: 读去重报告 → 产改写卡 + revision_tasks.json（不调 LLM）
- run_accept: 原稿 vs revised → diff/log；ingest=True 时追加版本快照，不覆盖原稿
"""
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.db import init_db
from src.pipeline._base import App
from src.pipeline.ingest import ingest
from src.pipeline.rewrite import run_rewrite, run_accept, _verify_with_guard_rerun


_COST_WARNING = {"source_guard": "scene_causality_guard", "type": "MISSING_COST",
                 "confidence": 0.8, "message": "缺代价"}
_DIALOGUE_WARNING = {"source_guard": "character_voice_guard", "type": "DIALOGUE",
                     "confidence": 0.8, "message": "对白雷同"}


def _patch_orchestrator(monkeypatch, warnings=None, raise_exc=False):
    def fake(*a, **k):
        if raise_exc:
            raise RuntimeError("boom")
        return {"warnings": warnings or [], "executed_guards": [], "warning_count": 0}
    monkeypatch.setattr("src.pipeline.guard_orchestrator.run_orchestrated", fake)


_CHAPTER_TEXT = (
    "清晨的阳光穿过窗棂，他站在门口想了很久。\n\n"
    '"你想好了吗？"她在身后问，声音里有犹豫。\n\n'
    "他没有回答，只是握紧了手里那枚旧铜钥匙。代价已经摆在面前。\n\n"
    "傍晚，他推开屋门，屋里空无一人，只剩桌上一封信。\n\n"
    "他握紧拳头，知道明天会有更难的对白等着他。\n"
)


@pytest.fixture
def rw_env(tmp_path, project_root, monkeypatch):
    monkeypatch.chdir(tmp_path)

    cfg = {
        "db_path": str(tmp_path / "data" / "test.db"),
        "novels_root": str(tmp_path / "novels"),
        "exports_root": str(tmp_path / "exports"),
        "outputs_root": str(tmp_path / "outputs"),
        "word_count": {"normal": {"min": 100, "best_min": 100, "best_max": 5000, "max": 9000}},
        "scene_quality": {"min_effective_scenes": 1},
    }
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    schema = project_root / "database" / "schema.sql"
    init_db.init_db(cfg["db_path"], str(schema), [])

    slug = "demo_novel"
    conn = sqlite3.connect(cfg["db_path"])
    conn.execute("INSERT INTO novels(slug, title, genre, status) VALUES(?,?,?,?)",
                 (slug, "Demo", "fantasy", "writing"))
    nid = conn.execute("SELECT id FROM novels WHERE slug=?", (slug,)).fetchone()[0]
    conn.execute(
        """INSERT INTO chapter_plans(novel_id, volume_no, chapter_no, planned_title,
           chapter_goal, conflict_point, ending_hook_direction, updated_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (nid, 1, 1, "开端", "抉择", "去留", "悬念", "2025-01-01 00:00:00"),
    )
    conn.commit()
    conn.close()

    chapters_dir = tmp_path / "novels" / slug / "第01卷"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    chapter_file = chapters_dir / "第1章_开端.txt"
    chapter_file.write_text(_CHAPTER_TEXT, encoding="utf-8")

    # post 产出的去重报告（rewrite 的输入）
    reports_dir = tmp_path / "exports" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    dedup = {
        "version": "test",
        "merged_issues": [],
        "top_revision_tasks": [
            {"issue": "对白口吻偏平，缺少角色个性",
             "fix": "给对白加上角色独有的称呼和停顿",
             "confidence": 0.88},
            {"issue": "代价交代不足，因果偏弱",
             "fix": "把抉择的损失写成具体动作",
             "confidence": 0.80},
        ],
    }
    (reports_dir / "chapter_001_deduplicated_report.json").write_text(
        json.dumps(dedup, ensure_ascii=False), encoding="utf-8")

    app = App(cfg, slug, "Demo", 1, str(chapters_dir),
              project_root=str(tmp_path), config_path=str(tmp_path / "config.json"))
    return {"app": app, "chapters_dir": chapters_dir, "chapter_file": chapter_file,
            "reports_dir": reports_dir, "db": cfg["db_path"], "slug": slug}


def test_run_rewrite_produces_card_and_tasks(rw_env):
    app = rw_env["app"]
    result = run_rewrite(1, novel_slug=app.novel_slug, novel_title=app.novel_title,
                         volume_no=1, context=app)

    assert result["status"] == "ok"
    assert result["task_count"] > 0

    card_path = rw_env["app"].outputs_root / "rewrite_cards" / "chapter_001_rewrite_card.md"
    assert card_path.exists()
    card = card_path.read_text(encoding="utf-8")
    assert "必须保留" in card                      # must_keep 注入
    assert "禁止" in card                          # avoid 注入
    assert "称呼" in card or "代价" in card          # 含任务指令/问题文案（章节尺度，不再引原文段落）

    tasks_path = rw_env["reports_dir"] / "chapter_001_revision_tasks.json"
    assert tasks_path.exists()
    bundle = json.loads(tasks_path.read_text(encoding="utf-8"))
    assert bundle["task_count"] == result["task_count"]


def test_run_rewrite_emits_semantic_request(rw_env):
    app = rw_env["app"]
    result = run_rewrite(1, novel_slug=app.novel_slug, novel_title="Demo", volume_no=1, context=app)
    assert result["semantic_request_path"]
    req = json.loads(Path(result["semantic_request_path"]).read_text(encoding="utf-8"))
    assert "contract" in req and "verdict_template" in req
    card = Path(result["semantic_card_path"])
    assert card.exists() and "语义保全清单" in card.read_text(encoding="utf-8")


def test_run_rewrite_requires_dedup_report(rw_env):
    (rw_env["reports_dir"] / "chapter_001_deduplicated_report.json").unlink()
    result = run_rewrite(1, novel_slug=rw_env["slug"], novel_title="Demo",
                         volume_no=1, context=rw_env["app"])
    assert result["status"] == "error"
    assert "去重报告" in result["message"]


def test_run_accept_diff_only(rw_env):
    app = rw_env["app"]
    run_rewrite(1, novel_slug=app.novel_slug, novel_title="Demo", volume_no=1, context=app)

    # 模拟 Agent 改写：仅改第 2 段对白
    revised = _CHAPTER_TEXT.replace(
        '"你想好了吗？"她在身后问，声音里有犹豫。',
        '"阿临，你到底想好了没有？"她在身后追问，话没说完又停住。')
    revised_path = rw_env["chapter_file"].parent / "chapter_001_revised.txt"
    revised_path.write_text(revised, encoding="utf-8")

    result = run_accept(1, novel_slug=app.novel_slug, novel_title="Demo",
                        volume_no=1, ingest=False, context=app)

    assert result["status"] == "ok"
    assert result["ingested"] is False
    assert result["recommendation"] in (
        "REVIEW_BEFORE_ACCEPT", "REVIEW_CAREFULLY", "REVISION_REJECTED")
    diff_path = rw_env["reports_dir"] / "chapter_001_revision_diff_report.json"
    log_path = rw_env["reports_dir"] / "chapter_001_rewrite_log.json"
    assert diff_path.exists() and log_path.exists()
    # 原稿未被改写（diff-only 不入库、不提升）
    assert rw_env["chapter_file"].read_text(encoding="utf-8") == _CHAPTER_TEXT


def test_run_accept_records_out_of_range_change(rw_env):
    app = rw_env["app"]
    run_rewrite(1, novel_slug=app.novel_slug, novel_title="Demo", volume_no=1, context=app)

    # 改最后一段（任务区间外也好、章节尺度也好，全文 diff 都该记到）
    revised = _CHAPTER_TEXT.replace(
        "他握紧拳头，知道明天会有更难的对白等着他。",
        "他攥着那枚铜钥匙，把信塞进怀里，转身走进雨里。")
    (rw_env["chapter_file"].parent / "chapter_001_revised.txt").write_text(revised, encoding="utf-8")

    run_accept(1, novel_slug=app.novel_slug, novel_title="Demo", volume_no=1,
               ingest=False, context=app)

    log = json.loads((rw_env["reports_dir"] / "chapter_001_rewrite_log.json").read_text(encoding="utf-8"))
    assert log["changed_ranges"]                       # 全文扫描捕获到改动
    assert any(r["change_type"] in ("replace", "insert", "delete")
               for r in log["changed_ranges"])


def test_run_accept_no_op_blocks_ingest(rw_env):
    app = rw_env["app"]
    run_rewrite(1, novel_slug=app.novel_slug, novel_title="Demo", volume_no=1, context=app)

    # 用户直接复制了原文（空改）
    (rw_env["chapter_file"].parent / "chapter_001_revised.txt").write_text(
        _CHAPTER_TEXT, encoding="utf-8")

    result = run_accept(1, novel_slug=app.novel_slug, novel_title="Demo", volume_no=1,
                        ingest=True, context=app)

    assert result["recommendation"] == "NO_CHANGE_DETECTED"
    assert result["ingested"] is False
    assert "ingest_skipped_reason" in result


def test_run_accept_missing_revised(rw_env):
    result = run_accept(1, novel_slug=rw_env["slug"], novel_title="Demo",
                        volume_no=1, ingest=False, context=rw_env["app"])
    assert result["status"] == "error"
    assert "改稿" in result["message"]


def test_run_accept_ingest_appends_snapshot_without_overwrite(rw_env):
    app = rw_env["app"]
    db = rw_env["db"]

    # 先入库原稿，建立 v1 快照
    assert ingest(1, "normal", app_inst=app) is not None
    conn = sqlite3.connect(db)
    v1 = conn.execute(
        "SELECT version_no, content FROM chapter_versions WHERE chapter_no=1 ORDER BY version_no").fetchall()
    conn.close()
    assert len(v1) == 1
    v1_content = v1[0][1]

    # Agent 改写
    run_rewrite(1, novel_slug=app.novel_slug, novel_title="Demo", volume_no=1, context=app)
    revised = _CHAPTER_TEXT.replace("他握紧拳头，知道明天会有更难的对白等着他。",
                                    "他攥着钥匙，指节发白，把那封信塞进了怀里。")
    (rw_env["chapter_file"].parent / "chapter_001_revised.txt").write_text(revised, encoding="utf-8")

    result = run_accept(1, novel_slug=app.novel_slug, novel_title="Demo",
                        volume_no=1, ingest=True, context=app)

    if result["recommendation"] == "REVISION_REJECTED":
        assert result["ingested"] is False
        return

    assert result["ingested"] is True
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT version_no, content FROM chapter_versions WHERE chapter_no=1 ORDER BY version_no").fetchall()
    conn.close()
    assert len(rows) == 2                       # 追加快照，不覆盖
    assert rows[0][1] == v1_content             # 原稿快照仍在
    assert "怀里" in rows[1][1]                  # 新快照是改稿
    # 原始章节文件不可变；当前版本由数据库版本记录承载
    assert rw_env["chapter_file"].read_text(encoding="utf-8") == _CHAPTER_TEXT


def test_verify_resolved_when_revised_clean(tmp_path, monkeypatch):
    _patch_orchestrator(monkeypatch, warnings=[])      # revised 无问题
    app = SimpleNamespace(cfg={})
    tasks = [{"task_id": "rev_001", "category": "MISSING_COST"}]
    v = _verify_with_guard_rerun(app, "改后正文", 1, tasks, tmp_path)
    assert v["available"] is True
    assert v["resolved"] == ["MISSING_COST"]
    assert v["persisted"] == [] and v["regressed"] == []


def test_verify_persisted_when_issue_remains(tmp_path, monkeypatch):
    _patch_orchestrator(monkeypatch, warnings=[_COST_WARNING])
    app = SimpleNamespace(cfg={})
    tasks = [{"task_id": "rev_001", "category": "MISSING_COST"}]
    v = _verify_with_guard_rerun(app, "改后正文", 1, tasks, tmp_path)
    assert v["persisted"] == ["MISSING_COST"]
    assert v["resolved"] == []


def test_verify_regressed_when_new_category_appears(tmp_path, monkeypatch):
    _patch_orchestrator(monkeypatch, warnings=[_DIALOGUE_WARNING])
    app = SimpleNamespace(cfg={})
    tasks = [{"task_id": "rev_001", "category": "MISSING_COST"}]
    v = _verify_with_guard_rerun(app, "改后正文", 1, tasks, tmp_path)
    assert "DIALOGUE_SAMENESS" in v["regressed"]


def test_verify_fail_open_on_exception(tmp_path, monkeypatch):
    _patch_orchestrator(monkeypatch, raise_exc=True)
    app = SimpleNamespace(cfg={})
    v = _verify_with_guard_rerun(app, "改后正文", 1, [], tmp_path)
    assert v["available"] is False
    assert "reason" in v


def test_run_accept_attaches_verification(rw_env, monkeypatch):
    _patch_orchestrator(monkeypatch, warnings=[])
    app = rw_env["app"]
    run_rewrite(1, novel_slug=app.novel_slug, novel_title="Demo", volume_no=1, context=app)
    revised = _CHAPTER_TEXT.replace("傍晚，他推开屋门", "黄昏时分，他缓缓推开屋门")
    (rw_env["chapter_file"].parent / "chapter_001_revised.txt").write_text(revised, encoding="utf-8")

    result = run_accept(1, novel_slug=app.novel_slug, novel_title="Demo",
                        volume_no=1, ingest=False, context=app)
    assert result["verification"]["available"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
