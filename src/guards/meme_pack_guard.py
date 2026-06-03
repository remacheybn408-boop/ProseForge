#!/usr/bin/env python3
"""
meme_pack_guard.py — 梗包密度门禁 v0.5.0

Meme pack density guard. Checks:
1. Same meme in consecutive chapters → WARN
2. Serious scene + high meme density → WARN
3. Unbound character using bound meme → FAIL
4. Dialect density too high → WARN
"""

import json
import re
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════
# Pack loading
# ═══════════════════════════════════════════════════

def _load_yaml_pack(path: Path) -> Optional[dict]:
    """Try to load a YAML meme pack file."""
    try:
        import yaml
    except ImportError:
        return None
    
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None
    except Exception:
        return None
    
    pack_id = raw.get("id", path.stem)
    
    return {
        "pack_id": pack_id,
        "name": raw.get("name", ""),
        "type": raw.get("type", "meme"),
        "markers": raw.get("variants", raw.get("allowed_terms", [])),
        "danger_markers": raw.get("banned_terms", raw.get("banned_markers", [])),
        "soft_markers": raw.get("soft_markers", []),
        "overuse_warning_threshold": (
            raw.get("frequency", {}).get("max_per_chapter", 5)
            if isinstance(raw.get("frequency"), dict) else 5
        ),
        "cooldown_chapters": (
            raw.get("frequency", {}).get("cooldown_chapters", 3)
            if isinstance(raw.get("frequency"), dict) else 3
        ),
        "allowed_roles": raw.get("allowed_roles", []),
        "forbidden_roles": raw.get("forbidden_roles", []),
        "severity_limit": raw.get("severity_limit", {}),
        "max_scene_seriousness": (
            raw.get("severity_limit", {}).get("max_scene_seriousness", "medium")
            if isinstance(raw.get("severity_limit"), dict) else "medium"
        ),
    }


def _load_json_pack(path: Path) -> Optional[dict]:
    """Load a JSON meme pack file."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    
    return {
        "pack_id": raw.get("pack_id", path.stem),
        "name": raw.get("name", ""),
        "type": raw.get("type", "meme"),
        "markers": raw.get("allowed_markers", raw.get("markers", [])),
        "danger_markers": raw.get("danger_markers", []) + raw.get("banned_markers", []),
        "soft_markers": raw.get("soft_markers", []),
        "overuse_warning_threshold": raw.get("overuse_warning_threshold", 5),
        "cooldown_chapters": raw.get("cooldown_chapters", 3),
        "allowed_roles": raw.get("allowed_roles", raw.get("suitable_archetypes", [])),
        "forbidden_roles": raw.get("forbidden_roles", raw.get("forbidden_archetypes", [])),
        "severity_limit": raw.get("severity_limit", {}),
        "max_scene_seriousness": raw.get("max_scene_seriousness", "medium"),
    }


def load_meme_packs(packs_dir: str) -> dict:
    """Load meme packs from both memes/ and other voice_packs subdirs."""
    packs = {}
    packs_path = Path(packs_dir)
    
    if not packs_path.exists():
        return packs
    
    for fp in sorted(packs_path.rglob("*")):
        if fp.suffix not in (".json", ".yaml", ".yml"):
            continue
        
        pack_data = None
        if fp.suffix == ".json":
            pack_data = _load_json_pack(fp)
        else:
            pack_data = _load_yaml_pack(fp)
        
        if not pack_data or not pack_data.get("pack_id"):
            continue
        
        # Only include meme-type packs
        ptype = str(pack_data.get("type", "")).lower()
        if "meme" not in ptype and "梗" not in ptype:
            continue
        
        pid = pack_data["pack_id"]
        if pid not in packs:
            packs[pid] = pack_data
    
    return packs


# ═══════════════════════════════════════════════════
# Serious scene detection
# ═══════════════════════════════════════════════════

SERIOUS_SCENE_PATTERNS = [
    r'(死[了亡去掉]|牺[牲]|殉|阵亡|殒[落命灭]|毙[命]|绝[气息命])',
    r'(重[伤创]|濒[死危]|垂[死危]|[致毙]命)',
    r'(审[判问讯]|拷[问打]|逼[供问迫])',
    r'(葬[礼]|追[悼]|告[别]|诀[别])',
    r'(血[流泊腥]|鲜[血]|染[红]|殷[红])',
    r'(哭[泣诉喊]|哀[嚎鸣伤]|悲[伤痛戚]|泪[水流])',
    r'(诀别|永别|再无|再也|永远[不没]|此生[不无])',
]

SERIOUSNESS_LEVELS = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "extreme": 4,
}


def _detect_scene_seriousness(text: str) -> tuple[str, int]:
    """Detect the seriousness level of a chapter's content."""
    matches = 0
    for pat in SERIOUS_SCENE_PATTERNS:
        if re.search(pat, text):
            matches += 1
    
    if matches == 0:
        return "none", 0
    elif matches <= 1:
        return "low", 1
    elif matches <= 3:
        return "medium", 2
    elif matches <= 6:
        return "high", 3
    else:
        return "extreme", 4


# ═══════════════════════════════════════════════════
# Checks
# ═══════════════════════════════════════════════════

def _check_same_meme_consecutive(
    current_chapter: str,
    previous_chapter: str,
    meme_packs: dict,
    chapter_no: int,
) -> list[dict]:
    """Check if same meme appears in consecutive chapters."""
    issues = []
    
    if not previous_chapter or not previous_chapter.strip():
        return issues
    
    for pid, pack in meme_packs.items():
        markers = pack.get("markers", [])
        if not markers:
            continue
        
        for marker in markers:
            if not marker or len(marker) < 2:
                continue
            
            in_prev = marker in previous_chapter
            in_curr = marker in current_chapter
            
            if in_prev and in_curr:
                cooldown = pack.get("cooldown_chapters", 3)
                issues.append({
                    "code": "CONSECUTIVE_MEME",
                    "severity": "WARN",
                    "message": (f"梗 '{marker}' ({pid}) 连续出现在第{chapter_no-1}章和第{chapter_no}章 "
                               f"(冷却需求: {cooldown}章)"),
                    "suggestion": f"避免同一梗连续使用，至少间隔{cooldown}章",
                    "confidence": 0.80,
                    "details": {"meme": marker, "pack": pid, "cooldown": cooldown},
                })
    
    return issues


def _check_serious_scene_meme_density(
    text: str,
    meme_packs: dict,
    voice_profiles: list,
) -> list[dict]:
    """Check if a serious scene has too many memes."""
    issues = []
    
    scene_level, level_num = _detect_scene_seriousness(text)
    
    if level_num < 2:  # Only check medium+ scenes
        return issues
    
    total_chars = len(text.replace('\n', '').replace(' ', '').replace('\u3000', ''))
    
    # Count all meme hits
    for pid, pack in meme_packs.items():
        markers = pack.get("markers", []) + pack.get("danger_markers", [])
        if not markers:
            continue
        
        hit_count = sum(text.count(m) for m in markers if m)
        density = hit_count / max(total_chars, 1) * 1000
        
        max_severity = pack.get("max_scene_seriousness", "medium")
        max_sev_num = SERIOUSNESS_LEVELS.get(max_severity, 2)
        
        if level_num > max_sev_num and hit_count > 0:
            issues.append({
                "code": "MEME_IN_SERIOUS_SCENE",
                "severity": "WARN",
                "message": (f"严肃场景(level={scene_level})中使用梗 '{pid}' "
                           f"({hit_count}次, 允许max={max_severity})"),
                "suggestion": "严肃场景（死亡/审判/诀别）应避免使用梗",
                "confidence": 0.85,
                "details": {
                    "pack": pid, "hits": hit_count, "density": round(density, 1),
                    "scene_level": scene_level, "max_allowed": max_severity,
                },
            })
        
        # Also high density in any scene
        threshold = pack.get("overuse_warning_threshold", 5)
        if hit_count > threshold:
            issues.append({
                "code": "MEME_DENSITY_HIGH",
                "severity": "WARN",
                "message": f"梗密度过高: '{pid}' {hit_count}次 (阈值{threshold})",
                "suggestion": f"每章每个梗包不超过{threshold}次",
                "confidence": 0.70,
                "details": {"pack": pid, "hits": hit_count, "threshold": threshold},
            })
    
    return issues


def _check_unbound_character_meme(
    text: str,
    meme_packs: dict,
    voice_profiles: list,
) -> list[dict]:
    """Check if an unbound character uses a bound meme (FAIL)."""
    issues = []
    
    # Build character → allowed meme_packs mapping
    char_meme_packs = {}
    for profile in voice_profiles:
        char_name = profile.get("character_name", "unknown")
        meme_pack = profile.get("meme_pack", "none")
        
        if isinstance(meme_pack, list):
            char_meme_packs[char_name] = meme_pack
        elif meme_pack != "none":
            char_meme_packs[char_name] = [meme_pack]
        else:
            char_meme_packs[char_name] = []
    
    if not char_meme_packs:
        return issues
    
    # For each meme pack, check which characters are allowed
    for pid, pack in meme_packs.items():
        allowed_roles = pack.get("allowed_roles", [])
        forbidden_roles = pack.get("forbidden_roles", [])
        
        if not allowed_roles and not forbidden_roles:
            continue
        
        markers = pack.get("markers", [])
        if not markers:
            continue
        
        # If a pack has allowed_roles, only those characters can use it
        if allowed_roles:
            # For each character NOT in allowed_roles, check if they use this meme
            for char_name, char_memes in char_meme_packs.items():
                if pid in char_memes:
                    continue  # Character has this pack explicitly
                
                # Check if character archetype/role matches allowed_roles
                # This requires knowledge of character roles — simplified check
                # against forbidden_roles
                pass
    
    # Simplified approach: check if any meme markers appear that shouldn't be
    # used by characters without explicit meme_pack assignment
    for pid, pack in meme_packs.items():
        markers = pack.get("markers", [])
        if not markers:
            continue
        
        found_markers = [m for m in markers if m and m in text]
        if not found_markers:
            continue
        
        # Check if ANY profile has this pack
        has_bound_character = any(
            pid in char_meme_packs.get(p.get("character_name", ""), [])
            for p in voice_profiles
        )
        
        if not has_bound_character:
            # Check if this pack is meant only for specific roles
            allowed_roles = pack.get("allowed_roles", [])
            forbidden_roles = pack.get("forbidden_roles", [])
            
            if allowed_roles and not forbidden_roles:
                # Pack requires specific role binding — but no character has it
                # This is a FAIL situation
                issues.append({
                    "code": "UNBOUND_MEME",
                    "severity": "FAIL",
                    "message": (f"未绑定角色使用了受限梗 '{pid}' "
                               f"(需要角色类型: {allowed_roles}): {', '.join(found_markers[:3])}"),
                    "suggestion": f"该梗只能由 {', '.join(allowed_roles)} 类型角色使用",
                    "confidence": 0.90,
                    "details": {
                        "pack": pid, "found_markers": found_markers,
                        "required_roles": allowed_roles,
                    },
                })
    
    return issues


def _check_dialect_density(
    text: str,
    dialect_packs: dict,
    voice_profiles: list,
) -> list[dict]:
    """Check if dialect density is too high."""
    issues = []
    
    total_chars = len(text.replace('\n', '').replace(' ', '').replace('\u3000', ''))
    
    for pid, pack in dialect_packs.items():
        markers = pack.get("markers", [])
        if not markers:
            continue
        
        hit_count = sum(text.count(m) for m in markers if m)
        density = hit_count / max(total_chars, 1) * 1000
        
        max_density = pack.get("max_density_per_1000_chars", 5)
        
        if density > max_density:
            issues.append({
                "code": "DIALECT_DENSITY_HIGH",
                "severity": "WARN",
                "message": (f"方言密度过高: '{pid}' {density:.1f}/千字 "
                           f"(上限{max_density}/千字)"),
                "suggestion": "降低方言词汇使用频率，保持可读性",
                "confidence": 0.75,
                "details": {"pack": pid, "density": round(density, 1),
                           "max": max_density, "hits": hit_count},
            })
    
    return issues


# ═══════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════

def run_meme_pack_check(
    chapter_text: str,
    chapter_no: int = 0,
    previous_chapter_text: str = "",
    voice_profiles: list = None,
    meme_packs_dir: str = None,
    dialect_packs: dict = None,
) -> dict:
    """
    Run meme pack density guard on a chapter.
    
    Args:
        chapter_text: Current chapter text.
        chapter_no: Chapter number.
        previous_chapter_text: Previous chapter text (for consecutive check).
        voice_profiles: List of character voice profile dicts.
        meme_packs_dir: Path to voice_packs directory.
        dialect_packs: Optional pre-loaded dialect packs dict.
    
    Returns:
        dict with status (PASS/WARN/FAIL), issues, warnings.
    """
    voice_profiles = voice_profiles or []
    dialect_packs = dialect_packs or {}
    
    # Load meme packs
    meme_packs = {}
    if meme_packs_dir:
        meme_packs = load_meme_packs(meme_packs_dir)
        
        # Also load dialect packs if not provided
        if not dialect_packs:
            packs_path = Path(meme_packs_dir)
            for fp in sorted(packs_path.rglob("*")):
                if fp.suffix not in (".json", ".yaml", ".yml"):
                    continue
                
                pack_data = None
                if fp.suffix == ".json":
                    try:
                        raw = json.loads(fp.read_text(encoding="utf-8"))
                        ptype = str(raw.get("type", "")).lower()
                        # Only load dialect-type packs; skip register/meme/english voice packs
                        if "dialect" not in ptype and "方言" not in ptype:
                            continue
                        pack_data = {"pack_id": raw.get("pack_id", fp.stem),
                                    "type": raw.get("type", "dialect"),
                                    "markers": raw.get("allowed_markers", raw.get("markers", [])),
                                    "max_density_per_1000_chars": raw.get("max_density_per_1000_chars", 5)}
                    except Exception:
                        continue
                else:
                    try:
                        import yaml
                        raw = yaml.safe_load(fp.read_text(encoding="utf-8"))
                        if isinstance(raw, dict):
                            ptype = str(raw.get("type", "")).lower()
                            if "dialect" in ptype or "方言" in ptype:
                                pack_data = {
                                    "pack_id": raw.get("id", raw.get("name", fp.stem)),
                                    "type": raw.get("type", "dialect"),
                                    "markers": (raw.get("features", {}).get("vocabulary", [])
                                               if isinstance(raw.get("features"), dict) else []),
                                    "max_density_per_1000_chars": 5,
                                }
                    except Exception:
                        continue
                
                if pack_data and pack_data.get("pack_id"):
                    dialect_packs.setdefault(pack_data["pack_id"], pack_data)
    
    # ── Run all checks ──
    all_issues = []
    
    # 1. Same meme in consecutive chapters
    if previous_chapter_text:
        consec_issues = _check_same_meme_consecutive(
            chapter_text, previous_chapter_text, meme_packs, chapter_no
        )
        all_issues.extend(consec_issues)
    
    # 2. Serious scene + high meme density
    serious_issues = _check_serious_scene_meme_density(
        chapter_text, meme_packs, voice_profiles
    )
    all_issues.extend(serious_issues)
    
    # 3. Unbound character using bound meme
    unbound_issues = _check_unbound_character_meme(
        chapter_text, meme_packs, voice_profiles
    )
    all_issues.extend(unbound_issues)
    
    # 4. Dialect density too high
    dialect_issues = _check_dialect_density(
        chapter_text, dialect_packs, voice_profiles
    )
    all_issues.extend(dialect_issues)
    
    # ── Determine status ──
    has_fail = any(i["severity"] == "FAIL" for i in all_issues)
    has_warn = any(i["severity"] == "WARN" for i in all_issues)
    
    if has_fail:
        status = "FAIL"
    elif has_warn:
        status = "WARN"
    else:
        status = "PASS"
    
    all_warnings = [i["message"] for i in all_issues]
    
    return {
        "guard": "meme_pack_guard",
        "version": "v0.5.0",
        "status": status,
        "final_decision": status,
        "chapter_no": chapter_no,
        "meme_packs_loaded": list(meme_packs.keys()),
        "dialect_packs_loaded": list(dialect_packs.keys()),
        "scene_seriousness": _detect_scene_seriousness(chapter_text)[0],
        "issues": all_issues,
        "warnings": all_warnings,
        "violations": all_warnings,
    }


# ═══════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Meme Pack Guard v0.5.0")
    parser.add_argument("content_file", help="Chapter TXT file path")
    parser.add_argument("--chapter-no", type=int, default=1, help="Chapter number")
    parser.add_argument("--prev-chapter", default=None, help="Previous chapter TXT file path")
    parser.add_argument("--voice-profiles", default=None, help="Voice profiles JSON file")
    parser.add_argument("--meme-packs-dir", default=None, help="Voice packs directory")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    args = parser.parse_args()

    text = Path(args.content_file).read_text(encoding="utf-8")
    
    prev_text = ""
    if args.prev_chapter and Path(args.prev_chapter).exists():
        prev_text = Path(args.prev_chapter).read_text(encoding="utf-8")
    
    vp = []
    if args.voice_profiles and Path(args.voice_profiles).exists():
        vp = json.loads(Path(args.voice_profiles).read_text(encoding="utf-8"))
    
    report = run_meme_pack_check(
        text, args.chapter_no, prev_text, vp, args.meme_packs_dir
    )
    
    print(json.dumps(report, ensure_ascii=False, indent=2))
    
    if args.output:
        p = Path(args.output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    
    status = report["status"]
    if status == "FAIL":
        print(f"\n[FAIL] Meme pack: {len(report['issues'])} issues (with FAIL)")
    elif status == "WARN":
        print(f"\n[WARN] Meme pack: {len(report['issues'])} issues")
    else:
        print(f"\n[OK] Meme pack check passed")
