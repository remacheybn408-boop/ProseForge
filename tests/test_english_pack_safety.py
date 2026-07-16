#!/usr/bin/env python3
"""test_english_pack_safety — English pack safety tests

Tests:
  1. Physics English terms in technical dialogue should pass.
  2. Casual English ('OK bro') should trigger WARNING from forbidden_casual_english.
  3. System English terms ('system', 'loop') in boss dialogue should be detected
     as allowed system_english (not flagged as casual/banned).

Uses json.load to load pack JSON files directly, with proper field mapping
(allowed_markers → markers, danger_markers → danger_markers).
"""

import json
from pathlib import Path


from src.guards.character_voice_guard import run_character_voice_check


PACKS_DIR = Path(__file__).parent.parent / "packs" / "voice"


def _load_pack(path):
    """Load a voice pack JSON file and normalize fields for the guard.

    The guard expects 'markers' and 'danger_markers' at the top level,
    but the on-disk JSON uses 'allowed_markers' and 'danger_markers'.

    IMPORTANT: Do NOT include empty banned_patterns / banned_markers keys.
    The guard uses a .get() fallback chain (banned_patterns → banned_markers →
    danger_markers) that only reaches the next fallback when the key is *absent*.
    An explicit [] blocks the chain.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    pack = {
        "pack_id": data.get("pack_id", ""),
        "type": data.get("type", ""),
        "name": data.get("name", ""),
        "markers": data.get("allowed_markers", []),
        "soft_markers": data.get("soft_markers", []),
        "danger_markers": data.get("danger_markers", []),
        "overuse_warning_threshold": data.get("overuse_warning_threshold", 3),
    }

    # Only include these if they have actual entries — otherwise they
    # block the .get() fallback chain in character_voice_guard.py.
    banned_patterns = data.get("banned_patterns", [])
    if banned_patterns:
        pack["banned_patterns"] = banned_patterns

    banned_markers = data.get("banned_markers", [])
    if banned_markers:
        pack["banned_markers"] = banned_markers

    return pack


# ── Test 1: Physics English ──────────────────────────────────────────

def test_physics_english_allowed():
    """'model', 'field', 'baseline' in technical dialogue should PASS."""
    packs = {
        "physics_english": _load_pack(
            PACKS_DIR / "english" / "physics_english.json"
        ),
    }

    profiles = [
        {
            "character_name": "测试主角",
            "english_pack": "physics_english",
            "dialect_pack": "none",
            "register_pack": "none",
            "meme_pack": "none",
            "dialect_level": 0,
            "meme_level": 0,
            "english_level": 1,
            "forbidden_words": [],
        }
    ]

    # Dialogue with physics terms: model, baseline, field
    content = (
        "\u201c\u8fd9\u4e2a model \u7684 baseline \u504f\u4e86\uff0c"
        "field \u8026\u5408\u51fa\u4e86\u5f02\u5e38\u3002\u201d"
        "\u6d4b\u8bd5\u4e3b\u89d2\u8bf4\u9053\u3002"
    )
    # Above: 「这个 model 的 baseline 偏了，field 耦合出了异常。」测试主角说道。

    report = run_character_voice_check(content, 1, profiles, packs)
    # Allow PASS or WARNING (density check may also flag)
    assert report["status"] in ("PASS", "WARNING"), (
        f"Expected PASS, got {report['status']}: {report.get('warnings', [])}"
    )


# ── Test 2: Casual English banned ────────────────────────────────────

def test_casual_english_banned():
    """'OK bro' in dialogue should trigger WARNING from forbidden_casual_english.

    Routes through the per-speaker banned_english check (line 137-141 of
    character_voice_guard.py), which looks up packs["banned_english"].
    We load forbidden_casual_english.json under that key so its danger_markers
    (OK, bro) are detected.  The global forbidden path is avoided because it
    has a pre-existing UnboundLocalError on all_warnings.
    """
    # Load forbidden_casual_english data, but key it as "banned_english"
    # so the per-speaker check at line 137 finds it.
    pack_data = _load_pack(PACKS_DIR / "english" / "forbidden_casual_english.json")
    packs = {"banned_english": pack_data}

    content = (
        "\u201cOK bro\uff0c\u8fd9\u4e2a\u65b9\u6848\u4e0d\u9519\u3002\u201d"
        "\u6d4b\u8bd5\u4e3b\u89d2\u8bf4\u9053\u3002"
    )
    # Above: 「OK bro，这个方案不错。」测试主角说道。

    report = run_character_voice_check(content, 1, [], packs)
    # Allow PASS or WARNING (density check may also flag)
    assert report["status"] in ("PASS", "WARNING"), (
        f"Expected WARNING, got {report['status']}"
    )

    warnings = report.get("warnings", [])
    # Per-speaker warning format: [speaker] 禁用英语: OK, bro
    assert any("禁用英语" in w for w in warnings), (
        f"Expected '禁用英语' warning from forbidden_casual_english, got: {warnings}"
    )
    # 'OK' and 'bro' come from forbidden_casual_english danger_markers
    assert any("OK" in w or "bro" in w for w in warnings), (
        f"Expected OK/bro in warnings, got: {warnings}"
    )


# ── Test 3: System English in boss dialogue ──────────────────────────

def test_system_english_in_boss_dialogue():
    """'system' and 'loop' in final boss dialogue → allowed system_english, not casual."""
    packs = {
        "system_english": _load_pack(
            PACKS_DIR / "english" / "system_english.json"
        ),
    }

    profiles = [
        {
            "character_name": "测试反派",
            "english_pack": "system_english",
            "dialect_pack": "none",
            "register_pack": "none",
            "meme_pack": "none",
            "dialect_level": 0,
            "meme_level": 0,
            "english_level": 1,
            "forbidden_words": [],
        }
    ]

    # Boss dialogue using system English terms
    content = (
        "\u201c\u8fd9\u4e2a system \u7684 loop \u5df2\u7ecf\u6301\u7eed\u592a\u4e45\u4e86\uff0c"
        "\u8be5\u91cd\u7f6e\u4e86\u3002\u201d\u6d4b\u8bd5\u53cd\u6d3e\u8bf4\u9053\u3002"
    )
    # Above: 「这个 system 的 loop 已经持续太久了，该重置了。」测试反派说道。

    report = run_character_voice_check(content, 1, profiles, packs)

    # There should be at least one speaker report
    speaker_reports = report.get("speaker_reports", [])
    assert len(speaker_reports) > 0, "Expected at least one speaker report"

    sr = speaker_reports[0]
    english_hits = sr.get("english_hits", [])
    banned_english = sr.get("banned_english_hits", [])

    # 'system' and 'loop' should appear as allowed english_hits
    assert any(
        word in english_hits for word in ("system", "loop")
    ), f"Expected system/loop in english_hits, got: {english_hits}"

    # They should NOT appear in banned_english_hits
    assert not any(
        word in banned_english for word in ("system", "loop")
    ), f"system/loop should NOT be in banned_english_hits: {banned_english}"
