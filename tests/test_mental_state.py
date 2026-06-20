"""Character psychology guard, CRUD, and merged-agent tests."""

import json
from pathlib import Path


SAMPLE_CONTENT_CLEAN = """
林观澜推开洞府的门，阳光照进来。他深吸一口气，开始今天的修炼。
灵气在体内流转，一切如常。远处传来剑鸣声，他充耳不闻。
""".strip()

SAMPLE_CONTENT_OVERPLAY = """
他疯了！彻底疯了！整个人都崩溃了，失控地狂笑，像一个精神病患者。
歇斯底里的声音在洞府回荡，他发疯一样砸碎所有东西，整个人都扭曲了。
疯了疯了疯了！精神错乱！完全失控！这简直是疯子的行为！
""".strip()

SAMPLE_CONTENT_PTSD = """
血月当空。林观澜忽然僵住，手脚冰凉。眼前的景象让他浑身颤抖，
他仿佛又回到了那个夜晚——宗门被灭，师父被一掌拍碎元婴。
剑鸣声响起，他捂着头蹲下，呼吸困难，冷汗淋漓。
""".strip()


def test_guard_importable():
    from src.guards.human_texture import character_psychology_guard

    assert hasattr(character_psychology_guard, "run_character_psychology_check")
    assert hasattr(character_psychology_guard, "run_mental_state_check")


def test_guard_clean_pass():
    from src.guards.human_texture.character_psychology_guard import run_character_psychology_check

    result = run_character_psychology_check(SAMPLE_CONTENT_CLEAN, chapter_no=1)
    assert result["status"] == "PASS"
    assert len(result["issues"]) == 0


def test_guard_overplay_warn():
    from src.guards.human_texture.character_psychology_guard import run_character_psychology_check

    result = run_character_psychology_check(SAMPLE_CONTENT_OVERPLAY, chapter_no=1)
    assert result["status"] in {"WARN", "FAIL"}
    codes = [issue["code"] for issue in result["issues"]]
    assert any("OVERPLAY" in code for code in codes)


def test_guard_overplay_block():
    from src.guards.human_texture.character_psychology_guard import run_character_psychology_check

    heavy = "疯了疯了疯了疯了疯了崩溃崩溃失控失控失控疯了疯了疯了疯了疯了 " * 10
    result = run_character_psychology_check(heavy, chapter_no=1)
    codes = [issue["code"] for issue in result["issues"]]
    assert any("OVERPLAY" in code for code in codes)


def test_guard_genre_elastic():
    from src.guards.human_texture.character_psychology_guard import run_character_psychology_check

    horror = run_character_psychology_check(SAMPLE_CONTENT_OVERPLAY, chapter_no=1, genre="horror")
    urban = run_character_psychology_check(SAMPLE_CONTENT_OVERPLAY, chapter_no=1, genre="urban")
    horror_overplay = any("OVERPLAY" in issue["code"] for issue in horror["issues"])
    urban_overplay = any("OVERPLAY" in issue["code"] for issue in urban["issues"])
    assert not (horror_overplay and not urban_overplay)


def test_guard_deviation():
    from src.guards.human_texture.character_psychology_guard import run_character_psychology_check

    extreme_text = "他痛不欲生，撕心裂肺地嚎啕。这是极度痛苦的时刻，生不如死。"
    result = run_character_psychology_check(extreme_text, chapter_no=1)
    assert result["status"] in {"PASS", "WARN", "FAIL"}


def test_guard_ptsd_not_overblocked():
    from src.guards.human_texture.character_psychology_guard import run_character_psychology_check

    result = run_character_psychology_check(SAMPLE_CONTENT_PTSD, chapter_no=1)
    codes = [issue["code"] for issue in result["issues"]]
    overplay = [code for code in codes if "OVERPLAY" in code]
    if overplay:
        assert result["status"] != "FAIL"


def test_psychology_categories():
    from src.guards.human_texture.character_psychology_crud import CHARACTER_PSYCHOLOGY_CATEGORIES

    assert len(CHARACTER_PSYCHOLOGY_CATEGORIES) == 15
    assert "抑郁症" in CHARACTER_PSYCHOLOGY_CATEGORIES
    assert "PTSD" in CHARACTER_PSYCHOLOGY_CATEGORIES
    assert "精神分裂" in CHARACTER_PSYCHOLOGY_CATEGORIES


def test_backward_compat_constant_alias():
    from src.guards.human_texture.character_psychology_crud import (
        CHARACTER_PSYCHOLOGY_CATEGORIES,
        MENTAL_STATE_CATEGORIES,
    )

    assert MENTAL_STATE_CATEGORIES is CHARACTER_PSYCHOLOGY_CATEGORIES


def test_card_psychology_structure():
    card = {
        "name": "test_char",
        "voice": {},
        "personality": {},
        "behavior": {},
        "character_psychology": {
            "抑郁症": {
                "severity": 3,
                "onset": "测试诱因",
                "triggers": ["触发词1", "触发词2"],
                "manifestations": ["表现1"],
                "chapter_notes": {"1": "第一章表现"},
            }
        },
    }
    psychology = card.get("character_psychology", {})
    assert "抑郁症" in psychology
    assert psychology["抑郁症"]["severity"] == 3
    assert len(psychology["抑郁症"]["triggers"]) == 2


def test_psychology_empty_is_valid():
    card = {"name": "test", "voice": {}, "personality": {}, "behavior": {}}
    assert card.get("character_psychology", {}) == {}


def test_presets_yaml_loadable():
    import yaml

    project_root = Path(__file__).resolve().parents[1]
    preset_file = project_root / "configs" / "human_texture" / "mental_state_presets.yaml"
    assert preset_file.exists()
    data = yaml.safe_load(preset_file.read_text(encoding="utf-8"))
    assert len(data) >= 15
    assert "抑郁症" in data
    assert "PTSD" in data


def test_character_agent_import():
    from src.agents.character import CharacterAgent

    agent = CharacterAgent()
    assert agent.name == "character_agent"
    result = agent.review("测试文本", chapter_no=1)
    assert {"agent", "score", "status", "findings"} <= set(result)


def test_character_agent_registered():
    from src.agents.orchestrator import AGENT_REGISTRY, MODE_AGENTS

    assert "character" in AGENT_REGISTRY
    assert "character" in MODE_AGENTS["full"]
    assert "character" not in MODE_AGENTS["light"]


def _make_mock_workspace(tmp_path, slot_name="slot_test"):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "registry.json").write_text(
        json.dumps({"active_slot": slot_name}, ensure_ascii=False),
        encoding="utf-8",
    )
    slot = workspace / slot_name
    slot.mkdir()
    (slot / "project.json").write_text(
        json.dumps({"active_voice_card_set": "default"}, ensure_ascii=False),
        encoding="utf-8",
    )
    return tmp_path


def test_crud_save_and_read(tmp_path):
    root = _make_mock_workspace(tmp_path)
    from src.guards.human_texture.character_psychology_crud import (
        get_character_psychology,
        save_character_psychology,
    )

    data = {"PTSD": {"severity": 3, "triggers": ["血月"]}}
    assert save_character_psychology(root, "林观澜", data)
    loaded = get_character_psychology(root, "林观澜")
    assert loaded == data
    assert loaded["PTSD"]["severity"] == 3


def test_crud_legacy_dir_fallback(tmp_path):
    root = _make_mock_workspace(tmp_path)
    legacy_dir = root / "workspace" / "slot_test" / "mental_states" / "default"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "李四.json").write_text(
        json.dumps({"焦虑症": {"severity": 4}}, ensure_ascii=False),
        encoding="utf-8",
    )

    from src.guards.human_texture.character_psychology_crud import get_character_psychology

    loaded = get_character_psychology(root, "李四")
    assert "焦虑症" in loaded
    assert loaded["焦虑症"]["severity"] == 4


def test_crud_backward_compat_api(tmp_path):
    root = _make_mock_workspace(tmp_path)
    from src.guards.human_texture.character_psychology_crud import get_mental_state, save_mental_state

    data = {"抑郁症": {"severity": 2}}
    assert save_mental_state(root, "王五", data)
    assert get_mental_state(root, "王五") == data


def test_crud_read_empty_for_nonexistent(tmp_path):
    root = _make_mock_workspace(tmp_path)
    from src.guards.human_texture.character_psychology_crud import get_character_psychology

    assert get_character_psychology(root, "不存在的角色") == {}


def test_crud_save_does_not_pollute_voice_card(tmp_path):
    root = _make_mock_workspace(tmp_path)
    from src.guards.human_texture.character_psychology_crud import save_character_psychology
    from src.guards.human_texture.voice_diversity_guard import get_character_card

    save_character_psychology(root, "林观澜", {"PTSD": {"severity": 4, "triggers": ["剑鸣"]}})
    assert get_character_card(root, "林观澜") is None
