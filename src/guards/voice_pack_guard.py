#!/usr/bin/env python3
"""
voice_pack_guard.py — 声纹包完整门禁 v0.5.0

Wraps character_voice_guard with enhanced reporting and additional checks:
1. Catchphrase overuse detection
2. Dialect level exceeded check
3. Voice pack binding compliance
4. Register mismatch detection

Loads voice packs from voice_packs/ directory (both JSON and YAML).
Delegates core voice checking to character_voice_guard.run_character_voice_check.
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional

# Add scripts to path for character_voice_guard import
_script_dir = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from src.guards.character_voice_guard import run_character_voice_check


# ═══════════════════════════════════════════════════
# Voice pack loading
# ═══════════════════════════════════════════════════

def _load_yaml_pack(path: Path) -> Optional[dict]:
    """Try to load a YAML voice pack file."""
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
    
    pack_id = raw.get("id") or raw.get("name") or path.stem
    
    # Map YAML fields to the format character_voice_guard expects
    return {
        "pack_id": pack_id,
        "type": raw.get("type", ""),
        "name": raw.get("name", raw.get("display_name", "")),
        "markers": (raw.get("variants", []) + raw.get("allowed_terms", []) +
                    raw.get("preferred", []) + raw.get("signature_phrases", [])),
        "soft_markers": raw.get("soft_markers", raw.get("allowed_markers", [])),
        "danger_markers": (raw.get("banned_terms", []) + raw.get("banned_markers", []) +
                          raw.get("danger_markers", [])),
        "overuse_warning_threshold": (raw.get("frequency", {}).get("max_per_chapter", 5)
                                      if isinstance(raw.get("frequency"), dict)
                                      else raw.get("overuse_warning_threshold", 5)),
        "dialect_level": (raw.get("level", 0) if isinstance(raw.get("level"), int)
                         else raw.get("dialect_level", 0)),
        "max_density_per_1000_chars": raw.get("max_density_per_1000_chars"),
        "allowed_roles": raw.get("allowed_roles", []),
        "forbidden_roles": raw.get("forbidden_roles", []),
    }


def _load_json_pack(path: Path) -> Optional[dict]:
    """Load a JSON voice pack file."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    
    return {
        "pack_id": raw.get("pack_id", path.stem),
        "type": raw.get("type", ""),
        "name": raw.get("name", ""),
        "markers": raw.get("allowed_markers", raw.get("markers", [])),
        "soft_markers": raw.get("soft_markers", []),
        "danger_markers": raw.get("danger_markers", []) + raw.get("banned_markers", []),
        "overuse_warning_threshold": raw.get("overuse_warning_threshold", 5),
        "dialect_level": raw.get("dialect_level", 0),
        "max_density_per_1000_chars": raw.get("max_density_per_1000_chars"),
        "allowed_roles": raw.get("allowed_roles", raw.get("suitable_archetypes", [])),
        "forbidden_roles": raw.get("forbidden_roles", raw.get("forbidden_archetypes", [])),
    }


def load_voice_packs(packs_dir: str) -> dict:
    """Load all voice packs from a directory (both YAML and JSON)."""
    packs = {}
    packs_path = Path(packs_dir)
    
    if not packs_path.exists():
        return packs
    
    for fp in sorted(packs_path.rglob("*")):
        if fp.suffix in (".json", ".yaml", ".yml"):
            pack_data = None
            if fp.suffix == ".json":
                pack_data = _load_json_pack(fp)
            elif fp.suffix in (".yaml", ".yml"):
                pack_data = _load_yaml_pack(fp)
            
            if pack_data and pack_data.get("pack_id"):
                pid = pack_data["pack_id"]
                if pid not in packs:
                    packs[pid] = pack_data
                else:
                    # Merge: YAML may have more data for same pack
                    existing = packs[pid]
                    for key in ("markers", "danger_markers", "soft_markers"):
                        existing[key] = list(set(existing.get(key, []) + pack_data.get(key, [])))
    
    return packs


# ═══════════════════════════════════════════════════
# Catchphrase overuse detection
# ═══════════════════════════════════════════════════

def _check_catchphrase_overuse(content: str, voice_packs: dict, voice_profiles: list) -> list[dict]:
    """Detect overuse of character catchphrases/signature phrases."""
    issues = []
    
    for profile in voice_profiles:
        char_name = profile.get("character_name", "unknown")
        voice_pack_id = profile.get("voice_pack", profile.get("register_pack", "none"))
        
        if voice_pack_id == "none" or voice_pack_id not in voice_packs:
            continue
        
        pack = voice_packs[voice_pack_id]
        signatures = pack.get("markers", [])
        threshold = pack.get("overuse_warning_threshold", 3)
        
        if not signatures:
            continue
        
        total_hits = 0
        hit_counts = {}
        for sig in signatures:
            count = content.count(sig)
            if count > 0:
                total_hits += count
                hit_counts[sig] = count
        
        if total_hits > threshold:
            issues.append({
                "code": "CATCHPHRASE_OVERUSE",
                "severity": "WARN",
                "message": f"[{char_name}] 口头禅/标志语过度使用: {total_hits}次 (阈值{threshold})",
                "details": hit_counts,
                "suggestion": f"减少标志性用语的重复，每章{threshold}次以内",
                "confidence": 0.75,
            })
    
    return issues


# ═══════════════════════════════════════════════════
# Dialect level exceeded
# ═══════════════════════════════════════════════════

def _check_dialect_level_exceeded(
    content: str, voice_packs: dict, voice_profiles: list,
) -> list[dict]:
    """Check if dialect usage exceeds the allowed level for each character."""
    issues = []
    
    for profile in voice_profiles:
        char_name = profile.get("character_name", "unknown")
        dialect_pack_id = profile.get("dialect_pack", "none")
        dialect_level = profile.get("dialect_level", 0)
        
        if dialect_pack_id == "none" or dialect_pack_id not in voice_packs:
            continue
        
        pack = voice_packs[dialect_pack_id]
        markers = pack.get("markers", [])
        
        if not markers:
            continue
        
        # Count dialect markers
        hit_count = sum(content.count(m) for m in markers if m)
        total_chars = len(content.replace('\n', '').replace(' ', '').replace('\u3000', ''))
        density = hit_count / max(total_chars, 1) * 1000  # per 1000 chars
        
        # Level thresholds: 0=none, 1=light(1/1000), 2=moderate(3/1000), 3=heavy(6/1000), 4=extreme(10/1000)
        level_limits = {0: 0, 1: 1, 2: 3, 3: 6, 4: 10}
        max_allowed = level_limits.get(dialect_level, 10)
        
        if density > max_allowed:
            issues.append({
                "code": "DIALECT_LEVEL_EXCEEDED",
                "severity": "WARN",
                "message": (f"[{char_name}] 方言密度{density:.1f}/千字超过允许等级"
                           f"(level={dialect_level}, max={max_allowed}/千字)"),
                "details": {"density_per_1k": round(density, 1), "level": dialect_level,
                           "max_allowed": max_allowed},
                "suggestion": "降低方言标志词的使用频率",
                "confidence": 0.70,
            })
    
    return issues


# ═══════════════════════════════════════════════════
# Register mismatch
# ═══════════════════════════════════════════════════

def _check_register_mismatch(content: str, voice_packs: dict, voice_profiles: list) -> list[dict]:
    """Detect when a character uses a register not assigned to them."""
    issues = []
    
    for profile in voice_profiles:
        char_name = profile.get("character_name", "unknown")
        allowed_registers = profile.get("register_pack", "none")
        
        if isinstance(allowed_registers, str):
            allowed_registers = [allowed_registers] if allowed_registers != "none" else []
        
        if not allowed_registers:
            continue
        
        # Check for markers from registers NOT in allowed list
        for pid, pack in voice_packs.items():
            if pack.get("type") not in ("register", "voice_pack"):
                continue
            if pid in allowed_registers:
                continue
            
            markers = pack.get("markers", [])
            hits = [m for m in markers if m and m in content]
            
            if hits:
                issues.append({
                    "code": "REGISTER_MISMATCH",
                    "severity": "WARN",
                    "message": f"[{char_name}] 使用了未授权的语体 '{pid}': {', '.join(hits[:5])}",
                    "suggestion": f"该角色应使用: {', '.join(allowed_registers)}",
                    "confidence": 0.65,
                })
    
    return issues


# ═══════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════

def run_voice_pack_check(
    content: str,
    chapter_no: int = 0,
    voice_profiles: list = None,
    voice_packs_dir: str = None,
    narration_policy: dict = None,
    mode: str = "warning",
) -> dict:
    """
    Run full voice pack guard check on a chapter.
    
    Args:
        content: Chapter text.
        chapter_no: Chapter number.
        voice_profiles: List of character voice profile dicts.
        voice_packs_dir: Path to voice_packs directory.
        narration_policy: Narration policy dict.
        mode: "warning" (default) — WARN only, never FAIL.
    
    Returns:
        dict with status, core_voice_report, extra_checks, issues, and warnings.
    """
    voice_profiles = voice_profiles or []
    
    # Load voice packs
    packs = {}
    if voice_packs_dir:
        packs = load_voice_packs(voice_packs_dir)
    
    narration_policy = narration_policy or {
        "dialect_level": 0, "meme_level": 0, "english_level": 0, "wenyan_level": 1,
    }
    
    # ── Run core character_voice_guard ──
    core_report = run_character_voice_check(
        content=content,
        chapter_no=chapter_no,
        voice_profiles=voice_profiles,
        voice_packs=packs,
        narration_policy=narration_policy,
        mode=mode,
    )
    
    # ── Extra checks ──
    extra_issues = []
    
    # 1. Catchphrase overuse
    catchphrase_issues = _check_catchphrase_overuse(content, packs, voice_profiles)
    extra_issues.extend(catchphrase_issues)
    
    # 2. Dialect level exceeded
    dialect_issues = _check_dialect_level_exceeded(content, packs, voice_profiles)
    extra_issues.extend(dialect_issues)
    
    # 3. Register mismatch
    register_issues = _check_register_mismatch(content, packs, voice_profiles)
    extra_issues.extend(register_issues)
    
    # ── Combine results ──
    all_issues = core_report.get("issues", []) if isinstance(core_report.get("issues"), list) else []
    
    # Convert extra issues to the same format as core issues
    for ei in extra_issues:
        all_issues.append({
            "code": ei["code"],
            "severity": ei["severity"],
            "message": ei["message"],
            "suggestion": ei.get("suggestion", ""),
            "confidence": ei.get("confidence", 0.65),
        })
    
    core_warnings = core_report.get("warnings", [])
    extra_warnings = [ei["message"] for ei in extra_issues]
    all_warnings = core_warnings + extra_warnings
    
    status = "WARN" if all_warnings else "PASS"
    
    return {
        "guard": "voice_pack_guard",
        "version": "v0.5.0",
        "status": status,
        "final_decision": status,
        "chapter_no": chapter_no,
        "core_voice_report": {
            "guard": core_report.get("guard"),
            "status": core_report.get("status"),
            "total_dialogues": core_report.get("total_dialogues", 0),
            "speaker_count": core_report.get("speaker_count", 0),
            "dialogue_ratio": core_report.get("dialogue_ratio", 0),
            "speaker_reports": core_report.get("speaker_reports", []),
            "narration_report": core_report.get("narration_report", {}),
            "character_voice_pass": core_report.get("character_voice_pass", True),
        },
        "extra_checks": {
            "catchphrase_overuse": catchphrase_issues,
            "dialect_level_exceeded": dialect_issues,
            "register_mismatch": register_issues,
        },
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

    parser = argparse.ArgumentParser(description="Voice Pack Guard v0.5.0")
    parser.add_argument("content_file", help="Chapter TXT file path")
    parser.add_argument("--chapter-no", type=int, default=1, help="Chapter number")
    parser.add_argument("--voice-profiles", default=None, help="Voice profiles JSON file")
    parser.add_argument("--voice-packs-dir", default=None, help="Voice packs directory")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    args = parser.parse_args()

    text = Path(args.content_file).read_text(encoding="utf-8")
    
    vp = []
    if args.voice_profiles and Path(args.voice_profiles).exists():
        vp = json.loads(Path(args.voice_profiles).read_text(encoding="utf-8"))
    
    report = run_voice_pack_check(
        text, args.chapter_no, vp, args.voice_packs_dir
    )
    
    print(json.dumps(report, ensure_ascii=False, indent=2))
    
    if args.output:
        p = Path(args.output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    
    if report["status"] == "WARN":
        print(f"\n[WARN] Voice pack: {len(report['warnings'])} issues")
    else:
        print(f"\n[OK] Voice pack check passed")
