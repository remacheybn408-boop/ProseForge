"""
test_post_pipeline.py — CODE_REVIEW #10 (run_post 特征测试)

run_post 此前零直接测试。本文件在拆分前锁定其**现有**端到端行为：
pre → 写章 TXT → run_post，断言落库/报告产物/关键 stdout。

隔离要点：App 默认 project_root=仓库根，而 run_post 把 agent-review 写到
project_root/reports/。这里用 project_root=tmp_path 构造 App，避免污染真实仓库；
其余报告走 app.exports_root（夹具已指向 tmp）。
"""
import json
import os
import sqlite3

import pytest

from src.pipeline._base import App
from src.pipeline.pre import run_pre
from src.pipeline.post import run_post

# 复用既有端到端夹具与造章助手
from tests.test_end_to_end_demo import _make_chapter_text

pytest_plugins = ["tests.test_end_to_end_demo"]


def _app_with_tmp_root(env):
    """同 e2e_env 的 App，但 project_root 指向 tmp，隔离 agent-review 落盘。"""
    return App(
        env["cfg"], env["slug"], env["app"].novel_title, 1,
        str(env["chapters_dir"]), project_root=str(env["tmp"]),
    )


class TestRunPostCharacterization:
    def test_run_post_full_cycle(self, e2e_env, capsys):
        env = e2e_env
        tmp = env["tmp"]
        app = _app_with_tmp_root(env)

        # 1) pre 第1章（同一 app 上下文）
        pre_result = run_pre(1, context=app)
        assert pre_result["chapter_no"] == 1

        # 2) 写章 TXT（字数足够过门禁）
        ch1 = _make_chapter_text(1, "山村的清晨", word_target=9000)
        (env["chapters_dir"] / "第1章_山村的清晨.txt").write_text(ch1, encoding="utf-8")

        # 3) post（不应抛异常；现实现返回 None）
        result = run_post(1, context=app)
        assert result is None

        out = capsys.readouterr().out
        # 关键 stdout 行（锁定现有流程顺序）
        assert "STEP 4: 字数门禁" in out
        assert "orchestrator (" in out
        assert "human_texture:" in out
        assert "post-processing complete" in out

        # 4) ingest 落库
        conn = sqlite3.connect(env["cfg"]["db_path"])
        conn.row_factory = sqlite3.Row
        ch = conn.execute("SELECT * FROM chapters WHERE chapter_no=1").fetchone()
        assert ch is not None and ch["word_count"] > 0
        v = conn.execute("SELECT COUNT(*) AS c FROM chapter_versions WHERE chapter_no=1").fetchone()
        assert v["c"] >= 1
        conn.close()

        # 5) exports 产物
        ex = app.exports_root
        assert (ex / "chapter_briefs" / "chapter_001_brief.json").exists()
        assert (ex / "reports" / "chapter_001_orchestrator_report.json").exists()
        assert (ex / "reports" / "chapter_001_texture_report.json").exists()
        assert (ex / "reports" / "chapter_001_deduplicated_report.json").exists()
        run_report_path = ex / "run_reports" / "chapter_001_run_report.json"
        assert run_report_path.exists()

        run_report = json.loads(run_report_path.read_text(encoding="utf-8"))
        canonical_run = ex / "run_reports" / "chapter_001" / run_report["run_id"] / "run_report.json"
        assert canonical_run.exists()
        expected_paths = {
            "continuity_evidence_report_path": ex / "reports" / "chapter_001_continuity_evidence_report.json",
            "hallucination_report_path": ex / "reports" / "chapter_001_hallucination_report.json",
            "canon_evidence_map_path": ex / "evidence" / "chapter_001_canon_evidence_map.json",
            "scene_delta_report_path": ex / "reports" / "chapter_001_scene_delta_report.json",
            "padding_report_path": ex / "reports" / "chapter_001_padding_report.json",
            "character_voice_report_path": ex / "reports" / "chapter_001_character_voice_report.json",
            "classical_register_report_path": ex / "reports" / "chapter_001_classical_register_report.json",
            "show_dont_tell_report_path": ex / "reports" / "chapter_001_show_dont_tell_report.json",
            "dialogue_beat_report_path": ex / "reports" / "chapter_001_dialogue_beat_report.json",
            "qgp_report_path": ex / "reports" / "chapter_001_perplexity_quality_report.json",
            "editor_revision_report_path": ex / "reports" / "chapter_001_editor_revision_report.json",
            "concrete_anchor_report_path": ex / "reports" / "chapter_001_concrete_anchor_report.json",
            "scene_causality_report_path": ex / "reports" / "chapter_001_scene_causality_report.json",
            "dialogue_structure_report_path": ex / "reports" / "chapter_001_dialogue_structure_report.json",
            "style_variation_report_path": ex / "reports" / "chapter_001_style_variation_report.json",
            "compliance_selfcheck_report_path": ex / "reports" / "chapter_001_compliance_selfcheck_report.json",
            "final_submission_report_path": ex / "reports" / "chapter_001_final_submission_report.json",
        }
        for field, target in expected_paths.items():
            relpath = run_report[field]
            assert not os.path.isabs(relpath)
            assert relpath == os.path.relpath(target, app.project_root)
            assert (app.project_root / relpath).resolve() == target.resolve()

        # 6) agent-review 写到 tmp/reports（验证 project_root 隔离生效）
        agent_review = tmp / "reports" / "agent_reviews" / "chapter_001_agent_review.json"
        assert agent_review.exists()
        # 真实仓库 reports 未被污染由 project_root=tmp 保证

    def test_run_post_short_chapter_raises(self, e2e_env):
        """字数门禁失败 → run_post 抛 RuntimeError（锁定现有失败语义）。"""
        env = e2e_env
        app = _app_with_tmp_root(env)
        run_pre(1, context=app)
        (env["chapters_dir"] / "第1章_山村的清晨.txt").write_text("太短了。", encoding="utf-8")
        with pytest.raises(RuntimeError):
            run_post(1, context=app)
