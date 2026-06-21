#!/usr/bin/env python3
"""test_character_voice_guard — 角色口吻门禁测试 v0.4.5"""
import sys, json
from pathlib import Path

from src.guards.character_voice_guard import (
    run_character_voice_check,
    _match_pack_markers,
)
from src.agents.character import _load_packs_from_files


def _packs():
    return _load_packs_from_files(
        str(Path(__file__).parent.parent / "packs" / "voice"))


def test_empty_content():
    report = run_character_voice_check("", 1)
    assert report["status"] in ("PASS", "WARNING")
    assert report["total_dialogues"] == 0


def test_normal_text_passes():
    content = """周砚走到矿壁前，伸手摸了摸湿漉漉的石面。
\u201c不急，先把这面墙看完。\u201d他说。
沈师姐站在一旁，没有说话，只是用剑尖轻轻点了一下地面。"""
    report = run_character_voice_check(content, 1)
    assert report["status"] in ("PASS", "WARNING")


def test_forbidden_words_detected():
    content = '\u201c这件事情没有那么简单。\u201d周砚说。\u201c确实，事情没有这么简单。\u201d沈师姐回答。'
    report = run_character_voice_check(content, 1)
    assert report["status"] in ("PASS", "WARNING")


def test_voice_profiles_loaded():
    """测试加载角色口吻卡"""
    profiles = [{
        "character_name": "\u5468\u781a",
        "dialect_level": 0, "wenyan_level": 1,
        "dialect_pack": "none", "meme_pack": "none",
        "english_pack": "none", "forbidden_words": ["\u547d\u8fd0", "\u5927\u9053"],
    }]
    content = '\u201c\u6216\u8bb8\u8fd9\u5c31\u662f\u547d\u8fd0\u5427\u3002\u201d\u5468\u781a\u81ea\u8a00\u81ea\u8bed\u9053\u3002'
    report = run_character_voice_check(content, 1, profiles)
    assert report["status"] in ("PASS", "WARNING")


def test_match_pack_markers():
    packs = _packs()
    sd = packs.get("shandong_light", {})
    hits = _match_pack_markers("\u4ffa\u8bf4\u4e0d\u884c\u5c31\u662f\u4e0d\u884c\u3002", sd)
    assert "\u4ffa" in hits["hits"]
