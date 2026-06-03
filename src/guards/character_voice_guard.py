#!/usr/bin/env python3
"""
character_voice_guard.py — 角色口吻门禁 v0.4.5

多语体检测：
1. 方言检测（按 pack 分治：山东/关中/晋地/东北/中原/川渝）
2. 网络梗检测（轻梗 + 禁用梗）
3. 英语检测（技术英语 + 禁用日常英语）
4. 角色错口吻检测（某角色说方言、某反派说梗等）
5. 缺失声纹检测（角色有对白但无声纹特征）
6. 旁白污染检测（方言/梗/英语进入旁白）

策略: WARNING only, 不 FAIL
"""

import re, json, sys, argparse
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════════════
# 对白提取 — 使用中文引号 \u201c\u201d 和 \u300c\u300d
# ═══════════════════════════════════════════════════

LQ = "\u201c"
RQ = "\u201d"
LJ = "\u300c"
RJ = "\u300d"
DIALOGUE_PATTERN = re.compile(f"[{LQ}{RQ}{LJ}{RJ}]([^{LQ}{RQ}{LJ}{RJ}]{{5,200}})[{LQ}{RQ}{LJ}{RJ}]")
SPEAKER_PATTERN = re.compile(
    # Generic: matches any 1-6 char name/title + speech verb (non-greedy)
    # Exclude whitespace and major punctuation before the speech verb
    r'([^\s，。！？]{1,6}?)[说问道喊叫吼骂叹曰：:]'
)


def extract_dialogues(content):
    """提取所有对白，尝试绑定说话者"""
    dialogues = []
    for m in DIALOGUE_PATTERN.finditer(content):
        text = m.group(1)
        start = max(0, m.start() - 30)
        context = content[start:m.start()]
        speaker_match = SPEAKER_PATTERN.search(context)
        speaker = speaker_match.group(1) if speaker_match else "\u672a\u77e5"
        dialogues.append({
            "text": text,
            "speaker": speaker,
            "position": m.start(),
            "length": len(text)
        })
    return dialogues


def extract_narration(content):
    """提取旁白（去掉对白）"""
    return re.sub(f"[{LQ}{RQ}{LJ}{RJ}][^{LQ}{RQ}{LJ}{RJ}]+[{LQ}{RQ}{LJ}{RJ}]", '', content)


# ═══════════════════════════════════════════════════
# 多语体检测
# ═══════════════════════════════════════════════════

def _match_pack_markers(text, pack):
    if not pack:
        return {"hits": [], "soft_hits": [], "danger_hits": []}
    markers = pack.get("markers", [])
    soft = pack.get("soft_markers", [])
    danger = pack.get("danger_markers", [])
    return {
        "hits": [m for m in markers if m in text],
        "soft_hits": [m for m in soft if m in text],
        "danger_hits": [m for m in danger if m in text],
    }


def check_speaker_against_packs(combined_text, profile, packs):
    """Check one speaker's dialogue against voice packs and profile."""
    result = {
        "speaker": profile.get("character_name", "\u672a\u77e5"),
        "dialogue_count": 0,
        "profile_found": bool(profile),
        "expected_dialect": profile.get("dialect_pack", "none"),
        "dialect_hits": [],
        "unexpected_dialect_hits": [],
        "meme_hits": [],
        "banned_meme_hits": [],
        "english_hits": [],
        "banned_english_hits": [],
        "forbidden_hits": [],
        "missing_signature": False,
        "warnings": [],
    }

    dialect_pack_id = profile.get("dialect_pack", "none")
    dialect_level = profile.get("dialect_level", 0)

    if dialect_pack_id != "none" and dialect_pack_id in packs:
        hits = _match_pack_markers(combined_text, packs[dialect_pack_id])
        result["dialect_hits"] = hits["hits"]

    expected_markers = set()
    if dialect_pack_id != "none" and dialect_pack_id in packs:
        expected_markers = set(packs[dialect_pack_id].get("markers", []))
    for pid, pack in packs.items():
        if pack.get("type") != "dialect":
            continue
        if pid == dialect_pack_id:
            continue
        hits = _match_pack_markers(combined_text, pack)
        unique_hits = [h for h in hits["hits"] if h not in expected_markers]
        if unique_hits:
            result["unexpected_dialect_hits"].extend(f"{pid}:{h}" for h in unique_hits)

    if dialect_level > 0 and not result["dialect_hits"] and not result["unexpected_dialect_hits"]:
        result["missing_signature"] = True
        result["warnings"].append(f"\u5e94\u4e3a{dialect_pack_id}\u58f0\u7eb9\uff0c\u4f46\u672a\u68c0\u6d4b\u5230")

    banned_meme = packs.get("banned_memes", {})
    bh = _match_pack_markers(combined_text, banned_meme)
    if bh["danger_hits"]:
        result["banned_meme_hits"] = bh["danger_hits"]
        result["warnings"].append(f"\u7981\u7528\u7f51\u7edc\u6897: {', '.join(bh['danger_hits'])}")

    meme_pack_id = profile.get("meme_pack", "none")
    light_meme = packs.get("light_net_meme", {})
    if meme_pack_id != "none" and meme_pack_id in packs:
        mh = _match_pack_markers(combined_text, packs[meme_pack_id])
        result["meme_hits"] = mh["hits"]
        threshold = packs[meme_pack_id].get("overuse_warning_threshold", 5)
        if len(mh["hits"]) > threshold:
            result["warnings"].append(f"\u7f51\u7edc\u6897\u8d85\u6807 ({len(mh['hits'])} > {threshold})")
    elif meme_pack_id == "none":
        lh = _match_pack_markers(combined_text, light_meme)
        if lh["hits"]:
            result["meme_hits"] = lh["hits"]
            result["warnings"].append(f"\u4e0d\u5e94\u4f7f\u7528\u7f51\u7edc\u6897: {', '.join(lh['hits'])}")

    banned_eng = packs.get("banned_english", {})
    beh = _match_pack_markers(combined_text, banned_eng)
    if beh["danger_hits"]:
        result["banned_english_hits"] = beh["danger_hits"]
        result["warnings"].append(f"\u7981\u7528\u82f1\u8bed: {', '.join(beh['danger_hits'])}")

    eng_pack_id = profile.get("english_pack", "none")
    if eng_pack_id != "none" and eng_pack_id in packs:
        eh = _match_pack_markers(combined_text, packs[eng_pack_id])
        result["english_hits"] = eh["hits"]
    elif eng_pack_id == "none":
        eng_words = re.findall(r'\b[a-zA-Z]{2,15}\b', combined_text)
        if eng_words:
            suspicious = [w for w in eng_words if w.lower() not in
                          ("a", "an", "the", "is", "in", "on", "at", "to", "of")]
            if suspicious:
                result["english_hits"] = suspicious[:5]

    forbidden = profile.get("forbidden_words", [])
    result["forbidden_hits"] = [w for w in forbidden if w in combined_text]
    if result["forbidden_hits"]:
        result["warnings"].append(f"\u7981\u7528\u8bcd: {', '.join(result['forbidden_hits'])}")

    return result


def check_narration_pollution(narration, packs, policy):
    result = {"dialect_hits": [], "meme_hits": [], "english_hits": [], "warnings": []}
    max_dialect = policy.get("dialect_level", 0)
    max_meme = policy.get("meme_level", 0)
    max_english = policy.get("english_level", 0)

    for pid, pack in packs.items():
        if pack.get("type") != "dialect":
            continue
        hits = _match_pack_markers(narration, pack)
        if hits["hits"]:
            result["dialect_hits"].extend(f"{pid}:{h}" for h in hits["hits"])
    if result["dialect_hits"] and max_dialect == 0:
        result["warnings"].append(f"\u65c1\u767d\u51fa\u73b0\u65b9\u8a00: {', '.join(result['dialect_hits'][:5])}")

    for pid in ("light_net_meme", "banned_memes"):
        pack = packs.get(pid)
        if not pack:
            continue
        hits = _match_pack_markers(narration, pack)
        all_hits = hits["hits"] + hits["danger_hits"]
        if all_hits:
            result["meme_hits"].extend(all_hits)
    if result["meme_hits"] and max_meme == 0:
        result["warnings"].append(f"\u65c1\u767d\u51fa\u73b0\u7f51\u7edc\u6897: {', '.join(result['meme_hits'][:5])}")

    banned_eng = packs.get("banned_english", {})
    beh = _match_pack_markers(narration, banned_eng)
    if beh["danger_hits"]:
        result["english_hits"] = beh["danger_hits"]
    if result["english_hits"] and max_english == 0:
        result["warnings"].append(f"\u65c1\u767d\u51fa\u73b0\u82f1\u8bed: {', '.join(result['english_hits'][:5])}")

    return result


# ═══════════════════════════════════════════════════
# 主入口 (v0.4.5 扩展)
# ═══════════════════════════════════════════════════

def run_character_voice_check(
    content,
    chapter_no=0,
    voice_profiles=None,
    voice_packs=None,
    narration_policy=None,
    mode="warning",
):
    voice_profiles = voice_profiles or []
    voice_packs = voice_packs or {}
    narration_policy = narration_policy or {
        "dialect_level": 0, "meme_level": 0, "english_level": 0, "wenyan_level": 1
    }

    dialogues = extract_dialogues(content)
    narration = extract_narration(content)

    profile_map = {}
    for p in voice_profiles:
        name = p.get("character_name", "")
        if name:
            profile_map[name] = p

    speaker_dialogues = {}
    for d in dialogues:
        s = d["speaker"]
        if s not in speaker_dialogues:
            speaker_dialogues[s] = []
        speaker_dialogues[s].append(d)

    speaker_reports = []
    all_warnings = []

    for speaker, dls in speaker_dialogues.items():
        combined = " ".join(d["text"] for d in dls)
        profile = profile_map.get(speaker, {
            "character_name": speaker,
            "dialect_pack": "none", "register_pack": "none",
            "meme_pack": "none", "english_pack": "none",
            "dialect_level": 0, "meme_level": 0, "english_level": 0,
            "forbidden_words": [],
        })
        profile["character_name"] = speaker

        sr = check_speaker_against_packs(combined, profile, voice_packs)
        sr["dialogue_count"] = len(dls)
        speaker_reports.append(sr)
        if sr["warnings"]:
            all_warnings.append(f"[{speaker}] {'; '.join(sr['warnings'])}")

    narration_report = check_narration_pollution(narration, voice_packs, narration_policy)
    if narration_report["warnings"]:
        all_warnings.extend(narration_report["warnings"])

    status = "WARNING" if all_warnings else "PASS"

    return {
        "guard": "character_voice_guard",
        "version": "v0.4.5",
        "status": status,
        "final_decision": status,
        "chapter_no": chapter_no,
        "total_dialogues": len(dialogues),
        "speaker_count": len(speaker_dialogues),
        "speaker_reports": speaker_reports,
        "narration_report": narration_report,
        "voice_memory_observations": [
            {
                "speaker": sr["speaker"],
                "warnings": sr["warnings"],
                "dialect_hits": sr["dialect_hits"],
                "meme_hits": sr["meme_hits"] + sr["banned_meme_hits"],
                "english_hits": sr["english_hits"] + sr["banned_english_hits"],
                "forbidden_hits": sr["forbidden_hits"],
            }
            for sr in speaker_reports if sr["warnings"]
        ],
        "warnings": all_warnings,
        "violations": all_warnings,
        "character_voice_pass": len(all_warnings) == 0,
    }


# ═══════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Character Voice Guard")
    parser.add_argument("content_file", help="章节 TXT 文件")
    parser.add_argument("--chapter-no", type=int, default=1)
    parser.add_argument("--voice-profiles", default=None)
    parser.add_argument("--voice-packs-dir", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    content = Path(args.content_file).read_text(encoding="utf-8")
    vp = []
    if args.voice_profiles and Path(args.voice_profiles).exists():
        vp = json.loads(Path(args.voice_profiles).read_text(encoding="utf-8"))
    packs = {}
    if args.voice_packs_dir:
        for fp in sorted(Path(args.voice_packs_dir).rglob("*.json")):
            try:
                d = json.loads(fp.read_text(encoding="utf-8"))
                packs[d.get("pack_id", fp.stem)] = {
                    "pack_id": d.get("pack_id"), "type": d.get("type", ""),
                    "markers": d.get("markers", []),
                    "soft_markers": d.get("soft_markers", []),
                    "danger_markers": d.get("danger_markers", []),
                    "overuse_warning_threshold": d.get("overuse_warning_threshold", 5),
                }
            except Exception:
                pass
    report = run_character_voice_check(content, args.chapter_no, vp, packs)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.output:
        p = Path(args.output); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["status"] == "WARNING":
        print(f"\n[WARN] Character voice: {len(report['warnings'])} issues")
    else:
        print(f"\n[OK] Character voice check passed")


if __name__ == "__main__":
    main()
