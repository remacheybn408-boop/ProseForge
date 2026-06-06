#!/usr/bin/env python3
"""src/cli/commands_texture.py — 人工味质量层 CLI v0.6.6

命令:
  python novel.py texture check <章节号>    对章节运行全部质量检测
"""
import sys, json
from pathlib import Path
from src.cli.shared import PROJECT_ROOT, find_chapter_file
from src.guards.human_texture import run_human_texture_guards
from src.guards.human_texture.plot_pacing_controller import PROGRESS_DELTAS


def cmd_texture(args):
    action = getattr(args, "texture_action", None)

    if action == "check":
        ch = getattr(args, "chapter_no", None)
        if not ch:
            print("  用法: python novel.py texture check <章节号>")
            return

        # 找章节文件
        ch_path = _resolve_chapter(ch)
        if not ch_path:
            print(f"  ❌ 找不到第{ch}章文件，请确认 --slug 参数")
            return

        genre = getattr(args, "genre", None) or "default"
        pace = getattr(args, "pace", "normal")
        content = Path(ch_path).read_text(encoding="utf-8")
        result = run_human_texture_guards(content, int(ch), project_root=PROJECT_ROOT, genre=genre, pace_level=pace)

        # 输出
        print(f"\n  ═══ 人工味质量层检测 — 第{ch}章 ═══")
        print(f"  综合评分: {result['score']}/100  |  状态: {result['status']}  |  题材: {genre}  |  速度: {pace}")
        print()

        scores = result.get("scores", {})
        for guard, score in sorted(scores.items()):
            name = guard.replace("_guard", "").replace("_", " ")
            icon = "✅" if score >= 70 else ("⚠️" if score >= 55 else "❌")
            print(f"  {icon} {name:25s} {score}/100")

        findings = result.get("findings", [])
        if findings:
            print(f"\n  发现 {len(findings)} 个问题:")
            for f_ in findings:
                lvl = f_.get("level", "INFO")
                msg = f_.get("message", "")
                sug = f_.get("suggestion", "")
                icon = " ⚠" if lvl == "WARN" else (" ❌" if lvl == "FAIL" else " ℹ")
                print(f"  {icon} [{f_.get('guard','?')}] {msg}")
                if sug:
                    print(f"     建议: {sug}")
        else:
            print("\n  未发现问题，章节质量良好 ✅")

        # 显示进度增量详情 — 从单个 guard 结果提取
        for gr in result.get("_guards_raw", []):
            if gr.get("guard") == "plot_pacing_controller":
                m = gr.get("metrics", {})
                d = m.get("deltas", {})
                print(f"\n  进度增量: {m.get('present_count',0)}/{m.get('required_min',0)}  |  题材命中: {m.get('genre_focus_hit','?')}")
                for dk, pv in d.items():
                    print(f"  {'✅' if pv else '  '} {dk:25s} {PROGRESS_DELTAS.get(dk,'?')}")
                break
        print()

    else:
        print("用法: python novel.py texture {check}")
        print("  check <章节号>    对章节运行全部质量检测")


def _resolve_chapter(chapter_no: str) -> str | None:
    """在当前 slot 或 novels_root 找章节文件。"""
    ws_dir = PROJECT_ROOT / "workspace"
    try:
        import json as _j
        reg = _j.loads((ws_dir / "registry.json").read_text(encoding="utf-8"))
        active = reg.get("active_slot", "")
        slot_dir = ws_dir / active

        # slot chapters/
        for d in [slot_dir / "chapters", slot_dir / "第01卷"]:
            if d.exists():
                ch_fp = find_chapter_file(int(chapter_no), d)
                if ch_fp:
                    return str(ch_fp)
        # v0.8.0: check volume subdirectories under chapters/
        ch_base = slot_dir / "chapters"
        if ch_base.exists():
            for vd in sorted(ch_base.glob("第*卷")):
                ch_fp = find_chapter_file(int(chapter_no), vd)
                if ch_fp:
                    return str(ch_fp)

        # novels_root
        from src.cli.shared import _load_project_config
        cfg = _load_project_config()
        novels_root = Path(cfg.get("novels_root", "./novels"))
        slug = ""
        proj = slot_dir / "project.json"
        if proj.exists():
            pj = _j.loads(proj.read_text(encoding="utf-8"))
            slug = pj.get("title") or pj.get("name", "")
        if slug:
            from src.cli.shared import _resolve_chapter_path as _rcp
            d = Path(_rcp(slug))
            if d.exists():
                ch_fp = find_chapter_file(int(chapter_no), d)
                if ch_fp:
                    return str(ch_fp)
    except Exception:
        pass
    return None
