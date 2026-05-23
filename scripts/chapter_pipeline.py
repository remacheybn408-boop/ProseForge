"""
chapter_pipeline.py — 章节写作总控流水线 V3
第一阶段：8步精简流水线
  pre → task_card → write → word_count → continuity → scene → anti_ai → ingest

字数标准：
  普通章 3300-4200 通过 | 高潮章 4200-5000 | 黄灯 3000-3300 | 红灯 <3000

用法:
  python chapter_pipeline.py pre <chapter_no> [--type normal|climax|final|short]
  python chapter_pipeline.py post <chapter_no>
  python chapter_pipeline.py review <chapter_no>
"""

import sqlite3, re, sys
from pathlib import Path
from datetime import datetime

# ============================================================
DB_PATH = Path(r"D:\HermesMemoryBase\database\hermes_memory.db")
CHAPTERS_DIR = Path(r"D:\小说\格物证道\第一卷_杂役观天")
EXPORTS_DIR = Path(r"D:\HermesMemoryBase\novels\gewuzhengdao\exports")
STATE_DIR = EXPORTS_DIR / "pipeline_state"
NOVEL_SLUG = "gewuzhengdao"

# 字数标准（分类型）
WORD_RULES = {
    "normal":  {"target": 3700, "min": 3300, "max": 4200, "fail": 3000},
    "climax":  {"target": 4500, "min": 4200, "max": 5000, "fail": 3000},
    "final":   {"target": 5000, "min": 4500, "max": 6000, "fail": 3000},
    "short":   {"target": 3200, "min": 3000, "max": 3300, "fail": 2800},
}

def now(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def _get_novel_id(cur):
    cur.execute("SELECT id FROM novels WHERE slug=?", (NOVEL_SLUG,))
    return cur.fetchone()[0]

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
    conn = sqlite3.connect(str(DB_PATH))
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
    rules = WORD_RULES.get(chapter_type, WORD_RULES["normal"])
    log_entries = []
    prev_ch = chapter_no - 1; prev_ending = ""

    print("="*60)
    print(f"STEP 1: PRE — 第{chapter_no}章 [{chapter_type}] — 《格物证道》")
    print("="*60)

    if prev_ch >= 1:
        cur.execute("SELECT title, content FROM chapters WHERE novel_id=? AND chapter_no=?", (nid, prev_ch))
        prev = cur.fetchone()
        if not prev:
            print(f"\n⛔ 第{prev_ch}章不存在于数据库"); conn.close(); return None
        prev_ending = _strip_selfcheck(prev['content'])[-800:]
        cur.execute("SELECT short_summary FROM chapter_summaries WHERE novel_id=? AND chapter_id=(SELECT id FROM chapters WHERE novel_id=? AND chapter_no=?)", (nid, nid, prev_ch))
        sm = cur.fetchone()
        print(f"✓ 上章: 第{prev_ch}章《{prev['title']}》末400字:")
        print(f"  {prev_ending[-400:]}")
        log_entries.append(f"读取第{prev_ch}章结尾{len(prev_ending)}字")
    else:
        print("✓ 第1章，无上章")

    # 最近3章
    print("\n✓ 最近3章:")
    for ch in range(max(1, chapter_no-3), chapter_no):
        cur.execute("SELECT cs.short_summary FROM chapter_summaries cs JOIN chapters c ON c.id=cs.chapter_id WHERE c.novel_id=? AND c.chapter_no=?", (nid, ch))
        cs = cur.fetchone()
        print(f"  第{ch}章: {cs['short_summary'][:100] if cs else '(无摘要)'}")

    # 人物
    cur.execute("SELECT name, role, identity FROM characters WHERE novel_id=?", (nid,))
    chars = cur.fetchall()
    print(f"\n✓ 人物({len(chars)}): " + ", ".join(f"[{c['role']}]{c['name']}" for c in chars))
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
        print(f"✓ {label}({len(rows)}): " + ", ".join(str(dict(r)) for r in rows[:5]))
        log_entries.append(f"{label}{len(rows)}条")

    # context_pack
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pack_path = EXPORTS_DIR / f"context_ch{chapter_no}_{datetime.now().strftime('%H%M%S')}.txt"
    pack_path.write_text(f"写作上下文包-第{chapter_no}章\n{'='*40}\n字数:{rules['target']} | 最低:{rules['min']} | 失败:{rules['fail']}\n", encoding='utf-8')
    print(f"\n✓ context_pack: {pack_path}")

    # task_card
    print(f"\n{'='*60}")
    print(f"TASK CARD - 第{chapter_no}章 [{chapter_type}]")
    draft_target = "3500-3800" if chapter_type == "normal" else f"{rules['min']}-{rules['target']}"
    print(f"  字数范围: {rules['min']}-{rules['max']} | 初稿目标: {draft_target}字 | 失败线: {rules['fail']}")
    print(f"  必须≥4场景 | ≥2生活细节 | ≥1不完美互动")
    print(f"  禁止: AI句式/硬科普/总结腔/空泛心理")
    if prev_ending:
        print(f"  承接: {prev_ending[-120:]}")
    print(f"{'='*60}")

    cur.execute("INSERT INTO novel_logs(action,target_type,detail) VALUES('pre_write','chapter',?)", ("; ".join(log_entries),))
    conn.commit(); conn.close()

    # 保存 pipeline_state.json 文件锁
    import json
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = {
        "chapter_no": chapter_no, "chapter_type": chapter_type,
        "pre_done": True, "previous_tail_loaded": prev_ch >= 1,
        "recent_summaries_loaded": True, "sqlite_search_logged": True,
        "reader_promises_checked": True, "context_pack": str(pack_path),
        "allowed_to_write": True, "timestamp": now()
    }
    state_path = STATE_DIR / f"chapter_{chapter_no:03d}_state.json"
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"✓ pipeline_state: {state_path}")

    print(f"\nSTEP 1 ✓ — 上下文就绪")
    return {"chapter_no": chapter_no, "prev_ch": prev_ch, "prev_ending": prev_ending,
            "chapter_type": chapter_type, "rules": rules, "context_pack": str(pack_path)}


# ============================================================
# STEP 4: WORD_COUNT — 字数门禁（新标准）
# ============================================================
def word_count_gate(content, chapter_no, chapter_type="normal"):
    rules = WORD_RULES.get(chapter_type, WORD_RULES["normal"])
    wc = _count_chinese(content)
    print(f"\n{'='*50}\nSTEP 4: 字数门禁 [{chapter_type}]\n{'='*50}")
    print(f"  字数: {wc} | 目标: {rules['target']} | 范围: {rules['min']}-{rules['max']} | 失败: {rules['fail']}")

    if rules['min'] <= wc <= rules['max']:
        print(f"  ✓ 正常通过")
        return True, wc
    elif wc > rules['max']:
        if chapter_type in ("climax", "final"):
            print(f"  ✓ 高潮/卷末章允许扩展")
            return True, wc
        else:
            print(f"  ⚠ 超上限，检查是否拖沓")
            return True, wc  # 不拦截，只提醒
    elif rules['fail'] <= wc < rules['min']:
        # 检查是否靠patch凑数
        conn_check = connect()
        vcount = conn_check.execute(
            "SELECT COUNT(*) FROM chapter_versions WHERE novel_id=(SELECT id FROM novels WHERE slug=?) AND chapter_no=?",
            (NOVEL_SLUG, chapter_no)).fetchone()[0]
        conn_check.close()
        if vcount >= 3:
            print(f"  ⛔ 黄灯+版本≥3 — 疑似patch凑数({vcount}个版本)，必须重铺场景而非继续patch")
            return "patch_suspect", wc
        print(f"  ⚠ 黄灯 ({wc}<{rules['min']}) — 检查场景质量和连续性")
        return "yellow", wc  # 黄灯：需其他门禁确认
    else:
        print(f"  ⛔ 红灯失败 ({wc}<{rules['fail']}) — 必须重写")
        return False, wc


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
        print(f"⛔ 连续性: 第{prev_ch}章不存在"); conn.close(); return False

    prev_end = _strip_selfcheck(prev['content'])[-400:]
    ch_start = content[:400]
    prev_words = set(re.findall(r'[\u4e00-\u9fff]{2,4}', prev_end[-200:]))
    start_words = set(re.findall(r'[\u4e00-\u9fff]{2,4}', ch_start[:200]))
    names_prev = set(re.findall(r'(林观澜|韩烈|顾长庚|赵管事|马瘸子|小五|吴执事|季长峰|萧无极|沈青霜|周不器|黑衣执事)', prev_end))
    names_start = set(re.findall(r'(林观澜|韩烈|顾长庚|赵管事|马瘸子|小五|吴执事|季长峰|萧无极|沈青霜|周不器|黑衣执事)', ch_start))
    overlap = prev_words & start_words
    score = len(overlap)*2 + len(names_prev & names_start)*5 + 3  # base score

    print(f"\n{'='*50}\nSTEP 5: 连续性检查\n{'='*50}")
    print(f"  重合词: {list(overlap)[:8]} | 人物承接: {names_prev & names_start} | 得分: {score}/15")

    cur.execute("INSERT INTO continuity_checks(novel_id,chapter_id,check_type,issue,severity,status) VALUES(?, (SELECT id FROM chapters WHERE novel_id=? AND chapter_no=?), 'continuity', ?, ?, ?)",
        (nid, nid, chapter_no, f"得分{score}/15" if score < 15 else "正常", 3 if score < 15 else 1, 'open' if score < 15 else 'resolved'))
    conn.commit(); conn.close()

    if score >= 12: print("  ✓ 通过"); return True
    else: print("  ⚠ 警告: 建议增强承接"); return True


# ============================================================
# STEP 6: SCENE — 场景质量门禁
# ============================================================
def scene_quality_gate(content):
    print(f"\n{'='*50}\nSTEP 6: 场景质量检查\n{'='*50}")

    # 简单场景检测：按空行+位置变化+人物出场分块
    paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
    # 检测场景切换标志：时间词、地点词、空行密集区
    scene_markers = re.findall(r'(第.*天|早上|傍晚|晚上|深夜|第二天|次日|清晨|黄昏|午后|下午|当天|回到|来到|走进|出了|站在|蹲在)', content)
    location_changes = len(set(re.findall(r'(杂役院|劈柴场|矿洞|井边|灵料坊|讲经台|演武场|禁地|铺位|后山|考核场)', content)))
    character_appearances = len(re.findall(r'(韩烈|顾长庚|赵管事|马瘸子|小五|吴执事|季长峰|萧无极|黑衣执事|老张头|赵大彪)', content))

    # 粗略场景估计
    estimated_scenes = max(len(scene_markers)//2, location_changes, 1)
    print(f"  场景标记: {len(scene_markers)} | 地点数: {location_changes} | 配角出场: {character_appearances}")
    print(f"  估计场景数: {estimated_scenes}")

    # 检查无效场景特征
    issues = []
    # 检查总结腔
    summary_lines = len(re.findall(r'(他知道|他明白|他意识到|这意味着|这说明|总之)', content))
    if summary_lines > 5: issues.append(f"总结腔过多({summary_lines}处)")
    # 检查是否缺少对话
    dialogue_lines = len(re.findall(r'"[^"]{5,}"', content))
    if dialogue_lines < 3: issues.append(f"对话过少({dialogue_lines}处)")
    # 检查是否缺少动作
    action_verbs = len(re.findall(r'(蹲|站|走|跑|拿|放|推|拉|按|握|劈|搬|涂|贴|刮|洗)', content))
    if action_verbs < 15: issues.append(f"动作描写过少({action_verbs}处)")

    passed = estimated_scenes >= 3 and len(issues) < 3
    if issues:
        for i in issues: print(f"  ⚠ {i}")
    if passed:
        print(f"  ✓ 通过 (≥3场景, 无明显水症)")
    else:
        print(f"  ⚠ 场景不足或存在水症")
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
        "他意识到": len(re.findall(r'他意识到|他意识到|他明白', content)),
        "这意味着": len(re.findall(r'这意味着|这说明|这代表', content)),
        "像一座废墟/像一尊雕像": len(re.findall(r'像一座|像一尊|像一个.*的', content)),
        "沉默了几秒": len(re.findall(r'沉默了几秒|沉默了片刻|沉默了.{1,4}秒', content)),
        "是她的救赎": len(re.findall(r'救赎|他就是她的|她就是他的', content)),
        "硬科普指标": len(re.findall(r'(公式|定律|方程|定理|热力学|量子力学|相对论)', content)),
        "论文式句子": len(re.findall(r'通过.{5,20}实现了|基于.{5,20}进行了|本质上是|从某种意义上说|事实上', content)),
    }

    total = sum(checks.values())
    for label, count in checks.items():
        if count > 0: print(f"  ⚠ {label}: {count}处")

    if total == 0:
        print(f"  ✓ 零AI腔")
        return True, []
    elif total <= 2:
        print(f"  ✓ 通过 ({total}处轻微)")
        return True, list(k for k,v in checks.items() if v>0)
    else:
        print(f"  ⛔ 不通过 ({total}处) — 需重写可疑段落")
        return False, list(k for k,v in checks.items() if v>0)


# ============================================================
# STEP 8: INGEST — 自动化入库
# ============================================================
def ingest(chapter_no, chapter_type="normal"):
    """自动化后处理：入库+版本+切片+摘要+日志"""
    conn = connect(); cur = conn.cursor(); nid = _get_novel_id(cur)
    ts = now()

    candidates = list(CHAPTERS_DIR.glob(f"第{chapter_no}章*.txt"))
    if not candidates:
        print(f"⛔ 找不到第{chapter_no}章TXT"); conn.close(); return None
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

    # --- novels ---
    cur.execute("UPDATE novels SET current_words=(SELECT COALESCE(SUM(word_count),0) FROM chapters WHERE novel_id=1), updated_at=? WHERE id=1", (ts,))

    # --- log ---
    cur.execute("INSERT INTO novel_logs(action,target_type,target_id,detail) VALUES('ingest','chapter',?,?)",
        (ch_id, f"第{chapter_no}章入库:{wc}字,v{vno},{len(chunks)}切片"))

    conn.commit()
    cur.execute("SELECT COUNT(*),COALESCE(SUM(word_count),0) FROM chapters WHERE novel_id=1")
    total_ch, total_wc = cur.fetchone()
    conn.close()

    print(f"\n{'='*50}\nSTEP 8: INGEST 入库\n{'='*50}")
    print(f"  章节: {wc}字 v{vno} | 切片: {len(chunks)} | 全书: {total_ch}章 {total_wc:,}字 ✓")
    return {"ch_id": ch_id, "word_count": wc, "version": vno, "chunks": len(chunks)}


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
        mark = " ✓" if r['word_count'] >= 3300 else " ⚠"
        total += r['word_count']; print(f"  第{r['chapter_no']}章: {r['word_count']}字{mark}")
    print(f"  合计: {total}字 | 均: {total//3}字")
    conn.close()


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    ensure_tables()

    if len(sys.argv) < 3:
        print("用法: python chapter_pipeline.py pre|post|review <chapter_no> [--type normal|climax|final|short]")
        sys.exit(1)

    action = sys.argv[1]
    chapter_no = int(sys.argv[2])

    # 解析 --type
    chapter_type = "normal"
    for i, a in enumerate(sys.argv):
        if a == "--type" and i+1 < len(sys.argv):
            chapter_type = sys.argv[i+1]

    if action == "pre":
        pre_write_gate(chapter_no, chapter_type)

    elif action == "post":
        candidates = list(CHAPTERS_DIR.glob(f"第{chapter_no}章*.txt"))
        if not candidates:
            print(f"⛔ 找不到第{chapter_no}章TXT"); sys.exit(1)

        # 检查 pre 是否完成（state文件锁）
        state_path = STATE_DIR / f"chapter_{chapter_no:03d}_state.json"
        if not state_path.exists():
            print(f"⛔ pipeline_state缺失: {state_path}")
            print(f"   必须先运行: python chapter_pipeline.py pre {chapter_no}")
            sys.exit(1)
        import json
        state = json.loads(state_path.read_text(encoding='utf-8'))
        if not state.get("allowed_to_write"):
            print(f"⛔ pre未完成，禁止post")
            sys.exit(1)
        print(f"✓ pipeline_state验证通过 (pre完成于{state.get('timestamp','?')})")

        with open(candidates[0], 'r', encoding='utf-8') as f:
            content = _strip_selfcheck(f.read())

        # STEP 4: word_count
        wc_pass, wc = word_count_gate(content, chapter_no, chapter_type)
        if wc_pass == False:
            print(f"\n⛔ 字数门禁失败。需补{WORD_RULES[chapter_type]['fail']-wc}字+。")
            sys.exit(1)
        if wc_pass == "patch_suspect":
            print(f"\n⛔ 疑似patch凑数 — 必须重铺缺失场景，而非继续patch。回到task_card找缺失场景。")
            sys.exit(1)

        # STEP 5: continuity
        continuity_gate(chapter_no, content)

        # STEP 6: scene
        scene_ok, scene_issues = scene_quality_gate(content)
        if wc_pass == "yellow" and not scene_ok:
            print(f"\n⛔ 黄灯+场景不足 → 必须扩写")
            sys.exit(1)

        # STEP 7: anti_ai
        ai_ok, ai_issues = anti_ai_style_gate(content)
        if not ai_ok:
            print(f"\n⛔ 反AI腔不通过: {ai_issues}")
            sys.exit(1)

        # STEP 8: ingest
        result = ingest(chapter_no, chapter_type)
        if not result:
            sys.exit(1)

        # 3章复盘
        stage_review(chapter_no)

        print(f"\n{'='*60}")
        print(f"第{chapter_no}章全部门禁通过 ✓  {wc}字 v{result['version']}")
        print(f"{'='*60}")

    elif action == "review":
        stage_review(chapter_no)
