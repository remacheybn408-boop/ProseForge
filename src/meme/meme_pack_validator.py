#!/usr/bin/env python3
"""
meme_pack_validator.py — Meme Pack YAML Validator
novel-pipeline-write-engine v0.5.0

Validates meme pack YAML files for:
  - Required fields present
  - Role lists are valid
  - Meme entries have required fields (meme_id, text)
  - Frequency values are in valid ranges
  - No duplicate pack_ids across packs
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


# === Required top-level fields for meme packs ===
REQUIRED_FIELDS = [
    "pack_id",
    "name",
]

# === Valid category values ===
VALID_CATEGORIES = [
    "general", "comedy", "satire", "situational", "cultural", "forbidden",
]

# === Valid meme types ===
VALID_MEME_TYPES = [
    "wordplay", "situational", "callback", "parody", "absurd",
]

# === Valid severity levels ===
VALID_SEVERITY_LEVELS = ["low", "medium", "high"]

# === Valid meme density levels ===
VALID_DENSITY_LEVELS = ["none", "light", "medium", "heavy"]

# === Valid meme frequency levels (per-meme) ===
VALID_MEME_FREQ = ["low", "medium", "high"]


def validate_meme_pack(pack: dict) -> ValidationResult:
    """
    Validate a single meme pack dict.

    Args:
        pack: Normalized meme pack dict (from meme_pack_loader).

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

    # 3. Category validation
    category = pack.get("category", "")
    if category and category not in VALID_CATEGORIES:
        result.warnings.append(ValidationError(
            pid, "category",
            f"'{category}' not in known categories: {VALID_CATEGORIES}",
            severity="warning"
        ))

    # 4. Role lists should be lists of strings
    for role_field in ["allowed_roles", "forbidden_roles"]:
        roles = pack.get(role_field, [])
        if roles is not None and not isinstance(roles, list):
            result.errors.append(ValidationError(
                pid, role_field,
                f"Must be a list, got {type(roles).__name__}"
            ))
        elif isinstance(roles, list):
            for i, r in enumerate(roles):
                if not isinstance(r, str):
                    result.warnings.append(ValidationError(
                        pid, f"{role_field}[{i}]",
                        f"Expected string, got {type(r).__name__}",
                        severity="warning"
                    ))

    # 5. Frequency validation
    freq = pack.get("frequency", {})
    if isinstance(freq, dict):
        for num_key in ["max_per_chapter", "max_per_1000_chars", "cooldown_chapters",
                        "cooldown_paragraphs", "overuse_warning_threshold"]:
            if num_key in freq:
                val = freq[num_key]
                if not isinstance(val, (int, float)):
                    result.errors.append(ValidationError(
                        pid, f"frequency.{num_key}",
                        f"Must be a number, got {type(val).__name__}"
                    ))
                elif val < 0:
                    result.errors.append(ValidationError(
                        pid, f"frequency.{num_key}",
                        f"Must be non-negative, got {val}"
                    ))

    # 6. Severity limit validation
    severity = pack.get("severity_limit", {})
    if isinstance(severity, dict):
        max_sev = severity.get("max_scene_seriousness", "")
        if max_sev and max_sev not in VALID_SEVERITY_LEVELS:
            result.warnings.append(ValidationError(
                pid, "severity_limit.max_scene_seriousness",
                f"'{max_sev}' not in {VALID_SEVERITY_LEVELS}",
                severity="warning"
            ))

    # 7. Usage policy validation
    usage = pack.get("usage_policy", {})
    if isinstance(usage, dict):
        default_level = usage.get("default_level", "")
        if default_level and default_level not in VALID_DENSITY_LEVELS:
            result.warnings.append(ValidationError(
                pid, "usage_policy.default_level",
                f"'{default_level}' not in {VALID_DENSITY_LEVELS}",
                severity="warning"
            ))

    # 8. Meme entries validation
    memes = pack.get("memes", [])
    if isinstance(memes, list):
        meme_ids_seen = set()
        for i, meme in enumerate(memes):
            if not isinstance(meme, dict):
                result.errors.append(ValidationError(
                    pid, f"memes[{i}]",
                    f"Expected dict, got {type(meme).__name__}"
                ))
                continue

            # meme_id required
            mid = meme.get("meme_id", "")
            if not mid:
                result.errors.append(ValidationError(
                    pid, f"memes[{i}].meme_id",
                    "meme_id is required for each meme entry"
                ))
            elif mid in meme_ids_seen:
                result.errors.append(ValidationError(
                    pid, f"memes[{i}].meme_id",
                    f"Duplicate meme_id '{mid}'"
                ))
            else:
                meme_ids_seen.add(mid)

            # text required
            if not meme.get("text", ""):
                result.errors.append(ValidationError(
                    pid, f"memes[{i}].text",
                    f"text is required for meme '{mid or '?'}'"
                ))

            # type validation
            mtype = meme.get("type", "")
            if mtype and mtype not in VALID_MEME_TYPES:
                result.warnings.append(ValidationError(
                    pid, f"memes[{i}].type",
                    f"'{mtype}' not in known meme types: {VALID_MEME_TYPES}",
                    severity="warning"
                ))

            # severity validation
            msev = meme.get("severity", "")
            if msev and msev not in VALID_SEVERITY_LEVELS:
                result.warnings.append(ValidationError(
                    pid, f"memes[{i}].severity",
                    f"'{msev}' not in {VALID_SEVERITY_LEVELS}",
                    severity="warning"
                ))

            # frequency validation
            mfreq = meme.get("frequency", "")
            if mfreq and mfreq not in VALID_MEME_FREQ:
                result.warnings.append(ValidationError(
                    pid, f"memes[{i}].frequency",
                    f"'{mfreq}' not in {VALID_MEME_FREQ}",
                    severity="warning"
                ))

            # context_required and context_forbidden should be lists
            for ctx_field in ["context_required", "context_forbidden"]:
                ctx_val = meme.get(ctx_field, [])
                if ctx_val is not None and not isinstance(ctx_val, list):
                    result.warnings.append(ValidationError(
                        pid, f"memes[{i}].{ctx_field}",
                        f"Expected list, got {type(ctx_val).__name__}",
                        severity="warning"
                    ))

            # variants should be a list
            variants = meme.get("variants", [])
            if variants is not None and not isinstance(variants, list):
                result.warnings.append(ValidationError(
                    pid, f"memes[{i}].variants",
                    f"Expected list, got {type(variants).__name__}",
                    severity="warning"
                ))
    elif memes is not None:
        result.errors.append(ValidationError(
            pid, "memes",
            f"Expected list, got {type(memes).__name__}"
        ))

    # 9. banned_terms should be a list of strings
    banned_terms = pack.get("banned_terms", [])
    if isinstance(banned_terms, list):
        for i, bt in enumerate(banned_terms):
            if not isinstance(bt, str):
                result.warnings.append(ValidationError(
                    pid, f"banned_terms[{i}]",
                    f"Expected string, got {type(bt).__name__}",
                    severity="warning"
                ))
    elif banned_terms is not None:
        result.warnings.append(ValidationError(
            pid, "banned_terms",
            f"Expected list, got {type(banned_terms).__name__}",
            severity="warning"
        ))

    # 10. misuse_risk should be a list of strings
    misuse = pack.get("misuse_risk", [])
    if isinstance(misuse, list):
        for i, mr in enumerate(misuse):
            if not isinstance(mr, str):
                result.warnings.append(ValidationError(
                    pid, f"misuse_risk[{i}]",
                    f"Expected string, got {type(mr).__name__}",
                    severity="warning"
                ))
    elif misuse is not None:
        result.warnings.append(ValidationError(
            pid, "misuse_risk",
            f"Expected list, got {type(misuse).__name__}",
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
        results.append(validate_meme_pack(pack))

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
    Convenience: load packs via meme_pack_loader then validate.

    Returns (packs, validation_results).
    """
    from src.meme.meme_pack_loader import load_meme_packs
    packs = load_meme_packs(extra_dirs=extra_dirs, root=root)
    results = validate_all_packs(packs)
    return packs, results


# ============================================================
# CLI entry point
# ============================================================
if __name__ == "__main__":
    import sys
    from src.meme.meme_pack_loader import load_meme_packs

    root = Path(__file__).resolve().parent.parent.parent
    packs = load_meme_packs(root=root)
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
