#!/usr/bin/env python3
"""
meme_pack_loader.py — Meme Pack YAML Loader
novel-pipeline-write-engine v0.5.0

Loads meme pack YAML files from:
  1. templates/meme_pack/   (template/reference packs)
  2. voice_packs/memes/     (existing meme packs)

Returns a list of dicts with normalized fields.
"""

import yaml
from pathlib import Path
from typing import Optional


def _project_root() -> Path:
    """Resolve project root from this file's location."""
    return Path(__file__).resolve().parent.parent.parent


def _resolve_search_dirs(root: Path, extra_dirs: list[str] = None) -> list[Path]:
    """Build ordered list of directories to search for meme pack YAMLs."""
    dirs = []
    # templates/meme_pack/ (new v0.5.0 template packs)
    templates_dir = root / "templates" / "meme_pack"
    if templates_dir.exists():
        dirs.append(templates_dir)
    # voice_packs/memes/ (existing meme packs)
    memes_dir = root / "voice_packs" / "memes"
    if memes_dir.exists():
        dirs.append(memes_dir)
    # Extra directories
    if extra_dirs:
        for d in extra_dirs:
            p = Path(d)
            if not p.is_absolute():
                p = root / p
            if p.exists():
                dirs.append(p)
    return dirs


def load_meme_packs(
    extra_dirs: list[str] = None,
    root: Path = None,
    pattern: str = "*.yaml",
) -> list[dict]:
    """
    Load all meme pack YAML files from configured directories.

    Args:
        extra_dirs: Additional directories to scan.
        root: Project root. Auto-detected if None.
        pattern: Glob pattern for YAML files (default: "*.yaml").

    Returns:
        List of meme pack dicts, each with at minimum:
        - pack_id: str
        - name: str
        - type: str
        - category: str
        - allowed_roles: list[str]
        - forbidden_roles: list[str]
        - trigger: dict
        - severity_limit: dict
        - frequency: dict
        - memes: list[dict]
        - banned_terms: list[str]
        - misuse_risk: list[str]
        - usage_policy: dict
        - examples: dict
        - metadata: dict
        - _source_file: str
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
                print(f"[meme_pack_loader] WARNING: Skipping {yaml_path}: {e}")
                continue
            except Exception as e:
                print(f"[meme_pack_loader] WARNING: Cannot read {yaml_path}: {e}")
                continue

            if not isinstance(data, dict):
                continue

            pid = data.get("pack_id", yaml_path.stem)
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                data["_source_file"] = str(yaml_path.resolve())
                packs.append(_normalize_pack(data))

    return packs


def _normalize_pack(data: dict) -> dict:
    """Normalize a meme pack dict with defaults for missing fields."""
    normalized = {
        "pack_id": data.get("pack_id", ""),
        "name": data.get("name", data.get("display_name", "")),
        "display_name": data.get("display_name", data.get("name", "")),
        "type": data.get("type", "meme_pack"),
        "category": data.get("category", "general"),
        "subcategory": data.get("subcategory", ""),
        "description": data.get("description", ""),
        "version": data.get("version", "0.5.0"),
        # Role bindings
        "allowed_roles": data.get("allowed_roles", []),
        "forbidden_roles": data.get("forbidden_roles", []),
        # Trigger config
        "trigger": data.get("trigger", {}),
        # Severity limit
        "severity_limit": data.get("severity_limit", {}),
        # Frequency control
        "frequency": data.get("frequency", {}),
        # Meme entries
        "memes": data.get("memes", []),
        # Banned terms
        "banned_terms": data.get("banned_terms", []),
        # Misuse risks
        "misuse_risk": data.get("misuse_risk", []),
        # Usage policy
        "usage_policy": data.get("usage_policy", {}),
        # Examples
        "examples": data.get("examples", {}),
        # Metadata
        "metadata": data.get("metadata", {}),
        # Source tracking
        "_source_file": data.get("_source_file", ""),
    }
    return normalized


def load_meme_pack_by_id(
    pack_id: str,
    extra_dirs: list[str] = None,
    root: Path = None,
) -> Optional[dict]:
    """
    Load a single meme pack by its pack_id.

    Returns None if not found.
    """
    packs = load_meme_packs(extra_dirs=extra_dirs, root=root)
    for pack in packs:
        if pack.get("pack_id") == pack_id:
            return pack
    return None


def list_meme_pack_ids(
    extra_dirs: list[str] = None,
    root: Path = None,
) -> list[str]:
    """List all available meme pack IDs."""
    packs = load_meme_packs(extra_dirs=extra_dirs, root=root)
    return sorted([p.get("pack_id", "") for p in packs if p.get("pack_id")])


# ============================================================
# CLI entry point for testing
# ============================================================
if __name__ == "__main__":
    import sys

    root = Path(__file__).resolve().parent.parent.parent
    print(f"Project root: {root}")
    print()

    packs = load_meme_packs(root=root)
    print(f"Loaded {len(packs)} meme pack(s):")
    for p in packs:
        pid = p.get("pack_id", "?")
        cat = p.get("category", "?")
        meme_count = len(p.get("memes", []))
        src = Path(p.get("_source_file", "")).name if p.get("_source_file") else "?"
        print(f"  [{cat}] {pid}  ({meme_count} memes)  ← {src}")

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
                    if k == "memes":
                        for m in v[:3]:
                            if isinstance(m, dict):
                                print(f"    - {m.get('meme_id', '?')}: {m.get('text', '?')[:40]}")
                else:
                    print(f"  {k}: {v}")
