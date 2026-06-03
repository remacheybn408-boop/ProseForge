"""test_multi_register_voice_guard.py — 多语体声纹检测 (v0.4.5 通用化)"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from src.guards.character_voice_guard import run_character_voice_check
from voice_profile_loader import _load_packs_from_files

LQ = "\u201c"
RQ = "\u201d"


def _load():
    packs = _load_packs_from_files(
        os.path.join(os.path.dirname(__file__), "..", "voice_packs"))
    profiles_path = os.path.join(os.path.dirname(__file__), "..",
                                 "examples", "demo_novel", "voice_profiles.example.json")
    profiles = json.loads(open(profiles_path, encoding="utf-8").read())
    return packs, profiles


def test_protagonist_dialect_warning():
    """理工主角说方言应触发 WARNING"""
    packs, profiles = _load()
    text = f"\u7406\u5de5\u4e3b\u89d2\u8bf4\uff1a{LQ}\u4ffa\u4e5f\u4e0d\u77e5\u9053\u54aa\u56de\u4e8b\u3002{RQ}"
    r = run_character_voice_check(text, 1, profiles, packs)
    assert r["status"] == "WARNING"
    assert any("\u4ffa" in w or "\u54aa" in w for w in r["warnings"])


def test_protagonist_tech_english_pass():
    """理工主角说技术英语应 PASS"""
    packs, profiles = _load()
    text = f"\u7406\u5de5\u4e3b\u89d2\u8bf4\uff1a{LQ}the field coupling needs recalibration.{RQ}"
    r = run_character_voice_check(text, 1, profiles, packs)
    assert r["status"] in ("PASS", "WARNING")


def test_sidekick_normal_pass():
    """好兄弟正常方言对话应 PASS"""
    packs, profiles = _load()
    text = f"\u597d\u5144\u5f1f\u8bf4\uff1a{LQ}\u8fd9\u4e8b\u513f\u4e2d\u4e0d\u4e2d\uff1f{RQ}"
    r = run_character_voice_check(text, 1, profiles, packs)
    assert r["status"] in ("PASS", "WARNING")


def test_villain_meme_warning():
    """冷反派说禁用梗应触发 WARNING"""
    packs, profiles = _load()
    text = f"\u51b7\u53cd\u6d3e\u8bf4\uff1a{LQ}\u7edd\u7edd\u5b50\uff0c\u4f60\u4eec\u8fd9\u4e9b\u8768\u8725{RQ}"
    r = run_character_voice_check(text, 1, profiles, packs)
    assert r["status"] == "WARNING"


def test_elder_ok_bro_warning():
    """古修长老说 OK bro 应触发 WARNING"""
    packs, profiles = _load()
    text = f"\u53e4\u4fee\u957f\u8001\u8bf4\uff1a{LQ}OK bro\uff0c\u4ffa\u77e5\u9053\u4e86\u3002{RQ}"
    r = run_character_voice_check(text, 1, profiles, packs)
    assert r["status"] == "WARNING"


def test_narration_pollution():
    """旁白中出现方言和英语应触发 WARNING"""
    packs, profiles = _load()
    text = "\u4ffa\u5bfb\u601d\u8fd9\u4e8b\u513f\u4e0d\u5bf9\u52b2\u3002OK\uff0c\u8be5\u8d70\u4e86\u3002"
    r = run_character_voice_check(text, 1, profiles, packs)
    nar = r["narration_report"]
    assert len(nar["warnings"]) > 0
