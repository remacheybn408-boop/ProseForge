#!/usr/bin/env python3
"""post.py — Post-write processing pipeline.

Runs word-count gating, guard orchestration, human-texture checks,
deduplicated revision tasks, ingest, stage review, and full agent review.
"""

import re, json, sys, os, sqlite3
from pathlib import Path
from datetime import datetime, timezone
from version import get_version
from src.pipeline._base import (
    App, now, connect, _get_novel_id, ensure_tables,
    _find_chapter_file, find_chapter_file_with_fallback, _arabic_to_chinese_numeral,
    write_json_atomic,
    _strip_selfcheck, _count_chinese, _resolve_slot_db_path,
    load_config,
)
from src.pipeline.ingest import ingest, stage_review
from src.runtime import build_guard_context

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
app = None


def _configure_console_output():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

def word_count_gate(content, chapter_no, chapter_type="normal", genre=None, app_inst=None):
    """字数门禁 V6：支持题材差异化。有 genre 时从 genre_presets.yaml 读取 min_words。"""
    if app_inst is None:
        app_inst = app
    if app_inst is None:
        raise RuntimeError("word_count_gate requires app_inst/context")
    rules = app_inst.wc_rules.get(chapter_type, app_inst.wc_default).copy()
    # v0.7.1: 题材感知 — 优先用 genre preset 的 min_words 覆盖 config.json 的硬编码
    if genre:
        try:
            import yaml
            _preset_path = Path("configs") / "human_texture" / "genre_presets.yaml"
            if _preset_path.exists():
                all_presets = yaml.safe_load(_preset_path.read_text(encoding="utf-8"))
                genre_preset = all_presets.get(genre, all_presets.get("default", {}))
                _genre_min = genre_preset.get("min_words")
                if _genre_min is not None:
                    rules["min"] = _genre_min
                    print(f"  [INFO] genre '{genre}' min words: {_genre_min}")
                _genre_max = genre_preset.get("max_words")
                if _genre_max is not None:
                    rules["max"] = _genre_max
                    print(f"  [INFO] genre '{genre}' max words: {_genre_max}")
        except Exception:
            pass
    wc = _count_chinese(content)
    print(f"\n{'='*50}\nSTEP 4: 字数门禁 [{chapter_type}]\n{'='*50}")
    print(f"  字数: {wc} | 范围: {rules['min']}-{rules['max']} | 最佳: {rules['best_min']}-{rules['best_max']}")

    _eff_min = rules['min']
    if wc < _eff_min:
        short_rules = app_inst.wc_rules.get("authorized_short", {})
        short_min = short_rules.get("min")
        short_max = short_rules.get("max")
        if (
            getattr(app_inst, "allow_short_chapter", False)
            and short_min is not None
            and short_max is not None
            and short_min <= wc <= short_max
        ):
            print(f"  [OK] authorized short chapter ({short_min}-{short_max})")
            return "authorized_short", wc, _eff_min
        print(f"  [FAIL] 低于最低线 ({wc} < {_eff_min}) — 需补场景或授权短章")
        return False, wc, _eff_min

    if rules['best_min'] <= wc <= rules['best_max']:
        print("  [OK] ideal range")
        return "ideal", wc, _eff_min

    if rules['best_max'] < wc <= rules['max']:
        print(f"  [OK] 正常通过 (偏长)")
        return True, wc, _eff_min

    if wc > rules['max']:
        if chapter_type in ("climax", "volume_finale") and wc <= 5500:
            print(f"  [OK] 高潮/卷末章允许长篇幅")
            return True, wc, _eff_min
        print(f"  [WARN] 超上限 ({wc}>{rules['max']}) — 建议拆章或精简")
        return "oversize", wc, _eff_min

    return True, wc, _eff_min

# CHAPTER_BRIEF — 生成章节摘要 JSON
# ============================================================


def run_post(
    chapter_no,
    chapter_type="normal",
    novel_slug="demo_novel",
    novel_title="",
    volume_no=1,
    chapters_dir=None,
    db_path=None,
    merge_if_short=False,
    genre=None,
    pace=None,
    project_root=None,
    config_path=None,
    context=None,
):
    """Unified entry point for chapter post-processing."""
    import argparse
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
    cfg = app.cfg
    ensure_tables(app)

    # Build args namespace for backward compat with extracted code
    args = argparse.Namespace(
        action="post", chapter_no=chapter_no, chapter_type=chapter_type,
        config=None, novel_slug=novel_slug, novel_title=novel_title,
        volume_no=volume_no, chapters_dir=chapters_dir, db_path=db_path,
        merge_if_short=merge_if_short, genre=genre, pace=pace,
    )


    candidates = find_chapter_file_with_fallback(chapter_no, app)
    if not candidates:
        raise RuntimeError(f"找不到第{chapter_no}章TXT (目录: {app.chapters_dir})")

    # 检查 pre 是否完成（允许 bootstrapped minimal state）
    state_path = app.state_dir / f"chapter_{chapter_no:03d}_state.json"
    if not state_path.exists():
        # Bootstrap minimal state — post doesn't need full pre
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state = {"allowed_to_write": True, "genre": "", "chapter_no": chapter_no,
                 "timestamp": datetime.now().isoformat(), "_bootstrapped": True}
        write_json_atomic(state_path, state)
        print(f"[OK] 已生成最小 pipeline_state (post 无需完整 pre)")
    else:
        state = json.loads(state_path.read_text(encoding='utf-8'))
        if not state.get("allowed_to_write"):
            raise RuntimeError("pre 未完成，禁止 post")
        print("[OK] pipeline_state verified (pre completed at {})".format(state.get("timestamp", "?")))

# v0.4.5: FTS5 health check before post
    try:
        from src.utils.fts_health import ensure_fts_healthy
        fts_result = ensure_fts_healthy(cfg)
        health_before = fts_result.get("health_before", {})
        print(f"  [FTS] scope: {health_before.get('total_tables', 0)} table(s)")
        for step in fts_result.get("repair", {}).get("progress", []):
            if step.get("status") == "repaired":
                print(f"  [FTS] {step['index']}/{step['total_tables']} {step['table']} -> {step.get('method', 'rebuild')}")
        if fts_result["action"] == "repaired":
            print(f"  [FTS] repaired: {fts_result.get('repair',{}).get('repaired_count',0)} table(s)")
        elif fts_result["action"] == "repair_failed":
            print(f"  [WARN] FTS repair failed — fallback LIKE search will be used")
    except ImportError:
        pass

    with open(candidates, 'r', encoding='utf-8') as f:
        content = _strip_selfcheck(f.read())

# ── 1.2 裂隙触发词检测 ──
    _fissure_triggers = ["水", "冷水", "刹车声", "玻璃碎裂",
                        "强光", "血味", "安全带", "束缚感"]
    _trigger_hits = 0
    _trigger_detail = {}
    for _tw in _fissure_triggers:
        _cnt = content.count(_tw)
        if _cnt > 0:
            _trigger_hits += _cnt
            _trigger_detail[_tw] = _cnt
    if _trigger_hits > 0:
        print(f"\n  [林观澜裂隙触发] 命中{_trigger_hits}次: {_trigger_detail}")
        state["裂隙触发词命中"] = _trigger_hits
        state["裂隙触发词详情"] = _trigger_detail
        write_json_atomic(state_path, state)
        if _trigger_hits <= 2:
            print(f"  ℹ️ 命中0-2次，不提示")
        elif _trigger_hits <= 3:
            print(f"  ⚠️ 裂隙触发词出现{_trigger_hits}次")
        else:
            print(f"  \U0001f534 裂隙加重，建议写一段解离戏")

# STEP 4: word_count
    _pipeline_genre = state.get("genre", "") if state else ""
# v0.7.1 fix: fallback to novels table if pipeline_state lacks genre (e.g. pre ran before genre was set)
    if not _pipeline_genre:
        try:
            conn3 = sqlite3.connect(str(app.db_path))
            cur3 = conn3.cursor()
            row3 = cur3.execute("SELECT genre FROM novels WHERE slug=?", (app.novel_slug,)).fetchone()
            if row3 and row3[0]:
                _pipeline_genre = row3[0]
            conn3.close()
        except Exception:
            pass
    wc_pass, wc, eff_min = word_count_gate(
        content,
        chapter_no,
        chapter_type,
        genre=_pipeline_genre or None,
        app_inst=app,
    )
    if wc_pass == False:
    # ── v0.4.5: 自动合并下一章 ──
        if args.merge_if_short:
            next_candidate = find_chapter_file_with_fallback(chapter_no + 1, app)
            if next_candidate:
                next_content = _strip_selfcheck(next_candidate.read_text(encoding='utf-8'))
                merged = content.rstrip() + "\n\n---\n\n" + next_content
            # Save merged content
                merged_path = candidates
                merged_path.write_text(merged, encoding='utf-8')
            # Rename next chapter as merged backup
                bak = str(next_candidate) + ".merged"
                next_candidate.rename(bak)
                print(f"\n[MERGE] chapter {chapter_no} ({wc} chars) merged with chapter {chapter_no + 1}")
                print(f"  [OK] merged content saved: {merged_path.name}")
                print(f"  [OK] next chapter backed up: {Path(bak).name}")
            # Re-check word count with merged content
                content = merged
                wc_pass, wc, eff_min2 = word_count_gate(
                    content,
                    chapter_no,
                    chapter_type,
                    genre=_pipeline_genre or None,
                    app_inst=app,
                )
                if wc_pass == False:
                    raise RuntimeError(f"合并后仍不足 {eff_min2} 字 (实际: {wc})")
            else:
                raise RuntimeError(f"word count gate failed and chapter {chapter_no + 1} was not available to merge; short by {eff_min - wc} chars")
        else:
            raise RuntimeError(f"word count gate failed; short by {eff_min - wc} chars")

# Read prev_brief/prev_tail once for all downstream guards
    prev_brief_path = app.exports_root / "chapter_briefs" / f"chapter_{chapter_no-1:03d}_brief.json"
    prev_brief = None
    prev_tail_text = ""
    if prev_brief_path.exists():
        try:
            prev_brief = json.loads(prev_brief_path.read_text(encoding='utf-8'))
            prev_tail_text = prev_brief.get("ending_state", "")
        except Exception: pass

    ce_reports_dir = app.exports_root / "reports"
    ce_reports_dir.mkdir(parents=True, exist_ok=True)

# ── STEP 7.6: Guard Orchestrator (single entry for all registered guards) ──
# v0.8.0: L1 安全 (continuity / canon / hallucination / scene_delta) +
#         L2 五个聚合 (scene_grounding / narrative_rhythm / dialogue_quality /
#                     prose_authenticity / reader_engagement) +
#         L3 compliance — 总计 10 个 guard 统一由 orchestrator 跑。
    quality_policy = cfg.get("quality_policy", {})
    orchestrator_mode = quality_policy.get("run_mode", "standard")

# Voice context（profiles/packs/narration_policy）供 dialogue_quality_guard /
# prose_authenticity_guard 的子检测使用；通过 extra_context 透传。
    selected_genre = _pipeline_genre or args.genre or cfg.get("default_genre", "default")
    extra_context = build_guard_context(
        app,
        chapter_no=chapter_no,
        prev_brief=prev_brief,
        genre=selected_genre,
    )
    try:
        from src.utils.voice_profile_loader import load_voice_context
        voice_context = load_voice_context(cfg, app.novel_slug)
        if voice_context["enabled"]:
            extra_context = build_guard_context(
                app,
                chapter_no=chapter_no,
                prev_brief=prev_brief,
                genre=selected_genre,
                voice_context=voice_context,
            )
            print(f"  [VOICE] {voice_context['source']}: {len(voice_context['profiles'])} profiles, {len(voice_context['packs'])} packs")
    except Exception:
        pass

    orch_report = None
    try:
        from src.pipeline.guard_orchestrator import run_orchestrated
        orch_report = run_orchestrated(
            content, chapter_no, mode=orchestrator_mode,
            config=cfg, reports_dir=str(ce_reports_dir),
            prev_tail=prev_tail_text, prev_brief=prev_brief,
            extra_context=extra_context)
        orch_path = ce_reports_dir / f"chapter_{chapter_no:03d}_orchestrator_report.json"
        orch_path.write_text(json.dumps(orch_report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [OK] orchestrator ({orchestrator_mode}): {len(orch_report['executed_guards'])} guards, {orch_report['warning_count']} warnings")
        if orch_report.get("blocked_by"):
            print(f"  [BLOCK] compliance: {orch_report['blocked_by']}")
        if orch_report.get("fail_count", 0) > 0:
            failed = orch_report.get("failed_guards", orch_report.get("executed_guards", []))
            print(f"  [WARN] {orch_report['fail_count']} guard(s) FAIL (level 1/2) — ingest 继续但需复查")

    # ── STEP 7.7: Punctuation Guard ──
        try:
            from src.guards.punctuation_guard import run_punctuation_check
            punct = run_punctuation_check(content, chapter_no)
            punct_status = punct["status"]
            dash_pairs = punct["stats"]["dash_pairs"]
            dash_per_kw = dash_pairs * 1000 / max(punct["stats"]["word_count"], 1)
            if punct_status == "FAIL":
                print(f"  ⚠️ 标点节奏: FAIL ({dash_pairs}组破折号, {dash_per_kw:.1f}/千字)")
            elif punct_status == "WARNING":
                print(f"  ⚠️ 标点节奏: WARN ({dash_pairs}组破折号, {dash_per_kw:.1f}/千字)")
            else:
                print(f"  ✅ 标点节奏: PASS ({dash_pairs}组破折号)")
        except Exception as e:
            print(f"  [INFO] punctuation guard skipped: {e}")

    # ── STEP 7.8: Human Texture Quality Layer (人工味质量层) ──
        try:
            from src.guards.human_texture import run_human_texture_guards
        # Phase 4: 优先 pipeline_state 中的 genre（由 pre 从 DB 读取）
            _state_genre = app.state_dir / f"chapter_{chapter_no:03d}_state.json"
            _pipeline_genre = ""
            if _state_genre.exists():
                try:
                    _ps = json.loads(_state_genre.read_text(encoding="utf-8"))
                    _pipeline_genre = _ps.get("genre", "")
                except Exception: pass
            genre = selected_genre
            pace_level = args.pace or quality_policy.get("pace_level", "normal")
            texture_report = run_human_texture_guards(
                content, chapter_no,
                project_root=str(_PROJECT_ROOT),
                genre=genre,
                pace_level=pace_level,
            )
            texture_path = ce_reports_dir / f"chapter_{chapter_no:03d}_texture_report.json"
            texture_path.write_text(json.dumps(texture_report, ensure_ascii=False, indent=2), encoding="utf-8")
            scores = texture_report.get("scores", {})
            texture_status = texture_report.get("status", "?")
            print(f"  [OK] human_texture: {len(scores)} guards, status={texture_status}")
            for gname, score in sorted(scores.items()):
                icon = "PASS" if score >= 70 else ("WARN" if score >= 55 else "FAIL")
                short = gname.replace("_guard", "").replace("_", " ")
                print(f"    {icon} {short:25s} {score}/100")
            if texture_status == "FAIL":
                print("  [BLOCK] human_texture quality gate failed")

        # ── 4.1 texture 趋势对比 ──
            _trend = {"direction": "first", "delta": "", "deltas": {}}
            _prev_tex_path = ce_reports_dir / f"chapter_{chapter_no - 1:03d}_texture_report.json"
            if _prev_tex_path.exists():
                try:
                    _prev_tex = json.loads(_prev_tex_path.read_text(encoding="utf-8"))
                    _prev_scores = _prev_tex.get("scores", {})
                    _deltas = {}
                    _up = _down = _same = 0
                    for _gname, _score in scores.items():
                        _prev = _prev_scores.get(_gname)
                        if _prev is not None and isinstance(_prev, (int, float)):
                            _d = _score - _prev
                            _deltas[_gname] = _d
                            if _d > 3: _up += 1
                            elif _d < -3: _down += 1
                            else: _same += 1
                    if _deltas:
                        _avg_delta = sum(_deltas.values()) / len(_deltas) if _deltas else 0
                        _trend["direction"] = "up" if _up > _down else ("down" if _down > _up else "stable")
                        _trend["delta"] = f"{_avg_delta:+.1f}"
                        _trend["deltas"] = _deltas
                    # Rewrite texture report with trend data
                        texture_report["trend"] = _trend
                        texture_path.write_text(json.dumps(texture_report, ensure_ascii=False, indent=2), encoding="utf-8")
                        _dir_icon = {"up": "^", "down": "v", "stable": "="}.get(_trend["direction"], "")
                        _changed = {k: v for k, v in _deltas.items() if abs(v) > 3}
                        if _changed:
                            _trend_parts = [f"{k.replace('_guard','').replace('_',' ')}:{_dir_icon}{v:+d}" for k, v in sorted(_changed.items(), key=lambda x: -abs(x[1]))[:4]]
                            print("  [TREND] vs chapter {}: {}".format(chapter_no - 1, " | ".join(_trend_parts)))
                except Exception:
                    pass
        except Exception as e:
            print(f"  [WARN] human_texture skipped: {e}")


    # ── 去重 + Top 5 修改任务 ──
        try:
            if quality_policy.get("deduplicate_warnings", True) and orch_report:
                from src.pipeline.report_deduplicator import deduplicate_warnings, get_top_revision_tasks
                merged = deduplicate_warnings(
                    orch_report.get("warnings", []),
                    quality_policy.get("min_warning_confidence", 0.55))
                tasks = get_top_revision_tasks(
                    merged, quality_policy.get("max_final_revision_tasks", 5))
                dedup_path = ce_reports_dir / f"chapter_{chapter_no:03d}_deduplicated_report.json"
                dedup_path.write_text(json.dumps({
                    "version": get_version(), "merged_issues": merged,
                    "top_revision_tasks": tasks,
                }, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"  [OK] deduplicated: {len(merged)} issues → {len(tasks)} tasks")
                if tasks:
                    for t in tasks[:3]:
                        print(f"    {t['rank']}. {t['issue']}")
        except Exception as e:
            print(f"  [WARN] dedup skipped: {e}")
    except Exception as e:
        print(f"  [WARN] orchestrator failed: {e}")

# STEP 8: ingest
    result = ingest(chapter_no, chapter_type, app_inst=app)
    if not result:
        raise RuntimeError(f"ingest failed for chapter {chapter_no}")

# 三章复盘
    stage_review(chapter_no, app_inst=app)

# ── 写作后自动流程：精神状态检查 + 完整审稿 + 改稿建议 ──
    try:
    # 1. 精神状态跨章跟踪（简易文件版）
        import os as _os
        _track_file = app.workspace_root / app.active_slot / "ptsd_tracker.json"
        _triggers = ["水", "冷水", "刹车声", "玻璃", "碎裂", "强光", "血味", "安全带", "束缚", "车祸"]
        _hits = sum(1 for _t in _triggers if _t in content)
        _tracker = {"chapter": chapter_no, "hits": _hits}
        if _track_file.exists():
            try:
                _prev = json.loads(_track_file.read_text(encoding="utf-8"))
                if isinstance(_prev, list):
                    _prev.append(_tracker)
                    _total = sum(t["hits"] for t in _prev[-5:])
                else:
                    _prev = [_prev, _tracker]
                    _total = _hits
            except Exception:
                _prev = [_tracker]
                _total = _hits
        else:
            _prev = [_tracker]
            _total = _hits
        _track_file.write_text(json.dumps(_prev, ensure_ascii=False), encoding="utf-8")
        if _hits >= 2:
            print(f"  [MENTAL] PTSD trigger terms hit {_hits} times; last five chapters total {_total}")
            if _total >= 8:
                print("    [WARN] consider adding a decompression scene in this chapter")
    except Exception as _e:
        print(f"  [WARN] PTSD tracker skipped: {_e}")

    try:
    # 2. 完整审稿
        from src.agents.orchestrator import run_agent_review
        _full = run_agent_review(content, chapter_no=chapter_no, mode="full")
        if _full:
            _score = _full.get("overall_score", "?")
            _status = _full.get("status", "?")
            print(f"  [REVIEW] full mode: score {_score}, status {_status}")
            _ce = _full.get("chief_editor", {})
            if isinstance(_ce, dict):
                _summary = _ce.get("suggestion", "")
                if _summary:
                    print(f"    chief editor summary: {str(_summary)[:120]}")
                _f = _ce.get("should_fix", [])
                if isinstance(_f, list):
                    for _item in _f[:2]:
                        _txt = str(_item.get("issue", _item))[:100]
                        print(f"    🔴 {_txt}")
    except Exception as _e:
        print(f"  [WARN] agent review skipped: {_e}")

    try:
    # 3. 改稿检测（v0.8.0：从聚合 guard 报告下钻 _guards_raw 取 padding / anti_ai 子项）
        _reports_dir = app.exports_root / "reports"
        if _reports_dir.exists():
            _fixes = []

            def _load_sub(parent_guard: str, sub_guard: str):
                _path = _reports_dir / f"chapter_{chapter_no:03d}_{parent_guard}_report.json"
                if not _path.exists():
                    return None
                try:
                    _data = json.loads(_path.read_text(encoding="utf-8"))
                except Exception:
                    return None
                # v0.8.0: _guards_raw 经 GuardResult.to_dict() 包进 metrics；旧聚合 dict 仍在顶层
                _subs = (_data.get("_guards_raw")
                         or (_data.get("metrics") or {}).get("_guards_raw")
                         or [])
                for _sub in _subs:
                    if isinstance(_sub, dict) and _sub.get("guard") == sub_guard:
                        return _sub
                return None

            _padding = _load_sub("narrative_rhythm_guard", "padding_guard")
            if _padding:
                if _padding.get("padding_detected") and _padding.get("padding_evidence"):
                    _ev = _padding["padding_evidence"]
                    if isinstance(_ev, list):
                        _fixes.extend([f"水文: {str(e)[:60]}" for e in _ev[:2]])

            _ai = _load_sub("prose_authenticity_guard", "anti_ai_guard")
            if _ai:
                _findings = _ai.get("findings", [])
                if isinstance(_findings, list):
                    for _f_item in _findings:
                        _msg = _f_item.get("message", "") if isinstance(_f_item, dict) else str(_f_item)
                        if _msg and len(_msg) > 5:
                            _fixes.append(_msg[:80])
                elif isinstance(_findings, dict):
                    for _k, _v in _findings.items():
                        if isinstance(_v, (list, dict)) and len(str(_v)) > 5:
                            _fixes.append(f"AI腔调: {_k}")

            if _fixes:
                print(f"  [改稿] 检测到{len(_fixes)}处可优化")
                for _f in _fixes[:3]:
                    print(f"    🟡 {_f}")
    except Exception as _e:
        print(f"  [WARN] fix detection skipped: {_e}")

    print(f"\n{'='*60}")
    print("chapter {} post-processing complete [OK] {} chars v{}".format(chapter_no, wc, result["version"]))
    print(f"{'='*60}")
