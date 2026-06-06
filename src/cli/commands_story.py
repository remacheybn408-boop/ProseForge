"""src/cli/commands_story.py — Story contract commands v0.7.0"""

from src.cli.shared import (PROJECT_ROOT, SCRIPTS_DIR, _load_project_config,
    _get_default_slug, _get_novels_root, _resolve_post_context,
    _resolve_chapter_path, _story_exists, _story_missing_msg, _get_workspace_dir,
    find_chapter_file,
    _get_active_db_path, _get_outline_manager, _check_outline_gate, _get_story_dir)
import sys
import json
from pathlib import Path
from scripts.config_utils import resolve_path


def cmd_story(args):
    """Story contract system: init, contract, commit, health."""
    from scripts.story import story_init, contract_builder, commit_builder, story_health

    action = getattr(args, "story_action", None)

    if action == "init":
        already_existed = _story_exists()
        result = story_init.init_story(PROJECT_ROOT)
        if already_existed:
            print(f"  .story/ 已存在，检查提交记录...")
        else:
            print(f"  [OK] .story/ 已初始化")
        for item in result.get("created", []):
            print(f"    + {item}")
        migrated = result.get("migrated", {})
        if migrated.get("migrated", 0) > 0:
            print(f"\n  [OK] 从 {migrated['migrated']} 个 commit 迁移生成了合同文件")
            if migrated.get("skipped"):
                print(f"  跳过: {', '.join(migrated['skipped'][:10])}")
        if not result.get("created") and not migrated.get("migrated"):
            print("  已是最新，无需操作。")
        print(f"\n  目录: {result['story_dir']}")
        return 0

    elif action == "contract":
        if not _story_exists():
            print(f"  {_story_missing_msg()}")
            return 1
        # No-outline gate
        if _check_outline_gate():
            return 1
        chapter_no = int(getattr(args, "chapter_no", "1") or "1")
        # Try loading previous commit for context
        prev_commit = None
        if chapter_no > 1:
            prev_commit_path = _get_story_dir() / "commits" / f"chapter_{chapter_no-1:03d}_commit.json"
            if prev_commit_path.exists():
                import json as _json
                prev_commit = _json.loads(prev_commit_path.read_text(encoding="utf-8"))

        contract = contract_builder.build_contract(PROJECT_ROOT, chapter_no, prev_commit=prev_commit)
        saved = contract_builder.save_contract(PROJECT_ROOT, chapter_no, contract)
        print(f"  [OK] 第{chapter_no}章合同已生成")
        print(f"  保存至: {saved}")
        print(f"  开放伏笔: {len(contract.get('open_promises_to_keep', []))} 个")
        print(f"  活跃角色: {len(contract.get('active_characters', []))} 个")
        return 0

    elif action == "commit":
        if not _story_exists():
            print(f"  {_story_missing_msg()}")
            return 1
        chapter_no = int(getattr(args, "chapter_no", "1") or "1")

        # P0-2: Verify contract exists before allowing commit
        contract_path = _get_story_dir() / "chapters" / f"chapter_{chapter_no:03d}_contract.json"
        if not contract_path.exists():
            print(f"  [FAIL] 第{chapter_no}章没有合同，不能提交。请先执行：python novel.py story contract {chapter_no}")
            return 1

        # Read real chapter file — use config's novels_root
        novels_dir = PROJECT_ROOT / "novels"
        if (PROJECT_ROOT / "config.json").exists():
            import json as _json
            try:
                cfg = _json.loads((PROJECT_ROOT / "config.json").read_text(encoding="utf-8"))
                nr = cfg.get("novels_root") or cfg.get("paths", {}).get("novels_root", "novels")
                novels_dir = Path(nr) if Path(nr).is_absolute() else PROJECT_ROOT / nr
            except: pass
        from src.cli.shared import _get_default_slug
        slug = _get_default_slug()
        slugs_to_try = [slug]
        try:
            if (PROJECT_ROOT / "config.json").exists():
                cfg2 = _json.loads((PROJECT_ROOT / "config.json").read_text(encoding="utf-8"))
                ds = cfg2.get("default_novel_slug") or cfg2.get("novel", {}).get("default_slug", "")
                if ds and ds != slug:
                    slugs_to_try.append(ds)
        except: pass
        import re as _re
        ch_fp = None
        # Search multiple possible locations
        search_dirs = []
        for s in slugs_to_try:
            search_dirs.append(Path(_resolve_chapter_path(s)))  # v0.8.0: volume-aware
            search_dirs.append(novels_dir / s / "第01卷")         # legacy fallback
            search_dirs.append(novels_dir / s)
            search_dirs.append(PROJECT_ROOT / "novels" / s / "第01卷")
        for sd in search_dirs:
            if not sd.exists(): continue
            ch_fp = find_chapter_file(int(chapter_no), sd)
            if ch_fp:
                break
        wc = 0
        ch_title = f"第{chapter_no}章"
        if ch_fp and ch_fp.exists():
            text = ch_fp.read_text(encoding="utf-8")
            wc = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf')
            ch_title = ch_fp.stem.replace("_", " ")

        commit = commit_builder.build_commit(
            PROJECT_ROOT, chapter_no,
            chapter_title=ch_title,
            word_count=wc,
            guard_summary={"note": "手动生成"} if wc == 0 else {},
        )
        saved = commit_builder.save_commit(PROJECT_ROOT, chapter_no, commit)
        print(f"  [OK] 第{chapter_no}章提交记录已生成")
        print(f"  保存至: {saved}")
        return 0

    elif action == "health":
        if not _story_exists():
            print(f"  {_story_missing_msg()}")
            return 1
        report = story_health.check_health(PROJECT_ROOT)
        print("=" * 60)
        print("  故事链健康检查")
        print("=" * 60)
        status = report["status"]
        print(f"  状态: {status}")
        print(f"  合同数: {report.get('contract_count', 0)}")
        print(f"  提交数: {report.get('commit_count', 0)}")
        print(f"  事件数: {report.get('event_count', 0)}")
        warnings = report.get("warnings", [])
        failures = report.get("failures", [])
        if failures:
            print(f"\n  失败 ({len(failures)}):")
            for iss in failures:
                print(f"    ✗ {iss}")
        if warnings:
            print(f"\n  警告 ({len(warnings)}):")
            for iss in warnings:
                print(f"    ⚠ {iss}")
        if not warnings and not failures:
            empty_hints = report.get("empty_hints", [])
            if empty_hints:
                print(f"\n  💡 提示:")
                for hint in empty_hints:
                    print(f"    · {hint}")
            else:
                print("\n  未发现问题。")
        print()
        return 0 if status == "OK" else (1 if status == "FAIL" else 0)

    elif action == "arc":
        from src.cli.commands_arc import cmd_arc
        return cmd_arc(args)

    else:
        print("Usage: python novel.py story {init|contract|commit|health|arc}")
        return 1
