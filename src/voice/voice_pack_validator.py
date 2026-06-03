#!/usr/bin/env python3
"""
voice_pack_validator.py — Voice Pack YAML Validator
novel-pipeline-write-engine v0.5.0

Validates voice pack YAML files for:
  - Required fields present
  - Value ranges are valid (0.0-1.0 for emotion_range, 0-3 for levels)
  - No duplicate pack_ids across packs
  - Structural integrity of nested fields
"""

from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class ValidationError:
    """A single validation issue."""
    pack_id: str
    field: str
    message: str
    severity: str = "error"  # error | warning


@dataclass
class ValidationResult:
    """Aggregate validation result."""
    pack_id: str = ""
    source_file: str = ""
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def error_count(self) -> int:
        return len(self.errors) + len(self.warnings)


# === Required top-level fields for character voice packs ===
REQUIRED_FIELDS = [
    "pack_id",
    "name",
    "role_type",
]

# === Fields that should be dicts ===
DICT_FIELDS = [
    "tone",
    "sentence_style",
    "vocabulary",
    "dialogue_rules",
    "action_coupling",
    "narration_levels",
    "meme_policy",
    "register_bindings",
    "dialect_bindings",
    "meme_bindings",
    "usage_policy",
    "signature",
    "samples",
    "applicability",
    "metadata",
]

# === Valid emotion keys ===
VALID_EMOTIONS = [
    "calm", "angry", "sad", "joy", "fear", "ironic", "warm", "cold",
]

# === Valid narration level keys ===
VALID_NARRATION_LEVELS = [
    "dialect_level", "meme_level", "english_level", "wenyan_level",
]


def validate_voice_pack(pack: dict) -> ValidationResult:
    """
    Validate a single voice pack dict.

    Args:
        pack: Normalized voice pack dict (from voice_pack_loader).

    Returns:
        ValidationResult with all errors and warnings.
    """
    pid = pack.get("pack_id", "<unknown>")
    src = pack.get("_source_file", "")
    result = ValidationResult(pack_id=pid, source_file=src)

    # 1. Required fields
    for field in REQUIRED_FIELDS:
        if field not in pack or not pack.get(field):
            result.errors.append(ValidationError(
                pid, field, f"Required field '{field}' is missing or empty"
            ))

    # 2. pack_id must be a non-empty string
    if not isinstance(pack.get("pack_id"), str) or not pack.get("pack_id", "").strip():
        result.errors.append(ValidationError(
            pid, "pack_id", "pack_id must be a non-empty string"
        ))

    # 3. Dict fields should be dicts if present
    for field in DICT_FIELDS:
        if field in pack and pack[field] is not None:
            if not isinstance(pack[field], dict):
                result.errors.append(ValidationError(
                    pid, field, f"'{field}' must be a dictionary, got {type(pack[field]).__name__}"
                ))

    # 4. Tone validation
    tone = pack.get("tone", {})
    if isinstance(tone, dict):
        # emotion_range values must be 0.0-1.0
        emotion_range = tone.get("emotion_range", {})
        if isinstance(emotion_range, dict):
            for ek, ev in emotion_range.items():
                if ek not in VALID_EMOTIONS:
                    result.warnings.append(ValidationError(
                        pid, f"tone.emotion_range.{ek}",
                        f"Unknown emotion key '{ek}'. Expected one of: {VALID_EMOTIONS}",
                        severity="warning"
                    ))
                if not isinstance(ev, (int, float)):
                    result.errors.append(ValidationError(
                        pid, f"tone.emotion_range.{ek}",
                        f"Emotion value must be a number, got {type(ev).__name__}"
                    ))
                elif ev < 0.0 or ev > 1.0:
                    result.errors.append(ValidationError(
                        pid, f"tone.emotion_range.{ek}",
                        f"Emotion value {ev} is out of range [0.0, 1.0]"
                    ))

        # forbidden_tones should be a list of strings
        forbidden_tones = tone.get("forbidden_tones", [])
        if isinstance(forbidden_tones, list):
            for i, ft in enumerate(forbidden_tones):
                if not isinstance(ft, str):
                    result.warnings.append(ValidationError(
                        pid, f"tone.forbidden_tones[{i}]",
                        f"Expected string, got {type(ft).__name__}",
                        severity="warning"
                    ))

    # 5. Narration levels validation (0-3 range)
    narration_levels = pack.get("narration_levels", {})
    if isinstance(narration_levels, dict):
        for nl_key in VALID_NARRATION_LEVELS:
            if nl_key in narration_levels:
                val = narration_levels[nl_key]
                if not isinstance(val, (int, float)):
                    result.errors.append(ValidationError(
                        pid, f"narration_levels.{nl_key}",
                        f"Must be a number, got {type(val).__name__}"
                    ))
                elif val < 0 or val > 3:
                    result.errors.append(ValidationError(
                        pid, f"narration_levels.{nl_key}",
                        f"Value {val} is out of range [0, 3]"
                    ))

    # 6. Meme policy validation
    meme_policy = pack.get("meme_policy", {})
    if isinstance(meme_policy, dict):
        allowed_level = meme_policy.get("allowed_level", "")
        valid_levels = ["none", "light", "medium", "heavy"]
        if allowed_level and allowed_level not in valid_levels:
            result.warnings.append(ValidationError(
                pid, "meme_policy.allowed_level",
                f"'{allowed_level}' not in {valid_levels}",
                severity="warning"
            ))

    # 7. Usage policy validation
    usage_policy = pack.get("usage_policy", {})
    if isinstance(usage_policy, dict):
        max_sig = usage_policy.get("max_signature_lines_per_chapter")
        if max_sig is not None:
            if not isinstance(max_sig, (int, float)) or max_sig < 0:
                result.errors.append(ValidationError(
                    pid, "usage_policy.max_signature_lines_per_chapter",
                    f"Must be a non-negative number, got {max_sig}"
                ))

    # 8. Action coupling validation
    action_coupling = pack.get("action_coupling", {})
    if isinstance(action_coupling, dict):
        if "must_pair_dialogue_with_action" in action_coupling:
            val = action_coupling["must_pair_dialogue_with_action"]
            if not isinstance(val, bool):
                result.warnings.append(ValidationError(
                    pid, "action_coupling.must_pair_dialogue_with_action",
                    f"Expected boolean, got {type(val).__name__}",
                    severity="warning"
                ))

    return result


def validate_all_packs(packs: list[dict]) -> list[ValidationResult]:
    """
    Validate all packs, including cross-pack checks for duplicate IDs.

    Returns list of ValidationResult, one per pack.
    """
    results = []

    # Per-pack validation
    for pack in packs:
        results.append(validate_voice_pack(pack))

    # Cross-pack: duplicate pack_ids
    seen_ids = {}
    for i, pack in enumerate(packs):
        pid = pack.get("pack_id", "")
        if not pid:
            continue
        if pid in seen_ids:
            prev_idx = seen_ids[pid]
            msg = f"Duplicate pack_id '{pid}' (also in pack #{prev_idx + 1})"
            results[i].errors.append(ValidationError(pid, "pack_id", msg))
        else:
            seen_ids[pid] = i

    return results


def validate_from_loader(
    extra_dirs: list[str] = None,
    root: Path = None,
) -> tuple[list[dict], list[ValidationResult]]:
    """
    Convenience: load packs via voice_pack_loader then validate.

    Returns (packs, validation_results).
    """
    # Import here to avoid circular dependency
    from src.voice.voice_pack_loader import load_voice_packs
    packs = load_voice_packs(extra_dirs=extra_dirs, root=root)
    results = validate_all_packs(packs)
    return packs, results


# ============================================================
# CLI entry point
# ============================================================
if __name__ == "__main__":
    import sys
    from src.voice.voice_pack_loader import load_voice_packs

    root = Path(__file__).resolve().parent.parent.parent
    packs = load_voice_packs(root=root)
    results = validate_all_packs(packs)

    total_errors = 0
    total_warnings = 0

    for r in results:
        status = "OK" if r.is_valid else "FAIL"
        tag = ""
        if not r.is_valid:
            tag = " [ERRORS]"
        elif r.has_warnings:
            tag = " [WARNINGS]"
        print(f"[{status}] {r.pack_id}{tag}  ← {Path(r.source_file).name if r.source_file else '?'}")

        for e in r.errors:
            print(f"  ERROR: {e.field}: {e.message}")
            total_errors += 1
        for w in r.warnings:
            print(f"  WARNING: {w.field}: {w.message}")
            total_warnings += 1

    print(f"\nTotal: {len(packs)} pack(s), {total_errors} error(s), {total_warnings} warning(s)")

    sys.exit(1 if total_errors > 0 else 0)
