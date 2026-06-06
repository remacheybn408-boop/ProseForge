"""src/cli/commands_diagnostic.py — Diagnostic/status commands (board, stability-check) v0.7.1"""

from src.cli.shared import (PROJECT_ROOT, SCRIPTS_DIR, _load_project_config,
    _get_default_slug, _get_novels_root, _resolve_post_context,
    _resolve_chapter_path, _story_exists, _story_missing_msg, _get_workspace_dir,
    _get_active_db_path, _get_outline_manager, _check_outline_gate, _get_story_dir)
import sys
import json
from pathlib import Path
from version import get_version
from scripts.config_utils import resolve_path


def cmd_board(args):
    """Print a readonly status board for the project."""
    print("=" * 60)
    print("  Novel Forge — 项目看板")
    print("=" * 60)
    print()

    # Version
    v = get_version()
    print(f"  引擎版本: {v}")

    # Story status
    if _story_exists():
        from scripts.story import story_health
        health = story_health.check_health(PROJECT_ROOT)
        status = health["status"]
        print(f"  故事链: {status}")
        print(f"    合同: {health.get('contract_count', 0)}  提交: {health.get('commit_count', 0)}  事件: {health.get('event_count', 0)}")
        issues = health.get("issues", [])
        if issues:
            for iss in issues[:3]:
                print(f"    ⚠ {iss}")
    else:
        print(f"  故事链: 未初始化 (python novel.py story init)")

    # Config — read from active slot's project.json
    cfg = PROJECT_ROOT / "config.json"
    if cfg.exists():
        import json as _json
        try:
            cfg_data = _load_project_config()
            genre = cfg_data.get("default_genre", "?")
            style = cfg_data.get("default_style", "?")
            # v0.6.7: Read project title from active slot
            title = cfg_data.get("default_novel_slug", "?")
            try:
                ws_dir = PROJECT_ROOT / "workspace"
                reg = _json.loads((ws_dir / "registry.json").read_text(encoding="utf-8"))
                active = reg.get("active_slot", "")
                proj_file = ws_dir / active / "project.json"
                if proj_file.exists():
                    proj = _json.loads(proj_file.read_text(encoding="utf-8"))
                    title = proj.get("title", proj.get("name", title))
            except Exception:
                pass
            print(f"  当前项目: {title}")
            print(f"  类型/风格: {genre} / {style}")

            # Word count config
            wc = cfg_data.get("word_count", {}).get("normal", {})
            if wc:
                print(f"  字数范围: {wc.get('min', '?')}-{wc.get('max', '?')} (最佳≥{wc.get('best_min', '?')})")
        except Exception:
            print(f"  配置: 读取失败")
    else:
        print(f"  配置: 未找到 config.json")

    # Chapters in novels dir
    if cfg.exists():
        import json as _json
        try:
            cfg_data = _load_project_config()
            # v0.6.7: resolve slug from active slot
            slot_slug = None
            try:
                ws_dir = PROJECT_ROOT / "workspace"
                reg = _json.loads((ws_dir / "registry.json").read_text(encoding="utf-8"))
                act = reg.get("active_slot", "")
                pf = ws_dir / act / "project.json"
                if pf.exists():
                    pj = _json.loads(pf.read_text(encoding="utf-8"))
                    slot_slug = pj.get("title") or pj.get("name")
            except Exception:
                pass
            from src.cli.shared import _get_default_slug
            slug = slot_slug or _get_default_slug()
            novels_root = resolve_path(PROJECT_ROOT, cfg_data.get("novels_root", "./novels"))
            ch_dir = Path(_resolve_chapter_path(slug))
            if ch_dir.exists():
                chapters = sorted(ch_dir.glob("第*章*.txt"))
                print(f"  已完成章节: {len(chapters)}")
                if chapters:
                    latest = chapters[-1]
                    cn = sum(1 for c in latest.read_text(encoding="utf-8")
                             if '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf')
                    print(f"    最新: {latest.name} ({cn} 汉字)")
            else:
                print(f"  章节目录: 未找到 {ch_dir}")
        except Exception:
            print(f"  章节: 读取失败")

    # DB status
    try:
        # P0-2: Use active slot novel.db instead of config.json db_path
        dbp = _get_active_db_path()
        if dbp.exists():
            import sqlite3
            conn = sqlite3.connect(str(dbp))
            cur = conn.execute("SELECT COUNT(*) FROM chapters")
            ch_count = cur.fetchone()[0]
            cur = conn.execute("SELECT COUNT(*) FROM characters")
            char_count = cur.fetchone()[0]
            conn.close()
            print(f"  数据库: {dbp.name} | 章节: {ch_count} | 角色: {char_count}")
        else:
            print(f"  数据库: 未找到 ({dbp})")
    except Exception:
        print(f"  数据库: 无法读取")

    print()
    print("=" * 60)
    return 0


def cmd_stability_check(args=None):
    """稳定性自检 — 输出评分和问题清单.
    v0.6.7-clean11: 默认快速模式，--full 运行 pytest+structure check.
    """
    import subprocess as _sp
    import importlib

    full_mode = getattr(args, "full", False)

    print("=" * 60)
    mode_label = "完整模式 (pytest + structure check)" if full_mode else "快速模式"
    print(f"  Novel Forge - 稳定性自检 ({mode_label})")
    print(f"  版本: {get_version()}")
    print("=" * 60)
    print()

    score = 100
    p0_issues = []
    p1_issues = []
    checks = []

    # 1. 版本号一致
    try:
        vfile = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        v = get_version()
        ok = v == vfile
        checks.append(("版本号一致性", ok, f"VERSION={vfile}, get_version()={v}"))
        if not ok:
            p0_issues.append("VERSION 文件与代码版本不一致")
            score -= 10
    except Exception as e:
        checks.append(("版本号一致性", False, str(e)))
        p0_issues.append(f"无法读取版本号: {e}")
        score -= 10

    # 2. config 可解析
    try:
        cfg = _load_project_config()
        checks.append(("配置文件", True, "config.json 可解析"))
    except Exception as e:
        checks.append(("配置文件", False, str(e)))
        p0_issues.append(f"config.json 解析失败: {e}")
        score -= 10

    # 3. workspace 初始化
    ws_dir = PROJECT_ROOT / "workspace"
    ws_ok = ws_dir.exists() and (ws_dir / "registry.json").exists()
    checks.append(("workspace 初始化", ws_ok, str(ws_dir)))
    if not ws_ok:
        p1_issues.append("workspace 未初始化——首次使用请先运行 python novel.py init（或 python novel.py demo 一键全流程）")
        score -= 5

    # 4. 默认 3 slot 完整
    if ws_ok:
        try:
            import json as _json
            reg = _json.loads((ws_dir / "registry.json").read_text(encoding="utf-8"))
            slots = reg.get("slots", [])
            slot_ok = len(slots) >= 3
            checks.append(("默认 slot 完整", slot_ok, f"{len(slots)} 个 slot"))
            if not slot_ok:
                p0_issues.append(f"仅有 {len(slots)} 个默认 slot，需要 3 个")
                score -= 10
        except Exception as e:
            checks.append(("默认 slot 完整", False, str(e)))
            score -= 5

    # 5. active slot 有 novel.db
    try:
        from scripts.db.slot_manager import SlotManager
        sm = SlotManager(PROJECT_ROOT)
        if sm.registry.exists():
            active = sm.registry.get_active_slot()
            db_path = sm.get_slot_db_path(active) if active else None
            db_ok = db_path and db_path.exists()
            checks.append(("active slot DB", db_ok, str(db_path) if db_path else "无活跃 slot"))
            if not db_ok:
                p0_issues.append(f"活跃 slot {active} 缺少 novel.db")
                score -= 10
        else:
            checks.append(("active slot DB", False, "registry 不存在"))
    except Exception as e:
        checks.append(("active slot DB", False, str(e)))
        p1_issues.append(f"无法检查 DB: {e}")
        score -= 5

    # 6. agent 数量达标（Python Agent 类数）
    agents_py_dir = PROJECT_ROOT / "scripts" / "agents"
    agent_count = len([f for f in agents_py_dir.glob("*_agent.py") if f.name != "base_agent.py" and f.name != "disabled_example_agent.py"]) if agents_py_dir.exists() else 0
    agent_ok = agent_count >= 15
    checks.append((f"Agent 类", agent_ok, f"{agent_count} 个 (需要 >=15)"))
    if not agent_ok:
        p0_issues.append(f"Agent 仅 {agent_count} 个，目标 >=15")
        score -= 10

    # 7. pytest (--full only)
    if full_mode:
        print("  [运行] pytest...", flush=True)
        try:
            import os as _os
            env = {**_os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
            result = _sp.run(
                [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"],
                cwd=str(PROJECT_ROOT), timeout=180,
                capture_output=True, text=True, env=env,
                stdin=_sp.DEVNULL
            )
            test_ok = result.returncode == 0
            checks.append(("pytest", test_ok, f"exit={result.returncode}"))
            if not test_ok:
                # Show last 3 lines of stderr for debugging
                err_lines = result.stderr.strip().split("\n")[-3:]
                p0_issues.append(f"pytest 运行失败 (exit={result.returncode})")
                score -= 10
        except _sp.TimeoutExpired:
            checks.append(("pytest", False, "超时 (180s)"))
            p0_issues.append("pytest 超时，可能挂起")
            score -= 15
        except Exception as e:
            checks.append(("pytest", False, str(e)[:60]))
            p1_issues.append(f"pytest 无法运行: {e}")
            score -= 5
    else:
        checks.append(("pytest", True, "跳过（使用 --full 运行）"))

    # 8. 交叉平台检查
    cp_script = PROJECT_ROOT / "scripts" / "cross_platform_check.py"
    if cp_script.exists():
        try:
            cp = _sp.run([sys.executable, str(cp_script)], cwd=str(PROJECT_ROOT),
                         timeout=30, capture_output=True, text=True)
            cp_ok = cp.returncode == 0
            checks.append(("交叉平台", cp_ok, "通过" if cp_ok else "有警告"))
            if not cp_ok:
                p1_issues.append("交叉平台检查有警告")
                score -= 5
        except Exception:
            checks.append(("交叉平台", False, "超时/异常"))
            score -= 5

    # 9. story contract 是否存在断链
    story_dir = _get_story_dir()
    if story_dir.exists():
        try:
            from scripts.story import story_health
            health = story_health.check_health(PROJECT_ROOT)
            h_ok = health["status"] == "OK"
            checks.append(("Story 健康", h_ok, health["status"]))
            if health["status"] == "FAIL":
                p0_issues.append(f"Story 链断裂: {len(health.get('failures', []))} 项")
                score -= 10
            elif health["status"] == "WARN":
                p1_issues.append(f"Story 链警告: {len(health.get('warnings', []))} 项")
                score -= 5
        except Exception as e:
            checks.append(("Story 健康", False, str(e)))

    # 10. v0.6.7-clean3: Slot FTS 完整性检查
    try:
        import sqlite3
        ws_dir = PROJECT_ROOT / "workspace"
        fts_issues = []
        for slot_dir in sorted(ws_dir.glob("slot_*")):
            db_path = slot_dir / "novel.db"
            if not db_path.exists():
                continue
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='novel_chapter_fts'")
            if not cur.fetchone():
                fts_issues.append(f"{slot_dir.name} 缺少 FTS5 表")
            conn.close()
        fts_ok = len(fts_issues) == 0
        detail = "所有 slot 有 FTS5" if fts_ok else f"{len(fts_issues)} 个 slot 缺 FTS5"
        checks.append(("Slot FTS 完整性", fts_ok, detail))
        if not fts_ok:
            p0_issues.append(f"Slot DB 缺 FTS5 表: {', '.join(fts_issues)}")
            score -= 10
    except Exception as e:
        checks.append(("Slot FTS 完整性", False, str(e)))
        p1_issues.append(f"无法检查 slot FTS: {e}")
        score -= 5

    # 11. --full 结构自检
    if full_mode:
        print("  [运行] 结构自检...", flush=True)
        try:
            smoke_ok = True
            smoke_parts = []

            # a) slot_001 DB 表完整性
            import sqlite3
            db = PROJECT_ROOT / "workspace" / "slot_001" / "novel.db"
            if db.exists():
                conn = sqlite3.connect(str(db))
                tables = [r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()]
                conn.close()
                has_chapters = "chapters" in tables
                has_fts = any("fts" in t for t in tables)
                smoke_parts.append("DB✓" if (has_chapters and has_fts) else "DB✗")
                if not has_chapters or not has_fts:
                    smoke_ok = False
            else:
                smoke_parts.append("DB✗")
                smoke_ok = False

            # b) config 可解析
            cfg_path = PROJECT_ROOT / "config.json"
            smoke_parts.append("CFG✓" if cfg_path.exists() else "CFG✗")

            # c) workspace 初始化
            ws = PROJECT_ROOT / "workspace"
            has_reg = (ws / "registry.json").exists()
            smoke_parts.append("WS✓" if has_reg else "WS✗")
            if not has_reg:
                smoke_ok = False

            # d) agents 配置存在
            agents = [f for f in (PROJECT_ROOT / "scripts" / "agents").glob("*_agent.py") if f.name != "base_agent.py" and f.name != "disabled_example_agent.py"]
            smoke_parts.append(f"Agents:{len(agents)}")
            if len(agents) < 15:
                smoke_ok = False

            checks.append(("结构自检", smoke_ok, " ".join(smoke_parts)))
            if not smoke_ok:
                p0_issues.append("结构自检未通过（DB/WS/Agents 不完整）")
                score -= 20
        except Exception as e:
            checks.append(("结构自检", False, str(e)[:60]))
            p0_issues.append(f"结构自检异常: {e}")
            score -= 20
    else:
        checks.append(("结构自检", True, "跳过（使用 --full 运行）"))

    # 12. demo 全流程 (--full only)
    if full_mode:
        print("  [运行] demo 全流程...", flush=True)
        try:
            demo = _sp.run(
                [sys.executable, str(PROJECT_ROOT / "novel.py"), "demo"],
                cwd=str(PROJECT_ROOT), timeout=120,
                capture_output=True, text=True,
                stdin=_sp.DEVNULL
            )
            demo_ok = demo.returncode == 0
            # Also check stderr for import errors
            stderr_clean = "No module named" not in demo.stderr and "Traceback" not in demo.stderr
            detail = f"exit={demo.returncode}"
            if not stderr_clean:
                detail += " stderr=有异常"
            checks.append(("demo 全流程", demo_ok and stderr_clean, detail))
            if not demo_ok or not stderr_clean:
                # Show last lines of stderr for debugging
                err_tail = demo.stderr.strip().split("\n")[-3:]
                p0_issues.append(f"demo 全流程失败 (exit={demo.returncode}): {'; '.join(err_tail)}")
                score -= 20
        except _sp.TimeoutExpired as _te:
            # Kill the hung demo process (may have orphaned grandchildren)
            try:
                _te.process.kill()
                _te.process.wait(timeout=5)
            except Exception:
                pass
            # Try to grab partial output for debugging
            partial = ""
            try:
                if _te.stdout:
                    partial = _te.stdout[-300:]
            except Exception:
                pass
            checks.append(("demo 全流程", False, f"超时 (120s) {partial[:100]}"))
            p0_issues.append("demo 全流程超时")
            score -= 15
        except Exception as e:
            checks.append(("demo 全流程", False, str(e)[:60]))
            p1_issues.append(f"demo 无法运行: {e}")
            score -= 5
    else:
        checks.append(("demo 全流程", True, "跳过（使用 --full 运行）"))

    # 输出结果
    for name, ok, detail in checks:
        icon = "✓" if ok else "✗"
        print(f"  [{icon}] {name}: {detail}")

    print()
    print("=" * 60)
    print(f"  稳定性评分: {max(0, score)}/100")
    print(f"  P0 问题: {len(p0_issues)} 个")
    print(f"  P1 问题: {len(p1_issues)} 个")

    if p0_issues:
        print(f"\n  P0 必须修复:")
        for iss in p0_issues:
            print(f"    ✗ {iss}")
    if p1_issues:
        print(f"\n  P1 建议修复:")
        for iss in p1_issues:
            print(f"    ⚠ {iss}")

    if p0_issues:
        print(f"\n  建议: 不建议发布（存在 P0 问题，必须先修复）")
    elif score >= 80:
        print(f"\n  建议: 可以发布正式版")
    elif score >= 60:
        print(f"\n  建议: 修复 P1 问题后再发布")
    else:
        print(f"\n  建议: 不建议发布")
    print("=" * 60)
    sys.stdout.flush()
    return 0 if not p0_issues and score >= 80 else 1
