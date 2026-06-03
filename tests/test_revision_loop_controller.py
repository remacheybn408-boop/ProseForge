#!/usr/bin/env python3
"""Test revision_loop_controller — 自动改稿闭环控制器测试"""
import sys, json, tempfile, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from revision_loop_controller import (
    run_suggest_mode, run_controlled_mode, DEFAULT_CONFIG
)


def _make_temp_dir():
    d = tempfile.mkdtemp()
    return d


def _make_chapter(path, content="段落一。\n\n段落二。\n\n段落三。\n\n段落四。"):
    Path(path).write_text(content, encoding="utf-8")


def _make_report(path):
    report = {
        "top_revision_tasks": [
            {"issue": "场景缺少代价", "confidence": 0.85,
             "fix": "补代价", "revision_task": "添加可见损失"},
        ],
        "chapter_no": 1,
    }
    Path(path).write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")


def test_suggest_mode():
    d = _make_temp_dir()
    cp = os.path.join(d, "ch.txt")
    rp = os.path.join(d, "report.json")
    _make_chapter(cp)
    _make_report(rp)
    result = run_suggest_mode(cp, rp, os.path.join(d, "out"), DEFAULT_CONFIG)
    assert result["status"] == "OK"
    assert result["task_count"] >= 1
    assert Path(result["tasks"]).exists()


def test_suggest_mode_no_tasks():
    d = _make_temp_dir()
    cp = os.path.join(d, "ch.txt")
    rp = os.path.join(d, "report.json")
    _make_chapter(cp)
    Path(rp).write_text(json.dumps({"top_revision_tasks": []}), encoding="utf-8")
    result = run_suggest_mode(cp, rp, os.path.join(d, "out"), DEFAULT_CONFIG)
    assert result["task_count"] == 0


def test_controlled_mode():
    d = _make_temp_dir()
    cp = os.path.join(d, "ch.txt")
    rp = os.path.join(d, "report.json")
    _make_chapter(cp, "开头段落。\n\n中间段落需要改。\n\n中间段落二。\n\n结尾钩子。")
    _make_report(rp)
    result = run_controlled_mode(cp, rp, os.path.join(d, "out"), DEFAULT_CONFIG)
    assert result["status"] == "OK"
    assert "revision_tasks" in result["outputs"]
    assert "revised_draft" in result["outputs"]
    assert "diff_report" in result["outputs"]
    assert result["auto_overwrite_source"] is False
    assert result["auto_ingest_revised"] is False


def test_controlled_outputs_exist():
    d = _make_temp_dir()
    cp = os.path.join(d, "ch.txt")
    rp = os.path.join(d, "report.json")
    _make_chapter(cp, "段一。\n\n段二。\n\n段三。\n\n段四。")
    _make_report(rp)
    result = run_controlled_mode(cp, rp, os.path.join(d, "out"), DEFAULT_CONFIG)
    for key, path in result.get("outputs", {}).items():
        assert Path(path).exists(), f"Missing: {key} at {path}"


def test_max_rounds_default():
    assert DEFAULT_CONFIG["max_rounds"] == 2


def test_aggressive_disabled_by_default():
    assert DEFAULT_CONFIG["allow_aggressive_mode"] is False


if __name__ == "__main__":
    import pytest; pytest.main([__file__, "-v"])
