#!/usr/bin/env python3
"""volume.py — Volume-level summaries and bridge reporting.

The main entry point produces volume_report and volume_bridge_report.
Deviation scoring and auto-learn helpers live in this module but are not the
headline behavior of volume_post().
"""

import re, json, sys, os, math
from pathlib import Path
from datetime import datetime
from version import get_version
from src.pipeline._base import (
    App, now, connect, _get_novel_id, ensure_tables,
    _count_chinese, _resolve_slot_db_path, load_config,
)
from src.pipeline.ingest import generate_chapter_brief

def volume_post(
    novel_slug="demo_novel",
    novel_title="",
    volume_no=1,
    db_path=None,
    chapters_dir=None,
    project_root=None,
    config_path=None,
    context=None,
):
    """卷级后处理：统计 + 状态 + 下一卷承接点"""
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
    ts = now()

    if nid is None:
        print(f"[FAIL] 小说 '{app.novel_slug}' 不存在于数据库"); conn.close(); return

    vol_no = app.volume_no

    # 统计本卷章节（通过 chapter_plans 找已写入的）
    cur.execute("""SELECT c.chapter_no, c.title, c.word_count, c.status
        FROM chapters c
        JOIN chapter_plans cp ON cp.novel_id=c.novel_id AND cp.chapter_no=c.chapter_no AND cp.volume_no=?
        WHERE c.novel_id=?
        ORDER BY c.chapter_no""",
        (vol_no, nid))
    chapters = cur.fetchall()
    if not chapters:
        print(f"[FAIL] 第{vol_no}卷无章节数据"); conn.close(); return

    total_ch = len(chapters)
    total_wc = sum(c['word_count'] for c in chapters)
    drafts = [c for c in chapters if c['status'] != 'final']

    # 卷计划
    vol_plan = cur.execute("SELECT * FROM volume_plans WHERE novel_id=? AND volume_no=?", (nid, vol_no)).fetchone()

    # 上一卷结尾（用于连续）
    prev_vol = None
    if vol_no > 1:
        prev_vol = cur.execute("SELECT volume_no, title FROM volumes WHERE novel_id=? AND volume_no=?",
            (nid, vol_no - 1)).fetchone()

    # 角色状态（最近的角色弧线变化）
    cur.execute("SELECT name, role, status, arc FROM characters WHERE novel_id=? AND status='active'", (nid,))
    active_chars = cur.fetchall()

    # 伏笔状态
    cur.execute("SELECT title, status, introduced_chapter FROM plot_threads WHERE novel_id=? AND status IN ('open','active') ORDER BY importance DESC", (nid,))
    open_threads = cur.fetchall()

    # 读者承诺状态
    cur.execute(
        "SELECT promise_title, status, introduced_chapter, importance "
        "FROM reader_promises WHERE novel_id=? AND status='open' ORDER BY importance DESC",
        (nid,)
    )
    open_promises = cur.fetchall()

    print("=" * 60)
    print(f"VOLUME POST — 第{vol_no}卷")
    print("=" * 60)
    print(f"  章节数: {total_ch}")
    print(f"  总字数: {total_wc:,}")
    print(f"  均字数: {total_wc // total_ch if total_ch else 0}")
    if drafts:
        print(f"  [WARN] {len(drafts)}章非final状态: {[c['chapter_no'] for c in drafts]}")

    if vol_plan:
        ending_target = vol_plan['ending_target'] or '(未设定)'
        unresolved = vol_plan['unresolved_hooks_to_next'] or '(无)'
        print(f"\n  卷目标完成状态:")
        print(f"    计划结局: {ending_target}")
        print(f"    遗留钩子: {unresolved}")

    if open_threads:
        print(f"\n  开放伏笔 ({len(open_threads)}):")
        for t in open_threads[:8]:
            print(f"    [{t['status']}] {t['title']} (引入: 第{t['introduced_chapter'] or '?'}章)")

    if active_chars:
        print(f"\n  活跃角色 ({len(active_chars)}):")
        for c in active_chars[:10]:
            arc_info = f" — {c['arc'][:60]}" if c['arc'] else ""
            print(f"    [{c['role']}] {c['name']}{arc_info}")

    # 下一卷承接点
    if vol_plan and vol_plan['unresolved_hooks_to_next']:
        print(f"\n  >>> 下一卷承接点 <<<")
        print(f"  {vol_plan['unresolved_hooks_to_next']}")

    print(f"\n  [OK] 卷级总结完成")

    # 更新 volume_plans 标记
    if vol_plan:
        cur.execute("UPDATE volume_plans SET updated_at=? WHERE novel_id=? AND volume_no=?",
            (ts, nid, vol_no))

    cur.execute("INSERT INTO novel_logs(action,target_type,detail) VALUES('volume_post','volume',?)",
        (f"第{vol_no}卷:{total_ch}章{total_wc}字",))
    conn.commit()
    conn.close()

    # ── 输出 volume_report.json ──
    reports_dir = app.exports_root / "volume_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    completed = total_ch - len(drafts)
    report = {
        "novel_slug": app.novel_slug,
        "volume_no": vol_no,
        "volume_title": vol_plan['planned_title'] if vol_plan else f"第{vol_no}卷",
        "total_chapters": total_ch,
        "completed_chapters": completed,
        "unfinished_chapters": len(drafts),
        "total_word_count": total_wc,
        "average_word_count": total_wc // total_ch if total_ch else 0,
        "volume_goal": vol_plan['volume_goal'] if vol_plan else "",
        "volume_goal_completion_status": "partial" if drafts else "complete",
        "opening_state": vol_plan['opening_state'] if vol_plan else "",
        "ending_state": vol_plan['ending_target'] if vol_plan else "",
        "open_plot_threads": [{"title": t['title'], "status": t['status']} for t in open_threads],
        "open_reader_promises": [
            {"title": p["promise_title"], "status": p["status"],
             "introduced_chapter": p["introduced_chapter"], "importance": p["importance"]}
            for p in open_promises
        ],
        "character_arc_updates": [{"name": c['name'], "role": c['role']} for c in active_chars],
        "unresolved_hooks_to_next": vol_plan['unresolved_hooks_to_next'] if vol_plan else "",
        "next_volume_opening_requirements": f"承接第{vol_no}卷结尾，处理遗留钩子",
        "quality_flags": "drafts_exist" if drafts else "all_final",
        "created_at": ts
    }
    report_path = reports_dir / f"volume_{vol_no:02d}_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"  [OK] volume_report: {report_path}")

    # ── volume_bridge_report.json ──
    bridge_dir = app.exports_root / "volumes"
    bridge_dir.mkdir(parents=True, exist_ok=True)
    bridge_report = {
        "volume_no": vol_no,
        "next_volume_no": vol_no + 1,
        "volume_post_done": True,
        "volume_summary_path": str(report_path),
        "ending_state": {
            "main_plot": vol_plan['ending_target'] if vol_plan else "",
            "character_state": f"{len(active_chars)} active characters",
            "world_state": report.get("volume_goal", "")
        },
        "unresolved_hooks_to_next": vol_plan['unresolved_hooks_to_next'] if vol_plan else "",
        "next_volume_opening_requirements": [
            f"第{vol_no+1}卷开头必须承接第{vol_no}卷结尾",
            f"处理遗留钩子: {vol_plan['unresolved_hooks_to_next'] if vol_plan else '(无)'}",
            f"第{vol_no}卷角色状态同步"
        ],
        "bridge_items_acknowledged": [],
        "bridge_score": 1.0,
        "next_volume_allowed": True
    }
    bridge_path = bridge_dir / f"volume_{vol_no:02d}_bridge_report.json"
    bridge_path.write_text(json.dumps(bridge_report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"  [OK] volume_bridge_report: {bridge_path}")


# ============================================================
# 3.2 Story deviation calculation
# ============================================================
def _resolve_story_for_deviation():
    """Resolve .story/ directory from active slot, for deviation calculation.

    Delegates to the canonical `src.story.resolve_story_dir` (M2 dedup). Passing
    `Path(".")` preserves the original cwd-relative `workspace/` lookup behavior.
    """
    from src.story import resolve_story_dir
    return resolve_story_dir(Path("."))


def _calc_story_deviation(cur, nid, chapter_no, story_dir):
    """Calculate deviation score 0-100. Higher = more off-track."""
    deviation = 0
    details = []

    # ── 连续5章未兑现伏笔：+10/每条 ──
    stale_ch = chapter_no - 5
    if stale_ch >= 1:
        stale_threads = cur.execute(
            "SELECT title, introduced_chapter FROM plot_threads "
            "WHERE novel_id=? AND status='open' AND introduced_chapter <= ?",
            (nid, stale_ch)).fetchall()
        if stale_threads:
            penalty = len(stale_threads) * 10
            deviation += penalty
            names = [f"{t['title']}(已搁置{chapter_no - t['introduced_chapter']}章)" for t in stale_threads[:3]]
            details.append(f"伏笔未兑现: {', '.join(names)}")
            if len(stale_threads) > 3:
                details[-1] += f" 等{len(stale_threads)}条"

    # ── 连续5章未兑现读者承诺：+10/每条 ──
    if stale_ch >= 1:
        stale_promises = cur.execute(
            "SELECT promise_title, introduced_chapter FROM reader_promises "
            "WHERE novel_id=? AND status='open' AND introduced_chapter <= ?",
            (nid, stale_ch)).fetchall()
        if stale_promises:
            penalty = len(stale_promises) * 10
            deviation += penalty
            names = [f"{p['promise_title']}(已搁置{chapter_no - p['introduced_chapter']}章)" for p in stale_promises[:3]]
            details.append(f"读者承诺未兑现: {', '.join(names)}")
            if len(stale_promises) > 3:
                details[-1] += f" 等{len(stale_promises)}条"

    # ── 角色弧线进度停滞（连续5章同一角色弧线%不变）：+15 ──
    if story_dir and story_dir.exists():
        try:
            chars = load_characters(story_dir)
            for c in chars:
                last_ch = c.get("last_chapter", 0)
                if isinstance(last_ch, int) and last_ch > 0:
                    gap = chapter_no - last_ch
                    if gap >= 5:
                        deviation += 15
                        details.append(f"弧线停滞: {c.get('name', '?')}（已{gap}章未推进）")
                        break  # Only count one for the +15
        except Exception:
            pass

    # ── 主线事件被跳跃（大纲有计划但章节跳过）：+20 ──
    skipped = cur.execute(
        "SELECT chapter_no, planned_title FROM chapter_plans "
        "WHERE novel_id=? AND chapter_no < ? AND plan_status != 'ingested'",
        (nid, chapter_no)).fetchall()
    if skipped:
        skipped_chs = [s['chapter_no'] for s in skipped]
        deviation += 20
        details.append(f"大纲事件跳跃: 第{','.join(str(x) for x in skipped_chs[:3])}章" +
                      (f"等{len(skipped)}章" if len(skipped_chs) > 3 else ""))

    return {"score": min(deviation, 100), "details": details}


# ============================================================
# 2.3 Auto-learn: jury should_fix → writing_rules
# ============================================================
def _extract_learnable_rules(items, prev_ch):
    """Scan jury should_fix items for patterns that can be auto-saved as writing rules."""
    rules = []
    for item in items:
        msg = item.get("message", "")
        sug = item.get("suggestion", "")
        combined = f"{msg} {sug}"

        # Voice deviation patterns
        voice_match = re.search(r'(声纹|口吻|方言|口音|口头禅).{0,20}(偏差|偏离|不符|错误|不当|过多|缺少|缺失)', combined)
        if voice_match:
            # Extract character name
            name_match = re.search(r'[\u4e00-\u9fff]{2,4}(?=声纹|口吻|方言|口音)', combined)
            char_name = name_match.group(0) if name_match else ""
            rules.append({
                "title": f"{char_name}声纹约束（第{prev_ch}章陪审团发现）",
                "content": sug or msg,
                "rule_type": "character_voice",
                "importance": 4,
            })
            continue

        # Missing item/prop patterns
        item_match = re.search(r'(?:物件|道具|物品).{0,10}(?:缺失|缺少|未出现|不见了)', combined)
        if item_match:
            name_match = re.search(r'[\u4e00-\u9fff]{2,4}(?=的.{0,4}(?:物件|道具|木尺|护腕|弓|笔|板|牌))', combined)
            char_name = name_match.group(0) if name_match else ""
            rules.append({
                "title": f"{char_name}随身物件提醒（第{prev_ch}章陪审团发现）",
                "content": sug or msg,
                "rule_type": "behavior",
                "importance": 4,
            })
            continue

        # AI-style patterns
        ai_match = re.search(r'(AI腔|套话|模板|总结腔|说明书|科普)', combined)
        if ai_match:
            rules.append({
                "title": f"反AI腔提醒（第{prev_ch}章陪审团发现）",
                "content": sug or msg,
                "rule_type": "anti_ai",
                "importance": 3,
            })
            continue

        # Pacing/structure issues: convert to general writing rules if specific
        pacing_match = re.search(r'(进度|节奏|冲突|压力|爽点|钩子).{0,15}(不足|缺失|过慢|太快|偏慢|偏快)', combined)
        if pacing_match and sug:
            rules.append({
                "title": f"写作节奏提醒（第{prev_ch}章陪审团发现）",
                "content": sug,
                "rule_type": "style",
                "importance": 3,
            })
            continue

    return rules


def _auto_write_rules(cur, nid, rules, chapter_no):
    """Write extractable rules to writing_rules table, avoiding exact duplicates."""
    saved = 0
    for rule in rules:
        existing = cur.execute(
            "SELECT id FROM writing_rules WHERE novel_id=? AND title=?",
            (nid, rule["title"])).fetchone()
        if existing:
            continue
        cur.execute(
            "INSERT INTO writing_rules(novel_id, title, content, rule_type, importance, status) "
            "VALUES(?, ?, ?, ?, ?, 'active')",
            (nid, rule["title"], rule["content"], rule["rule_type"], rule.get("importance", 3)))
        saved += 1
    return saved


# ============================================================
# 3章复盘
# ============================================================
