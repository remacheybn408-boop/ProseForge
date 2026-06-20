#!/usr/bin/env python3
"""pre.py — Pre-write preparation pipeline.

Builds chapter context from DB, outline, story state, role cards, and recent
chapter data. Produces task-card guidance, context_pack, and pipeline_state.
Does not generate chapter prose.
"""

import re, json, sys, os, sqlite3, yaml
from pathlib import Path
from datetime import datetime, timezone
from version import get_version
from src.pipeline._base import (
    App, now, connect, _get_novel_id, ensure_tables,
    _arabic_to_chinese_numeral,
    _strip_selfcheck, _count_chinese, _resolve_slot_db_path,
    load_config, story_health, load_characters,
    write_json_atomic,
)
from src.pipeline.chapter_context import _build_context_injection
from src.pipeline.volume import (
    _resolve_story_for_deviation,
    _calc_story_deviation,
    _extract_learnable_rules,
    _auto_write_rules,
)


def _configure_console_output():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                # Console reconfigure is a best-effort startup fallback.
                pass


def _warn_optional(step, exc, log_entries=None):
    print(f"  [WARN] {step}: {exc}")
    if log_entries is not None:
        log_entries.append(f"WARN:{step}")


def _load_json_dict(path, step, log_entries=None):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _warn_optional(step, exc, log_entries)
        return None
    if not isinstance(payload, dict):
        _warn_optional(step, ValueError("expected JSON object"), log_entries)
        return None
    return payload

def run_pre(
    chapter_no,
    chapter_type="normal",
    novel_slug="demo_novel",
    novel_title="",
    volume_no=1,
    chapters_dir=None,
    db_path=None,
    project_root=None,
    config_path=None,
    context=None,
):
    _configure_console_output()
    if context is None:
        cfg = load_config(config_path, project_root=project_root)
        if db_path:
            cfg["db_path"] = db_path
        else:
            cfg["db_path"] = _resolve_slot_db_path(cfg, project_root=project_root)
        if not novel_title:
            novel_title = cfg.get("default_novel_title", novel_slug)
        context = App(
            cfg,
            novel_slug,
            novel_title,
            volume_no,
            chapters_dir,
            project_root=project_root,
            config_path=config_path,
        )
    app = context
    ensure_tables(app)
    conn = connect(app)
    cur = conn.cursor()
    nid = _get_novel_id(cur, app)
    log_entries = []
    prev_ch = chapter_no - 1; prev_ending = ""

    # ── FTS5 健康检查 ──
    try:
        from src.utils.fts_health import ensure_fts_healthy
        _fts_cfg = {"db_path": str(app.db_path)}
        fts_result = ensure_fts_healthy(_fts_cfg)
        health_before = fts_result.get("health_before", {})
        print(f"  [FTS] scope: {health_before.get('total_tables', 0)} table(s)")
        for step in fts_result.get("repair", {}).get("progress", []):
            if step.get("status") == "repaired":
                print(
                    f"  [FTS] {step['index']}/{step['total_tables']} {step['table']} -> {step.get('method', 'rebuild')}"
                )
        if fts_result["action"] == "repair_failed":
            print("  [WARN] FTS repair failed; downstream retrieval will use LIKE fallback")
    except ImportError as exc:
        _warn_optional("FTS health check unavailable", exc, log_entries)
    except (sqlite3.Error, OSError) as exc:
        _warn_optional("FTS health check failed", exc, log_entries)

    # ── story contract 变量初始化 ──
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    story_health_result = None
    char_arcs = None
    open_promises = None
    contract_goal = None
    genre = ""
    # ── 优先读取题材 genre ──
    try:
        row = cur.execute("SELECT genre FROM novels WHERE id=?", (nid,)).fetchone()
        if row and row[0]:
            genre = row[0]
    except sqlite3.Error as exc:
        _warn_optional("genre lookup failed", exc, log_entries)

    print("="*60)
    print(f"STEP 1: PRE — 第{chapter_no}章 [{chapter_type}] — 《{app.novel_title}》")
    print("="*60)

    # ── 标题骨架：从 volume_plans / chapter_plans 读取 ──
    vol = cur.execute(
        "SELECT planned_title, volume_goal, opening_state, ending_target, must_complete, suggested_chapters "
        "FROM volume_plans WHERE novel_id=? AND volume_no=?", (nid, app.volume_no)).fetchone()
    ch_plan = cur.execute(
        "SELECT planned_title, chapter_goal, main_event, character_focus, conflict_point, "
        "must_include, plot_threads_to_advance, reader_promises_to_advance, "
        "ending_hook_direction, continuity_from_previous "
        "FROM chapter_plans WHERE novel_id=? AND volume_no=? AND chapter_no=?", 
        (nid, app.volume_no, chapter_no)).fetchone()

    if vol:
        print(f"\n  >>> 第{app.volume_no}卷《{vol['planned_title']}》")
        print(f"      目标: {vol['volume_goal']}")
        if vol['opening_state']: print(f"      开端: {vol['opening_state']}")
        if vol['ending_target']: print(f"      卷末: {vol['ending_target']}")
        log_entries.append(f"读取卷骨架:第{app.volume_no}卷")
    if ch_plan:
        print(f"\n  >>> 本章骨架《{ch_plan['planned_title']}》")
        if ch_plan['chapter_goal']:       print(f"      章节目标: {ch_plan['chapter_goal']}")
        if ch_plan['main_event']:         print(f"      核心事件: {ch_plan['main_event']}")
        if ch_plan['character_focus']:    print(f"      人物重点: {ch_plan['character_focus']}")
        if ch_plan['conflict_point']:     print(f"      冲突点:   {ch_plan['conflict_point']}")
        if ch_plan['must_include']:       print(f"      必须包含: {ch_plan['must_include']}")
        if ch_plan['plot_threads_to_advance']:    print(f"      推进伏笔: {ch_plan['plot_threads_to_advance']}")
        if ch_plan['ending_hook_direction']:      print(f"      结尾钩子: {ch_plan['ending_hook_direction']}")
        if ch_plan['continuity_from_previous']:   print(f"      上章承接: {ch_plan['continuity_from_previous']}")
        log_entries.append(f"读取章骨架:第{chapter_no}章")
    else:
        print(f"\n  [INFO] 第{chapter_no}章无标题骨架数据，按自由模式写作")
    # ── 标题骨架结束 ──

    # ── 卷序检查：前面各卷是否完成 ──
    if app.volume_no > 1:
        for vn in range(1, app.volume_no):
            prev_vol_chs = cur.execute(
                "SELECT COUNT(*) as cnt FROM chapters WHERE novel_id=? AND volume_id=(SELECT id FROM volumes WHERE novel_id=? AND volume_no=?)",
                (nid, nid, vn)).fetchone()
            prev_vol_plan = cur.execute("SELECT planned_title FROM volume_plans WHERE novel_id=? AND volume_no=?",
                (nid, vn)).fetchone()
            prev_vol_name = prev_vol_plan['planned_title'] if prev_vol_plan else f"第{vn}卷"
            if prev_vol_chs and prev_vol_chs['cnt'] == 0:
                print(f"\n  [WARN] 卷序警告: 《{prev_vol_name}》(第{vn}卷)尚无已入库章节")
                print(f"         建议先完成第{vn}卷再开始第{app.volume_no}卷")
                log_entries.append(f"卷序警告:第{vn}卷未完成")
    # ── 卷序检查结束 ──

    if prev_ch >= 1:
        cur.execute("SELECT title, content FROM chapters WHERE novel_id=? AND chapter_no=?", (nid, prev_ch))
        prev = cur.fetchone()
        if not prev:
            print(f"\n[WARN] 第{prev_ch}章不存在于数据库")
        else:
            prev_ending = _strip_selfcheck(prev['content'])[-800:]
            cur.execute("SELECT short_summary FROM chapter_summaries WHERE novel_id=? AND chapter_id=(SELECT id FROM chapters WHERE novel_id=? AND chapter_no=?)", (nid, nid, prev_ch))
            sm = cur.fetchone()
            print(f"  [OK] 上章: 第{prev_ch}章《{prev['title']}》末400字:")
            print(f"  {prev_ending[-400:]}")
            log_entries.append(f"读取第{prev_ch}章结尾{len(prev_ending)}字")

        # ── 读取上一章 actual chapter_brief ──
        prev_brief_path = app.exports_root / "chapter_briefs" / f"chapter_{prev_ch:03d}_brief.json"
        brief_data = None
        if prev_brief_path.exists():
            brief_data = _load_json_dict(
                prev_brief_path,
                f"chapter {prev_ch} brief load failed",
                log_entries,
            ) or {}
            if brief_data:
                print(f"\n  [OK] 上章 brief 已加载:")
                if brief_data.get('ending_state'):
                    print(f"    实际结尾: {brief_data['ending_state'][:120]}")
                if brief_data.get('next_chapter_hooks'):
                    print(f"    遗留钩子: {brief_data['next_chapter_hooks'][:120]}")
                diff = brief_data.get('planned_vs_actual_diff', {})
                if isinstance(diff, str):
                    try:
                        diff = json.loads(diff)
                    except json.JSONDecodeError:
                        diff = {}
                elif not isinstance(diff, dict):
                    diff = {}
                if diff.get('title_match') == 'changed':
                    print(f"    [WARN] 上章标题已变更: {diff.get('planned_title','')} → {diff.get('actual_title','')}")
                log_entries.append(f"读取第{prev_ch}章brief")
        elif prev_ch > 1:
            print(f"\n  [WARN] 第{prev_ch}章 brief 文件缺失 — 建议先执行 post")

        # ── 读取上章 agent review ──
        jury_path = PROJECT_ROOT / "reports" / "agent_reviews" / f"chapter_{prev_ch:03d}_agent_review.json"
        jury = None
        if jury_path.exists():
            try:
                jury = _load_json_dict(
                    jury_path,
                    f"chapter {prev_ch} jury load failed",
                    log_entries,
                )
                jury = jury or {}
                ce = jury.get("chief_editor", {})
                print(f"  [OK] 上章陪审团意见: score={jury.get('overall_score')}, status={jury.get('status')}, "
                      f"must_fix={len(ce.get('must_fix', []))}, should_fix={len(ce.get('should_fix', []))}")
                log_entries.append(f"读取第{prev_ch}章jury({jury.get('status')})")
            except (TypeError, ValueError) as e:
                print(f"  [WARN] 上章jury读取失败: {e}")

        # ── 读取上章 orchestrator 报告（更细粒度的 guard 建议）──
        orch_path = app.exports_root / "reports" / f"chapter_{prev_ch:03d}_orchestrator_report.json"
        orch_report = None
        if orch_path.exists():
            try:
                orch_report = _load_json_dict(
                    orch_path,
                    f"chapter {prev_ch} orchestrator report load failed",
                    log_entries,
                )
                log_entries.append(f"读取第{prev_ch}章orchestrator({orch_report.get('final_status','?')})")
            except (TypeError, ValueError) as e:
                print(f"  [WARN] chapter {prev_ch} orchestrator report load failed: {e}")
        # ── brief + jury 结束 ──
    else:
        jury = None
        print("  [OK] 第1章，无上章")

    # ── 读取故事合同健康（所有章节均执行） ──
    if story_health is not None:
        try:
            health = story_health.check_health(PROJECT_ROOT)
            story_health_result = health
            if health["status"] != "FAIL" or any("missing" not in f for f in health.get("failures", [])):
                sd = Path(health["story_dir"])
                char_arcs = load_characters(sd)
                contract_file = sd / "chapters" / f"chapter_{chapter_no:03d}_contract.json"
                if contract_file.exists():
                    contract = json.loads(contract_file.read_text(encoding="utf-8"))
                    contract_goal = contract.get("required_scene_goal", "")
                prom_file = sd / "memory" / "promises.json"
                if prom_file.exists():
                    all_promises = json.loads(prom_file.read_text(encoding="utf-8"))
                    open_promises = [p for p in all_promises if not p.get("resolved")]
                print(f"  [OK] 故事合同: status={health['status']}, "
                      f"合同={health['contract_count']}, 提交={health['commit_count']}, "
                      f"角色弧线={len(char_arcs) if char_arcs else 0}")
                log_entries.append(f"story_health({health['status']})")
        except (OSError, json.JSONDecodeError, sqlite3.Error, TypeError, ValueError) as e:
            print(f"  [WARN] 故事合同读取失败: {e}")

    # ── 加载题材约束和上章 texture 报告 ──
    genre_preset = {}
    prev_texture = None
    if genre:
        try:
            import yaml
            _preset_path = PROJECT_ROOT / "configs" / "human_texture" / "genre_presets.yaml"
            if _preset_path.exists():
                all_presets = yaml.safe_load(_preset_path.read_text(encoding="utf-8"))
                genre_preset = all_presets.get(genre, all_presets.get("default", {}))
        except (ImportError, OSError, AttributeError, ValueError, yaml.YAMLError) as e:
            print(f"  [WARN] genre preset load failed: {e}")
    if prev_ch >= 1:
        _tex_path = app.exports_root / "reports" / f"chapter_{prev_ch:03d}_texture_report.json"
        if _tex_path.exists():
            try:
                prev_texture = json.loads(_tex_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
                print(f"  [WARN] chapter {prev_ch} texture report load failed: {e}")

    # 最近3章摘要
    print("\n  [OK] 最近3章:")
    for ch in range(max(1, chapter_no-3), chapter_no):
        cur.execute("SELECT cs.short_summary FROM chapter_summaries cs JOIN chapters c ON c.id=cs.chapter_id WHERE c.novel_id=? AND c.chapter_no=?", (nid, ch))
        cs = cur.fetchone()
        print(f"    第{ch}章: {cs['short_summary'][:100] if cs else '(无摘要)'}")

    # 人物
    cur.execute("SELECT name, role, identity FROM characters WHERE novel_id=?", (nid,))
    chars = cur.fetchall()
    print(f"\n  [OK] 人物({len(chars)}): " + ", ".join(f"[{c['role']}]{c['name']}" for c in chars))
    log_entries.append(f"人物{len(chars)}人")

    if genre:
        print(f"  [OK] 题材: {genre}")

    # ── 加载声纹卡 ──
    char_cards = {}
    voice_dir = app.workspace_root / app.active_slot / "voice_cards" / "default"
    if app.active_slot and voice_dir.exists():
        for card_file in sorted(voice_dir.glob("*.json")):
            card = _load_json_dict(card_file, f"voice card load failed ({card_file.name})", log_entries)
            if card:
                name = card.get("name", "")
                if name:
                    char_cards[name] = card

    # ── 加载角色心理状态 ──
    mental_states = {}
    if app.active_slot:
        slot_root = app.workspace_root / app.active_slot
        # 优先新目录，向后兼容旧目录
        for dir_name in ("character_psychology", "mental_states"):
            ps_dir = slot_root / dir_name / "default"
            if not ps_dir.exists():
                continue
            for ps_file in sorted(ps_dir.glob("*.json")):
                data = _load_json_dict(ps_file, f"mental state load failed ({ps_file.name})", log_entries)
                if data:
                    name = data.get("name", "")
                    if name and name not in mental_states:
                        mental_states[name] = {k: v for k, v in data.items() if k != "name"}
    if char_cards:
        print(f"\n  [OK] 声纹卡({len(char_cards)}): " + ", ".join(char_cards.keys()))
    if mental_states:
        print(f"  [OK] 精神状态({len(mental_states)}): " + ", ".join(mental_states.keys()))

    # 世界观/伏笔/规则
    for label, sql, params in [
        ("世界观", "SELECT title,importance FROM worldbuilding WHERE novel_id=? ORDER BY importance DESC", (nid,)),
        ("伏笔", "SELECT title,status,importance FROM plot_threads WHERE novel_id=? ORDER BY status,importance DESC", (nid,)),
        ("写作规则", "SELECT title,rule_type FROM writing_rules WHERE novel_id=? AND status='active' ORDER BY importance DESC", (nid,)),
        ("读者承诺", "SELECT promise_title,status,reader_emotion FROM reader_promises WHERE novel_id=? AND status='open' ORDER BY importance DESC", (nid,)),
    ]:
        cur.execute(sql, params)
        rows = cur.fetchall()
        print(f"  [OK] {label}({len(rows)}): " + ", ".join(str(dict(r)) for r in rows[:5]))
        log_entries.append(f"{label}{len(rows)}条")

    # ── 世界观关键词提醒 ──
    try:
        from src.outline.similarity import _extract_world_keywords
        scan_text = ""
        if ch_plan:
            # ch_plan 是 sqlite3.Row，不是 dict — 不能用 .get()
            scan_text += (ch_plan["chapter_goal"] or "") + " "
            scan_text += (ch_plan["main_event"] or "") + " "
            scan_text += (ch_plan["conflict_point"] or "") + " "
            scan_text += (ch_plan["must_include"] or "") + " "
        try:
            outline_manager = getattr(app, "outline_manager", None)
            outline = outline_manager.current_outline() if outline_manager else None
            if outline:
                outline_content = outline.get("content", "")
                for pat in [f"第{chapter_no}章", f"第{chapter_no:02d}章"]:
                    idx = outline_content.find(pat)
                    if idx >= 0:
                        scan_text += outline_content[idx:idx + 500] + " "
                        break
                else:
                    scan_text += outline_content[:1000] + " "
        except (OSError, TypeError, ValueError, AttributeError) as e:
            print(f"  [WARN] outline context load failed: {e}")
        if scan_text.strip():
            chapter_keywords = _extract_world_keywords(scan_text)
            if chapter_keywords:
                cur.execute(
                    "SELECT title, content, category, importance FROM worldbuilding WHERE novel_id=?",
                    (nid,),
                )
                all_wb = cur.fetchall()
                seen = set()
                matches = []
                for wb in all_wb:
                    wb_title = wb["title"]
                    if wb_title in seen:
                        continue
                    for kw in chapter_keywords:
                        if kw in wb_title or wb_title in kw:
                            matches.append(wb)
                            seen.add(wb_title)
                            break
                if matches:
                    print(f"\n  🌍 世界观提醒 (匹配 {len(matches)} 条):")
                    for wb in matches[:8]:
                        imp = wb["importance"] or 3
                        imp_bar = "\u2605" * imp + "\u2606" * (5 - imp)
                        content_preview = ""
                        if wb["content"]:
                            c = wb["content"]
                            content_preview = (c[:80] + "...") if len(c) > 80 else c
                        print(f"    [{imp_bar}] {wb['title']:<16s} [{wb['category'] or '—'}]")
                        if content_preview:
                            print(f"          {content_preview}")
    except (ImportError, sqlite3.Error, TypeError, ValueError) as e:
        print(f"  [WARN] world keyword reminder failed: {e}")

    # ── 情节线索提醒 ──
    try:
        _thread_labels = {"伏笔": "伏笔", "主线": "主线", "支线": "支线", "感情线": "感情线", "成长线": "成长线"}
        cur.execute(
            "SELECT title, thread_type, status, importance, introduced_chapter, content "
            "FROM plot_threads WHERE novel_id=? AND status IN ('open','active') "
            "ORDER BY importance DESC",
            (nid,),
        )
        open_threads = cur.fetchall()
        if open_threads:
            planned_titles = set()
            if ch_plan and ch_plan.get("plot_threads_to_advance"):
                for t in open_threads:
                    if t["title"] in (ch_plan["plot_threads_to_advance"] or ""):
                        planned_titles.add(t["title"])
            print(f"\n  \U0001f9f5 活跃情节线索 ({len(open_threads)} 条):")
            for t in open_threads[:5]:
                imp = t["importance"] or 3
                imp_bar = "\u2605" * imp + "\u2606" * (5 - imp)
                marker = " ▶ 本章计划推进" if t["title"] in planned_titles else ""
                intro = f" 第{t['introduced_chapter']}章引入" if t["introduced_chapter"] else ""
                ttype = _thread_labels.get(t["thread_type"], t["thread_type"])
                content_preview = ""
                if t["content"]:
                    c = t["content"]
                    content_preview = (c[:60] + "...") if len(c) > 60 else c
                print(f"    [{imp_bar}] {t['title']:<18s} [{ttype:6s}]{marker}{intro}")
                if content_preview:
                    print(f"          {content_preview}")
    except sqlite3.Error as e:
        print(f"  [WARN] plot thread reminder failed: {e}")

    # ── 读者承诺提醒 ──
    try:
        cur.execute(
            "SELECT promise_title, introduced_chapter, importance "
            "FROM reader_promises WHERE novel_id=? AND status='open' ORDER BY importance DESC",
            (nid,),
        )
        open_promises = cur.fetchall()
        if open_promises:
            print(f"\n  📝 待兑现读者承诺 ({len(open_promises)} 条):")
            for p in open_promises[:3]:
                imp = p["importance"] or 3
                imp_bar = "\u2605" * imp + "\u2606" * (5 - imp)
                intro = f" 第{p['introduced_chapter']}章提出" if p["introduced_chapter"] else ""
                print(f"    [{imp_bar}] {p['promise_title']}{intro}")
    except sqlite3.Error as e:
        print(f"  [WARN] reader promise reminder failed: {e}")

    # context_pack (包含标题骨架)
    app.exports_root.mkdir(parents=True, exist_ok=True)
    pack_path = app.exports_root / f"context_ch{chapter_no}_{datetime.now().strftime('%H%M%S')}.txt"
    skeleton_info = ""
    if ch_plan:
        skeleton_info = (
            f"=== 标题骨架 ===\n"
            f"卷: 第{app.volume_no}卷《{vol['planned_title'] if vol else '?'}》\n"
            f"章: 第{chapter_no}章《{ch_plan['planned_title']}》\n"
            f"目标: {ch_plan['chapter_goal']}\n"
            f"冲突: {ch_plan['conflict_point']}\n"
            f"钩子: {ch_plan['ending_hook_direction']}\n"
        )
    pack_path.write_text(
        f"写作上下文包-第{chapter_no}章\n{'='*40}\n"
        f"目标字数: {app.wc_default['best_min']}-{app.wc_default['best_max']} | "
        f"下限: {app.wc_default['min']}\n"
        f"{skeleton_info}\n", encoding='utf-8')
    print(f"  [OK] context_pack: {pack_path}")

    # ── 上下文注入：读取前3章 chapter_contexts ──
    context_injection = _build_context_injection(cur, nid, chapter_no, max_chapters=3)
    if context_injection:
        print(f"\n  📖 上下文注入\n    {context_injection}")
        log_entries.append(f"上下文注入:前{min(3, chapter_no-1)}章")

    # task_card (含标题骨架指引)
    print(f"\n{'='*60}")
    print(f"TASK CARD - 第{chapter_no}章 [{chapter_type}]")
    print(f"  字数范围: {app.wc_default['min']}-{app.wc_default['max']} | 最佳: {app.wc_default['best_min']}-{app.wc_default['best_max']}")
    print(f"  必须>={app.min_scenes}场景 | >=2生活细节 | >=1不完美互动")
    print(f"  禁止: AI句式/硬科普/总结腔/空泛心理")
    if ch_plan:
        print(f"  ─── 标题骨架指引 ───")
        print(f"  章节目标: {ch_plan['chapter_goal']}")
        print(f"  核心事件: {ch_plan['main_event'] or '(自由发挥)'}")
        print(f"  冲突点:   {ch_plan['conflict_point']}")
        print(f"  结尾钩子: {ch_plan['ending_hook_direction']}")
        if ch_plan['must_include']: print(f"  必须包含: {ch_plan['must_include']}")
    if prev_ending:
        print(f"  ─── 承接上章 ───")
        print(f"  {prev_ending[-120:]}")
    if jury and jury.get("chief_editor"):
        print(f"  ─── 上章审稿意见（第{prev_ch}章）───")
        must_fix = jury["chief_editor"].get("must_fix", [])
        should_fix = jury["chief_editor"].get("should_fix", [])
        if must_fix:
            print(f"  🔴 建议优先处理 ({len(must_fix)}项):")
            for i, item in enumerate(must_fix, 1):
                msg = item.get("message", "")
                sug = item.get("suggestion", "")
                print(f"  {i}. {msg}")
                if sug: print(f"     → {sug}")
        if should_fix:
            print(f"  🟡 值得关注 ({len(should_fix)}项):")
            for i, item in enumerate(should_fix, 1):
                msg = item.get("message", "")
                sug = item.get("suggestion", "")
                print(f"  {i}. {msg}")
                if sug: print(f"     → {sug}")

        # ── 质量指标摘要 ──
        print(f"  📊 质量指标:")
        agents = jury.get("agents", {})
        q_metrics = []
        if isinstance(agents, list):
            for ag in agents:
                if isinstance(ag, dict):
                    score = ag.get("score")
                    ag_name = ag.get("agent", "")
                    if score is not None and isinstance(score, (int, float)):
                        icon = "✅" if score >= 70 else ("⚠️" if score >= 50 else "❌")
                        short = ag_name.replace("_agent", "").replace("_guard", "").replace("_", " ")
                        q_metrics.append(f"{icon} {short}={score}")
        elif isinstance(agents, dict):
            for ag_name, ag_data in agents.items():
                if isinstance(ag_data, dict):
                    score = ag_data.get("score", ag_data.get("overall_score"))
                    if score is not None and isinstance(score, (int, float)):
                        icon = "✅" if score >= 70 else ("⚠️" if score >= 50 else "❌")
                        short = ag_name.replace("_agent", "").replace("_guard", "").replace("_", " ")
                        q_metrics.append(f"{icon} {short}={score}")
        if q_metrics:
            print(f"  {' | '.join(q_metrics)}")

        if not must_fix and not should_fix:
            print(f"  ✅ 无问题，上章质量良好")
    elif prev_ch >= 1:
        print(f"  [WARN] 第{prev_ch}章无审稿意见 — 建议先运行 post/review")
    # ── 故事合同区块 ──
    if story_health_result:
        h = story_health_result
        status_icon = {"OK": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(h["status"], "❓")
        print(f"  ─── 故事合同 ───")
        print(f"  {status_icon} 健康: {h['status']} | 合同: {h['contract_count']} | 提交: {h['commit_count']} | 事件: {h['event_count']}")
        if h.get("empty_hints"):
            for hint in h["empty_hints"][:1]:
                print(f"  ℹ️ {hint}")
        if h.get("warnings"):
            for w in h["warnings"][:2]:
                print(f"  ⚠️ {w[:100]}")
        if h.get("failures"):
            for f in h["failures"][:2]:
                print(f"  ❌ {f[:100]}")
        if char_arcs:
            active_arcs = [c for c in char_arcs if c.get("active", True)]
            if active_arcs:
                print(f"  角色弧线:")
                for c in active_arcs[:5]:
                    name = c.get("name", "?")
                    arc = c.get("arc", "")
                    last_ch = c.get("last_chapter", "")
                    last_st = c.get("last_state", "")
                    parts = []
                    if last_ch: parts.append(f"第{last_ch}章")
                    if last_st: parts.append(last_st)
                    if arc: parts.append(f"弧线:{arc}")
                    print(f"    {name}: {' | '.join(parts)}" if parts else f"    {name}")
        if open_promises:
            print(f"  待兑现伏笔: {len(open_promises)}个")
            for p in open_promises[:3]:
                txt = p.get("promise", "")[:80]
                ch = p.get("chapter", "?")
                print(f"    ① {txt} (第{ch}章)")
        if contract_goal:
            print(f"  场景目标: {contract_goal[:120]}")

        # ── 3.2 偏离检测 ──
        sd = _resolve_story_for_deviation()
        dev = _calc_story_deviation(cur, nid, chapter_no, sd)
        if dev["score"] >= 30:
            icon = "🔴" if dev["score"] >= 60 else "⚠️"
            print(f"  {icon} 故事偏离度: {dev['score']}/100")
            for d in dev["details"][:3]:
                print(f"     → {d}")

    # ── 写作约束区块 ──
    if genre_preset:
        print(f"  ─── 写作约束 [{genre}] ───")
        _constraints = []
        for key, label in [("water_density_min", "注水阈值"), ("conflict_pressure_min", "冲突压力"),
                           ("life_texture_min", "生活质感"), ("cliche_sentence_max", "陈词上限"),
                           ("emotion_summary_max", "情感总结上限"), ("goal_progress_min", "目标推进")]:
            val = genre_preset.get(key)
            if val is not None:
                _constraints.append(f"{label}={val}")
        if _constraints:
            print(f"  质量阈值: {' | '.join(_constraints)}")
        _pacing = genre_preset.get("pacing", {})
        _focus = _pacing.get("focus_deltas", [])
        if _focus:
            _labels = {"conflict_delta":"冲突", "power_delta":"实力", "cost_delta":"代价",
                       "event_delta":"事件", "hook_delta":"钩子", "decision_delta":"抉择",
                       "relationship_delta":"关系", "clue_delta":"线索"}
            _foci = [_labels.get(d, d) for d in _focus]
            print(f"  节奏侧重: {' → '.join(_foci)}")
    # ── 上章纹理报告（独立于 genre_preset）──
    if prev_texture:
        _ts = prev_texture.get("status", "?")
        _sc = prev_texture.get("scores", {})
        _avg = sum(_sc.values()) / len(_sc) if _sc else 0
        _icon = {"OK":"✅", "WARNING":"⚠️", "FAIL":"❌"}.get(_ts, "❓")
        print(f"  ─── 上章纹理 ───")
        print(f"  状态: {_icon} {_ts}, 平均分={_avg:.0f}/100")
        _low = [(gn, gs) for gn, gs in sorted(_sc.items()) if gs < 70]
        if _low:
            for gn, gs in _low[:3]:
                _short = gn.replace("_guard","").replace("_"," ")
                print(f"    ⚠️ {_short:25s} {gs}/100")

        # ── 4.2 质量趋势 ──
        _trend = prev_texture.get("trend", {})
        _deltas = _trend.get("deltas", {})
        if _deltas:
            _changed = {k: v for k, v in _deltas.items() if abs(v) > 3}
            if _changed:
                print(f"  \u2500\u2500\u2500 \u8d28\u91cf\u8d8b\u52bf \u2500\u2500\u2500")
                for _gname, _delta in sorted(_changed.items(), key=lambda x: -abs(x[1])):
                    _short = _gname.replace("_guard", "").replace("_", " ")
                    _arrow = "\u2191" if _delta > 0 else "\u2193"
                    _label = "stable" if abs(_delta) <= 3 else f"{_arrow} {_delta:+d}"
                    print(f"  {_short:20s} {_label}")

    # ── 上章裂隙触发词 ──
    if prev_ch >= 1:
        prev_state_path = app.state_dir / f"chapter_{prev_ch:03d}_state.json"
        if prev_state_path.exists():
            try:
                _ps = json.loads(prev_state_path.read_text(encoding="utf-8"))
                _trig_hits = _ps.get("裂隙触发词命中", 0)
                _trig_detail = _ps.get("裂隙触发词详情", {})
                if _trig_hits >= 2:
                    if _trig_hits >= 4:
                        print(f"  \U0001f534 上章裂隙触发词出现{_trig_hits}次: {_trig_detail}")
                        print(f"     \u2192 \u5efa\u8bae\u672c\u7ae0\u5199\u4e00\u6bb5\u89e3\u79bb\u620f")
                    else:
                        print(f"  \u26a0\ufe0f 上章裂隙触发词出现{_trig_hits}次: {_trig_detail}")
            except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
                print(f"  [WARN] read prev state failed: {exc}")

    if char_cards or chars:
        print(f"  \u2500\u2500\u2500 \u51fa\u573a\u89d2\u8272 \u2500\u2500\u2500")
        for c in chars[:5]:
            name = c['name']
            card = char_cards.get(name, {})
            voice = card.get("voice", {})
            personality = card.get("personality", {})
            behavior = card.get("behavior", {})
            mental = mental_states.get(name, {})

            parts = []
            # Personality core
            core = personality.get("core", "")
            if core:
                core_clean = core.replace("\uff08", "(").replace("\uff09", ")")
                parts.append(core_clean)

            # Dialect (first clause only)
            dialect = voice.get("dialect", "")
            if dialect:
                dialect_short = dialect.split("\uff0c")[0].split(",")[0].strip()
                if len(dialect_short) > 10:
                    dialect_short = dialect_short[:10]
                parts.append(dialect_short)

            # Signature item from habits (heuristic: 用X量/记/写/带/拿/握/挂/绑)
            habits = behavior.get("habits", [])
            if isinstance(habits, list) and habits:
                for h in habits:
                    obj_match = re.search(r'\u7528([\u4e00-\u9fff]{2,4})(?:\u91cf|\u8bb0|\u5199|\u5e26|\u62ff|\u63e1|\u6302|\u7ed1|\u7f20|\u6234|\u88c5|\u653e|\u63a8|\u62c9|\u5256|\u780d|\u5288|\u70b9|\u6572)', h)
                    if obj_match:
                        parts.append(obj_match.group(1))
                        break

            # Mental state severity if non-zero
            if mental:
                active = [(k, v.get("severity", 0)) for k, v in mental.items()
                          if isinstance(v, dict) and v.get("severity", 0) > 0]
                if active:
                    ms_label = ",".join(f"{k}({v})" for k, v in sorted(active, key=lambda x: -x[1])[:2])
                    parts.append(ms_label)

            if parts:
                print(f"  {name:6s} | {' | '.join(parts)}")
        if not chars:
            print(f"  (无角色数据)")

        # ── 连续缺场角色提醒 ──
        absent_warnings = []
        for c in chars:
            cname = c['name']
            # Check last 10 chapters for consecutive absence
            recent_chs = cur.execute(
                "SELECT c.chapter_no, cs.characters_involved FROM chapter_summaries cs "
                "JOIN chapters c ON c.id=cs.chapter_id "
                "WHERE c.novel_id=? AND c.chapter_no < ? "
                "ORDER BY c.chapter_no DESC LIMIT 10",
                (nid, chapter_no)).fetchall()
            consecutive_missing = 0
            for ch_row in recent_chs:
                involved = ch_row['characters_involved'] or ""
                if cname not in involved:
                    consecutive_missing += 1
                else:
                    break
            if consecutive_missing >= 3:
                absent_warnings.append(f"\u26a0\ufe0f {cname}\u5df2\u8fde\u7eed{consecutive_missing}\u7ae0\u672a\u51fa\u573a")
        if absent_warnings:
            for w in absent_warnings[:3]:
                print(f"  {w}")

    # ── 角色关系网络 ──
    try:
        from src.guards.human_texture.voice_diversity_guard import list_relations
        rels = list_relations(PROJECT_ROOT)
        if rels:
            char_rels = {}
            for r in rels:
                a, b, t = r["char_a"], r["char_b"], r["type"]
                char_rels.setdefault(a, {}).setdefault(t, []).append(b)
                char_rels.setdefault(b, {}).setdefault(t, []).append(a)
            our_names = {c['name'] for c in chars}
            relevant = {k: v for k, v in char_rels.items() if k in our_names}
            if relevant:
                print(f"  ─── 角色关系 ───")
                for cname in sorted(relevant.keys()):
                    for rtype, others in relevant[cname].items():
                        others_str = "、".join(others)
                        print(f"  {cname} ←{rtype}→ {others_str}")
        elif chars and chapter_no <= 3:
            # v0.8.0: 首次写作时自动从大纲提取角色关系
            try:
                from src.outline.outline_manager import OutlineManager
                _om = OutlineManager(PROJECT_ROOT)
                _outline = _om.current_outline()
                if _outline:
                    _total_extracted = _om._auto_extract_relations(_outline.get("content", ""))
                    if _total_extracted:
                        # Re-display after extraction
                        _rels = list_relations(PROJECT_ROOT)
                        if _rels:
                            char_rels2 = {}
                            for r in _rels:
                                a, b, t = r["char_a"], r["char_b"], r["type"]
                                char_rels2.setdefault(a, {}).setdefault(t, []).append(b)
                                char_rels2.setdefault(b, {}).setdefault(t, []).append(a)
                            _relevant2 = {k: v for k, v in char_rels2.items() if k in our_names}
                            if _relevant2:
                                print(f"  ─── 角色关系 ───")
                                for cname in sorted(_relevant2.keys()):
                                    for rtype, others in _relevant2[cname].items():
                                        others_str = "、".join(others)
                                        print(f"  {cname} ←{rtype}→ {others_str}")
            except (ImportError, AttributeError, KeyError, TypeError) as exc:
                print(f"  [WARN] auto-extract relations failed: {exc}")
    except (ImportError, AttributeError, KeyError, TypeError) as exc:
        print(f"  [WARN] character relations skipped: {exc}")

    # ── 2.3 审稿建议 → writing_rules 自动固化 ──
    if jury and jury.get("chief_editor"):
        all_items = jury["chief_editor"].get("must_fix", []) + jury["chief_editor"].get("should_fix", [])
        auto_rules = _extract_learnable_rules(all_items, prev_ch)
        if auto_rules:
            _saved = _auto_write_rules(cur, nid, auto_rules, prev_ch)
            if _saved > 0:
                print(f"  [LEARN] 自动写入{_saved}条写作规则")

    print(f"{'='*60}")

    cur.execute("INSERT INTO novel_logs(action,target_type,detail) VALUES('pre_write','chapter',?)", ("; ".join(log_entries),))
    conn.commit(); conn.close()

    # 保存 pipeline_state.json
    app.state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "chapter_no": chapter_no, "chapter_type": chapter_type,
        "genre": genre,  # Phase 4: 从 novels 表读取
        "pre_done": True, "previous_tail_loaded": prev_ch >= 1,
        "recent_summaries_loaded": True, "sqlite_search_logged": True,
        "reader_promises_checked": True, "context_pack": str(pack_path),
        "allowed_to_write": True, "timestamp": now()
    }
    state_path = app.state_dir / f"chapter_{chapter_no:03d}_state.json"
    write_json_atomic(state_path, state)
    print(f"  [OK] pipeline_state: {state_path}")

    print(f"\nSTEP 1 [OK] — 上下文就绪")
    return {"chapter_no": chapter_no, "prev_ch": prev_ch, "prev_ending": prev_ending,
            "chapter_type": chapter_type, "context_pack": str(pack_path)}


# ============================================================
# STEP 4: WORD_COUNT — 字数门禁
# ============================================================
