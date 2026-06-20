#!/usr/bin/env python3
"""arc_checker.py — 跨章孤线检测引擎 v0.7.2

Continuity & logic break detection across chapters:
  - Physical state: 重伤 → 健康 without transition
  - Emotional: 失恋 → 开心 without transition
  - Item arc: 物品出现 → 消失 → 再现无交代
  - Promise alignment: 承诺 ↔ actual context
  - Plot Thread dormancy: 活跃线索长期无推进
"""

import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional


SEVERITY = {
    "critical": "❌ 确定断层",
    "warning": "⚠️ 疑似断层",
    "info": "ℹ️ 关注点",
}


class ArcChecker:
    """Cross-chapter arc consistency checker."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_tables()

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS arc_character_states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id INTEGER NOT NULL REFERENCES novels(id),
            character_id INTEGER NOT NULL REFERENCES characters(id),
            chapter_no INTEGER NOT NULL,
            physical_state TEXT DEFAULT '',
            emotional_state TEXT DEFAULT '',
            arc_progress TEXT DEFAULT '',
            key_decisions TEXT DEFAULT '[]',
            active_relationships TEXT DEFAULT '[]',
            UNIQUE(novel_id, character_id, chapter_no)
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS arc_alignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id INTEGER NOT NULL REFERENCES novels(id),
            promise_id INTEGER REFERENCES reader_promises(id),
            thread_id INTEGER REFERENCES plot_threads(id),
            chapter_no INTEGER NOT NULL,
            alignment_type TEXT NOT NULL,
            context_field TEXT DEFAULT '',
            context_value TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        )""")
        conn.commit()
        conn.close()

    # ── Physical State Checks ──

    def check_physical_continuity(self, nid: int, min_ch=1, max_ch=None) -> List[Dict]:
        """Detect physical state breaks without transition chapters."""
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""SELECT c.name, a.chapter_no, a.physical_state
            FROM arc_character_states a
            JOIN characters c ON c.id = a.character_id
            WHERE a.novel_id=? AND a.physical_state != ''
            ORDER BY c.name, a.chapter_no""", (nid,))
        rows = cur.fetchall()
        conn.close()

        findings = []
        # Group by character
        char_states = {}
        for r in rows:
            char_states.setdefault(r["name"], []).append((r["chapter_no"], r["physical_state"]))

        for name, states in char_states.items():
            for i in range(len(states) - 1):
                ch_prev, st_prev = states[i]
                ch_curr, st_curr = states[i + 1]
                # Heal transition: 重伤/中伤 → 健康 without 恢复 in between
                severe = {"重伤", "中伤", "中毒"}
                if st_prev in severe and st_curr not in ("重伤", "中伤", "中毒", "恢复"):
                    # Check if there's a gap > 1 chapter without transition
                    if ch_curr - ch_prev > 1:
                        findings.append({
                            "type": "physical_break",
                            "severity": "warning",
                            "character": name,
                            "chapters": (ch_prev, ch_curr),
                            "message": f"第{ch_prev}章{st_prev} → 第{ch_curr}章{st_curr}，中间{ch_curr - ch_prev - 1}章无过渡",
                        })
                    elif ch_curr - ch_prev == 1 and st_curr == "健康":
                        findings.append({
                            "type": "physical_break",
                            "severity": "critical",
                            "character": name,
                            "chapters": (ch_prev, ch_curr),
                            "message": f"第{ch_prev}章{st_prev} → 第{ch_curr}章健康，相邻章无恢复过程",
                        })
        return findings

    # ── Emotional Arc Checks ──

    def check_emotional_continuity(self, nid: int, min_ch=1, max_ch=None) -> List[Dict]:
        """Detect abrupt emotional transitions."""
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""SELECT c.name, a.chapter_no, a.emotional_state
            FROM arc_character_states a
            JOIN characters c ON c.id = a.character_id
            WHERE a.novel_id=? AND a.emotional_state != '{}' AND a.emotional_state != ''
            ORDER BY c.name, a.chapter_no""", (nid,))
        rows = cur.fetchall()
        conn.close()

        findings = []
        char_emos = {}
        for r in rows:
            try:
                emo_data = json.loads(r["emotional_state"])
            except Exception:
                continue
            if emo_data.get("state"):
                char_emos.setdefault(r["name"], []).append(
                    (r["chapter_no"], emo_data["state"], emo_data.get("intensity", 1)))

        # Emotion groups for transition detection
        NEGATIVE = {"愤怒", "暴怒", "怒火", "恼怒", "生气", "悲伤", "难过", "哀伤", "悲痛",
                     "心痛", "心酸", "恐惧", "害怕", "惊恐", "畏惧", "厌恶", "反感",
                     "嫌弃", "憎恨", "恨", "焦虑", "焦躁", "烦躁", "不安", "忐忑",
                     "失望", "失落", "沮丧", "灰心", "愧疚", "内疚", "自责", "悔恨",
                     "孤独", "寂寞", "孤单", "无奈", "苦笑"}
        POSITIVE = {"喜悦", "高兴", "开心", "欣喜", "兴奋", "欢喜", "释然", "宽慰",
                     "安心", "放松", "感动", "触动", "坚定", "决然", "果断", "刚毅"}

        for name, emos in char_emos.items():
            for i in range(len(emos) - 1):
                ch_prev, st_prev, int_prev = emos[i]
                ch_curr, st_curr, int_curr = emos[i + 1]
                # Large emotional swing in adjacent chapters
                if (st_prev in NEGATIVE and st_curr in POSITIVE) or \
                   (st_prev in POSITIVE and st_curr in NEGATIVE):
                    # If intensity difference is large and chapters are adjacent
                    if abs(int_prev - int_curr) >= 3 and ch_curr - ch_prev <= 2:
                        findings.append({
                            "type": "emotional_swing",
                            "severity": "warning",
                            "character": name,
                            "chapters": (ch_prev, ch_curr),
                            "message": f"第{ch_prev}章{st_prev}(强度{int_prev}) → 第{ch_curr}章{st_curr}(强度{int_curr})，情绪转变急促",
                        })
        return findings

    # ── Item Arc Checks ──

    def check_item_continuity(self, nid: int, min_ch=1, max_ch=None) -> List[Dict]:
        """Detect items that appear, disappear for many chapters, then reappear."""
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""SELECT chapter_no, active_items FROM chapter_contexts
            WHERE novel_id=? ORDER BY chapter_no""", (nid,))
        rows = cur.fetchall()
        conn.close()

        # Build item → [chapter appearances]
        item_chapters = {}
        for r in rows:
            ch = r["chapter_no"]
            if min_ch and ch < min_ch:
                continue
            if max_ch and ch > max_ch:
                continue
            try:
                items = json.loads(r["active_items"]) if isinstance(r["active_items"], str) else (r["active_items"] or [])
            except Exception:
                continue
            for item in items:
                item_chapters.setdefault(item, []).append(ch)

        findings = []
        for item, chapters in item_chapters.items():
            if len(chapters) >= 2:
                # Check gap between appearances
                for i in range(len(chapters) - 1):
                    gap = chapters[i + 1] - chapters[i]
                    if gap > 10:
                        findings.append({
                            "type": "item_void",
                            "severity": "warning",
                            "item": item,
                            "chapters": (chapters[i], chapters[i + 1]),
                            "message": f"「{item}」第{chapters[i]}章出现后消失{gap}章，第{chapters[i+1]}章再现",
                        })
        return findings

    # ── Promise Alignment Checks ──

    def check_promise_alignment(self, nid: int, min_ch=1, max_ch=None) -> List[Dict]:
        """Detect open promises past their expected payoff range."""
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""SELECT id, promise_title, promise_detail, introduced_chapter,
                       payoff_chapter, status, expected_payoff_range
            FROM reader_promises WHERE novel_id=? AND status='open'
            ORDER BY introduced_chapter""", (nid,))
        promises = cur.fetchall()

        # Get max chapter written
        cur.execute("SELECT MAX(chapter_no) FROM chapter_contexts WHERE novel_id=?", (nid,))
        max_ch_row = cur.fetchone()
        max_written = max_ch_row[0] if max_ch_row and max_ch_row[0] else 0
        conn.close()

        findings = []
        for p in promises:
            intro = p["introduced_chapter"] or 0
            # Parse expected payoff range if present
            payoff_range = p["expected_payoff_range"] or ""
            expected_max = None
            if payoff_range:
                try:
                    parts = payoff_range.split("-")
                    if len(parts) == 2:
                        expected_max = int(parts[1].strip())
                except Exception:
                    pass
            if not expected_max:
                expected_max = intro + 15  # Default: 15 chapters max

            if max_written > expected_max:
                overdue = max_written - expected_max
                findings.append({
                    "type": "promise_overdue",
                    "severity": "warning" if overdue <= 5 else "critical",
                    "promise_id": p["id"],
                    "promise_title": p["promise_title"],
                    "message": f"承诺「{p['promise_title']}」第{intro}章提出，应于第{expected_max}章前兑现，已逾期{overdue}章",
                })

            # Check alignment records
            cur2 = self._connect().cursor()
            cur2.execute("""SELECT COUNT(*) FROM arc_alignments
                WHERE novel_id=? AND promise_id=? AND alignment_type='fulfillment'""",
                         (nid, p["id"]))
            aligned = cur2.fetchone()[0]
            cur2.connection.close()
            if aligned == 0 and intro > 0:
                findings.append({
                    "type": "promise_unaligned",
                    "severity": "info",
                    "promise_id": p["id"],
                    "promise_title": p["promise_title"],
                    "message": f"承诺「{p['promise_title']}」无对齐记录，未确认文本中已体现",
                })
        return findings

    # ── Plot Thread Dormancy ──

    def check_thread_dormancy(self, nid: int, min_ch=1, max_ch=None) -> List[Dict]:
        """Detect active plot threads with no recent advancement."""
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""SELECT id, title, introduced_chapter, status, content
            FROM plot_threads WHERE novel_id=? AND status='active'
            ORDER BY introduced_chapter""", (nid,))
        threads = cur.fetchall()

        # Get alignments for threads
        cur.execute("""SELECT thread_id, MAX(chapter_no) FROM arc_alignments
            WHERE novel_id=? AND thread_id IS NOT NULL
            GROUP BY thread_id""", (nid,))
        thread_last_advance = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute("SELECT MAX(chapter_no) FROM chapter_contexts WHERE novel_id=?", (nid,))
        max_ch_row = cur.fetchone()
        max_written = max_ch_row[0] if max_ch_row and max_ch_row[0] else 0
        conn.close()

        findings = []
        for t in threads:
            last_ch = thread_last_advance.get(t["id"], t["introduced_chapter"] or 0)
            gap = max_written - last_ch if max_written > last_ch else 0
            if gap > 10:
                findings.append({
                    "type": "thread_dormant",
                    "severity": "warning" if gap <= 20 else "critical",
                    "thread_id": t["id"],
                    "thread_title": t["title"],
                    "message": f"线索「{t['title']}」活跃但已{gap}章无推进（最后:第{last_ch}章）",
                })
        return findings

    # ── Full Arc Check ──

    def run_full_check(self, nid: int, min_ch=1, max_ch=None,
                       check_types: List[str] = None) -> Dict:
        """Run all arc checks and return aggregated report."""
        all_types = ["physical", "emotional", "item", "promise", "thread"]
        if check_types:
            all_types = [t for t in all_types if t in check_types]

        all_findings = []
        for ct in all_types:
            if ct == "physical":
                all_findings.extend(self.check_physical_continuity(nid, min_ch, max_ch))
            elif ct == "emotional":
                all_findings.extend(self.check_emotional_continuity(nid, min_ch, max_ch))
            elif ct == "item":
                all_findings.extend(self.check_item_continuity(nid, min_ch, max_ch))
            elif ct == "promise":
                all_findings.extend(self.check_promise_alignment(nid, min_ch, max_ch))
            elif ct == "thread":
                all_findings.extend(self.check_thread_dormancy(nid, min_ch, max_ch))

        # Count severity
        critical = sum(1 for f in all_findings if f["severity"] == "critical")
        warnings = sum(1 for f in all_findings if f["severity"] == "warning")
        infos = sum(1 for f in all_findings if f["severity"] == "info")

        # Overall status
        if critical > 0:
            status = "CRITICAL"
        elif warnings > 3:
            status = "WARNING"
        else:
            status = "OK"

        return {
            "status": status,
            "total_findings": len(all_findings),
            "critical": critical,
            "warnings": warnings,
            "infos": infos,
            "findings": all_findings,
        }


# ── Convenience runner ──

def run_arc_check(db_path: str, nid: int, min_ch=1, max_ch=None,
                  check_types: List[str] = None) -> Dict:
    checker = ArcChecker(Path(db_path))
    return checker.run_full_check(nid, min_ch, max_ch, check_types)
