"""story/health — Check story chain health (three-tier: OK / WARN / FAIL)."""
import json
from pathlib import Path
from typing import List

STORY_DIR = ".story"


def _resolve_story(project_root: Path) -> Path:
    """Resolve per-slot .story/ directory, fallback to project root."""
    try:
        ws_dir = project_root / "workspace"
        reg_file = ws_dir / "registry.json"
        if reg_file.exists():
            reg = json.loads(reg_file.read_text(encoding="utf-8"))
            active = reg.get("active_slot", "")
            if active:
                sd = ws_dir / active / ".story"
                if sd.exists():
                    return sd
    except Exception:
        pass
    return project_root / STORY_DIR


def check_health(project_root: Path) -> dict:
    """Run story health checks and return report with three-tier status.

    Tier rules:
      - word_count <= 0  →  FAIL
      - empty contract fields  →  WARN
      - missing commit  →  WARN
    """
    story = _resolve_story(project_root)
    warnings = []
    failures = []

    # Check story dir exists
    if not story.exists():
        return {
            "status": "FAIL",
            "story_dir": str(story),
            "issues": ["Story directory not initialized. Run: python novel.py story init"],
        }

    # Check master setting
    ms = story / "master_setting.json"
    if not ms.exists():
        warnings.append("master_setting.json missing")

    # Check memory files
    memory = story / "memory"
    for fname in ["characters.json", "promises.json", "world_facts.json"]:
        if not (memory / fname).exists():
            warnings.append(f"memory/{fname} missing")

    # Check for broken chapter chain
    chapters_dir = story / "chapters"
    commits_dir = story / "commits"
    if chapters_dir.exists() and commits_dir.exists():
        contracts = sorted(chapters_dir.glob("chapter_*_contract.json"))
        commits = sorted(commits_dir.glob("chapter_*_commit.json"))
        if len(contracts) > len(commits):
            warnings.append(
                f"Warning: {len(contracts)} contracts but only {len(commits)} commits — "
                f"{len(contracts)-len(commits)} uncommitted chapters"
            )
        # P0-3: Check for commits without matching contracts
        for cf in commits:
            ch_num = cf.stem.split("_")[1]
            matching_contract = chapters_dir / f"chapter_{ch_num}_contract.json"
            if not matching_contract.exists():
                failures.append(
                    f"commit {cf.stem} exists but no matching contract"
                )
        # Check for gaps
        contract_nums = [int(f.stem.split("_")[1]) for f in contracts]
        commit_nums = [int(f.stem.split("_")[1]) for f in commits]
        if contract_nums:
            expected = set(range(1, max(contract_nums) + 1))
            missing = expected - set(contract_nums)
            if missing:
                warnings.append(f"Missing contracts for chapters: {sorted(missing)}")

        # v0.6.5-clean4: Check contract field quality
        for cf in contracts:
            try:
                contract = json.loads(cf.read_text(encoding="utf-8"))
                ch = contract.get("chapter_no", "?")
                empty_fields = []
                if not contract.get("chapter_title", "").strip():
                    empty_fields.append("标题")
                if not contract.get("required_scene_goal", "").strip():
                    empty_fields.append("场景目标")
                if not contract.get("active_characters"):
                    empty_fields.append("活跃角色")
                if not contract.get("open_promises_to_keep"):
                    empty_fields.append("开放伏笔")
                if not contract.get("forbidden_changes"):
                    empty_fields.append("禁止变更")
                if not contract.get("target_scenes"):
                    empty_fields.append("目标场景")
                if empty_fields:
                    warnings.append(
                        f"合同 ch{ch} 字段为空: {', '.join(empty_fields)}"
                    )
            except Exception as e:
                warnings.append(f"无法解析合同: {cf.name} — {e}")

        # Check each commit for empty/invalid data
        for cf in commits:
            try:
                commit = json.loads(cf.read_text(encoding="utf-8"))
                ch = commit.get("chapter_no", "?")
                wc = commit.get("word_count", 0)
                title = commit.get("title", "")
                events = commit.get("events", [])
                guard = commit.get("guard_summary", {})
                has_only_placeholder = (
                    wc <= 0
                    and not events
                    and guard.get("note") == "手动生成"
                    and not guard.get("status")
                )
                if wc <= 0:
                    failures.append(
                        f"Empty commit: ch{ch} word_count={wc} — 章节文件可能未找到或为空"
                    )
                if not title:
                    warnings.append(f"Empty commit: ch{ch} title missing")
                if has_only_placeholder:
                    warnings.append(
                        f"Placeholder commit: ch{ch} 仅有占位数据，word_count=0, events=[]"
                    )
            except Exception as e:
                failures.append(f"Broken commit file: {cf.name} — {e}")

    # Check open promises
    promises_file = memory / "promises.json"
    if promises_file.exists():
        promises = json.loads(promises_file.read_text(encoding="utf-8"))
        open_promises = [p for p in promises if not p.get("resolved")]
        if open_promises:
            warnings.append(
                f"Open promises: {len(open_promises)} — "
                f"chapters: {set(p['chapter'] for p in open_promises)}"
            )

    # Check event ledger
    ledger = story / "events" / "event_ledger.jsonl"
    if ledger.exists():
        lines = ledger.read_text(encoding="utf-8").strip().split("\n")
        event_count = len([l for l in lines if l.strip()])
    else:
        event_count = 0

    # Determine tier
    if failures:
        status = "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "OK"

    # v0.6.5-clean3: Empty project is OK but should hint "未开始" not "未发现问题"
    contract_count = (
        len(list((story / "chapters").glob("chapter_*_contract.json")))
        if (story / "chapters").exists()
        else 0
    )
    commit_count = (
        len(list((story / "commits").glob("chapter_*_commit.json")))
        if (story / "commits").exists()
        else 0
    )
    empty_hints = []
    if contract_count == 0:
        empty_hints.append("当前还没有合同（未开始写作流程）")
    if commit_count == 0:
        empty_hints.append("当前还没有提交（未开始写作流程）")

    return {
        "status": status,
        "story_dir": str(story),
        "warnings": warnings,
        "failures": failures,
        "issues": failures + warnings,
        "contract_count": contract_count,
        "commit_count": commit_count,
        "event_count": event_count,
        "empty_hints": empty_hints,  # v0.6.5-clean3: 空项目提示
    }
