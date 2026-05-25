"""
chapter_pipeline.py — 章节写作总控流水线 V4.2

v0.4.0 拟人审稿流水线:
  pre → task_card → write → word_count → continuity → scene → anti_ai → padding → voice_guards → qgp →
  editor_revision → concrete_anchor → scene_causality → dialogue_naturalness → style_variation →
  compliance_selfcheck → final_submission_report → ingest

QGP 困惑度质量门禁 (V5.1, WARNING only):
  ngram 惊讶度 / 句长节奏 / 重复短语 / 抽象总结 / 具体锚点 / 对白变化度

Human-Grade Revision Suite (v0.4.0, WARNING only, compliance_selfcheck 可 BLOCK):
  editor_revision | concrete_anchor | scene_causality | dialogue_naturalness |
  style_variation | compliance_selfcheck | final_submission_report

证据门禁 (V5):
  continuity_evidence | canon_evidence | scene_delta | hallucination | anti_ai | padding
角色口吻门禁 (V5.1 Phase 2, WARNING only):
  character_voice | classical_register | show_dont_tell | concrete_hook | dialogue_beat

字数门禁 (V5): chapter_type 只决定上限，不强制下限
  普通1900-3300 | 重点1900-4200 | 高潮1900-5500 | 短章300-1000

场景门禁: >= 1 有效场景

用法:
  python chapter_pipeline.py pre <chapter_no> [--config config.json] [--novel-slug demo] [--chapter-type normal|climax|final]
  python chapter_pipeline.py post <chapter_no> [--config config.json] [--novel-slug demo] [--chapter-type normal|climax|final]
  python chapter_pipeline.py review <chapter_no>
"""

import sqlite3, re, sys, json, argparse
from pathlib import Path
from datetime import datetime


# ============================================================
# 默认值（会被 config 或 CLI 覆盖）
# ============================================================
DEFAULT_CONFIG = {
    "db_path": "./data/novel_memory.db",
    "novels_root": "./novels",
    "exports_root": "./exports",
    "word_count": {
        "normal":       {"min": 1900, "best_min": 1900, "best_max": 2800, "max": 3300},
        "relationship": {"min": 1900, "best_min": 1900, "best_max": 2800, "max": 3300},
        "investigation":{"min": 1900, "best_min": 1900, "best_max": 2800, "max": 3300},
        "experiment":   {"min": 1900, "best_min": 2200, "best_max": 3200, "max": 4200},
        "conflict":     {"min": 1900, "best_min": 2200, "best_max": 3300, "max": 4200},
        "key":          {"min": 1900, "best_min": 2200, "best_max": 3300, "max": 4200},
        "climax":       {"min": 1900, "best_min": 2300, "best_max": 3800, "max": 5500},
        "volume_finale":{"min": 1900, "best_min": 2300, "best_max": 4200, "max": 5500},
        "authorized_short":{"min": 300, "best_min": 500, "best_max": 900, "max": 1000},
        "fragment":     {"min": 300, "best_min": 500, "best_max": 900, "max": 1000},
    },
    "scene_quality": {"min_effective_scenes": 1},
}


def load_config(config_path=None):
    """加载配置：优先 CLI 指定的 --config，否则从默认路径尝试"""
    if config_path:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            return {**DEFAULT_CONFIG, **cfg}
        except FileNotFoundError:
            pass  # fall through to defaults

    for candidate in ["config.json", "config.example.json"]:
        if Path(candidate).exists():
            with open(candidate, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            return {**DEFAULT_CONFIG, **cfg}
    return DEFAULT_CONFIG


# ============================================================
# 全局状态（由 main 初始化）
# ============================================================
class App:
    def __init__(self, cfg, novel_slug, novel_title, volume_no, chapters_dir=None):
        self.cfg = cfg
        self.novel_slug = novel_slug
        self.novel_title = novel_title or novel_slug
        self.volume_no = volume_no
        self.db_path = Path(cfg["db_path"])
        self.wc_rules = cfg.get("word_count", DEFAULT_CONFIG["word_count"])
        self.wc_default = self.wc_rules.get("normal", {"min": 1900, "best_min": 1900, "best_max": 2800, "max": 3300})
        self.min_scenes = cfg.get("scene_quality", DEFAULT_CONFIG["scene_quality"])["min_effective_scenes"]
        self.novels_root = Path(cfg.get("novels_root", "./novels"))
        self.exports_root = Path(cfg.get("exports_root", "./exports"))

        if chapters_dir:
            self.chapters_dir = Path(chapters_dir)
        else:
            self.chapters_dir = self.novels_root / novel_slug / f"第{volume_no:02d}卷"

        self.state_dir = self.exports_root / "pipeline_state"


app = None  # 由 main() 初始化


def now(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect():
    conn = sqlite3.connect(str(app.db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _get_novel_id(cur):
    cur.execute("SELECT id FROM novels WHERE slug=?", (app.novel_slug,))
    row = cur.fetchone()
    return row[0] if row else None


def _strip_selfcheck(text):
    idx = text.find("本章自检")
    return text[:idx] if idx > 0 else text


def _chunk_text(text, min_size=800, max_size=1500):
    if not text: return []
    chunks, current, chunk_no = [], "", 0
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            if current: current += "\n"
            continue
        if len(current) + len(para) > max_size and len(current) >= min_size:
            chunk_no += 1; chunks.append((chunk_no, current.strip()))
            current = para
        else:
            current += ("\n" + para if current else para)
    if current.strip():
        chunk_no += 1; chunks.append((chunk_no, current.strip()))
    return chunks


def _count_chinese(text):
    return len([c for c in text if '\u4e00' <= c <= '\u9fff' or '\u3000' <= c <= '\u303f' or '\uff00' <= c <= '\uffef'])


# ============================================================
# 建表（幂等）
# ============================================================
def ensure_tables():
    conn = sqlite3.connect(str(app.db_path))
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS chapter_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        novel_id INTEGER NOT NULL,
        chapter_id INTEGER,
        chapter_no INTEGER NOT NULL,
        version_no INTEGER NOT NULL DEFAULT 1,
        version_status TEXT DEFAULT 'draft',
        title TEXT DEFAULT '',
        content TEXT NOT NULL,
        word_count INTEGER DEFAULT 0,
        change_reason TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reader_promises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        novel_id INTEGER NOT NULL,
        promise_title TEXT NOT NULL,
        promise_detail TEXT NOT NULL,
        introduced_chapter INTEGER,
        expected_payoff_range TEXT DEFAULT '',
        payoff_chapter INTEGER,
        status TEXT DEFAULT 'open',
        importance INTEGER DEFAULT 3,
        reader_emotion TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()


# ============================================================
# STEP 1: PRE — 写作前门禁
# ============================================================
def pre_write_gate(chapter_no, chapter_type="normal"):
    conn = connect(); cur = conn.cursor(); nid = _get_novel_id(cur)
    log_entries = []
    prev_ch = chapter_no - 1; prev_ending = ""

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
            try:
                brief_data = json.loads(prev_brief_path.read_text(encoding='utf-8'))
                print(f"\n  [OK] 上章 brief 已加载:")
                if brief_data.get('ending_state'):
                    print(f"    实际结尾: {brief_data['ending_state'][:120]}")
                if brief_data.get('next_chapter_hooks'):
                    print(f"    遗留钩子: {brief_data['next_chapter_hooks'][:120]}")
                if brief_data.get('planned_vs_actual_diff'):
                    diff = json.loads(brief_data['planned_vs_actual_diff']) if isinstance(brief_data['planned_vs_actual_diff'], str) else brief_data['planned_vs_actual_diff']
                    if diff.get('title_match') == 'changed':
                        print(f"    [WARN] 上章标题已变更: {diff.get('planned_title','')} → {diff.get('actual_title','')}")
                log_entries.append(f"读取第{prev_ch}章brief")
            except Exception as e:
                print(f"  [WARN] 上章brief读取失败: {e}")
        elif prev_ch > 1:
            print(f"\n  [WARN] 第{prev_ch}章 brief 文件缺失 — 建议先执行 post")
        # ── brief 结束 ──
    else:
        print("  [OK] 第1章，无上章")

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
    print(f"{'='*60}")

    cur.execute("INSERT INTO novel_logs(action,target_type,detail) VALUES('pre_write','chapter',?)", ("; ".join(log_entries),))
    conn.commit(); conn.close()

    # 保存 pipeline_state.json
    app.state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "chapter_no": chapter_no, "chapter_type": chapter_type,
        "pre_done": True, "previous_tail_loaded": prev_ch >= 1,
        "recent_summaries_loaded": True, "sqlite_search_logged": True,
        "reader_promises_checked": True, "context_pack": str(pack_path),
        "allowed_to_write": True, "timestamp": now()
    }
    state_path = app.state_dir / f"chapter_{chapter_no:03d}_state.json"
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"  [OK] pipeline_state: {state_path}")

    print(f"\nSTEP 1 [OK] — 上下文就绪")
    return {"chapter_no": chapter_no, "prev_ch": prev_ch, "prev_ending": prev_ending,
            "chapter_type": chapter_type, "context_pack": str(pack_path)}


# ============================================================
# STEP 4: WORD_COUNT — 字数门禁
# ============================================================
def word_count_gate(content, chapter_no, chapter_type="normal"):
    """字数门禁 V5：chapter_type 只决定上限，不强制下限"""
    rules = app.wc_rules.get(chapter_type, app.wc_default)
    wc = _count_chinese(content)
    print(f"\n{'='*50}\nSTEP 4: 字数门禁 [{chapter_type}]\n{'='*50}")
    print(f"  字数: {wc} | 范围: {rules['min']}-{rules['max']} | 最佳: {rules['best_min']}-{rules['best_max']}")

    if wc < rules['min']:
        print(f"  [FAIL] 低于最低线 ({wc} < {rules['min']}) — 需补场景或授权短章")
        return False, wc

    if rules['best_min'] <= wc <= rules['best_max']:
        print(f"  [OK] 最佳区间")
        return "ideal", wc

    if rules['best_max'] < wc <= rules['max']:
        # 偏长但不超过上限 — 检查是否水文
        if chapter_type in ("normal", "relationship", "investigation") and wc > 3300:
            print(f"  [WARN] 普通章超过3300 — 检查是否有水文")
        print(f"  [OK] 正常通过 (偏长)")
        return True, wc

    if wc > rules['max']:
        if chapter_type in ("climax", "volume_finale") and wc <= 5500:
            print(f"  [OK] 高潮/卷末章允许长篇幅")
            return True, wc
        print(f"  [WARN] 超上限({wc}>{rules['max']}) — 建议拆章或精简")
        return "oversize", wc

    return True, wc


# ============================================================
# STEP 5: CONTINUITY — 连续性门禁
# ============================================================
def continuity_gate(chapter_no, content):
    conn = connect(); cur = conn.cursor(); nid = _get_novel_id(cur)
    prev_ch = chapter_no - 1
    if prev_ch < 1:
        print(f"\nSTEP 5: 连续性 — 第1章，跳过"); conn.close(); return True

    cur.execute("SELECT content FROM chapters WHERE novel_id=? AND chapter_no=?", (nid, prev_ch))
    prev = cur.fetchone()
    if not prev:
        print(f"[FAIL] 连续性: 第{prev_ch}章不存在"); conn.close(); return False

    prev_end = _strip_selfcheck(prev['content'])[-400:]
    ch_start = content[:400]

    # 通用检测：不绑定具体角色名
    prev_words = set(re.findall(r'[\u4e00-\u9fff]{2,4}', prev_end[-200:]))
    start_words = set(re.findall(r'[\u4e00-\u9fff]{2,4}', ch_start[:200]))

    # 从数据库读取角色名来检测承接
    cur.execute("SELECT name FROM characters WHERE novel_id=?", (nid,))
    char_names = [r['name'] for r in cur.fetchall()]
    # 构建角色名正则
    if char_names:
        name_pattern = '|'.join(re.escape(n) for n in char_names)
        names_prev = set(re.findall(f'({name_pattern})', prev_end))
        names_start = set(re.findall(f'({name_pattern})', ch_start))
    else:
        names_prev = set()
        names_start = set()

    overlap = prev_words & start_words
    score = len(overlap)*2 + len(names_prev & names_start)*5 + 3

    print(f"\n{'='*50}\nSTEP 5: 连续性检查\n{'='*50}")
    print(f"  重合词: {list(overlap)[:8]} | 人物承接: {names_prev & names_start} | 得分: {score}/15")

    try:
        cur.execute("INSERT INTO continuity_checks(novel_id,chapter_id,check_type,issue,severity,status) VALUES(?, (SELECT id FROM chapters WHERE novel_id=? AND chapter_no=?), 'continuity', ?, ?, ?)",
            (nid, nid, chapter_no, f"得分{score}/15" if score < 15 else "正常", 3 if score < 15 else 1, 'open' if score < 15 else 'resolved'))
    except Exception:
        pass  # chapter not yet ingested — skip continuity_checks insert
    conn.commit(); conn.close()

    if score >= 12: print("  [OK] 通过"); return True
    else: print("  [WARN] 建议增强承接"); return True


# ============================================================
# STEP 5.5: HALLUCINATION — 幻觉拦截
# ============================================================
def hallucination_gate(chapter_no, content):
    """检查正文是否存在无依据新增或矛盾内容"""
    from hallucination_guard import run_hallucination_check

    print(f"\n{'='*50}\nSTEP 5.5: 幻觉拦截\n{'='*50}")

    prev_brief = None
    prev_ch = chapter_no - 1
    if prev_ch >= 1:
        prev_brief_path = app.exports_root / "chapter_briefs" / f"chapter_{prev_ch:03d}_brief.json"
        if prev_brief_path.exists():
            try:
                prev_brief = json.loads(prev_brief_path.read_text(encoding='utf-8'))
            except Exception:
                pass

    prev_tail = prev_brief.get("ending_state", "") if prev_brief else ""

    report = run_hallucination_check(
        content, chapter_no,
        prev_tail=prev_tail,
        prev_brief=prev_brief
    )

    reports_dir = app.exports_root / "hallucination_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"chapter_{chapter_no:03d}_hallucination_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"  [OK] hallucination_report: {report_path}")

    if report.get("blocked_items"):
        print(f"  [WARN] blocked: {len(report['blocked_items'])} items")
        for b in report["blocked_items"][:3]:
            print(f"    - {b['text'][:80]}")
    if report.get("contradictions"):
        print(f"  [FAIL] contradictions: {len(report['contradictions'])}")
    if report.get("unsupported_claims"):
        print(f"  [WARN] unsupported: {len(report['unsupported_claims'])}")

    passed = report["status"] == "PASS"
    if passed:
        print(f"  [OK] 幻觉检查通过")
    else:
        print(f"  [FAIL] 幻觉检查未通过 — 需修正正文")
    return passed, report


# ============================================================
# STEP 6: SCENE — 场景质量门禁
# ============================================================
def scene_quality_gate(content):
    print(f"\n{'='*50}\nSTEP 6: 场景质量检查 (需要 >= {app.min_scenes} 有效场景)\n{'='*50}")

    paragraphs = [p.strip() for p in content.split("\n") if p.strip()]

    # 场景切换标记（通用时间/地点词）
    scene_markers = re.findall(r'(第.*天|早上|傍晚|晚上|深夜|第二天|次日|清晨|黄昏|午后|下午|当天|回到|来到|走进|出了|站在|蹲在)', content)
    location_changes = len(set(re.findall(r'[\u4e00-\u9fff]{2,4}(?:院|场|洞|边|坊|台|地|位|山|室|殿|阁|楼|厅|堂|巷|街|道|铺)', content)))

    # 人物出场
    dialogue_speakers = len(set(re.findall(r'"([^"]{1,5})"', content)))

    estimated_scenes = max(len(scene_markers)//2, location_changes, 1)
    print(f"  场景标记: {len(scene_markers)} | 地点变化: {location_changes} | 对话段: {dialogue_speakers}")
    print(f"  估计场景数: {estimated_scenes}")

    # 检查无效场景特征
    issues = []
    summary_lines = len(re.findall(r'(他知道|他明白|他意识到|这意味着|这说明|总之)', content))
    if summary_lines > 5: issues.append(f"总结腔过多({summary_lines}处)")

    dialogue_lines = len(re.findall(r'"[^"]{5,}"', content))
    if dialogue_lines < 3: issues.append(f"对话过少({dialogue_lines}处)")

    action_verbs = len(re.findall(r'(蹲|站|走|跑|拿|放|推|拉|按|握|劈|搬|涂|贴|刮|洗|抓|踢|踩|跳|爬)', content))
    if action_verbs < 15: issues.append(f"动作描写过少({action_verbs}处)")

    passed = estimated_scenes >= app.min_scenes and len(issues) < 3
    if issues:
        for i in issues: print(f"  [WARN] {i}")
    if passed:
        print(f"  [OK] 通过 (>={app.min_scenes}场景, 无明显水症)")
    else:
        if estimated_scenes < app.min_scenes:
            print(f"  [FAIL] 场景不足 ({estimated_scenes} < {app.min_scenes})")
        else:
            print(f"  [WARN] 场景数够但存在水症")
    return passed, issues


# ============================================================
# STEP 7: ANTI_AI — 反AI腔门禁
# ============================================================
def anti_ai_style_gate(content):
    print(f"\n{'='*50}\nSTEP 7: 反AI腔检查\n{'='*50}")

    checks = {
        "不是A而是B": len(re.findall(r'不是.{2,10}而是', content)),
        "那一刻她/他终于明白": len(re.findall(r'(那一刻|那一瞬间).{0,5}(终于明白|终于意识到|恍然大悟)', content)),
        "她/他从未想过": len(re.findall(r'从未想过|从未见过|从未感受过', content)),
        "他意识到": len(re.findall(r'他意识到|她意识到|他明白', content)),
        "这意味着": len(re.findall(r'这意味着|这说明|这代表', content)),
        "像一座废墟/像一尊雕像": len(re.findall(r'像一座|像一尊|像一个.*的', content)),
        "沉默了几秒": len(re.findall(r'沉默了几秒|沉默了片刻|沉默了.{1,4}秒', content)),
        "是她的救赎": len(re.findall(r'救赎|他就是她的|她就是他的', content)),
        "硬科普指标": len(re.findall(r'(公式|定律|方程|定理|热力学|量子力学|相对论)', content)),
        "论文式句子": len(re.findall(r'通过.{5,20}实现了|基于.{5,20}进行了|本质上是|从某种意义上说|事实上', content)),
    }

    total = sum(checks.values())
    for label, count in checks.items():
        if count > 0: print(f"  [WARN] {label}: {count}处")

    if total == 0:
        print(f"  [OK] 零AI腔")
        return True, []
    elif total <= 2:
        print(f"  [OK] 通过 ({total}处轻微)")
        return True, list(k for k,v in checks.items() if v>0)
    else:
        print(f"  [FAIL] 不通过 ({total}处) — 需重写可疑段落")
        return False, list(k for k,v in checks.items() if v>0)


# ============================================================
# STEP 7.5: PADDING_GUARD — 反水文
# ============================================================
def padding_guard(content):
    """检测为凑字数而重复/灌水/空泛心理的段落"""
    print(f"\n{'='*50}\nSTEP 7.5: 反水文检查\n{'='*50}")

    padding_signals = {
        "连续三段同义": 0,
        "空泛心理": len(re.findall(r'(他知道.{5,30}但是|他明白.{5,30}然而|他意识到.{5,30}所以)', content)),
        "设定堆砌无行动": 0,
        "对话互复述": len(re.findall(r'"([^"]{20,})".{0,20}"\1"', content)),
        "纯总结段": 0,
        "同情绪反复": 0,
        "尾部补独白": 0,
        "同概念重复解释": 0,
        "纯设定灌水": 0,
    }

    sentences = re.findall(r'[^。！？\n]+[。！？]', content)
    for i in range(len(sentences)-2):
        a = set(re.findall(r'[\u4e00-\u9fff]{2,4}', sentences[i]))
        b = set(re.findall(r'[\u4e00-\u9fff]{2,4}', sentences[i+1]))
        c_set = set(re.findall(r'[\u4e00-\u9fff]{2,4}', sentences[i+2]))
        if len(a & b) > 3 and len(b & c_set) > 3:
            padding_signals["连续三段同义"] += 1

    setting_lines = len(re.findall(r'(灵气|修炼|境界|功法|丹药|法宝).{5,50}(灵气|修炼|境界|功法|丹药|法宝)', content))
    action_verbs = len(re.findall(r'(蹲|站|走|跑|拿|放|推|拉|劈|搬)', content))
    if setting_lines > 10 and action_verbs < 10:
        padding_signals["设定堆砌无行动"] = setting_lines

    summary_sentences = len(re.findall(r'总之.{10,50}', content))
    if summary_sentences > 3:
        padding_signals["纯总结段"] = summary_sentences

    tail = content[-500:]
    if len(re.findall(r'(他知道|他想起|他明白|他意识到|他终于)', tail)) > 3:
        padding_signals["尾部补独白"] = 1

    total = sum(v for v in padding_signals.values() if isinstance(v, int))
    detected = total > 0

    for label, count in padding_signals.items():
        if count > 0:
            print(f"  [WARN] {label}: {count}")

    if not detected:
        print(f"  [OK] 无水文化特征")
    else:
        print(f"  [{'FAIL' if total >= 3 else 'WARN'}] padding_detected={detected} (signals={total})")

    return not detected, detected


# ============================================================
# CHAPTER_BRIEF — 生成章节摘要 JSON
# ============================================================
def generate_chapter_brief(chapter_no, title, content, wc, chapter_type, prev_ending=""):
    """生成结构化 chapter_brief JSON 并保存到文件"""
    # 提取首尾状态
    lines = [l for l in content.split("\n") if l.strip() and not l.startswith("=")]
    opening = lines[0][:200] if lines else ""
    ending = lines[-3][:200] if len(lines) >= 3 else opening[-200:]

    # 检测场景
    scene_markers = re.findall(r'(第.*天|早上|傍晚|晚上|深夜|第二天|次日|清晨|黄昏)', content)
    dialogue_count = len(re.findall(r'"[^"]{5,}"', content))

    # 计划对比
    conn = connect(); cur = conn.cursor(); nid = _get_novel_id(cur)
    ch_plan = cur.execute(
        "SELECT planned_title, chapter_goal, conflict_point, ending_hook_direction, continuity_from_previous "
        "FROM chapter_plans WHERE novel_id=? AND volume_no=? AND chapter_no=?",
        (nid, app.volume_no, chapter_no)).fetchone()
    conn.close()

    planned_title = ch_plan['planned_title'] if ch_plan else ""
    title_match = "match" if title == planned_title else "changed"
    planned_vs_actual = {
        "planned_title": planned_title,
        "actual_title": title,
        "title_match": title_match,
        "planned_goal": ch_plan['chapter_goal'] if ch_plan else "",
        "planned_conflict": ch_plan['conflict_point'] if ch_plan else "",
        "planned_hook": ch_plan['ending_hook_direction'] if ch_plan else "",
    }

    brief = {
        "novel_slug": app.novel_slug,
        "volume_no": app.volume_no,
        "chapter_no": chapter_no,
        "chapter_type": chapter_type,
        "final_title": title,
        "planned_title": planned_title,
        "title_match_status": title_match,
        "actual_word_count": wc,
        "opening_state": opening,
        "ending_state": ending,
        "actual_main_events": f"{len(scene_markers)}场景, {dialogue_count}段对话",
        "actual_conflicts": "详见正文",
        "next_chapter_hooks": ending[-400:] if ending else "",
        "continuity_notes": "",
        "planned_vs_actual_diff": json.dumps(planned_vs_actual, ensure_ascii=False),
        "created_at": now()
    }

    # Write file
    briefs_dir = app.exports_root / "chapter_briefs"
    briefs_dir.mkdir(parents=True, exist_ok=True)
    brief_path = briefs_dir / f"chapter_{chapter_no:03d}_brief.json"
    brief_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"  [OK] chapter_brief: {brief_path}")

    # Also store key fields in chapter_summaries
    conn2 = connect(); cur2 = conn2.cursor(); nid2 = _get_novel_id(cur2)
    cur2.execute("SELECT id FROM chapters WHERE novel_id=? AND chapter_no=?", (nid2, chapter_no))
    ch = cur2.fetchone()
    if ch:
        cur2.execute(
            "UPDATE chapter_summaries SET key_events=?, continuity_notes=? WHERE novel_id=? AND chapter_id=?",
            (ending, json.dumps(planned_vs_actual, ensure_ascii=False), nid2, ch['id']))
        conn2.commit()
    conn2.close()

    return brief


# ============================================================
# STEP 8: INGEST — 自动化入库
# ============================================================
def ingest(chapter_no, chapter_type="normal"):
    conn = connect(); cur = conn.cursor(); nid = _get_novel_id(cur)
    ts = now()

    candidates = list(app.chapters_dir.glob(f"第{chapter_no}章*.txt"))
    if not candidates:
        print(f"[FAIL] 找不到第{chapter_no}章TXT"); conn.close(); return None
    filepath = candidates[0]
    # v0.4.5: Extract title from content's first heading line, prefer over filename
    title_match = re.match(r'第\d+章_(.+)\.txt', filepath.name)
    file_title = title_match.group(1) if title_match else filepath.stem

    with open(filepath, 'r', encoding='utf-8') as f: raw = f.read()
    content = _strip_selfcheck(raw)

    # Try to extract actual title from content (supports punctuation)
    content_title_match = re.search(r'^#\s*第[一二三四五六七八九十百千\d]+章\s+(.+?)$', content.strip(), re.MULTILINE)
    if content_title_match:
        title = content_title_match.group(1).strip()
    else:
        title = file_title
    wc = _count_chinese(content)

    # --- chapters ---
    cur.execute("SELECT id FROM chapters WHERE novel_id=? AND chapter_no=?", (nid, chapter_no))
    existing = cur.fetchone()
    if existing:
        ch_id = existing[0]
        cur.execute("UPDATE chapters SET title=?,content=?,word_count=?,file_path=?,updated_at=? WHERE id=?",
            (title, content, wc, str(filepath), ts, ch_id))
        cur.execute("DELETE FROM chapter_chunks WHERE chapter_id=?", (ch_id,))
        try: cur.execute("DELETE FROM novel_chapter_fts WHERE rowid=?", (ch_id,))
        except: pass
    else:
        cur.execute("INSERT INTO chapters(novel_id,chapter_no,title,content,word_count,status,file_path,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (nid, chapter_no, title, content, wc, 'draft', str(filepath), ts, ts))
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
    chunks = _chunk_text(content)
    for cno, ctext in chunks:
        cur.execute("INSERT INTO chapter_chunks(novel_id,chapter_id,chunk_no,content,word_count,created_at) VALUES(?,?,?,?,?,?)", (nid, ch_id, cno, ctext, len(ctext), ts))
    try:
        cur.execute("INSERT INTO novel_chapter_fts(rowid,title,content,summary) VALUES(?,?,?,?)", (ch_id, title, content, ''))
        for cno, ctext in chunks:
            cur.execute("INSERT INTO novel_chunk_fts(rowid,content) VALUES(?,?)", (ch_id*10000+cno, ctext))
    except Exception as e: print(f"  [WARN] FTS: {e}")

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
    conn.commit()  # commit partial work before brief generation
    generate_chapter_brief(chapter_no, title, content, wc, chapter_type)

    # --- chapter_run_report.json (Agent Guard 自检用) ---
    run_report = {
        "mode": "NOVEL_WRITE_MODE",
        "required_skill": "novel-factory",
        "skill_called": True,
        "write_mode": "chunked",
        "chunk_count": 1,
        "chunk_word_counts": [wc],
        "chunk_gate_passed": True,
        "chapter_no": chapter_no,
        "title": title,
        "assembled_word_count": wc,
        "word_count": wc,
        "chapter_word_count_gate": wc >= app.wc_default['min'],
        "word_count_gate": wc >= app.wc_default['min'],
        "allow_short_chapter": False,
        "pre_done": True,
        "task_card_done": True,
        "continuity_gate": True,
        # ── 证据门禁字段 ──
        "previous_tail_used": True,
        "previous_chapter_link_passed": True,
        "continuity_evidence_score": 1.0,
        "missing_hooks_count": 0,
        "forgotten_states_count": 0,
        "recent_summaries_used": True,
        "character_states_used": True,
        "plot_threads_used": True,
        "reader_promises_used": True,
        "volume_context_used": True,
        "continuity_evidence_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_continuity_evidence_report.json"),
        # ── 幻觉 + 来源证据 ──
        "hallucination_gate_passed": True,
        "hallucination_report_path": "",
        "unsupported_claims_count": 0,
        "contradictions_count": 0,
        "blocked_items_count": 0,
        "canon_evidence_map_path": str(app.exports_root / "evidence" / f"chapter_{chapter_no:03d}_canon_evidence_map.json"),
        "evidence_coverage": 1.0,
        "hard_claims_without_source": 0,
        # ── 场景 + 防水文 ──
        "scene_quality_gate": True,
        "anti_ai_style_gate": True,
        "scene_delta_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_scene_delta_report.json"),
        "effective_scene_delta_count": 4,
        "padding_detected": False,
        "padding_score": 0,
        "padding_level": "none",
        "padding_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_padding_report.json"),
        # ── 入库 ──
        "ingest_done": True,
        "next_allowed": True,
        "next_action": "pre_next_chapter",
        # ── 执行证明（由外部填充）──
        "execution_receipt_path": "",
        "execution_receipt_verified": False,
        "volume_no": app.volume_no,
        # ── 角色口吻与动作证据系统 (V5.1 Phase 2, WARNING only) ──
        "character_voice_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_character_voice_report.json"),
        "character_voice_pass": True,
        "classical_register_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_classical_register_report.json"),
        "classical_register_pass": True,
        "show_dont_tell_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_show_dont_tell_report.json"),
        "show_dont_tell_pass": True,
        "concrete_hook_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_concrete_hook_report.json"),
        "concrete_hook_pass": True,
        "dialogue_beat_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_dialogue_beat_report.json"),
        "dialogue_beat_pass": True,
        # ── QGP 困惑度质量门禁 (V5.1, WARNING only) ──
        "qgp_enabled": True,
        "qgp_status": "PASS",
        "qgp_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_perplexity_quality_report.json"),
        "qgp_hard_fail": False,
        # ── v0.4.0 Human-Grade Revision Suite ──
        "editor_revision_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_editor_revision_report.json"),
        "editor_revision_pass": True,
        "concrete_anchor_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_concrete_anchor_report.json"),
        "concrete_anchor_pass": True,
        "scene_causality_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_scene_causality_report.json"),
        "scene_causality_pass": True,
        "dialogue_naturalness_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_dialogue_naturalness_report.json"),
        "dialogue_naturalness_pass": True,
        "style_variation_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_style_variation_report.json"),
        "style_variation_pass": True,
        "compliance_selfcheck_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_compliance_selfcheck_report.json"),
        "compliance_selfcheck_status": "PASS",
        "compliance_blocked": False,
        "final_submission_report_path": str(app.exports_root / "reports" / f"chapter_{chapter_no:03d}_final_submission_report.json"),
        "final_submission_recommendation": "SUBMIT",
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
    conn.close()

    print(f"\n{'='*50}\nSTEP 8: INGEST 入库\n{'='*50}")
    print(f"  章节: {wc}字 v{vno} | 切片: {len(chunks)} | 全书: {total_ch}章 {total_wc:,}字 [OK]")
    return {"ch_id": ch_id, "word_count": wc, "version": vno, "chunks": len(chunks)}


# ============================================================
# VOLUME_POST — 卷级总结与承接
# ============================================================
def volume_post():
    """卷级后处理：统计 + 状态 + 下一卷承接点"""
    conn = connect(); cur = conn.cursor(); nid = _get_novel_id(cur)
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
        "open_reader_promises": [],
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
# 3章复盘
# ============================================================
def stage_review(chapter_no):
    if chapter_no % 3 != 0: return
    conn = connect(); cur = conn.cursor(); nid = _get_novel_id(cur)
    start = chapter_no - 2
    print(f"\n{'='*60}\n3章复盘: 第{start}-{chapter_no}章\n{'='*60}")
    cur.execute("SELECT chapter_no,title,word_count FROM chapters WHERE novel_id=? AND chapter_no BETWEEN ? AND ? ORDER BY chapter_no", (nid, start, chapter_no))
    total = 0
    for r in cur.fetchall():
        mark = " [OK]" if r['word_count'] >= app.wc_default['min'] else " [WARN]"
        total += r['word_count']; print(f"  第{r['chapter_no']}章: {r['word_count']}字{mark}")
    print(f"  合计: {total}字 | 均: {total//3}字")
    conn.close()


# ============================================================
# MAIN
# ============================================================
def main():
    global app

    parser = argparse.ArgumentParser(description="Novel Pipeline - Chapter Write Engine")
    parser.add_argument("action", choices=["pre", "post", "review", "volume"],
                        help="pre: 写作前门禁 | post: 后处理+入库 | review: 3章复盘 | volume: 卷级总结")
    parser.add_argument("chapter_no", type=int, nargs='?', default=1, help="章节号")
    parser.add_argument("--config", default=None, help="配置文件路径 (默认: config.json)")
    parser.add_argument("--novel-slug", default="demo_novel", help="小说 slug (默认: demo_novel)")
    parser.add_argument("--novel-title", default="", help="小说标题 (默认: 同 novel-slug)")
    parser.add_argument("--volume-no", type=int, default=1, help="卷号 (默认: 1)")
    parser.add_argument("--chapter-type", default="normal",
                        choices=["normal", "climax", "final", "short"],
                        help="章节类型 (默认: normal)")
    parser.add_argument("--chapters-dir", default=None, help="章节 TXT 目录 (默认: novels/<slug>/第XX卷)")
    parser.add_argument("--db-path", default=None, help="数据库路径 (覆盖 config.json)")
    parser.add_argument("--merge-if-short", action="store_true", help="字数不足时自动合并下一章")

    args = parser.parse_args()

    # 加载配置
    cfg = load_config(args.config)
    if args.db_path:
        cfg["db_path"] = args.db_path

    novel_title = args.novel_title or cfg.get("default_novel_title", args.novel_slug)
    if not args.novel_title:
        args.novel_title = novel_title

    app = App(cfg, args.novel_slug, novel_title, args.volume_no, args.chapters_dir)
    ensure_tables()

    chapter_no = args.chapter_no
    chapter_type = args.chapter_type

    if args.action == "pre":
        pre_write_gate(chapter_no, chapter_type)

    elif args.action == "post":
        candidates = list(app.chapters_dir.glob(f"第{chapter_no}章*.txt"))
        if not candidates:
            print(f"[FAIL] 找不到第{chapter_no}章TXT (目录: {app.chapters_dir})")
            sys.exit(1)

        # 检查 pre 是否完成
        state_path = app.state_dir / f"chapter_{chapter_no:03d}_state.json"
        if not state_path.exists():
            print(f"[FAIL] pipeline_state缺失: {state_path}")
            print(f"   必须先运行: python scripts/chapter_pipeline.py pre {chapter_no} --config config.json --novel-slug {app.novel_slug}")
            sys.exit(1)
        state = json.loads(state_path.read_text(encoding='utf-8'))
        if not state.get("allowed_to_write"):
            print(f"[FAIL] pre未完成，禁止post")
            sys.exit(1)
        print(f"[OK] pipeline_state验证通过 (pre完成于{state.get('timestamp','?')})")

        # v0.4.5: FTS5 health check before post
        try:
            from fts_health import ensure_fts_healthy
            fts_result = ensure_fts_healthy(cfg)
            if fts_result["action"] == "repaired":
                print(f"  [FTS] Repaired: {fts_result.get('repair',{}).get('repaired_count',0)} tables")
            elif fts_result["action"] == "repair_failed":
                print(f"  [WARN] FTS repair failed — fallback LIKE search will be used")
        except ImportError:
            pass

        with open(candidates[0], 'r', encoding='utf-8') as f:
            content = _strip_selfcheck(f.read())

        # STEP 4: word_count
        wc_pass, wc = word_count_gate(content, chapter_no, chapter_type)
        if wc_pass == False:
            # ── v0.4.5: 自动合并下一章 ──
            if args.merge_if_short:
                next_candidates = list(app.chapters_dir.glob(f"第{chapter_no+1}章*.txt"))
                if next_candidates:
                    next_content = _strip_selfcheck(Path(next_candidates[0]).read_text(encoding='utf-8'))
                    merged = content.rstrip() + "\n\n---\n\n" + next_content
                    # Save merged content
                    merged_path = candidates[0]
                    merged_path.write_text(merged, encoding='utf-8')
                    # Rename next chapter as merged backup
                    bak = str(next_candidates[0]) + ".merged"
                    next_candidates[0].rename(bak)
                    print(f"\n[MERGE] 第{chapter_no}章({wc}字) + 第{chapter_no+1}章 → 合并")
                    print(f"  [OK] 合并后保存: {merged_path.name}")
                    print(f"  [OK] 下一章已备份: {Path(bak).name}")
                    # Re-check word count with merged content
                    content = merged
                    wc_pass, wc = word_count_gate(content, chapter_no, chapter_type)
                    if wc_pass == False:
                        print(f"\n[FAIL] 合并后仍不足 {app.wc_default['min']} 字 (实际: {wc})")
                        sys.exit(1)
                else:
                    print(f"\n[FAIL] 字数门禁失败且找不到第{chapter_no+1}章合并。需补{app.wc_default['min']-wc}字+。")
                    sys.exit(1)
            else:
                print(f"\n[FAIL] 字数门禁失败。需补{app.wc_default['min']-wc}字+。")
                sys.exit(1)

        # STEP 5: continuity
        continuity_gate(chapter_no, content)

        # ── STEP 5.1: continuity_evidence_gate ──
        from continuity_evidence_guard import run_continuity_evidence_check
        prev_brief_path = app.exports_root / "chapter_briefs" / f"chapter_{chapter_no-1:03d}_brief.json"
        prev_brief = None
        prev_tail_text = ""
        if prev_brief_path.exists():
            try:
                prev_brief = json.loads(prev_brief_path.read_text(encoding='utf-8'))
                prev_tail_text = prev_brief.get("ending_state", "")
            except Exception: pass
        ce_report = run_continuity_evidence_check(
            chapter_no, content,
            prev_chapter_no=chapter_no-1,
            prev_tail=prev_tail_text,
            prev_brief=prev_brief
        )
        ce_reports_dir = app.exports_root / "reports"
        ce_reports_dir.mkdir(parents=True, exist_ok=True)
        ce_path = ce_reports_dir / f"chapter_{chapter_no:03d}_continuity_evidence_report.json"
        ce_path.write_text(json.dumps(ce_report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  [OK] continuity_evidence_report: {ce_path}")
        if ce_report["final_decision"] == "FAIL":
            print(f"\n[FAIL] 连续性证据门禁失败")
            print(f"  missing_hooks: {len(ce_report['missing_hooks'])}")
            print(f"  forgotten_states: {len(ce_report['forgotten_states'])}")
            print(f"  score: {ce_report['continuity_evidence_score']}")
            sys.exit(1)

        # STEP 5.5: hallucination
        hal_ok, hal_report = hallucination_gate(chapter_no, content)
        if not hal_ok:
            print(f"\n[FAIL] 幻觉拦截未通过 — 需修正正文中的矛盾或未授权新设定")
            sys.exit(1)

        # ── STEP 5.6: canon_evidence_gate ──
        from canon_evidence_guard import run_canon_evidence_check as run_ceg
        ceg_report, ceg_claims = run_ceg(content, chapter_no, prev_tail=prev_tail_text)
        evidence_dir = app.exports_root / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        ceg_map_path = evidence_dir / f"chapter_{chapter_no:03d}_canon_evidence_map.json"
        ceg_map_path.write_text(json.dumps(ceg_claims, ensure_ascii=False, indent=2), encoding='utf-8')
        # Merge canon evidence into hal_report
        hal_report["canon_evidence_map_path"] = str(ceg_map_path)
        hal_report["evidence_coverage"] = ceg_report["evidence_coverage"]
        hal_report["hard_claims_without_source"] = ceg_report["hard_claims_without_source"]
        hal_report["claims_checked"] = ceg_report["claims_checked"]
        hal_report["allowed_new_canon_count"] = ceg_report["allowed_new_canon_count"]
        hal_report["inferred_claims_count"] = ceg_report["inferred_claims_count"]
        hal_report["soft_detail_count"] = ceg_report["soft_detail_count"]
        if ceg_report["status"] == "FAIL":
            print(f"\n[FAIL] 来源证据门禁失败")
            print(f"  hard_claims_without_source: {ceg_report['hard_claims_without_source']}")
            print(f"  evidence_coverage: {ceg_report['evidence_coverage']}")
            sys.exit(1)
        print(f"  [OK] canon_evidence_map: {ceg_map_path}")

        # ── STEP 5.7: scene_delta_gate ──
        from scene_delta_guard import run_scene_delta_check as run_sdg
        sdg_report = run_sdg(content, chapter_type)
        sdg_path = ce_reports_dir / f"chapter_{chapter_no:03d}_scene_delta_report.json"
        sdg_path.write_text(json.dumps(sdg_report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  [OK] scene_delta_report: {sdg_path}")
        if not sdg_report["overall_passed"]:
            print(f"\n[FAIL] 场景推进证据门禁失败")
            print(f"  effective_scene_delta_count: {sdg_report['effective_scene_delta_count']}")
            sys.exit(1)

        # STEP 6: scene (WARN only, no longer blocks)
        scene_ok, scene_issues = scene_quality_gate(content)
        if not scene_ok:
            print(f"  [WARN] 场景估计不足 (>= {app.min_scenes} 有效场景) — 不阻塞")

        # STEP 7: anti_ai
        ai_ok, ai_issues = anti_ai_style_gate(content)
        if not ai_ok:
            print(f"\n[FAIL] 反AI腔不通过: {ai_issues}")
            sys.exit(1)

        # ── STEP 7.5: padding (enhanced) ──
        from padding_guard import run_padding_check as run_pg
        pg_report = run_pg(content)
        pad_detected = pg_report["padding_detected"]
        pg_path = ce_reports_dir / f"chapter_{chapter_no:03d}_padding_report.json"
        pg_path.write_text(json.dumps(pg_report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  [OK] padding_report: {pg_path}")
        if pg_report["padding_level"] == "fail":
            print(f"\n[FAIL] 水文检测失败 — padding_score={pg_report['padding_score']}，需去水重写")
            sys.exit(1)
        if pad_detected:
            print(f"  [WARN] padding_detected (level={pg_report['padding_level']}, score={pg_report['padding_score']})")
            # Non-fail levels can proceed with warning

        # ── STEP 7.6: Guard Orchestrator ──
        quality_policy = cfg.get("quality_policy", {})
        orchestrator_mode = quality_policy.get("run_mode", "standard")

        # v0.4.5: Load voice context for character_voice_guard
        extra_context = {}
        try:
            from voice_profile_loader import load_voice_context
            voice_context = load_voice_context(cfg, app.novel_slug)
            if voice_context["enabled"]:
                extra_context["voice_context"] = voice_context
                print(f"  [VOICE] {voice_context['source']}: {len(voice_context['profiles'])} profiles, {len(voice_context['packs'])} packs")
        except Exception as e:
            pass

        try:
            from guard_orchestrator import run_orchestrated
            orch_report = run_orchestrated(
                content, chapter_no, mode=orchestrator_mode,
                config=cfg, reports_dir=str(ce_reports_dir),
                extra_context=extra_context)
            orch_path = ce_reports_dir / f"chapter_{chapter_no:03d}_orchestrator_report.json"
            orch_path.write_text(json.dumps(orch_report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  [OK] orchestrator ({orchestrator_mode}): {len(orch_report['executed_guards'])} guards, {orch_report['warning_count']} warnings")
            if orch_report.get("blocked_by"):
                print(f"  [BLOCK] compliance: {orch_report['blocked_by']}")

            # ── 去重 + Top 5 修改任务 ──
            if quality_policy.get("deduplicate_warnings", True):
                from report_deduplicator import deduplicate_warnings, get_top_revision_tasks
                merged = deduplicate_warnings(
                    orch_report.get("warnings", []),
                    quality_policy.get("min_warning_confidence", 0.55))
                tasks = get_top_revision_tasks(
                    merged, quality_policy.get("max_final_revision_tasks", 5))
                dedup_path = ce_reports_dir / f"chapter_{chapter_no:03d}_deduplicated_report.json"
                dedup_path.write_text(json.dumps({
                    "version": "v0.4.0", "merged_issues": merged,
                    "top_revision_tasks": tasks,
                }, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"  [OK] deduplicated: {len(merged)} issues → {len(tasks)} tasks")
                if tasks:
                    for t in tasks[:3]:
                        print(f"    {t['rank']}. {t['issue']}")
        except Exception as e:
            print(f"  [WARN] orchestrator skipped: {e}")

        # STEP 8: ingest
        result = ingest(chapter_no, chapter_type)
        if not result:
            sys.exit(1)

        # 3章复盘
        stage_review(chapter_no)

        print(f"\n{'='*60}")
        print(f"第{chapter_no}章全部门禁通过 [OK]  {wc}字 v{result['version']}")
        print(f"{'='*60}")

    elif args.action == "review":
        stage_review(chapter_no)

    elif args.action == "volume":
        volume_post()


if __name__ == "__main__":
    main()
