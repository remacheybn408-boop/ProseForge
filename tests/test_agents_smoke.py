#!/usr/bin/env python3
"""Smoke tests for the merged 6-agent review board."""

from pathlib import Path

import src.agents.character as character_module
import src.guards.human_texture.character_psychology_crud as psychology_crud
from version import get_version

from src.agents.base_agent import BaseAgent
from src.agents.character import CharacterAgent
from src.agents.chief_editor_agent import ChiefEditor
from src.agents.continuity import ContinuityAgent
from src.agents.detail import DetailAgent
from src.agents.orchestrator import run_agent_review
from src.agents.plot import PlotAgent
from src.agents.prose import ProseAgent
from src.agents.reader import ReaderAgent
from src.guards.human_texture.character_psychology_guard import _load_genre_preset


TEST_CONTENT = """
清晨的阳光透过粗布门帘照进通铺房。林夜睁开眼，右肩还带着三天前搬矿留下的肿痛。

食堂里，杂役们已经排起长队。今天的粥比平时稀，但每人多领了一个粗面馒头。管事赵执事站在台上，手里拿着灰纸簿子。

“今日考核搬运。每人五百斤灵矿，从矿洞搬到矿场。完不成者，扣三天饭。”

林夜摸了摸怀里的树皮。那东西昨晚还在发热，像在催他尽快去矿洞里验证什么。可他也知道，一旦露出来，刘黑子绝不会放过。

矿洞深处泛着幽蓝的光。他深吸一口气，咬着牙扛起矿石，肩背立刻绷紧。汗水顺着额角滑下，手心却越来越烫。

那一刻，他终于明白，树皮并不是普通的破木片，而是一条能改命的路。可就在他超额完成任务时，刘黑子已经带着两个杂役堵在通铺门口，冷笑着让他把东西交出来。
""".strip()

AGENT_CONTEXT = {
    "prev_tail": "林夜拖着疲惫的身体回到通铺房。右肩的肿包还在隐隐作痛，怀里的止血丹只剩三颗。",
    "prev_hooks": ["明天考核会更难", "止血丹只剩三颗"],
}

ALL_AGENTS = [
    ContinuityAgent,
    CharacterAgent,
    ProseAgent,
    PlotAgent,
    ReaderAgent,
    DetailAgent,
]


def test_individual_agents_return_standard_shape():
    for agent_cls in ALL_AGENTS:
        agent = agent_cls()
        assert isinstance(agent, BaseAgent)
        result = agent.review(TEST_CONTENT, chapter_no=2, context=AGENT_CONTEXT)
        assert result["agent"] == agent.name
        assert result["status"] in {"PASS", "WARNING", "FAIL"}
        assert isinstance(result["score"], int)
        assert isinstance(result["findings"], list)


def test_chief_editor_aggregates_six_merged_agents():
    agent_results = []
    for agent_cls in ALL_AGENTS:
        agent = agent_cls()
        result = agent.review(TEST_CONTENT, chapter_no=2, context=AGENT_CONTEXT)
        result["chapter"] = 2
        agent_results.append(result)

    chief = ChiefEditor()
    chief_result = chief.review(TEST_CONTENT, chapter_no=2, context={"agent_results": agent_results})

    assert chief_result["agent"] == "chief_editor"
    assert chief_result["status"] in {"PASS", "WARNING", "FAIL"}
    assert chief_result["summary"]["must_fix_count"] >= 0
    assert chief_result["summary"]["should_fix_count"] >= 0
    assert set(chief_result["agent_scores"]) == {agent_cls().name for agent_cls in ALL_AGENTS}


def test_orchestrator_light_mode_runs_three_agents(tmp_path):
    report = run_agent_review(
        TEST_CONTENT,
        chapter_no=2,
        mode="light",
        context=AGENT_CONTEXT,
        config={"output_dir": str(tmp_path)},
    )
    assert [result["agent"] for result in report["agents"]] == [
        "continuity_agent",
        "prose_agent",
        "plot_agent",
    ]
    assert report["summary"]["total_agents"] == 3
    assert report["status"] in {"PASS", "WARNING", "FAIL"}
    assert Path(report["_report_path"]).exists()


def test_orchestrator_full_mode_runs_six_agents(tmp_path):
    report = run_agent_review(
        TEST_CONTENT,
        chapter_no=2,
        mode="full",
        context=AGENT_CONTEXT,
        config={"output_dir": str(tmp_path)},
    )
    assert [result["agent"] for result in report["agents"]] == [
        "continuity_agent",
        "character_agent",
        "prose_agent",
        "plot_agent",
        "reader_agent",
        "detail_agent",
    ]
    assert report["summary"]["total_agents"] == 6
    assert report["status"] in {"PASS", "WARNING", "FAIL"}
    assert report["version"] == get_version()
    assert Path(report["_report_path"]).exists()


def test_character_agent_loads_psychologies_from_repo_root(monkeypatch):
    captured = {}
    sentinel = [{"name": "Lin", "character_psychology": {"PTSD": {"severity": 1}}}]

    def fake_list_character_psychologies(project_root):
        captured["project_root"] = project_root
        return sentinel

    monkeypatch.setattr(
        psychology_crud,
        "list_character_psychologies",
        fake_list_character_psychologies,
    )

    result = CharacterAgent._load_character_psychologies()

    assert result == sentinel
    assert captured["project_root"] == Path(character_module.__file__).resolve().parents[2]


def test_character_psychology_guard_loads_genre_presets():
    preset = _load_genre_preset("xianxia")

    assert preset["overplay_density_warn"] == 5
    assert preset["overplay_density_block"] == 12
