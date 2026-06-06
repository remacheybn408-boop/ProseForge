"""src/cli/commands_pipeline.py — Pipeline commands (pre/post/review/export) v0.7.0"""

from src.cli.shared import (PROJECT_ROOT, SCRIPTS_DIR, _load_project_config,
    _get_default_slug, _get_novels_root, _resolve_post_context,
    _resolve_chapter_path, _story_exists, find_chapter_file,
    _get_workspace_dir, _get_active_db_path, _check_outline_gate)
import json
import sys
from pathlib import Path
from scripts.config_utils import resolve_path


def cmd_pre(chapter_no: str = None, slug: str = None, volume_no: str = None):
    """Run pre-write gate for a chapter."""
    cfg = PROJECT_ROOT / "config.json"
    if not chapter_no:
        print("Usage: python novel.py pre <chapter_no> [--slug <slug>] [--volume <n>]")
        return 1
    # No-outline gate
    if _check_outline_gate():
        return 1
    print(f"  Running pre-write gate for chapter {chapter_no}...")
    # v0.6.7-clean7: resolve slug from active slot
    vno = int(volume_no) if volume_no else 1
    chapters_dir, slot_db_path, resolved_slug, resolved_title = _resolve_post_context(cfg, vno)
    slug = slug or resolved_slug
    try:
        import subprocess
        cmd = [sys.executable, str(SCRIPTS_DIR / "chapter_pipeline.py"), "pre", str(chapter_no),
               "--config", str(cfg), "--novel-slug", slug,
               "--novel-title", resolved_title]
        if volume_no: cmd.extend(["--volume-no", str(volume_no)])
        if slot_db_path: cmd.extend(["--db-path", slot_db_path])
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), timeout=120)
        return result.returncode
    except Exception as e:
        print(f"  [ERROR] {e}")
        return 1


def cmd_post(chapter_no: str = None, slug: str = None, volume_no: str = None, file_path: str = None, story: bool = False, no_jury: bool = False, skip_pre: bool = False):
    """Post-write: run guards and ingest."""
    cfg = PROJECT_ROOT / "config.json"
    if not chapter_no and not file_path:
        print("Usage: python novel.py post <chapter_no> [--file <path>] [--slug <slug>] [--story]")
        return 1
    # No-outline gate
    if _check_outline_gate():
        return 1
    if file_path:
        print(f"  Running post-write guards for file: {file_path}")
    else:
        print(f"  Running post-write guards for chapter {chapter_no}...")

    # v0.6.7-clean6: Resolve from active slot, fallback to config
    vno = int(volume_no) if volume_no else 1
    chapters_dir, slot_db_path, resolved_slug, resolved_title = _resolve_post_context(cfg, vno)
    slug = slug or resolved_slug

    try:
        import subprocess, json as _json
        from datetime import datetime as _dt
        ch_no_str = str(chapter_no) if chapter_no else "1"
        ch_int = int(ch_no_str)
        state_path = PROJECT_ROOT / "exports" / "pipeline_state" / f"chapter_{ch_int:03d}_state.json"
        skip_pre = skip_pre  # use parameter, not undefined args
        if not state_path.exists() and not skip_pre:
            # Bootstrap minimal state — post doesn't need full pre output
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state = {"allowed_to_write": True, "genre": "", "chapter_no": ch_int,
                     "timestamp": _dt.now().isoformat(), "_bootstrapped": True}
            state_path.write_text(_json.dumps(state, ensure_ascii=False), encoding="utf-8")
            print(f"  [pre] 已生成最小任务卡状态 (post 无需完整 pre)")
        cmd = [sys.executable, str(SCRIPTS_DIR / "chapter_pipeline.py"), "post",
               str(chapter_no) if chapter_no else "1",
               "--config", str(cfg), "--novel-slug", slug,
               "--novel-title", resolved_title]
        if volume_no: cmd.extend(["--volume-no", str(volume_no)])
        if file_path:
            cmd.extend(["--chapters-dir", str(Path(file_path).parent)])
        else:
            cmd.extend(["--chapters-dir", chapters_dir])
        if slot_db_path:
            cmd.extend(["--db-path", slot_db_path])
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), timeout=300)
        if result.returncode != 0:
            return result.returncode

        # Auto-generate story commit if --story flag is set and .story/ exists
        if story and _story_exists():
            print()
            print("  [story] 自动生成提交记录...")
            try:
                from scripts.story import commit_builder
                ch_no = int(chapter_no) if chapter_no else 1

                # Try to read word count from the chapter file
                wc = 0
                if file_path:
                    ch_fp = Path(file_path)
                else:
                    ch_dir = Path(chapters_dir)
                    if not ch_dir.exists():
                        ch_dir = Path(_resolve_chapter_path(slug, vno))
                    ch_fp = find_chapter_file(ch_no, ch_dir)

                if ch_fp and ch_fp.exists():
                    text = ch_fp.read_text(encoding="utf-8")
                    wc = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf')

                # Try reading guard report for summary
                guard_summary = {}
                try:
                    import json as _json
                    cfg_data = _load_project_config()
                    reports_dir = resolve_path(PROJECT_ROOT, cfg_data.get("reports_root", "./exports/reports"))
                    if reports_dir.exists():
                        reports = sorted(reports_dir.rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
                        if reports:
                            rpt = _json.loads(reports[0].read_text(encoding="utf-8"))
                            guard_summary = {
                                "status": rpt.get("status", rpt.get("overall_status", "?")),
                                "issues": len(rpt.get("issues", [])),
                            }
                except Exception:
                    pass

                commit = commit_builder.build_commit(
                    PROJECT_ROOT, ch_no,
                    chapter_title=f"第{ch_no}章",
                    word_count=wc,
                    guard_summary=guard_summary,
                )
                saved = commit_builder.save_commit(PROJECT_ROOT, ch_no, commit)
                print(f"  [story] 第{ch_no}章提交记录已保存: {Path(saved).name}")
            except Exception as e:
                print(f"  [story] 提交生成失败: {e}")

        # Auto-run agent jury after post (default ON, use --no-jury to skip)
        if not no_jury and result.returncode == 0:
            try:
                print()
                print("  [jury] 自动运行 Agent 陪审团...")
                ch_no = int(chapter_no) if chapter_no else 1
                import argparse as _ap
                from src.cli.commands_agents import cmd_agents
                _ns = _ap.Namespace(
                    agents_action="review", chapter_no=str(ch_no),
                    mode="light", slug=slug, genre=None, style=None
                )
                cmd_agents(_ns)
            except Exception as e:
                print(f"  [jury] 跳过: {e}")

        # Hint for revise if high-confidence tasks exist
        if result.returncode == 0:
            _dedup_path = PROJECT_ROOT / "exports" / "reports" / f"chapter_{int(chapter_no) if chapter_no else 1:03d}_deduplicated_report.json"
            if _dedup_path.exists():
                try:
                    _dedup = json.loads(_dedup_path.read_text(encoding="utf-8"))
                    _tasks = _dedup.get("top_revision_tasks", [])
                    if _tasks and _tasks[0].get("confidence", 0) >= 0.7:
                        print(f"\n  💡 检测到 {len(_tasks)} 个高置信度改稿建议")
                        print(f"     运行: python novel.py revise {chapter_no}")
                except Exception:
                    pass

        return result.returncode
    except Exception as e:
        print(f"  [ERROR] {e}")
        return 1


def cmd_revise(chapter_no: str = None, mode: str = "controlled",
               approve: bool = False, slug: str = None, volume_no: str = None):
    """改稿闭环: 读取 deduplicated_report → 生成任务 → 规划补丁 → 改写 → diff"""
    cfg = PROJECT_ROOT / "config.json"
    if not chapter_no:
        print("Usage: python novel.py revise <chapter_no> [--mode controlled|suggest] [--approve] [--slug <slug>]")
        return 1

    vno = int(volume_no) if volume_no else 1
    ctx = _resolve_post_context(cfg, vno)
    if not ctx:
        return 1
    chapters_dir, db_path, resolved_slug, title = ctx
    slug = slug or resolved_slug
    try:
        ch = int(chapter_no)
    except ValueError:
        print(f"  ❌ 无效章节号: '{chapter_no}' (必须为数字)")
        print(f"  用法: python novel.py revise <chapter_no> [--mode controlled|suggest] [--approve]")
        return 1

    # Find chapter file
    ch_dir = Path(chapters_dir)
    ch_fp = find_chapter_file(ch, ch_dir)
    if not ch_fp:
        print(f"  ❌ 章节文件未找到: {ch_dir} (第{ch}章)")
        if db_path:
            print(f"    提示: 确认章节文件路径是否正确, 或手动指定 --slug")
        return 1
    ch_path = ch_fp

    # Read deduplicated_report
    report_dir = PROJECT_ROOT / "exports" / "reports"
    report_path = report_dir / f"chapter_{ch:03d}_deduplicated_report.json"
    if not report_path.exists():
        print(f"  ❌ 未找到去重报告, 请先执行 post")
        print(f"     {report_path}")
        return 1

    print(f"\n{'='*60}")
    print(f"REVISE — 第{ch}章 | 模式: {mode}")
    print(f"  源文件: {ch_path}")
    print(f"  报告: {report_path}")
    print(f"{'='*60}")

    out_dir = Path("exports") / "revision" / f"chapter_{ch:03d}"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from scripts.revision_loop_controller import run_controlled_mode, DEFAULT_CONFIG
        config = dict(DEFAULT_CONFIG)
        config["require_user_approval"] = not approve
        config["auto_overwrite_source"] = approve
        config["auto_ingest_revised"] = approve

        result = run_controlled_mode(str(ch_path), str(report_path), str(out_dir), config)

        if result["status"] == "OK":
            if "outputs" not in result or not result["outputs"]:
                print(f"\n✅ 无需修订 — {result.get('message', '没有高置信度改稿任务')}")
                return 0
            print(f"\n✅ 修订完成")
            print(f"  修订稿: {result['outputs']['revised_draft']}")
            print(f"  差异报告: {result['outputs']['diff_report']}")
            if result.get("recommendation"):
                print(f"  建议: {result['recommendation']}")

            # Show diff summary
            diff_path = result["outputs"].get("diff_report")
            if diff_path and Path(diff_path).exists():
                diff = json.loads(Path(diff_path).read_text(encoding="utf-8"))
                changed = diff.get("summary", {}).get("changed_paragraphs", 0)
                unchanged = diff.get("summary", {}).get("unchanged_ratio", 1)
                print(f"  改动: {changed} 段, 未改比例: {unchanged:.0%}")
                for rf in diff.get("risk_flags", []):
                    print(f"  ⚠️ {rf}")

            if not approve:
                print(f"\n  下一步: 查看 {result['outputs']['revised_draft']}")
                print(f"  满意后覆盖原文再执行: python novel.py post {chapter_no}")
        else:
            print(f"\n❌ 修订失败: {result.get('reason', result.get('error', '未知'))}")

        return 0 if result["status"] == "OK" else 1

    except ImportError as e:
        print(f"  [WARN] 修订模块未就绪: {e}")
        print(f"  提示: 手动编辑 {ch_path} 后运行 post")
        return 1


def cmd_review(chapter_no: str = None, slug: str = None, volume_no: str = None):
    """Run guard review on a chapter."""
    cfg = PROJECT_ROOT / "config.json"
    if not chapter_no:
        print("Usage: python novel.py review <chapter_no> [--slug <slug>] [--volume <n>]")
        return 1
    print(f"  Running review for chapter {chapter_no}...")
    vno = int(volume_no) if volume_no else 1
    slug = slug or _get_default_slug(cfg)
    try:
        import subprocess
        cmd = [sys.executable, str(SCRIPTS_DIR / "chapter_pipeline.py"), "review", str(chapter_no),
               "--config", str(cfg), "--novel-slug", slug]
        if volume_no: cmd.extend(["--volume-no", str(volume_no)])
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), timeout=300)
        return result.returncode
    except Exception as e:
        print(f"  [ERROR] {e}")
        return 1


def cmd_export(slug: str = None, fmt: str = "md"):
    """Export novel to a single file, v0.6.7-clean7: 用小说名建文件夹."""
    # v0.6.7-clean7: 无slug时自动从活跃slot读取
    if not slug:
        try:
            import json as _j, sqlite3 as _s
            ws = PROJECT_ROOT / "workspace"
            reg = _j.loads((ws / "registry.json").read_text(encoding="utf-8"))
            active = reg.get("active_slot", "")
            slot_db = ws / active / "novel.db"
            if slot_db.exists():
                conn = _s.connect(str(slot_db))
                row = conn.execute("SELECT slug FROM novels LIMIT 1").fetchone()
                conn.close()
                if row:
                    slug = row[0]
        except Exception:
            pass
    if not slug:
        print("用法: python novel.py export [--slug <标识>] [--format txt|md]")
        print()
        print("  示例:")
        print("    python novel.py export --slug demo_novel --format md")
        print("    python novel.py export --slug demo_novel --format txt")
        return 1
    fmt = fmt or "md"
    ext = ".txt" if fmt == "txt" else ".md"

    # v0.6.7-clean7: 从活跃 slot DB 读取标题 + DB 路径
    import sqlite3 as _sql
    title = slug
    slot_db_path = None
    chapters_dir = None
    try:
        ws = PROJECT_ROOT / "workspace"
        reg_file = ws / "registry.json"
        if reg_file.exists():
            import json as _json
            reg = _json.loads(reg_file.read_text(encoding="utf-8"))
            active = reg.get("active_slot", "")
            slot_db = ws / active / "novel.db"
            if slot_db.exists():
                slot_db_path = slot_db
                chapters_dir = ws / active / "chapters"
                conn = _sql.connect(str(slot_db))
                row = conn.execute("SELECT title FROM novels WHERE slug=?", (slug,)).fetchone()
                if row:
                    title = row[0]
                conn.close()
    except Exception:
        pass

    # 输出到小说自己的文件夹：novels_root/{书名}/{书名}.txt
    cfg = _load_project_config()
    nr = Path(_get_novels_root())
    out_dir = nr / title
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{title}{ext}"

    print(f"  正在导出小说「{title}」(slug={slug})，格式: {fmt}...")
    import subprocess
    try:
        args = [sys.executable, str(SCRIPTS_DIR / "export_novel.py"),
                "--slug", slug, "--config", str(PROJECT_ROOT / "config.json"), "--format", fmt,
                "--output", str(out_path)]
        if slot_db_path:
            args.extend(["--db-path", str(slot_db_path)])
        if chapters_dir:
            args.extend(["--chapters-dir", str(chapters_dir)])
        result = subprocess.run(args, cwd=str(PROJECT_ROOT), timeout=60, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        if result.returncode == 0:
            print(f"  ✅ 已导出全书到 {out_path}")
            # 同时拆分每章为独立文件
            full_text = Path(out_path).read_text(encoding="utf-8")
            import re as _re
            # 找所有章节标题位置
            _matches = list(_re.finditer(r'^第(\d+)章\s+(.+)$', full_text, _re.MULTILINE))
            count = 0
            for i, m in enumerate(_matches):
                ch_num = int(m.group(1))
                ch_title = _re.sub(r'\s*\{#chapter-\d+\}', '', m.group(2).strip())[:20]
                start = m.end()
                end = _matches[i+1].start() if i+1 < len(_matches) else len(full_text)
                chapter_text = full_text[start:end].strip()
                full_chapter = f"第{ch_num}章 {ch_title}\n\n{chapter_text}\n"
                ch_file = out_dir / f"第{ch_num}章_{ch_title}.txt"
                ch_file.write_text(full_chapter, encoding="utf-8")
                count += 1
            if count:
                print(f"  ✅ 已拆分 {count} 章到 {out_dir}/")
        else:
            print(f"  ⚠️ 导出未完成（退出码: {result.returncode}）")
        return result.returncode
    except subprocess.TimeoutExpired:
        print(f"  ⏱️ 导出超时，请检查章节数量是否过多。")
        return 1
    except Exception as e:
        print(f"  ❌ 导出失败: {e}")
        return 1
