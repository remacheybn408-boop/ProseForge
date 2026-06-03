#!/usr/bin/env python3
"""
import_outline_skeleton.py — 标题骨架 JSON → SQLite 导入

用法:
  python scripts/import_outline_skeleton.py --config config.json --input skeleton.json
  python scripts/import_outline_skeleton.py --config config.json --input skeleton.json --dry-run

skeleton.json 结构:
{
  "novel_outline": {
    "slug": "demo_novel",
    "title": "示例小说",
    "genre": "玄幻",
    "total_chapters_target": 250
  },
  "volume_plans": [
    {
      "volume_no": 1,
      "planned_title": "杂役观天",
      "volume_goal": "主角从底层杂役初步接触修炼世界",
      "opening_state": "...",
      "ending_target": "...",
      "must_complete": "...",
      "suggested_chapters": 25
    }
  ],
  "chapter_plans": [
    {
      "volume_no": 1,
      "chapter_no": 1,
      "planned_title": "杂役院的清晨",
      "chapter_goal": "建立主角底层身份和生活环境",
      "conflict_point": "主角与杂役管事的不平等关系",
      "ending_hook_direction": "主角发现被刻意分配超量重活——悬念",
      "main_event": "",
      "character_focus": "主角、赵管事",
      "must_include": "",
      "plot_threads_to_advance": "",
      "reader_promises_to_advance": "",
      "continuity_from_previous": ""
    }
  ]
}

校验规则:
- 每卷章数 20-29
- 每章必须有 chapter_goal
- 每章必须有 conflict_point
- 每章必须有 ending_hook_direction
"""

import sqlite3, json, sys, argparse
from pathlib import Path
from datetime import datetime

MIN_CHAPTERS_PER_VOLUME = 20
MAX_CHAPTERS_PER_VOLUME = 29


def load_config(config_path):
    cfg = {"db_path": "./data/novel_memory.db"}
    if config_path and Path(config_path).exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg.update(json.load(f))
    return cfg


def connect(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_novel(cur, outline):
    """Ensure the novel record exists; create if missing."""
    slug = outline.get("slug", "")
    title = outline.get("title", slug)
    genre = outline.get("genre", "")
    target = outline.get("total_chapters_target", 0)

    cur.execute("SELECT id, slug FROM novels WHERE slug=?", (slug,))
    row = cur.fetchone()
    if row:
        return row["id"]

    cur.execute(
        "INSERT INTO novels(slug, title, genre, target_words, status) VALUES(?,?,?,?,?)",
        (slug, title, genre, target, "planning"),
    )
    return cur.lastrowid


def validate(data, dry_run=False):
    """Validate skeleton and return (errors, warnings, stats)."""
    errors = []
    warnings = []
    outline = data.get("novel_outline", {})
    volume_plans = data.get("volume_plans", [])
    chapter_plans = data.get("chapter_plans", [])

    if not outline.get("slug"):
        errors.append("novel_outline.slug 缺失")

    if not volume_plans:
        errors.append("volume_plans 为空")
    if not chapter_plans:
        errors.append("chapter_plans 为空")

    # Group chapters by volume
    vol_chapters = {}
    for vp in volume_plans:
        vno = vp.get("volume_no")
        if vno is None:
            errors.append(f"volume_plan 缺少 volume_no: {vp.get('planned_title', '?')}")
        else:
            vol_chapters[vno] = []

    for cp in chapter_plans:
        vno = cp.get("volume_no")
        cno = cp.get("chapter_no")
        if vno is None or cno is None:
            errors.append(f"chapter_plan 缺少 volume_no/chapter_no: {cp.get('planned_title', '?')}")
            continue
        if vno not in vol_chapters:
            vol_chapters[vno] = []
        vol_chapters[vno].append(cno)

    # Per-volume chapter count
    for vno, chapters in vol_chapters.items():
        count = len(chapters)
        if count < MIN_CHAPTERS_PER_VOLUME:
            warnings.append(f"第{vno}卷: {count}章 (建议 {MIN_CHAPTERS_PER_VOLUME}-{MAX_CHAPTERS_PER_VOLUME})")
        elif count > MAX_CHAPTERS_PER_VOLUME:
            warnings.append(f"第{vno}卷: {count}章 (超过建议上限 {MAX_CHAPTERS_PER_VOLUME})")

    # Per-chapter required fields
    for cp in chapter_plans:
        loc = f"第{cp.get('volume_no','?')}卷第{cp.get('chapter_no','?')}章"
        if not cp.get("chapter_goal"):
            errors.append(f"{loc}: 缺少 chapter_goal")
        if not cp.get("conflict_point"):
            errors.append(f"{loc}: 缺少 conflict_point")
        if not cp.get("ending_hook_direction"):
            errors.append(f"{loc}: 缺少 ending_hook_direction")

    stats = {
        "novel_slug": outline.get("slug", "?"),
        "volumes": len(volume_plans),
        "total_chapters": len(chapter_plans),
        "chapters_per_volume": {vno: len(chs) for vno, chs in vol_chapters.items()},
    }

    return errors, warnings, stats


def import_skeleton(db_path, data, dry_run=False):
    """Import validated skeleton into SQLite."""
    conn = connect(db_path)
    cur = conn.cursor()
    ts = now()
    outline = data["novel_outline"]

    # Novel
    novel_id = ensure_novel(cur, outline)
    slug = outline["slug"]

    # Volume plans
    vol_count = 0
    for vp in data.get("volume_plans", []):
        vno = vp["volume_no"]
        cur.execute(
            """INSERT OR REPLACE INTO volume_plans(
                novel_id, volume_no, planned_title, final_title, title_status,
                suggested_chapters, min_chapters, max_chapters,
                volume_goal, opening_state, ending_target, must_complete,
                unresolved_hooks_to_next, outline_version, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                novel_id, vno,
                vp.get("planned_title", ""),
                vp.get("final_title", vp.get("planned_title", "")),
                "planned",
                vp.get("suggested_chapters", 25),
                MIN_CHAPTERS_PER_VOLUME,
                MAX_CHAPTERS_PER_VOLUME,
                vp.get("volume_goal", ""),
                vp.get("opening_state", ""),
                vp.get("ending_target", ""),
                vp.get("must_complete", ""),
                vp.get("unresolved_hooks_to_next", ""),
                1,
                ts,
            ),
        )
        vol_count += 1

    # Chapter plans
    ch_count = 0
    for cp in data.get("chapter_plans", []):
        cur.execute(
            """INSERT OR REPLACE INTO chapter_plans(
                novel_id, volume_no, chapter_no,
                planned_title, final_title, title_status,
                chapter_goal, main_event, character_focus, conflict_point,
                must_include, plot_threads_to_advance, reader_promises_to_advance,
                ending_hook_direction, continuity_from_previous,
                title_change_reason, outline_version, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                novel_id,
                cp["volume_no"],
                cp["chapter_no"],
                cp.get("planned_title", ""),
                cp.get("final_title", cp.get("planned_title", "")),
                "planned",
                cp.get("chapter_goal", ""),
                cp.get("main_event", ""),
                cp.get("character_focus", ""),
                cp.get("conflict_point", ""),
                cp.get("must_include", ""),
                cp.get("plot_threads_to_advance", ""),
                cp.get("reader_promises_to_advance", ""),
                cp.get("ending_hook_direction", ""),
                cp.get("continuity_from_previous", ""),
                cp.get("title_change_reason", ""),
                1,
                ts,
            ),
        )
        ch_count += 1

    # Log
    cur.execute(
        "INSERT INTO novel_logs(action, target_type, detail) VALUES(?,?,?)",
        ("import_outline", "novel", f"导入标题骨架: {slug}, {vol_count}卷, {ch_count}章"),
    )

    if not dry_run:
        conn.commit()

    conn.close()
    return {"volumes_imported": vol_count, "chapters_imported": ch_count}


def main():
    parser = argparse.ArgumentParser(description="Novel Forge — 导入标题骨架")
    parser.add_argument("--config", default=None, help="配置文件路径 (默认: config.json)")
    parser.add_argument("--input", required=True, help="骨架 JSON 文件路径")
    parser.add_argument("--dry-run", action="store_true", help="仅校验不写入")
    parser.add_argument("--db-path", default=None, help="数据库路径 (覆盖配置)")
    args = parser.parse_args()

    # Load config
    cfg = load_config(args.config)
    if args.db_path:
        cfg["db_path"] = args.db_path

    # Load skeleton
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[FAIL] 文件不存在: {input_path}")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate
    errors, warnings, stats = validate(data, dry_run=args.dry_run)

    print("=" * 60)
    print(f"标题骨架校验: {stats['novel_slug']}")
    print("=" * 60)
    print(f"  卷数: {stats['volumes']}")
    print(f"  总章数: {stats['total_chapters']}")
    for vno, count in stats["chapters_per_volume"].items():
        ok = MIN_CHAPTERS_PER_VOLUME <= count <= MAX_CHAPTERS_PER_VOLUME
        mark = " [OK]" if ok else " [WARN]"
        print(f"    第{vno}卷: {count}章{mark}")

    if warnings:
        print(f"\n[WARN] 警告 ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")

    if errors:
        print(f"\n[FAIL] 校验失败 ({len(errors)} 个错误):")
        for e in errors:
            print(f"  - {e}")
        print("\n拒绝导入。请修复上述错误后重试。")
        sys.exit(1)

    print(f"\n[OK] 校验通过 ({stats['total_chapters']}章)")

    if args.dry_run:
        print("\n--dry-run 模式，未写入数据库。")
        return

    # Import
    result = import_skeleton(cfg["db_path"], data)
    print(f"\n[OK] 导入完成:")
    print(f"  volumes: {result['volumes_imported']}")
    print(f"  chapters: {result['chapters_imported']}")
    print(f"  database: {cfg['db_path']}")


if __name__ == "__main__":
    main()
