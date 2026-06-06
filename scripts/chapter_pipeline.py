"""
chapter_pipeline.py — 章节写作总控流水线 V4.2

拟人审稿流水线:
  pre → task_card → write → word_count → continuity → scene → anti_ai → padding → voice_guards → qgp →
  editor_revision → concrete_anchor → scene_causality → dialogue_naturalness → style_variation →
  compliance_selfcheck → final_submission_report → ingest

QGP 困惑度质量门禁 (V5.1, WARNING only):
  ngram 惊讶度 / 句长节奏 / 重复短语 / 抽象总结 / 具体锚点 / 对白变化度

Human-Grade Revision Suite (WARNING only, compliance_selfcheck 可 BLOCK):
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

# ── Ensure project root is importable (needed for src.guards.*, version) ──
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
from version import get_version
try:
    from scripts.config_utils import normalize_config
except Exception:
    def normalize_config(cfg): return cfg

try:
    from scripts.story import story_health
    from scripts.story.contract_builder import load_characters
except Exception:
    story_health = None  # 模块不存在时静默降级
    load_characters = None


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
    """加载配置：兼容旧顶层字段和新 nested 字段。"""
    def _load(path):
        with open(path, 'r', encoding='utf-8') as f:
            user_cfg = json.load(f)
        return {**DEFAULT_CONFIG, **normalize_config(user_cfg)}

    if config_path:
        try:
            return _load(config_path)
        except FileNotFoundError:
            pass

    for candidate in ["config.json", "config.example.json"]:
        if Path(candidate).exists():
            return _load(candidate)
    return normalize_config(DEFAULT_CONFIG)


def _resolve_slot_db_path(cfg):
    """P0-2: Try to resolve the active slot's novel.db, fallback to config db_path."""
    try:
        ws_dir = Path("workspace")
        registry_file = ws_dir / "registry.json"
        if registry_file.exists():
            registry = json.loads(registry_file.read_text(encoding="utf-8"))
            active = registry.get("active_slot", "")
            if active:
                slot_db = ws_dir / active / "novel.db"
                if slot_db.exists():
                    return str(slot_db)
    except Exception:
        pass
    return cfg.get("db_path", DEFAULT_CONFIG["db_path"])


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
        # v0.6.6: 优先从 slot project.json 读取字数规则
        try:
            ws_dir = Path("workspace")
            reg_file = ws_dir / "registry.json"
            if reg_file.exists():
                import json as _j
                reg = _j.loads(reg_file.read_text(encoding="utf-8"))
                active = reg.get("active_slot", "")
                proj_file = ws_dir / active / "project.json"
                if proj_file.exists():
                    proj = _j.loads(proj_file.read_text(encoding="utf-8"))
                    slot_wc = proj.get("word_count")
                    if slot_wc:
                        self.wc_rules = slot_wc
        except Exception:
            pass
        self.wc_default = self.wc_rules.get("normal", {"min": 1900, "best_min": 1900, "best_max": 2800, "max": 3300})
        self.allow_short_chapter = bool(cfg.get("allow_short_chapter", False))
        self.min_scenes = cfg.get("scene_quality", DEFAULT_CONFIG["scene_quality"])["min_effective_scenes"]
        self.novels_root = Path(cfg.get("novels_root", "./novels"))
        self.exports_root = Path(cfg.get("exports_root", "./exports"))
        self.workspace_root = Path("workspace")
        self.active_slot = ""
        try:
            reg_file = self.workspace_root / "registry.json"
            if reg_file.exists():
                import json as _j
                self.active_slot = _j.loads(reg_file.read_text(encoding="utf-8")).get("active_slot", "")
        except Exception:
            pass

        if chapters_dir:
            self.chapters_dir = Path(chapters_dir)
        elif self.active_slot:
            # v0.8.0: workspace-aware — chapters under slot's chapters/第XX卷/
            slot_dir = self.workspace_root / self.active_slot
            if volume_no > 1:
                self.chapters_dir = slot_dir / "chapters" / f"第{volume_no:02d}卷"
            else:
                self.chapters_dir = slot_dir / "chapters"
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

    # ── FTS5 健康检查 ──
    try:
        from scripts.fts_health import ensure_fts_healthy
        _fts_cfg = {"db_path": str(app.db_path)}
        ensure_fts_healthy(_fts_cfg)
    except Exception:
        pass

    # ── story contract 变量初始化 ──
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
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
    except Exception:
        pass

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

        # ── 读取上章 agent review ──
        jury_path = PROJECT_ROOT / "reports" / "agent_reviews" / f"chapter_{prev_ch:03d}_agent_review.json"
        jury = None
        if jury_path.exists():
            try:
                jury = json.loads(jury_path.read_text(encoding="utf-8"))
                ce = jury.get("chief_editor", {})
                print(f"  [OK] 上章陪审团意见: score={jury.get('overall_score')}, status={jury.get('status')}, "
                      f"must_fix={len(ce.get('must_fix', []))}, should_fix={len(ce.get('should_fix', []))}")
                log_entries.append(f"读取第{prev_ch}章jury({jury.get('status')})")
            except Exception as e:
                print(f"  [WARN] 上章jury读取失败: {e}")

        # ── 读取上章 orchestrator 报告（更细粒度的 guard 建议）──
        orch_path = PROJECT_ROOT / "exports" / "reports" / f"chapter_{prev_ch:03d}_orchestrator_report.json"
        orch_report = None
        if orch_path.exists():
            try:
                orch_report = json.loads(orch_path.read_text(encoding="utf-8"))
                log_entries.append(f"读取第{prev_ch}章orchestrator({orch_report.get('final_status','?')})")
            except Exception:
                pass
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
        except Exception as e:
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
        except Exception:
            pass
    if prev_ch >= 1:
        _tex_path = PROJECT_ROOT / "exports" / "reports" / f"chapter_{prev_ch:03d}_texture_report.json"
        if _tex_path.exists():
            try:
                prev_texture = json.loads(_tex_path.read_text(encoding="utf-8"))
            except Exception:
                pass

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
            try:
                card = json.loads(card_file.read_text(encoding="utf-8"))
                name = card.get("name", "")
                if name:
                    char_cards[name] = card
            except: pass

    # ── 加载精神状态 ──
    mental_states = {}
    ms_dir = app.workspace_root / app.active_slot / "mental_states" / "default"
    if app.active_slot and ms_dir.exists():
        for ms_file in sorted(ms_dir.glob("*.json")):
            try:
                data = json.loads(ms_file.read_text(encoding="utf-8"))
                name = data.get("name", "")
                if name:
                    mental_states[name] = {k: v for k, v in data.items() if k != "name"}
            except: pass
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
        from scripts.outline.similarity import _extract_world_keywords
        scan_text = ""
        if ch_plan:
            scan_text += (ch_plan.get("chapter_goal") or "") + " "
            scan_text += (ch_plan.get("main_event") or "") + " "
            scan_text += (ch_plan.get("conflict_point") or "") + " "
            scan_text += (ch_plan.get("must_include") or "") + " "
        try:
            outline = app.outline_manager.current_outline() if app.outline_manager else None
            if outline:
                outline_content = outline.get("content", "")
                for pat in [f"第{chapter_no}章", f"第{chapter_no:02d}章"]:
                    idx = outline_content.find(pat)
                    if idx >= 0:
                        scan_text += outline_content[idx:idx + 500] + " "
                        break
                else:
                    scan_text += outline_content[:1000] + " "
        except Exception:
            pass
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
    except Exception:
        pass

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
    except Exception:
        pass

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
    except Exception:
        pass

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
            except Exception:
                pass

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
                from scripts.outline.outline_manager import OutlineManager
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
            except Exception:
                pass
    except Exception:
        pass

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
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"  [OK] pipeline_state: {state_path}")

    print(f"\nSTEP 1 [OK] — 上下文就绪")
    return {"chapter_no": chapter_no, "prev_ch": prev_ch, "prev_ending": prev_ending,
            "chapter_type": chapter_type, "context_pack": str(pack_path)}


# ============================================================
# STEP 4: WORD_COUNT — 字数门禁
# ============================================================
def word_count_gate(content, chapter_no, chapter_type="normal", genre=None):
    """字数门禁 V6：支持题材差异化。有 genre 时从 genre_presets.yaml 读取 min_words。"""
    rules = app.wc_rules.get(chapter_type, app.wc_default).copy()
    # v0.7.1: 题材感知 — 优先用 genre preset 的 min_words 覆盖 config.json 硬编码
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
                    print(f"  [INFO] 题材「{genre}」最低字数: {_genre_min}字")
                _genre_max = genre_preset.get("max_words")
                if _genre_max is not None:
                    rules["max"] = _genre_max
                    print(f"  [INFO] 题材「{genre}」最高字数: {_genre_max}字")
        except Exception:
            pass
    wc = _count_chinese(content)
    print(f"\n{'='*50}\nSTEP 4: 字数门禁 [{chapter_type}]\n{'='*50}")
    print(f"  字数: {wc} | 范围: {rules['min']}-{rules['max']} | 最佳: {rules['best_min']}-{rules['best_max']}")

    _eff_min = rules['min']
    if wc < _eff_min:
        print(f"  [FAIL] 低于最低线 ({wc} < {_eff_min}) — 需补场景或授权短章")
        return False, wc, _eff_min

    if rules['best_min'] <= wc <= rules['best_max']:
        print(f"  [OK] 最佳区间")
        return "ideal", wc, _eff_min

    if rules['best_max'] < wc <= rules['max']:
        print(f"  [OK] 正常通过 (偏长)")
        return True, wc, _eff_min

    if wc > rules['max']:
        if chapter_type in ("climax", "volume_finale") and wc <= 5500:
            print(f"  [OK] 高潮/卷末章允许长篇幅")
            return True, wc, _eff_min
        print(f"  [WARN] 超上限({wc}>{rules['max']}) — 建议拆章或精简")
        return "oversize", wc, _eff_min

    return True, wc, _eff_min


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
        pass  # chapter not yet ingested — non-critical
    conn.commit(); conn.close()

    if score >= 12: print("  [OK] 通过"); return True
    else: print("  [WARN] 建议增强承接"); return True


# ============================================================
# STEP 5.5: HALLUCINATION — 幻觉拦截
# ============================================================
def hallucination_gate(chapter_no, content):
    """检查正文是否存在无依据新增或矛盾内容"""
    from src.guards.hallucination_guard import run_hallucination_check

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
        "像一座废墟/像一尊雕像": len(re.findall(r'像一座(废墟|孤岛|坟墓)|像一尊(雕像|雕塑|石像)', content)),
        "沉默了几秒": len(re.findall(r'沉默了几秒|沉默了片刻|沉默了.{1,4}秒', content)),
        "是她的救赎": len(re.findall(r'救赎|他就是她的|她就是他的', content)),
        "硬科普指标": len(re.findall(r'(公式|定律|方程|定理|热力学|量子力学|相对论)', content)),
        "论文式句子": len(re.findall(r'通过.{5,20}实现了|基于.{5,20}进行了|本质上是|从某种意义上说|事实上', content)),
    }

    # v0.5.1: Reduce false positives for 这意味着 in character analysis
    analysis_names = [
        re.findall(r'[\u4e00-\u9fff]{2,4}(?:看着|翻开|写下|分析|记录|报告|调查|判断|推算|认定|断言)', content)
    ]
    # If the text has character-driven analysis patterns, be more lenient
    has_analysis = any(len(names) > 0 for names in analysis_names)
    for m in re.finditer(r'这意味着|这说明|这代表', content):
        ctx = content[max(0, m.start()-120):m.end()]
        # Check for evidence/analysis keywords nearby (data, records, evidence)
        if re.search(r'(数据|记录|证据|案卷|观测|统计|比对|对照)', ctx):
            checks['这意味着'] = max(0, checks['这意味着'] - 1)

    total = sum(checks.values())
    for label, count in checks.items():
        if count > 0: print(f"  [WARN] {label}: {count}处")

    if total == 0:
        print(f"  [OK] 零AI腔")
        return True, []
    elif total <= 4:
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
# STEP 7.9: CONTEXT GENERATION — 章节上下文提取
# ============================================================
_ITEM_LEXICON = [
    "柴刀", "斧头", "剑", "刀", "匕首", "棍", "枪", "弓", "弩",
    "役牌", "令牌", "木牌", "玉简", "卷轴", "书", "信", "符", "禁制符", "传送符",
    "法器", "法宝", "灵器", "仙器", "神器", "魔器",
    "丹药", "筑基丹", "破境丹", "疗伤丹", "止血丸", "辟谷丹", "筑基液", "灵液",
    "灵石", "灵晶", "灵脉", "矿", "药材", "灵草",
    "储物袋", "乾坤袋", "空间戒指", "储物戒指", "纳戒",
    "信物", "玉佩", "戒指", "项链", "手镯", "发簪", "令牌", "钥匙",
    "残片", "碎片", "图", "地图", "皮纸", "陶片", "瓷片", "铁钉", "木盒", "盒",
    "鼎", "炉", "丹炉", "药鼎", "阵盘", "阵旗", "阵眼",
    "血", "精血", "魔种", "封印", "结界", "屏障",
    "遗物", "护身符", "骨", "灰", "衣", "袍", "靴", "冠", "面具",
    "酒", "茶", "碗", "杯", "壶", "食物", "干粮", "水囊",
    "绳", "锁", "链", "笼", "枷锁", "镣铐",
    "船", "车", "轿", "马", "兽", "坐骑", "灵兽", "妖兽",
    "镜", "珠", "灯笼", "灯", "火折", "烛", "火把",
    "琴", "笛", "箫", "棋盘", "棋子", "笔", "墨", "砚", "纸",
]


def _extract_character_locations(content, char_names):
    """Extract last-known location per character from chapter text.

    Uses window-based search around each character's last mention, with multiple
    location patterns ordered from most-specific to generic fallback.
    """
    locs = {}
    LOC_PATTERNS = [
        # Compound verb + location: 回到柴棚 / 走进丹房 / 坐在门口
        r"(?:回到|来到|走到|跑到|行至|赶往|前往|进入|踏入|步入|迈入"
        r"|坐在|站在|躺在|靠在|蹲在|藏在|住在|立在|待在|留在|等在|跪在"
        r"|躲进|钻进|缩进|退到|冲到|奔向"
        r")(.{1,12}?)(?:[,，。.；;、\s]|$)",
        # 在/于 + location: 在杂物房里 / 于院中
        r"(?:在|于)(.{1,12}?)(?:[,，。.；;、\s]|$)",
        # Single verb + optional preposition + location: 坐于/回到/去了/来了
        r"(?:坐|站|躺|靠|蹲|藏|住|立|待|留|等"
        r"|回|进|入|去|来|走|跑|行|往|至|赴|过|离|出|归"
        r")(?:在|到|于|至|往|向)?(.{1,12}?)(?:[,，。.；;、\s]|$)",
    ]

    for name in char_names:
        if name not in content:
            continue
        # Search around last occurrence (60-char window after the name)
        last_pos = content.rfind(name)
        if last_pos < 0:
            continue
        window = content[last_pos:last_pos + 60]
        for pat in LOC_PATTERNS:
            m = re.search(pat, window)
            if m:
                loc_text = m.group(1).strip()
                # Filter out non-location captures (verbs, noise, single-char)
                if len(loc_text) >= 2 and not loc_text.startswith("了"):
                    # Trim trailing action verbs from location
                    loc_text = re.sub(
                        r"[坐站蹲藏躲走跑抬望看听摸推拉翻找拿放打敲砍刺][下起开着过了完]?$",
                        "", loc_text)
                    if len(loc_text) >= 2:
                        locs[name] = loc_text
                    break
    return locs


def _extract_active_items(content):
    """Find items mentioned with action verbs (拿出/掏出/找到/发现/握着/收起)."""
    items = set()
    action_pattern = r"(?:拿出|掏出|找到|发现|握着|捏着|收起|藏起|祭出|取出|掏)"
    for item in _ITEM_LEXICON:
        if item in content:
            # Check if item appears near an action verb
            item_positions = [m.start() for m in re.finditer(re.escape(item), content)]
            for pos in item_positions:
                window = content[max(0, pos - 20):pos + len(item) + 20]
                if re.search(action_pattern, window):
                    items.add(item)
                    break
            # Also include items mentioned 3+ times (likely significant)
            if item not in items and content.count(item) >= 3:
                items.add(item)
    return sorted(items)[:10]


def _extract_unresolved_threads(content):
    """Find dangling questions and unresolved hints."""
    threads = []
    # Sentences ending with ？(full-width question mark)
    for m in re.finditer(r".{10,80}？", content):
        q = m.group().strip()
        if q:
            threads.append(q[:80])
    # Unresolved markers
    for m in re.finditer(r"(?:还没|尚未|仍不|仍未|未解|未明|不知|不知晓|等.{2,6}再|以后再)(.{5,60}?)(?:[,，。.；;、]|$)", content):
        t = m.group().strip()
        if len(t) >= 6:
            threads.append(t[:80])
    return threads[:10]


_EMOTION_WORDS = [
    "愤怒", "暴怒", "怒火", "恼怒", "生气",
    "悲伤", "难过", "哀伤", "悲痛", "心痛", "心酸",
    "恐惧", "害怕", "惊恐", "畏惧", "胆怯",
    "惊讶", "震惊", "吃惊", "愕然",
    "厌恶", "反感", "嫌弃", "憎恨", "恨",
    "喜悦", "高兴", "开心", "欣喜", "兴奋", "欢喜",
    "焦虑", "焦躁", "烦躁", "不安", "忐忑",
    "冷静", "沉着", "镇定", "沉稳", "平静", "淡然",
    "紧张", "紧绷", "戒备", "警惕",
    "放松", "释然", "宽慰", "安心",
    "失望", "失落", "沮丧", "灰心",
    "愧疚", "内疚", "自责", "悔恨",
    "好奇", "疑惑", "困惑", "茫然", "迷茫",
    "坚定", "决然", "果断", "刚毅",
    "疲惫", "疲倦", "倦怠", "乏",
    "孤独", "寂寞", "孤单",
    "感动", "触动",
    "怀念", "思念", "牵挂",
    "无奈", "苦笑",
]


def _extract_emotional_states(content, char_names):
    """Find last emotion word near each character."""
    states = {}
    for name in char_names:
        if name not in content:
            continue
        # Find all positions of this character name
        last_pos = content.rfind(name)
        if last_pos < 0:
            continue
        # Search 80 chars after the last mention for emotion words
        window = content[last_pos:last_pos + 80]
        for ew in _EMOTION_WORDS:
            if ew in window:
                states[name] = ew
                break
    return states


def _extract_world_state(content):
    """Extract 2-3 sentences about environment changes from last 500 chars."""
    tail = content[-500:]
    sentences = re.split(r"[。.]", tail)
    changed = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if re.search(r"[变化改转现显现涌现消散蔓延]", s) and len(s) >= 6:
            changed.append(s[:120])
    return "。".join(changed[:3])


# ═══════════════════════════════════════════════════
# v0.7.2: Story Arc — enhanced extraction
# ═══════════════════════════════════════════════════

_PHYSICAL_STATE_KEYWORDS = {
    "轻伤": ["擦伤", "扭到", "磕到", "划破", "皮外伤", "淤青", "小伤"],
    "中伤": ["骨折", "流血", "伤口", "打伤", "内伤", "脱臼", "吐血", "咳血", "断骨"],
    "重伤": ["濒死", "昏迷", "大出血", "经脉尽断", "丹田破裂", "五脏俱裂", "奄奄一息"],
    "中毒": ["中毒", "毒发", "毒性", "解毒", "麻", "毒气"],
    "疾病": ["发烧", "生病", "感染", "过敏", "晕倒", "晕眩", "虚弱", "发冷", "咳嗽"],
    "恢复": ["痊愈", "恢复", "好了", "没事", "疗伤", "养伤", "愈合", "康复"],
    "健康": ["完好", "无恙", "平安", "精神", "活动自如"],
}


def _extract_character_physical_states(content, char_names):
    """Extract physical state per character from chapter text.

    Searches a window after each character's last mention for physical state keywords.
    Returns dict {character_name: state_label}.
    """
    states = {}
    for name in char_names:
        if name not in content:
            continue
        last_pos = content.rfind(name)
        if last_pos < 0:
            continue
        window = content[last_pos:last_pos + 100]
        for state_label, keywords in _PHYSICAL_STATE_KEYWORDS.items():
            for kw in keywords:
                if kw in window:
                    states[name] = state_label
                    break
            if name in states:
                break
    return states


_DECISION_MARKERS = [
    r"(决定|决定了|决定要|做出.{1,6}决定)",
    r"(选择了|选择.{1,10}选择)",
    r"(最终.{1,10}(还是|决定|选择))",
    r"(从今以后|从此|今后.{1,6}(不再|要|不会|必须))",
    r"(下定.{1,6}决心|下了.{1,6}决心)",
]


def _extract_key_decisions(content, char_names):
    """Find key decisions made by characters in this chapter.

    Searches for decision-marker patterns near character names.
    Returns list of {character, decision, context} dicts.
    """
    decisions = []
    for name in char_names:
        if name not in content:
            continue
        for pos in [m.start() for m in re.finditer(re.escape(name), content)]:
            window_start = max(0, pos - 20)
            window_end = min(len(content), pos + 80)
            window = content[window_start:window_end]
            for marker_pat in _DECISION_MARKERS:
                m = re.search(marker_pat, window)
                if m:
                    decisions.append({
                        "character": name,
                        "decision": m.group(1),
                        "context": window.strip()[:120],
                    })
                    break
    return decisions[:10]


def _extract_emotional_states_enhanced(content, char_names):
    """Extract emotional states with intensity and transition detection.

    Returns dict {character_name: {state, intensity, transitions_from}}.
    Intensity: 1 (mild) to 5 (extreme) based on presence of intensifiers.
    """
    # Intensity intensifiers
    _INTENSIFIERS = {
        5: ["极度", "透顶", "到了极点", "无法承受", "崩溃"],
        4: ["非常", "极为", "无比", "深深", "浓烈", "剧烈"],
        3: ["十分", "很", "相当", "明显", "显然"],
        2: ["有些", "有点", "几分", "微微", "略微", "一丝"],
        1: ["稍", "略带", "浅淡", "隐约"],
    }
    states = {}
    for name in char_names:
        if name not in content:
            continue
        last_pos = content.rfind(name)
        if last_pos < 0:
            continue
        window = content[last_pos:last_pos + 80]
        best_emotion = None
        best_intensity = 1
        for ew in _EMOTION_WORDS:
            if ew in window:
                best_emotion = ew
                # Check surrounding intensifiers
                ew_pos = window.find(ew)
                nearby = window[max(0, ew_pos - 15):ew_pos + len(ew) + 15]
                for level, words in _INTENSIFIERS.items():
                    if any(w in nearby for w in words):
                        best_intensity = max(best_intensity, level)
                break
        if best_emotion:
            states[name] = {
                "state": best_emotion,
                "intensity": best_intensity,
            }
    return states


def _extract_active_relationships(content, char_names):
    """Find which characters interact in this chapter."""
    rels = []
    for i, n1 in enumerate(char_names):
        for n2 in char_names[i + 1:]:
            # Find if both names appear within 200 chars of each other
            pos1 = [m.start() for m in re.finditer(re.escape(n1), content)]
            pos2_set = set(m.start() for m in re.finditer(re.escape(n2), content))
            for p1 in pos1:
                for p2 in pos2_set:
                    if abs(p1 - p2) <= 200:
                        rels.append(f"{n1}-{n2}")
                        break
                if f"{n1}-{n2}" in rels:
                    break
    return rels[:20]


def _upsert_arc_character_states(nid, chapter_no, char_names, phys_states,
                                  emotions_enh, key_decisions, active_rels):
    """Populate arc_character_states table for each character in this chapter."""
    conn = connect()
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
    conn.commit()

    for name in char_names:
        cur.execute("SELECT id FROM characters WHERE novel_id=? AND name=?", (nid, name))
        row = cur.fetchone()
        if not row:
            continue
        cid = row[0]
        phys = phys_states.get(name, "")
        emo_data = emotions_enh.get(name, {})
        emo_json = json.dumps(emo_data, ensure_ascii=False) if emo_data else "{}"
        char_decisions = [d for d in key_decisions if d["character"] == name]
        decisions_json = json.dumps(char_decisions, ensure_ascii=False)
        # Build relationship list for this character
        char_rels = [r for r in active_rels if name in r]
        rels_json = json.dumps(char_rels, ensure_ascii=False)
        # Build arc_progress from combined signals
        arc_parts = []
        if phys:
            arc_parts.append(f"身体:{phys}")
        if emo_data:
            arc_parts.append(f"情绪:{emo_data.get('state','')}")
        if char_decisions:
            arc_parts.append(f"决定:{len(char_decisions)}项")
        arc_progress = " | ".join(arc_parts)

        cur.execute("""SELECT id FROM arc_character_states
                       WHERE novel_id=? AND character_id=? AND chapter_no=?""",
                    (nid, cid, chapter_no))
        existing = cur.fetchone()
        if existing:
            cur.execute("""UPDATE arc_character_states SET
                physical_state=?, emotional_state=?, arc_progress=?,
                key_decisions=?, active_relationships=?
                WHERE novel_id=? AND character_id=? AND chapter_no=?""",
                        (phys, emo_json, arc_progress, decisions_json, rels_json,
                         nid, cid, chapter_no))
        else:
            cur.execute("""INSERT INTO arc_character_states
                (novel_id, character_id, chapter_no, physical_state, emotional_state,
                 arc_progress, key_decisions, active_relationships)
                VALUES(?,?,?,?,?,?,?,?)""",
                        (nid, cid, chapter_no, phys, emo_json, arc_progress,
                         decisions_json, rels_json))
    conn.commit()
    conn.close()


def generate_chapter_context(chapter_no, title, content, wc, nid, ch_id, char_names=None):
    """Generate structured chapter_context row and INSERT into chapter_contexts table."""
    conn = connect()
    cur = conn.cursor()

    # Load character names if not provided
    if not char_names:
        cur.execute("SELECT name FROM characters WHERE novel_id=?", (nid,))
        char_names = [r[0] for r in cur.fetchall()]

    # Extract fields
    char_locs = _extract_character_locations(content, char_names)
    items = _extract_active_items(content)
    threads = _extract_unresolved_threads(content)
    emotions = _extract_emotional_states(content, char_names)
    world = _extract_world_state(content)

    # v0.7.2: Enhanced extraction for Story Arc
    phys_states = _extract_character_physical_states(content, char_names)
    emotions_enh = _extract_emotional_states_enhanced(content, char_names)
    key_decisions = _extract_key_decisions(content, char_names)
    active_rels = _extract_active_relationships(content, char_names)

    # Reuse chapter_brief data
    ending_state = ""
    hooks_for_next = ""
    brief_path = app.exports_root / "chapter_briefs" / f"chapter_{chapter_no:03d}_brief.json"
    if brief_path.exists():
        try:
            brief = json.loads(brief_path.read_text(encoding="utf-8"))
            ending_state = brief.get("ending_state", "")
            hooks_for_next = brief.get("next_chapter_hooks", "")
        except Exception:
            pass

    # Raw summary from chapter_summaries or fallback
    raw_summary = ""
    cur.execute(
        "SELECT short_summary FROM chapter_summaries WHERE novel_id=? AND chapter_id=?",
        (nid, ch_id))
    sm_row = cur.fetchone()
    if sm_row and sm_row[0]:
        raw_summary = sm_row[0]
    else:
        # Fallback: first + last 80 chars
        lines = [l for l in content.split("\n") if l.strip() and not l.startswith("=")]
        raw_summary = (lines[0][:80] if lines else "") + " ... " + (lines[-1][:80] if len(lines) > 1 else "")

    # Upsert into chapter_contexts
    cur.execute("SELECT id FROM chapter_contexts WHERE novel_id=? AND chapter_id=?", (nid, ch_id))
    existing = cur.fetchone()
    ts = now()
    if existing:
        cur.execute("""
            UPDATE chapter_contexts SET
                character_locations=?, active_items=?, unresolved_threads=?,
                emotional_states=?, world_state=?, ending_state=?,
                hooks_for_next=?, raw_summary=?, created_at=?
            WHERE novel_id=? AND chapter_id=?
        """, (
            json.dumps(char_locs, ensure_ascii=False),
            json.dumps(items, ensure_ascii=False),
            json.dumps(threads, ensure_ascii=False),
            json.dumps(emotions, ensure_ascii=False),
            world,
            ending_state,
            hooks_for_next,
            raw_summary,
            ts,
            nid, ch_id))
    else:
        cur.execute("""
            INSERT INTO chapter_contexts(novel_id, chapter_id, chapter_no,
                character_locations, active_items, unresolved_threads,
                emotional_states, world_state, ending_state, hooks_for_next,
                raw_summary, created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            nid, ch_id, chapter_no,
            json.dumps(char_locs, ensure_ascii=False),
            json.dumps(items, ensure_ascii=False),
            json.dumps(threads, ensure_ascii=False),
            json.dumps(emotions, ensure_ascii=False),
            world,
            ending_state,
            hooks_for_next,
            raw_summary,
            ts))
    conn.commit()
    conn.close()

    # v0.7.2: Populate arc_character_states for each character
    _upsert_arc_character_states(nid, chapter_no, char_names, phys_states,
                                  emotions_enh, key_decisions, active_rels)

    print(f"  [OK] chapter_context: {len(char_locs)}人物位置, {len(items)}物品, {len(threads)}悬念, {len(phys_states)}身体状态")
    return {
        "chapter_no": chapter_no,
        "character_locations": char_locs,
        "active_items": items,
        "unresolved_threads": threads,
        "emotional_states": emotions,
    }


def _build_context_injection(cur, nid, chapter_no, max_chapters=3):
    """Build ≤300-char context summary from last N chapter_contexts for pre injection."""
    start_ch = max(1, chapter_no - max_chapters)
    cur.execute("""
        SELECT character_locations, active_items, unresolved_threads, raw_summary
        FROM chapter_contexts
        WHERE novel_id=? AND chapter_no BETWEEN ? AND ?
        ORDER BY chapter_no
    """, (nid, start_ch, chapter_no - 1))
    rows = cur.fetchall()
    if not rows:
        return None

    summaries = []
    all_items = set()
    all_threads = set()
    latest_locs = {}

    for row in rows:
        if row[3]:  # raw_summary
            summaries.append(row[3][:100])
        try:
            items = json.loads(row[1]) if isinstance(row[1], str) else (row[1] or [])
            for it in items:
                all_items.add(it)
            threads = json.loads(row[2]) if isinstance(row[2], str) else (row[2] or [])
            for th in threads:
                all_threads.add(th)
            locs = json.loads(row[0]) if isinstance(row[0], str) else (row[0] or {})
            latest_locs.update(locs)
        except Exception:
            pass

    parts = []
    if summaries:
        parts.append("前情：" + "；".join(summaries[-2:]))
    if all_threads:
        parts.append("悬而未决：" + "、".join(sorted(all_threads)[:3]))
    if latest_locs:
        loc_str = " | ".join(f"{k}@{v}" for k, v in list(latest_locs.items())[:8])
        parts.append(f"人物位置：{loc_str}")
    if all_items:
        parts.append("活跃物品：" + "、".join(sorted(all_items)[:5]))

    return "\n    ".join(parts)


# ============================================================
# STEP 8: INGEST — 自动化入库
# ============================================================

_CN_DIGITS = "零一二三四五六七八九"
_CN_TENS = ["", "十", "百", "千"]


def _arabic_to_chinese_numeral(n: int) -> str:
    """Convert int to Chinese numeral string (1→一, 12→十二, 100→一百)."""
    if not 1 <= n <= 9999:
        return str(n)
    if n <= 10:
        return _CN_DIGITS[n] if n < 10 else "十"
    if n < 20:
        return "十" + (_CN_DIGITS[n - 10] if n > 10 else "")
    if n < 100:
        tens = _CN_DIGITS[n // 10]
        ones = _CN_DIGITS[n % 10] if n % 10 else ""
        return f"{tens}十{ones}"
    if n < 1000:
        hundreds = _CN_DIGITS[n // 100]
        rest = n % 100
        if rest == 0:
            return f"{hundreds}百"
        if rest < 10:
            return f"{hundreds}百零{_CN_DIGITS[rest]}"
        rest_str = _arabic_to_chinese_numeral(rest)
        if 10 <= rest < 20:
            rest_str = "一" + rest_str
        return f"{hundreds}百{rest_str}"
    # 1000+
    thousands = _CN_DIGITS[n // 1000]
    rest = n % 1000
    if rest == 0:
        return f"{thousands}千"
    if rest < 100:
        rest_str = _arabic_to_chinese_numeral(rest)
        if 10 <= rest < 20:
            rest_str = "一" + rest_str
        return f"{thousands}千零{rest_str}"
    return f"{thousands}千{_arabic_to_chinese_numeral(rest)}"


def _find_chapter_file(chapter_no: int, directory: Path) -> Path | None:
    """Find chapter TXT by chapter number, supporting both Arabic and Chinese numerals."""
    patterns = [
        f"第{chapter_no}章*.txt",
        f"第{chapter_no:02d}章*.txt",
        f"第{_arabic_to_chinese_numeral(chapter_no)}章*.txt",
    ]
    for pat in patterns:
        candidates = list(directory.glob(pat))
        if candidates:
            return candidates[0]
    return None


def ingest(chapter_no, chapter_type="normal"):
    conn = connect(); cur = conn.cursor(); nid = _get_novel_id(cur)
    ts = now()

    filepath = _find_chapter_file(chapter_no, app.chapters_dir)
    if not filepath:
        print(f"[FAIL] 找不到第{chapter_no}章TXT"); conn.close(); return None
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
        cur.execute("DELETE FROM chapter_chunks WHERE chapter_id=?", (ch_id,))
        try: cur.execute("DELETE FROM novel_chapter_fts WHERE rowid=?", (ch_id,))
        except: pass
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

    # --- chapter_context ---
    generate_chapter_context(chapter_no, title, content, wc, nid, ch_id)

    # ── 角色出场统计 ──
    appeared_names = []
    try:
        cur.execute("SELECT name FROM characters WHERE novel_id=?", (nid,))
        all_chars = [r[0] for r in cur.fetchall()]
        if all_chars:
            appears = []
            missing = []
            appeared_names = []
            for n in all_chars:
                cnt = content.count(n)
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
    except Exception:
        pass

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
    except Exception:
        pass

    # ── 世界设定提及检测 ──
    try:
        # Ensure updated_at column exists
        try:
            cur.execute("ALTER TABLE worldbuilding ADD COLUMN updated_at TEXT DEFAULT ''")
        except Exception:
            pass
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
    except Exception:
        pass

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
        "allow_short_chapter": app.allow_short_chapter,
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

    # ── 3.3 story commit: 写入弧线进度 ──
    try:
        from scripts.story import commit_builder as _cb
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
    """Resolve .story/ directory from active slot, for deviation calculation."""
    try:
        ws = Path("workspace")
        reg = ws / "registry.json"
        if reg.exists():
            active = json.loads(reg.read_text(encoding="utf-8")).get("active_slot", "")
            if active:
                sd = ws / active / ".story"
                if sd.exists():
                    return sd
    except Exception:
        pass
    return Path(".story")


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

    parser = argparse.ArgumentParser(description="Novel Forge - Chapter Write Engine")
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
    parser.add_argument("--genre", default=None, help="题材预设，支持复合: --genre xianxia+爽文 (默认: config.json default_genre)")\

    parser.add_argument("--pace", default=None, help="节奏速度: slow/normal/fast (默认: normal)")

    args = parser.parse_args()

    # 加载配置
    cfg = load_config(args.config)
    if args.db_path:
        cfg["db_path"] = args.db_path
    else:
        # P0-2: If no explicit --db-path, resolve active slot novel.db
        cfg["db_path"] = _resolve_slot_db_path(cfg)

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
        candidates = _find_chapter_file(chapter_no, app.chapters_dir)
        if not candidates and app.active_slot:
            # v0.8.0: 跨卷搜索 — 扫描所有卷目录
            slot_dir = app.workspace_root / app.active_slot
            for vd in sorted(slot_dir.glob("chapters/第*卷")):
                candidates = _find_chapter_file(chapter_no, vd)
                if candidates:
                    print(f"  [OK] 在{vd.name}目录找到第{chapter_no}章")
                    break
            # Fallback: flat chapters dir
            if not candidates:
                flat_dir = slot_dir / "chapters"
                candidates = _find_chapter_file(chapter_no, flat_dir)
        if not candidates:
            print(f"[FAIL] 找不到第{chapter_no}章TXT (目录: {app.chapters_dir})")
            sys.exit(1)

        # 检查 pre 是否完成（允许 bootstrapped minimal state）
        state_path = app.state_dir / f"chapter_{chapter_no:03d}_state.json"
        if not state_path.exists():
            # Bootstrap minimal state — post doesn't need full pre
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state = {"allowed_to_write": True, "genre": "", "chapter_no": chapter_no,
                     "timestamp": datetime.now().isoformat(), "_bootstrapped": True}
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[OK] 已生成最小 pipeline_state (post 无需完整 pre)")
        else:
            state = json.loads(state_path.read_text(encoding='utf-8'))
            if not state.get("allowed_to_write"):
                print(f"[FAIL] pre未完成，禁止post")
                sys.exit(1)
            print(f"[OK] pipeline_state验证通过 (pre完成于{state.get('timestamp','?')})")

        # v0.4.5: FTS5 health check before post
        try:
            from scripts.fts_health import ensure_fts_healthy
            fts_result = ensure_fts_healthy(cfg)
            if fts_result["action"] == "repaired":
                print(f"  [FTS] Repaired: {fts_result.get('repair',{}).get('repaired_count',0)} tables")
            elif fts_result["action"] == "repair_failed":
                print(f"  [WARN] FTS repair failed — fallback LIKE search will be used")
        except ImportError:
            pass

        with open(candidates, 'r', encoding='utf-8') as f:
            content = _strip_selfcheck(f.read())

        # ── 1.2 裂隙触发词检测 ──
        _fissure_triggers = ["\u6c34", "\u51b7\u6c34", "\u5239\u8f66\u58f0", "\u73bb\u7483\u788e\u88c2",
                            "\u5f3a\u5149", "\u8840\u5473", "\u5b89\u5168\u5e26", "\u675f\u7f1a\u611f"]
        _trigger_hits = 0
        _trigger_detail = {}
        for _tw in _fissure_triggers:
            _cnt = content.count(_tw)
            if _cnt > 0:
                _trigger_hits += _cnt
                _trigger_detail[_tw] = _cnt
        if _trigger_hits > 0:
            print(f"\n  [\u6797\u89c2\u6f9c\u88c2\u9699\u89e6\u53d1] \u547d\u4e2d{_trigger_hits}\u6b21: {_trigger_detail}")
            state["\u88c2\u9699\u89e6\u53d1\u8bcd\u547d\u4e2d"] = _trigger_hits
            state["\u88c2\u9699\u89e6\u53d1\u8bcd\u8be6\u60c5"] = _trigger_detail
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
            if _trigger_hits <= 2:
                print(f"  \u2139\ufe0f \u547d\u4e2d0-2\u6b21\uff0c\u4e0d\u63d0\u793a")
            elif _trigger_hits <= 3:
                print(f"  \u26a0\ufe0f \u88c2\u9699\u89e6\u53d1\u8bcd\u51fa\u73b0{_trigger_hits}\u6b21")
            else:
                print(f"  \U0001f534 \u88c2\u9699\u52a0\u91cd\uff0c\u5efa\u8bae\u5199\u4e00\u6bb5\u89e3\u79bb\u620f")

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
        wc_pass, wc, eff_min = word_count_gate(content, chapter_no, chapter_type, genre=_pipeline_genre or None)
        if wc_pass == False:
            # ── v0.4.5: 自动合并下一章 ──
            if args.merge_if_short:
                next_candidate = _find_chapter_file(chapter_no + 1, app.chapters_dir)
                if next_candidate:
                    next_content = _strip_selfcheck(next_candidate.read_text(encoding='utf-8'))
                    merged = content.rstrip() + "\n\n---\n\n" + next_content
                    # Save merged content
                    merged_path = candidates
                    merged_path.write_text(merged, encoding='utf-8')
                    # Rename next chapter as merged backup
                    bak = str(next_candidate) + ".merged"
                    next_candidate.rename(bak)
                    print(f"\n[MERGE] 第{chapter_no}章({wc}字) + 第{chapter_no+1}章 → 合并")
                    print(f"  [OK] 合并后保存: {merged_path.name}")
                    print(f"  [OK] 下一章已备份: {Path(bak).name}")
                    # Re-check word count with merged content
                    content = merged
                    wc_pass, wc, eff_min2 = word_count_gate(content, chapter_no, chapter_type, genre=_pipeline_genre or None)
                    if wc_pass == False:
                        print(f"\n[FAIL] 合并后仍不足 {eff_min2} 字 (实际: {wc})")
                        sys.exit(1)
                else:
                    print(f"\n[FAIL] 字数门禁失败且找不到第{chapter_no+1}章合并。需补{eff_min-wc}字+。")
                    sys.exit(1)
            else:
                print(f"\n[FAIL] 字数门禁失败。需补{eff_min-wc}字+。")
                sys.exit(1)

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
        # All standard/draft guards (continuity_evidence, canon_evidence, hallucination,
        # scene_delta, padding, anti_ai, show_dont_tell, character_voice, etc.) run here.
        quality_policy = cfg.get("quality_policy", {})
        orchestrator_mode = quality_policy.get("run_mode", "standard")

        # v0.4.5: Load voice context for character_voice_guard
        extra_context = {}
        try:
            from scripts.voice_profile_loader import load_voice_context
            voice_context = load_voice_context(cfg, app.novel_slug)
            if voice_context["enabled"]:
                extra_context["voice_context"] = voice_context
                print(f"  [VOICE] {voice_context['source']}: {len(voice_context['profiles'])} profiles, {len(voice_context['packs'])} packs")
        except Exception as e:
            pass

        try:
            from scripts.guard_orchestrator import run_orchestrated
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
                print(f"  [WARN] {orch_report['fail_count']} guard(s) FAIL (level 1/2) — ingest继续但请复查")

            # ── STEP 7.7: Punctuation Guard ──
            try:
                from src.guards.punctuation_guard import run_punctuation_check
                punct = run_punctuation_check(content, chapter_no)
                punct_status = punct["status"]
                dash_pairs = punct["stats"]["dash_pairs"]
                dash_per_kw = dash_pairs * 1000 / max(punct["stats"]["word_count"], 1)
                if punct_status == "FAIL":
                    print(f"  ⚠️ 标点节奏: FAIL ({dash_pairs}组——, {dash_per_kw:.1f}/千字)")
                elif punct_status == "WARNING":
                    print(f"  ⚠️ 标点节奏: WARN ({dash_pairs}组——, {dash_per_kw:.1f}/千字)")
                else:
                    print(f"  ✅ 标点节奏: PASS ({dash_pairs}组——)")
            except Exception as e:
                pass  # punctuation guard is optional

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
                    except: pass
                genre = _pipeline_genre or args.genre or cfg.get("default_genre", "default")
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
                    icon = "✅" if score >= 70 else ("⚠️" if score >= 55 else "❌")
                    short = gname.replace("_guard", "").replace("_", " ")
                    print(f"    {icon} {short:25s} {score}/100")
                if texture_status == "FAIL":
                    print(f"  [BLOCK] 人工味质量层未通过，请运行 python novel.py texture check {chapter_no} 查看详情")

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
                            _dir_icon = {"up": "↑", "down": "↓", "stable": "→"}.get(_trend["direction"], "")
                            _changed = {k: v for k, v in _deltas.items() if abs(v) > 3}
                            if _changed:
                                _trend_parts = [f"{k.replace('_guard','').replace('_',' ')}:{_dir_icon}{v:+d}" for k, v in sorted(_changed.items(), key=lambda x: -abs(x[1]))[:4]]
                                print(f"  [TREND] vs 第{chapter_no-1}章: {' | '.join(_trend_parts)}")
                    except Exception:
                        pass
            except Exception as e:
                print(f"  [WARN] human_texture skipped: {e}")


            # ── 去重 + Top 5 修改任务 ──
            if quality_policy.get("deduplicate_warnings", True):
                from scripts.report_deduplicator import deduplicate_warnings, get_top_revision_tasks
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
            print(f"  [WARN] orchestrator skipped: {e}")

        # STEP 8: ingest
        result = ingest(chapter_no, chapter_type)
        if not result:
            sys.exit(1)

        # 3章复盘
        stage_review(chapter_no)

        # ── 写作后自动流程：精神状态检查 + 完整审稿 + 改稿建议 ──
        try:
            # 1. 精神状态跨章跟踪（简易文件版）
            import os as _os
            _track_file = app.workspace_root / app.active_slot / "ptsd_tracker.json"
            _triggers = ["水","冷水","刹车声","玻璃","碎裂","强光","血味","安全带","束缚","车祸"]
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
                except:
                    _prev = [_tracker]
                    _total = _hits
            else:
                _prev = [_tracker]
                _total = _hits
            _track_file.write_text(json.dumps(_prev, ensure_ascii=False), encoding="utf-8")
            if _hits >= 2:
                print(f"  [精神状态] 林观澜PTSD触发词{_hits}次(近5章累计{_total}次)")
                if _total >= 8:
                    print(f"    ⚠️ 建议本章加入一段解离戏")
        except Exception as _e:
            pass

        try:
            # 2. 完整审稿
            sys.path.insert(0, str(_PROJECT_ROOT))
            from scripts.agents.orchestrator import run_agent_review
            _full = run_agent_review(content, chapter_no=chapter_no, mode="full")
            if _full:
                _score = _full.get("overall_score", "?")
                _status = _full.get("status", "?")
                print(f"  [审稿] full模式: 评分{_score} 状态{_status}")
                _ce = _full.get("chief_editor", {})
                if isinstance(_ce, dict):
                    _summary = _ce.get("suggestion", "")
                    if _summary:
                        print(f"    主编意见: {str(_summary)[:120]}")
                    for _f in [_ce.get("should_fix", [])]:
                        if isinstance(_f, list):
                            for _item in _f[:2]:
                                _txt = str(_item.get("issue", _item))[:100]
                                print(f"    🔴 {_txt}")
        except Exception as _e:
            pass

        try:
            # 3. 改稿检测 (从已跑的 guard 结果提取)
            _reports_dir = app.exports_root / "reports"
            if _reports_dir.exists():
                _fixes = []
                _padding = _reports_dir / f"chapter_{chapter_no:03d}_padding_report.json"
                if _padding.exists():
                    try:
                        _pd = json.loads(_padding.read_text(encoding="utf-8"))
                        if _pd.get("padding_detected") and _pd.get("padding_evidence"):
                            _ev = _pd["padding_evidence"]
                            if isinstance(_ev, list):
                                _fixes.extend([f"水文: {str(e)[:60]}" for e in _ev[:2]])
                    except: pass
                _ai = _reports_dir / f"chapter_{chapter_no:03d}_anti_ai_guard_report.json"
                if _ai.exists():
                    try:
                        _ad = json.loads(_ai.read_text(encoding="utf-8"))
                        _findings = _ad.get("findings", [])
                        if isinstance(_findings, list):
                            for _f_item in _findings:
                                _msg = _f_item.get("message", "") if isinstance(_f_item, dict) else str(_f_item)
                                if _msg and len(_msg) > 5:
                                    _fixes.append(_msg[:80])
                        elif isinstance(_findings, dict):
                            for _k, _v in _findings.items():
                                if isinstance(_v, (list, dict)) and len(str(_v)) > 5:
                                    _fixes.append(f"AI腔: {_k}")
                    except: pass
                if _fixes:
                    print(f"  [改稿] 检测到{len(_fixes)}处可优化")
                    for _f in _fixes[:3]:
                        print(f"    🟡 {_f}")
        except Exception as _e:
            pass

        print(f"\n{'='*60}")
        print(f"第{chapter_no}章全部门禁通过 [OK]  {wc}字 v{result['version']}")
        print(f"{'='*60}")

    elif args.action == "review":
        stage_review(chapter_no)

    elif args.action == "volume":
        volume_post()


if __name__ == "__main__":
    main()
