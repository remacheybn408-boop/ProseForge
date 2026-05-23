"""
chapter_pipeline.py — 章节写作总控流水线 V4
8步精简流水线:
  pre → task_card → write → word_count → continuity → scene → anti_ai → ingest

字数门禁:
  < 3300: 红灯失败
  3300-3500: pass_but_low（字数额度紧，需场景/连续性确认）
  3500-3900: 最佳
  3900-4200: 正常通过
  4200-5000: 仅特殊章
  > 5000: 警告

场景门禁: >= 4 有效场景

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
    "word_count": {"hard_min": 3300, "ideal_min": 3500, "ideal_max": 3900, "normal_max": 4200, "special_max": 5000},
    "scene_quality": {"min_effective_scenes": 4},
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
        f"目标字数: {app.wc_rules['ideal_min']}-{app.wc_rules['ideal_max']} | "
        f"红线: {app.wc_rules['hard_min']}\n"
        f"{skeleton_info}\n", encoding='utf-8')
    print(f"  [OK] context_pack: {pack_path}")

    # task_card (含标题骨架指引)
    print(f"\n{'='*60}")
    print(f"TASK CARD - 第{chapter_no}章 [{chapter_type}]")
    print(f"  字数范围: {app.wc_rules['hard_min']}-{app.wc_rules['normal_max']} | 最佳: {app.wc_rules['ideal_min']}-{app.wc_rules['ideal_max']}")
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
    rules = app.wc_rules
    wc = _count_chinese(content)
    print(f"\n{'='*50}\nSTEP 4: 字数门禁 [{chapter_type}]\n{'='*50}")
    print(f"  字数: {wc} | 红线: {rules['hard_min']} | 最佳: {rules['ideal_min']}-{rules['ideal_max']}")

    if wc < rules['hard_min']:
        print(f"  [FAIL] 红灯失败 ({wc} < {rules['hard_min']}) — 必须重写")
        return False, wc

    if rules['ideal_min'] <= wc <= rules['ideal_max']:
        print(f"  [OK] 最佳区间")
        return "ideal", wc

    if app.wc_rules['hard_min'] <= wc < app.wc_rules['ideal_min']:
        # pass_but_low: 字数额度紧，需其他门禁确认
        vcount = 0
        try:
            conn_check = connect()
            vcount = conn_check.execute(
                "SELECT COUNT(*) FROM chapter_versions WHERE novel_id=(SELECT id FROM novels WHERE slug=?) AND chapter_no=?",
                (app.novel_slug, chapter_no)).fetchone()[0]
            conn_check.close()
        except Exception:
            pass  # table may not exist yet
        if vcount >= 3:
            print(f"  [FAIL] pass_but_low+版本>={vcount} — 疑似patch凑数，必须重铺场景")
            return "patch_suspect", wc
        print(f"  [WARN] pass_but_low ({wc} < {app.wc_rules['ideal_min']}) — 需场景/连续性确认")
        return "pass_but_low", wc

    if rules['ideal_max'] < wc <= rules['normal_max']:
        print(f"  [OK] 正常通过 (偏长)")
        return True, wc

    if rules['normal_max'] < wc <= rules['special_max']:
        if chapter_type in ("climax", "final"):
            print(f"  [OK] 特殊章允许")
            return True, wc
        else:
            print(f"  [WARN] 超上限({wc}>{rules['normal_max']}) — 检查是否拖沓")
            return "oversize", wc

    # > special_max
    print(f"  [WARN] 超长({wc}>{rules['special_max']}) — 仅卷终章建议此字数")
    return "oversize", wc


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

    cur.execute("INSERT INTO continuity_checks(novel_id,chapter_id,check_type,issue,severity,status) VALUES(?, (SELECT id FROM chapters WHERE novel_id=? AND chapter_no=?), 'continuity', ?, ?, ?)",
        (nid, nid, chapter_no, f"得分{score}/15" if score < 15 else "正常", 3 if score < 15 else 1, 'open' if score < 15 else 'resolved'))
    conn.commit(); conn.close()

    if score >= 12: print("  [OK] 通过"); return True
    else: print("  [WARN] 建议增强承接"); return True


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
# STEP 8: INGEST — 自动化入库
# ============================================================
def ingest(chapter_no, chapter_type="normal"):
    conn = connect(); cur = conn.cursor(); nid = _get_novel_id(cur)
    ts = now()

    candidates = list(app.chapters_dir.glob(f"第{chapter_no}章*.txt"))
    if not candidates:
        print(f"[FAIL] 找不到第{chapter_no}章TXT"); conn.close(); return None
    filepath = candidates[0]
    title_match = re.match(r'第\d+章_(.+)\.txt', filepath.name)
    title = title_match.group(1) if title_match else filepath.stem

    with open(filepath, 'r', encoding='utf-8') as f: raw = f.read()
    content = _strip_selfcheck(raw)
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
            cur.execute("INSERT INTO novel_chunk_fts(rowid,content,summary,tags) VALUES(?,?,?,?)", (ch_id*10000+cno, ctext, '', ''))
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

    # 统计本卷章节
    cur.execute("SELECT chapter_no, title, word_count, status FROM chapters WHERE novel_id=? AND volume_id=(SELECT id FROM volumes WHERE novel_id=? AND volume_no=?) ORDER BY chapter_no",
        (nid, nid, vol_no))
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
            arc_info = f" — {c['arc'][:60]}" if c.get('arc') else ""
            print(f"    [{c['role']}] {c['name']}{arc_info}")

    # 下一卷承接点
    if vol_plan and vol_plan.get('unresolved_hooks_to_next'):
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
        mark = " [OK]" if r['word_count'] >= app.wc_rules['hard_min'] else " [WARN]"
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

        with open(candidates[0], 'r', encoding='utf-8') as f:
            content = _strip_selfcheck(f.read())

        # STEP 4: word_count
        wc_pass, wc = word_count_gate(content, chapter_no, chapter_type)
        if wc_pass == False:
            print(f"\n[FAIL] 字数门禁失败。需补{app.wc_rules['hard_min']-wc}字+。")
            sys.exit(1)
        if wc_pass == "patch_suspect":
            print(f"\n[FAIL] 疑似patch凑数 — 必须重铺缺失场景。回到task_card找缺失场景。")
            sys.exit(1)

        # STEP 5: continuity
        continuity_gate(chapter_no, content)

        # STEP 6: scene
        scene_ok, scene_issues = scene_quality_gate(content)
        if wc_pass == "pass_but_low" and not scene_ok:
            print(f"\n[FAIL] pass_but_low+场景不足 → 必须扩写")
            sys.exit(1)
        if not scene_ok and wc_pass != "pass_but_low":
            print(f"\n[FAIL] 场景门禁失败 — 需要 >= {app.min_scenes} 有效场景")
            sys.exit(1)

        # STEP 7: anti_ai
        ai_ok, ai_issues = anti_ai_style_gate(content)
        if not ai_ok:
            print(f"\n[FAIL] 反AI腔不通过: {ai_issues}")
            sys.exit(1)

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
