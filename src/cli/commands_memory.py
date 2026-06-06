"""src/cli/commands_memory.py — Memory/query/learn/RAG commands v0.7.0"""

from src.cli.shared import (PROJECT_ROOT, SCRIPTS_DIR, _load_project_config,
    _get_default_slug, _get_novels_root, _resolve_post_context,
    _story_exists, _story_missing_msg, _get_workspace_dir, _get_active_db_path,
    _get_outline_manager, _check_outline_gate, _get_story_dir)
import sys
import json
from pathlib import Path
from datetime import datetime
from scripts.config_utils import resolve_path


def cmd_query(args):
    """Query project memory for matching content."""
    if not _story_exists():
        print(f"  {_story_missing_msg()}")
        return 1

    question = " ".join(getattr(args, "question", []) or [])
    if not question.strip():
        print("Usage: python novel.py query <question>")
        print("Example: python novel.py query 主角的名字是什么")
        return 1

    print(f"  查询: {question}")
    print()

    story = _get_story_dir()

    # Search memory JSON files
    memory = story / "memory"
    hits = 0

    for fname, label in [("characters.json", "角色"), ("promises.json", "伏笔"),
                          ("world_facts.json", "世界观"), ("learned_rules.json", "规则")]:
        fp = memory / fname
        if not fp.exists():
            continue
        try:
            import json as _json
            data = _json.loads(fp.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for item in data:
                    text = str(item)
                    if question.lower() in text.lower() or any(kw in text for kw in question.split()):
                        hits += 1
                        preview = text[:120].replace("\n", " ")
                        print(f"  [{label}] {preview}...")
        except Exception:
            pass

    # Search event ledger
    ledger = story / "events" / "event_ledger.jsonl"
    if ledger.exists():
        try:
            for line in ledger.read_text(encoding="utf-8").strip().split("\n"):
                if not line.strip():
                    continue
                if question.lower() in line.lower() or any(kw in line for kw in question.split()):
                    hits += 1
                    import json as _json
                    evt = _json.loads(line)
                    preview = str(evt.get("event", line))[:120]
                    print(f"  [事件 ch{evt.get('chapter', '?')}] {preview}...")
        except Exception:
            pass

    # Search contracts
    chapters_dir = story / "chapters"
    if chapters_dir.exists():
        for cf in sorted(chapters_dir.glob("chapter_*_contract.json")):
            try:
                import json as _json
                text = cf.read_text(encoding="utf-8")
                if question.lower() in text.lower() or any(kw in text for kw in question.split()):
                    hits += 1
                    data = _json.loads(text)
                    ch_no = data.get('chapter_no', '?')
                    ch_title = data.get('chapter_title', '')
                    scene_goal = data.get('required_scene_goal', '')
                    open_promises = data.get('open_promises_to_keep', [])
                    forbidden = data.get('forbidden_changes', [])
                    active_chars = data.get('active_characters', [])
                    min_rules = data.get('minimum_quality_rules', {})
                    must_advance = min_rules.get('must_advance_plot', None)
                    print(f"  [合同 ch{ch_no}] {ch_title}")
                    if scene_goal:
                        print(f"    场景目标: {scene_goal}")
                    if open_promises:
                        print(f"    开放伏笔 ({len(open_promises)}):")
                        for p in open_promises[:3]:
                            print(f"      · {str(p)[:80]}")
                        if len(open_promises) > 3:
                            print(f"      ...还有 {len(open_promises)-3} 个")
                    if forbidden:
                        print(f"    禁止变更 ({len(forbidden)}):")
                        for f in forbidden[:3]:
                            print(f"      · {str(f)[:80]}")
                        if len(forbidden) > 3:
                            print(f"      ...还有 {len(forbidden)-3} 项")
                    if must_advance is not None:
                        print(f"    必须推进剧情: {'是' if must_advance else '否'}")
                    if active_chars:
                        print(f"    活跃角色: {len(active_chars)} 个")
            except Exception:
                pass

    if hits == 0:
        # Fallback: search FTS5 in active slot DB
        try:
            from src.cli.shared import _get_active_db_path
            db_path = _get_active_db_path()
            if db_path:
                import sqlite3 as _s
                conn = _s.connect(str(db_path))
                terms = [t for t in question.strip().split() if t]
                fts_hits = []
                for t in terms:
                    cur = conn.execute(
                        "SELECT c.chapter_no, c.title, substr(fts.content,1,80) "
                        "FROM novel_chapter_fts fts "
                        "LEFT JOIN chapters c ON c.id = fts.rowid "
                        "WHERE fts.content LIKE ? LIMIT 10",
                        (f"%{t}%",)
                    )
                    fts_hits.extend(cur.fetchall())
                if fts_hits:
                    seen = set()
                    print(f"  [全文搜索] 找到 {len(fts_hits)} 条匹配:\n")
                    for row in fts_hits:
                        ch_no = row[0] or "?"
                        title = row[1] or f"第{ch_no}章"
                        key = (ch_no, title)
                        if key in seen:
                            continue
                        seen.add(key)
                        preview = (row[2] or "").replace("\n", " ")
                        print(f"  第{ch_no}章 {title}")
                        print(f"    {preview}...\n")
                    if seen:
                        print(f"  共 {len(seen)} 章匹配。")
                        conn.close()
                        return 0
                conn.close()
        except Exception:
            pass
        print("  未找到匹配的记忆。")
    else:
        print(f"\n  共 {hits} 条匹配。")
    return 0


def cmd_learn(args):
    """Add/list/remove learned writing rules."""
    if not _story_exists():
        print(f"  {_story_missing_msg()}")
        return 1

    import json as _json

    rules_file = _get_story_dir() / "memory" / "learned_rules.json"
    rules = []
    if rules_file.exists():
        try:
            rules = _json.loads(rules_file.read_text(encoding="utf-8"))
        except Exception:
            rules = []

    action = getattr(args, "action", "list")
    rule_text = " ".join(getattr(args, "rule", []) or [])

    # Auto-detect: if action is not a known command, treat it as rule text
    if action not in ("add", "list", "remove"):
        rule_text = action + (" " + rule_text if rule_text else "")
        action = "add"

    if action == "list":
        if not rules:
            print("  暂无已学规则。用 python novel.py learn add <规则> 添加。")
            return 0
        print(f"  已学规则 ({len(rules)}):")
        for i, r in enumerate(rules):
            rule_str = r.get("rule", str(r))
            ch = r.get("chapter", "?")
            print(f"    [{i+1}] (ch{ch}) {rule_str}")
        return 0

    elif action == "add":
        if not rule_text.strip():
            print("Usage: python novel.py learn add <规则内容>")
            print("Example: python novel.py learn add 主角李明的口头禅是'走着瞧'")
            return 1
        from datetime import datetime
        rules.append({
            "rule": rule_text,
            "chapter": "manual",
            "added_at": datetime.now().isoformat(),
        })
        rules_file.write_text(_json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [OK] 规则已添加: {rule_text}")
        return 0

    elif action == "remove":
        if not rule_text.strip():
            print("Usage: python novel.py learn remove <number>")
            return 1
        try:
            idx = int(rule_text) - 1
            if 0 <= idx < len(rules):
                removed = rules.pop(idx)
                rules_file.write_text(_json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"  [OK] 规则已移除: {removed.get('rule', str(removed))}")
                return 0
            else:
                print(f"  无效编号: {idx+1} (共 {len(rules)} 条)")
                return 1
        except ValueError:
            print(f"  请输入有效编号。当前共 {len(rules)} 条规则。")
            return 1

    return 0


def cmd_rag(args):
    """Vector RAG queries."""
    action = getattr(args, "rag_action", None)
    if action == "status":
        print("RAG Status:")
        try:
            from scripts.rag.rag_config import load_rag_config, get_rag_mode
            cfg = load_rag_config()
            mode = get_rag_mode(cfg)
            # Vector available if sentence_transformers is installed
            try:
                import sentence_transformers
                vector_ok = True
            except ImportError:
                vector_ok = False
            print(f"  Mode: {mode}")
            print(f"  Vector: {'available' if vector_ok else 'unavailable (fallback to FTS5)'}")
        except Exception as e:
            print(f"  FTS5: available (default)")
            print(f"  Vector: unavailable ({e})")
        return 0
    elif action == "query":
        question = " ".join(getattr(args, "question", []))
        if not question:
            print("Usage: python novel.py rag query <question>")
            return 1
        try:
            from scripts.rag.rag_query import rag_query
            result = rag_query(question)
            print(f"Query: {question}")
            print(f"Mode: {result.get('mode', 'fts5')}")
            for r in result.get("results", [])[:5]:
                print(f"  [{r.get('chapter_no', '?')}] {r.get('evidence', '')[:80]}")
        except Exception as e:
            print(f"  [WARN] RAG query unavailable: {e}")
        return 0
    else:
        print("Usage: python novel.py rag {status|query}")
        return 1
