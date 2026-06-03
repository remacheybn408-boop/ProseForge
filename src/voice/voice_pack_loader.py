#!/usr/bin/env python3
"""
voice_pack_loader.py — Voice Pack YAML Loader
novel-pipeline-write-engine v0.5.0

Loads voice pack YAML files from:
  1. templates/voice_pack/  (template/reference packs)
  2. voice_packs/base/      (existing base packs)

Returns a list of dicts with normalized fields.
"""

import yaml
from pathlib import Path
from typing import Optional


def _project_root() -> Path:
    """Resolve project root from this file's location."""
    return Path(__file__).resolve().parent.parent.parent


def _resolve_search_dirs(root: Path, extra_dirs: list[str] = None) -> list[Path]:
    """Build ordered list of directories to search for voice pack YAMLs."""
    dirs = []
    # templates/voice_pack/ (new v0.5.0 template packs)
    templates_dir = root / "templates" / "voice_pack"
    if templates_dir.exists():
        dirs.append(templates_dir)
    # voice_packs/base/ (existing base packs)
    base_dir = root / "voice_packs" / "base"
    if base_dir.exists():
        dirs.append(base_dir)
    # Any extra directories
    if extra_dirs:
        for d in extra_dirs:
            p = Path(d)
            if not p.is_absolute():
                p = root / p
            if p.exists():
                dirs.append(p)
    return dirs


def load_voice_packs(
    extra_dirs: list[str] = None,
    root: Path = None,
    pattern: str = "*.yaml",
) -> list[dict]:
    """
    Load all voice pack YAML files from configured directories.

    Args:
        extra_dirs: Additional directories to scan (relative to project root
                    unless absolute).
        root: Project root. Auto-detected if None.
        pattern: Glob pattern for YAML files (default: "*.yaml").

    Returns:
        List of voice pack dicts, each with at minimum:
        - pack_id: str
        - name: str
        - type: str
        - role_type: str (if character voice pack)
        - tone: dict (if present)
        - sentence_style: dict (if present)
        - vocabulary: dict (if present)
        - dialogue_rules: dict (if present)
        - action_coupling: dict (if present)
        - narration_levels: dict (if present)
        - meme_policy: dict (if present)
        - register_bindings: dict (if present)
        - dialect_bindings: dict (if present)
        - meme_bindings: dict (if present)
        - usage_policy: dict (if present)
        - signature: dict (if present)
        - samples: dict (if present)
        - applicability: dict (if present)
        - metadata: dict (if present)
        - _source_file: str (absolute path to source YAML)
    """
    if root is None:
        root = _project_root()

    search_dirs = _resolve_search_dirs(root, extra_dirs)
    packs = []
    seen_ids = set()

    for search_dir in search_dirs:
        for yaml_path in sorted(search_dir.glob(pattern)):
            try:
                with open(yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                # Skip malformed YAML
                print(f"[voice_pack_loader] WARNING: Skipping {yaml_path}: {e}")
                continue
            except Exception as e:
                print(f"[voice_pack_loader] WARNING: Cannot read {yaml_path}: {e}")
                continue

            if not isinstance(data, dict):
                continue

            # Handle xianxia_character.yaml style bundle (contains sub-packs)
            if "type" in data and data.get("type") == "character_voice_bundle":
                sub_packs = _extract_sub_packs(data, yaml_path)
                for sp in sub_packs:
                    pid = sp.get("pack_id", "")
                    if pid and pid not in seen_ids:
                        seen_ids.add(pid)
                        packs.append(sp)
            else:
                pid = data.get("pack_id", yaml_path.stem)
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    data["_source_file"] = str(yaml_path.resolve())
                    packs.append(_normalize_pack(data))

    return packs


def _extract_sub_packs(bundle: dict, source_path: Path) -> list[dict]:
    """Extract individual character voice packs from a bundle YAML."""
    sub_packs = []
    # Known sub-pack keys in bundle format
    role_keys = [
        "protagonist", "elder", "villain", "merchant",
        "companion", "rival", "narrator", "female_observer",
        "best_friend",
    ]
    for key in role_keys:
        if key in bundle and isinstance(bundle[key], dict):
            sub = dict(bundle[key])
            sub["_source_file"] = str(source_path.resolve())
            sub["_bundle_id"] = bundle.get("pack_id", source_path.stem)
            sub_packs.append(_normalize_pack(sub))
    return sub_packs


def _normalize_pack(data: dict) -> dict:
    """Normalize a voice pack dict with defaults for missing fields."""
    normalized = {
        "pack_id": data.get("pack_id", ""),
        "name": data.get("name", data.get("display_name", "")),
        "display_name": data.get("display_name", data.get("name", "")),
        "type": data.get("type", "character_voice"),
        "role_type": data.get("role_type", ""),
        "subtype": data.get("subtype", ""),
        "description": data.get("description", ""),
        "version": data.get("version", "0.5.0"),
        # Complex fields — keep as-is or empty dict
        "tone": data.get("tone", {}),
        "sentence_style": data.get("sentence_style", {}),
        "vocabulary": data.get("vocabulary", {}),
        "dialogue_rules": data.get("dialogue_rules", {}),
        "action_coupling": data.get("action_coupling", {}),
        "narration_levels": data.get("narration_levels", {}),
        "meme_policy": data.get("meme_policy", {}),
        "register_bindings": data.get("register_bindings", {}),
        "dialect_bindings": data.get("dialect_bindings", {}),
        "meme_bindings": data.get("meme_bindings", {}),
        "usage_policy": data.get("usage_policy", {}),
        "signature": data.get("signature", {}),
        "samples": data.get("samples", {}),
        "applicability": data.get("applicability", {}),
        "metadata": data.get("metadata", {}),
        # Source tracking
        "_source_file": data.get("_source_file", ""),
        "_bundle_id": data.get("_bundle_id", ""),
    }
    return normalized


def load_voice_pack_by_id(
    pack_id: str,
    extra_dirs: list[str] = None,
    root: Path = None,
) -> Optional[dict]:
    """
    Load a single voice pack by its pack_id.

    Returns None if not found.
    """
    packs = load_voice_packs(extra_dirs=extra_dirs, root=root)
    for pack in packs:
        if pack.get("pack_id") == pack_id:
            return pack
    return None


def list_voice_pack_ids(
    extra_dirs: list[str] = None,
    root: Path = None,
) -> list[str]:
    """List all available voice pack IDs."""
    packs = load_voice_packs(extra_dirs=extra_dirs, root=root)
    return sorted([p.get("pack_id", "") for p in packs if p.get("pack_id")])


# ============================================================
# CLI entry point for testing
# ============================================================
if __name__ == "__main__":
    import sys

    root = Path(__file__).resolve().parent.parent.parent
    print(f"Project root: {root}")
    print()

    packs = load_voice_packs(root=root)
    print(f"Loaded {len(packs)} voice pack(s):")
    for p in packs:
        pid = p.get("pack_id", "?")
        role = p.get("role_type", "?")
        src = Path(p.get("_source_file", "")).name if p.get("_source_file") else "?"
        print(f"  [{role}] {pid}  ← {src}")

    if "--verbose" in sys.argv:
        for p in packs:
            print(f"\n--- {p.get('pack_id')} ---")
            for k, v in p.items():
                if k.startswith("_"):
                    continue
                if isinstance(v, dict):
                    print(f"  {k}:")
                    for sk, sv in v.items():
                        val_str = str(sv)[:80]
                        print(f"    {sk}: {val_str}")
                elif isinstance(v, list):
                    print(f"  {k}: [{len(v)} items]")
                else:
                    print(f"  {k}: {v}")
