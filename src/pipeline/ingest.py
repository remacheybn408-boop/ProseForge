#!/usr/bin/env python3
"""ingest.py — Chapter ingestion (DB + FTS + summaries + character tracking)"""

import re, json, sys, os, sqlite3
from pathlib import Path
from datetime import datetime
from version import get_version
from src.pipeline.chapter_context import generate_chapter_brief, generate_chapter_context
from src.pipeline._base import (
    now, connect, _get_novel_id, ensure_tables,
    find_chapter_file_with_fallback, _arabic_to_chinese_numeral,
    _strip_selfcheck, _chunk_text, _count_chinese,
)


# ============================================================
# STEP 7.9 上下文提取已统一到 src/pipeline/chapter_context.py
# （generate_chapter_context / _build_context_injection / _extract_* / 词库常量）。
# 本模块通过顶部 import 复用 generate_chapter_context，避免双份副本各自分叉。
# ============================================================


# ============================================================
# STEP 8: INGEST — 自动化入库
# ============================================================

def _resolve_chapter_title(filename, content):
    """解析章节标题：优先正文 `# 第N章 标题`，否则文件名（分隔符可选），再否则 stem。

    文件名可能按 `第N章_标题.txt` 或 `第N章标题.txt`（无下划线）落盘
    （`_find_chapter_file` 按 `第N章*.txt` glob），故分隔符 `[_\\s]*` 可选。
    """
    fname = Path(filename).name
    m = re.match(r'第\d+章[_\s]*(.+)\.txt$', fname)
    file_title = m.group(1).strip() if m else Path(fname).stem
    content_m = re.search(
        r'^#\s*第[一二三四五六七八九十百千\d]+章\s+(.+?)$',
        content.strip(), re.MULTILINE)
    return content_m.group(1).strip() if content_m else file_title


def _count_character_appearances(content, names):
    """统计每个角色名的出场次数，longest-first + span 掩码消除『名字套名字』误计（CODE_REVIEW #19）。

    长名优先占用字符 span；短名只计入未被更长角色名占用的位置。
    对互不为子串的常规名集，结果与 str.count 完全一致（零回归）。
    Mode B（单字/常用字撞普通词，如 `李`↔`行李`）仍是已知局限——确定性方案无法廉价覆盖。
    返回 {name: count}。
    """
    counts = {n: 0 for n in names}
    consumed = [False] * len(content)
    for name in sorted((n for n in names if n), key=len, reverse=True):
        start = 0
        while True:
            idx = content.find(name, start)
            if idx < 0:
                break
            end = idx + len(name)
            if not any(consumed[idx:end]):
                counts[name] += 1
                for i in range(idx, end):
                    consumed[i] = True
                start = end            # 非重叠推进，对齐 str.count 语义
            else:
                start = idx + 1        # 跳过被长名占用的命中，继续扫描
    return counts


def ingest(chapter_no, chapter_type="normal", app_inst=None):
    if app_inst is None:
        raise RuntimeError("ingest requires app_inst/context")
    app = app_inst
    conn = connect(app)
    cur = conn.cursor()
    nid = _get_novel_id(cur, app)
    try:
        ts = now()
        state_path = app.state_dir / f"chapter_{chapter_no:03d}_state.json"
        fts_sync_errors = []

        def _update_pipeline_state(**fields):
            try:
                state = {}
                if state_path.exists():
                    raw_state = json.loads(state_path.read_text(encoding="utf-8"))
                    if isinstance(raw_state, dict):
                        state = raw_state
                state.update(fields)
                state_path.parent.mkdir(parents=True, exist_ok=True)
                state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

        def _record_fts_error(step, exc):
            msg = f"{step}: {exc}"
            fts_sync_errors.append(msg)
            print(f"  [WARN] FTS sync failed - {msg}")

        filepath = find_chapter_file_with_fallback(chapter_no, app)
        if not filepath:
            print(f"[FAIL] 找不到第{chapter_no}章TXT"); conn.close(); return None
        with open(filepath, 'r', encoding='utf-8') as f: raw = f.read()
        content = _strip_selfcheck(raw)

        # v0.4.5: 标题优先正文 `# 第N章 标题`，否则文件名（分隔符可选），再否则 stem
        title = _resolve_chapter_title(filepath.name, content)
        wc = _count_chinese(content)

        # ── Resolve volume_id ──
        vol_id = None
        try:
            vr = cur.execute(
                "SELECT id FROM volumes WHERE novel_id=? AND volume_no=?",
                (nid, app.volume_no)).fetchone()
            if vr:
                vol_id = vr[0]
        except Exception:
            pass

        # --- chapters ---
        cur.execute("SELECT id FROM chapters WHERE novel_id=? AND chapter_no=?", (nid, chapter_no))
        existing = cur.fetchone()
        if existing:
            ch_id = existing[0]
            cur.execute("UPDATE chapters SET title=?,content=?,word_count=?,file_path=?,updated_at=?,volume_id=? WHERE id=?",
                (title, content, wc, str(filepath), ts, vol_id, ch_id))
            # 外部内容 FTS：先用 'delete' 命令（需旧 rowid+content）移除旧 chunk 索引，再删基表行。
            # rowid 与 chapter_chunks.id 对齐，rebuild 才不会和本地维护打架。
            try:
                old_chunks = cur.execute(
                    "SELECT id, content FROM chapter_chunks WHERE chapter_id=?", (ch_id,)
                ).fetchall()
                for _cid, _ctext in old_chunks:
                    cur.execute(
                        "INSERT INTO novel_chunk_fts(novel_chunk_fts, rowid, content) VALUES('delete', ?, ?)",
                        (_cid, _ctext),
                    )
            except Exception as exc:
                _record_fts_error("delete novel_chunk_fts", exc)
            cur.execute("DELETE FROM chapter_chunks WHERE chapter_id=?", (ch_id,))
            try:
                cur.execute("DELETE FROM novel_chapter_fts WHERE rowid=?", (ch_id,))
            except Exception as exc:
                _record_fts_error("delete novel_chapter_fts", exc)
        else:
            cur.execute("INSERT INTO chapters(novel_id,chapter_no,title,content,word_count,status,file_path,volume_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (nid, chapter_no, title, content, wc, 'draft', str(filepath), vol_id, ts, ts))
            ch_id = cur.lastrowid

        # --- 同步 chapter_plans 状态 ---
        planned_title_row = cur.execute(
            "SELECT planned_title FROM chapter_plans WHERE novel_id=? AND volume_no=? AND chapter_no=?",
            (nid, app.volume_no, chapter_no)).fetchone()
        planned_title = planned_title_row['planned_title'] if planned_title_row else ""

        cur.execute("""UPDATE chapter_plans SET final_title=?, title_status='written', plan_status='ingested',
            actual_word_count=?, completion_status='done', ingested_at=?, updated_at=?
            WHERE novel_id=? AND volume_no=? AND chapter_no=?""",
            (title, wc, ts, ts, nid, app.volume_no, chapter_no))

        # --- title_history: 标题变化追踪 ---
        if planned_title and title != planned_title:
            cur.execute("""INSERT INTO title_history(novel_id, volume_no, chapter_no,
                old_title, new_title, title_type, change_reason, changed_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                (nid, app.volume_no, chapter_no, planned_title, title, "chapter",
                 "正文重点与预设标题不完全一致，post后自动调整标题", ts))
            print(f"  [INFO] 标题变化已记录: '{planned_title}' → '{title}'")
        # --- chapter_plans 状态更新完成 ---
        # --- chapter_versions ---
        cur.execute("SELECT COALESCE(MAX(version_no),0) FROM chapter_versions WHERE novel_id=? AND chapter_no=?", (nid, chapter_no))
        vno = cur.fetchone()[0] + 1
        cur.execute("INSERT INTO chapter_versions(novel_id,chapter_id,chapter_no,version_no,version_status,title,content,word_count,change_reason) VALUES(?,?,?,?,?,?,?,?,?)",
            (nid, ch_id, chapter_no, vno, 'draft', title, content, wc, f"第{chapter_no}章v{vno}"))

        # --- chunks + FTS ---
        # 外部内容 FTS（content='chapter_chunks', content_rowid='id'）要求 FTS rowid == chapter_chunks.id，
        # 否则 _enrich_chunk_results 命中不到、rebuild 又会覆盖本地写。用 lastrowid 取真实 id。
        chunks = _chunk_text(content)
        for cno, ctext in chunks:
            cur.execute("INSERT INTO chapter_chunks(novel_id,chapter_id,chunk_no,content,word_count,created_at) VALUES(?,?,?,?,?,?)", (nid, ch_id, cno, ctext, len(ctext), ts))
            chunk_id = cur.lastrowid
            try:
                cur.execute("INSERT INTO novel_chunk_fts(rowid,content) VALUES(?,?)", (chunk_id, ctext))
            except Exception as exc:
                _record_fts_error(f"insert novel_chunk_fts chunk {cno}", exc)
        try:
            cur.execute("INSERT INTO novel_chapter_fts(rowid,title,content,summary) VALUES(?,?,?,?)", (ch_id, title, content, ''))
        except Exception as exc:
            _record_fts_error("insert novel_chapter_fts", exc)
        _update_pipeline_state(
            fts_sync_ok=not fts_sync_errors,
            fts_sync_errors=fts_sync_errors,
            ingest_updated_at=ts,
        )

        # --- chapter_summaries ---
        lines = [l for l in content.split("\n") if l.strip() and not l.startswith("=")]
        short = lines[0][:200] if lines else ""
        long = " ".join(lines[-5:])[:500] if len(lines) >= 5 else short
        ending_state = lines[-3][:200] if len(lines) >= 3 else ""
        cur.execute("SELECT id FROM chapter_summaries WHERE novel_id=? AND chapter_id=?", (nid, ch_id))
        if cur.fetchone():
            cur.execute("UPDATE chapter_summaries SET short_summary=?,long_summary=?,key_events=?,updated_at=? WHERE novel_id=? AND chapter_id=?",
                (short, long, ending_state, ts, nid, ch_id))
        else:
            cur.execute("INSERT INTO chapter_summaries(novel_id,chapter_id,short_summary,long_summary,key_events,characters_involved,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (nid, ch_id, short, long, ending_state, '', ts, ts))

        # --- novels update ---
        cur.execute("UPDATE novels SET current_words=(SELECT COALESCE(SUM(word_count),0) FROM chapters WHERE novel_id=?), updated_at=? WHERE id=?", (nid, ts, nid))

        # --- chapter_brief ---
        conn.commit()  # commit and release the write lock before nested DB work
    finally:
        conn.close()
    generate_chapter_brief(chapter_no, title, content, wc, chapter_type, app_inst=app)

    # --- chapter_context ---
    generate_chapter_context(chapter_no, title, content, wc, nid, ch_id, app_inst=app)
    conn = connect(app)
    cur = conn.cursor()
    try:

        # ── 角色出场统计 ──
        appeared_names = []
        try:
            cur.execute("SELECT name FROM characters WHERE novel_id=?", (nid,))
            all_chars = [r[0] for r in cur.fetchall()]
            if all_chars:
                appears = []
                missing = []
                appeared_names = []
                appearance_counts = _count_character_appearances(content, all_chars)
                for n in all_chars:
                    cnt = appearance_counts[n]
                    if cnt > 0:
                        appears.append(f"{n}({cnt}次)")
                        appeared_names.append(n)
                    else:
                        missing.append(n)
                if appears:
                    print(f"\n  本章出场角色：{', '.join(appears)}")
                if missing:
                    print(f"  ⚠️ 未出场角色：{', '.join(missing)}")
                # Store in chapter_summaries for absence tracking
                cur.execute(
                    "UPDATE chapter_summaries SET characters_involved=? WHERE novel_id=? AND chapter_id=?",
                    (",".join(appeared_names), nid, ch_id))
        except Exception as _e:
            from src.utils.error_handling import log_optional_failure
            log_optional_failure("ingest: 角色出场统计", _e)

        # ── 敌对角色同场检测 ──
        try:
            hostile_rels = cur.execute(
                "SELECT char_a, char_b FROM character_relationships WHERE relation_type='敌对'"
            ).fetchall()
            if hostile_rels and appeared_names:
                for hr in hostile_rels:
                    a, b = hr[0], hr[1]
                    if a in appeared_names and b in appeared_names:
                        print(f"  🔴 {a}和{b}同章出场但零互动确认，建议加一场冲突")
        except Exception as _e:
            from src.utils.error_handling import log_optional_failure
            log_optional_failure("ingest: 敌对角色同场检测", _e)

        # ── 世界设定提及检测 ──
        try:
            cur.execute("SELECT id, title FROM worldbuilding WHERE novel_id=?", (nid,))
            wb_rows = cur.fetchall()
            mentioned = []
            for wb in wb_rows:
                if wb["title"] in content:
                    mentioned.append(wb["id"])
            if mentioned:
                placeholders = ",".join("?" * len(mentioned))
                cur.execute(
                    f"UPDATE worldbuilding SET updated_at=datetime('now') WHERE id IN ({placeholders})",
                    mentioned,
                )
                conn.commit()
        except Exception as _e:
            from src.utils.error_handling import log_optional_failure
            log_optional_failure("ingest: 世界设定提及统计", _e)

        # --- chapter_run_report.json (Agent Guard 自检用) ---
        run_report = {
            "chapter_no": chapter_no,
            "title": title,
            "word_count": wc,
            "volume_no": app.volume_no,
            "fts_sync_ok": not fts_sync_errors,
            "fts_sync_errors": fts_sync_errors,
            # ── Report paths (actual guard results live in these files) ──
            "continuity_evidence_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_continuity_evidence_report.json"),
            "hallucination_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_hallucination_report.json"),
            "canon_evidence_map_path": str(app.exports_root / "evidence" / f"chapter_{chapter_no:03d}_canon_evidence_map.json"),
            "scene_delta_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_scene_delta_report.json"),
            "padding_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_padding_report.json"),
            "character_voice_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_character_voice_report.json"),
            "classical_register_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_classical_register_report.json"),
            "show_dont_tell_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_show_dont_tell_report.json"),
            "dialogue_beat_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_dialogue_beat_report.json"),
            "qgp_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_perplexity_quality_report.json"),
            "editor_revision_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_editor_revision_report.json"),
            "concrete_anchor_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_concrete_anchor_report.json"),
            "scene_causality_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_scene_causality_report.json"),
            "dialogue_structure_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_dialogue_structure_report.json"),
            "style_variation_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_style_variation_report.json"),
            "compliance_selfcheck_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_compliance_selfcheck_report.json"),
            "final_submission_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_final_submission_report.json"),
        }
        reports_dir = app.exports_root / "run_reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"chapter_{chapter_no:03d}_run_report.json"
        report_path.write_text(json.dumps(run_report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  [OK] run_report: {report_path}") 
         # --- log ---
        cur.execute("INSERT INTO novel_logs(action,target_type,target_id,detail) VALUES('ingest','chapter',?,?)",
            (ch_id, f"第{chapter_no}章入库:{wc}字,v{vno},{len(chunks)}切片"))

        conn.commit()
        cur.execute("SELECT COUNT(*),COALESCE(SUM(word_count),0) FROM chapters WHERE novel_id=?", (nid,))
        total_ch, total_wc = cur.fetchone()
    finally:
        conn.close()

    print(f"\n{'='*50}\nSTEP 8: INGEST 入库\n{'='*50}")
    print(f"  章节: {wc}字 v{vno} | 切片: {len(chunks)} | 全书: {total_ch}章 {total_wc:,}字 [OK]")

    # ── 3.3 story commit: 写入弧线进度 ──
    try:
        from src.story import commit_builder as _cb
        _project_root = Path(__file__).resolve().parent.parent
        try:
            _appeared_names = appeared_names
        except NameError:
            _appeared_names = []
        _char_changes = {}
        for _aname in _appeared_names:
            _char_changes[_aname] = {"after": f"第{chapter_no}章出场", "chapter": chapter_no}
        _commit = _cb.build_commit(
            _project_root, chapter_no, chapter_title=title, word_count=wc,
            character_changes=_char_changes,
            next_hooks=[ending_state] if ending_state else [],
        )
        _commit_path = _cb.save_commit(_project_root, chapter_no, _commit)
        print(f"  [OK] story commit: {_commit_path}")
    except Exception as _e:
        print(f"  [WARN] story commit 失败: {_e}")

    return {"ch_id": ch_id, "word_count": wc, "version": vno, "chunks": len(chunks)}


# ============================================================
# VOLUME_POST — 卷级总结与承接
# ============================================================
def stage_review(chapter_no, app_inst=None):
    if app_inst is None:
        raise RuntimeError("stage_review requires app_inst/context")
    app = app_inst
    if chapter_no % 3 != 0: return
    conn = connect(app)
    cur = conn.cursor()
    nid = _get_novel_id(cur, app)
    try:
        start = chapter_no - 2
        print(f"\n{'='*60}\n3章复盘: 第{start}-{chapter_no}章\n{'='*60}")
        cur.execute("SELECT chapter_no,title,word_count FROM chapters WHERE novel_id=? AND chapter_no BETWEEN ? AND ? ORDER BY chapter_no", (nid, start, chapter_no))
        total = 0
        for r in cur.fetchall():
            mark = " [OK]" if r['word_count'] >= app.wc_default['min'] else " [WARN]"
            total += r['word_count']; print(f"  第{r['chapter_no']}章: {r['word_count']}字{mark}")
        print(f"  合计: {total}字 | 均: {total//3}字")
    finally:
        conn.close()


# ============================================================
# MAIN
# ============================================================
