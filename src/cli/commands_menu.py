#!/usr/bin/env python3
"""src/cli/commands_menu.py — CLI commands for novel-pipeline-write-engine v0.6.5"""

from src.cli.shared import PROJECT_ROOT, SCRIPTS_DIR, _get_default_slug, _get_novels_root, _get_outline_manager, _story_exists, _story_missing_msg
import sys
import json
from pathlib import Path
from datetime import datetime
from version import get_version
from config_utils import normalize_config, load_json_config, resolve_path

def cmd_scc_help():
    """打印中文用户手册。"""
    print("=" * 68)
    print("  小说写作流水线 — 操作手册")
    v = get_version()
    print(f"  Novel Forge {v}")
    print("=" * 68)
    print()
    print("  novel.py 是所有操作的统一入口。")
    print()
    print("  ── Hermes/Agent 用户 ──")
    print("  如果你是 Hermes Agent 用户，可以直接用自然语言与我对话：")
    print("  · 说「我要写第3章」→ 我会检查上下文并生成任务卡")
    print("  · 说「添加大纲」→ 我会引导你上传或粘贴大纲内容")
    print("  · 说「审稿第1章」→ 我会运行 Agent 陪审团审查")
    print("  · 说「导出小说」→ 我会帮你导出 Markdown")
    print("  · 说「菜单」→ 我会显示交互式中文菜单")
    print()
    print("  ── CLI/终端用户 ──")
    print("  以下按功能分类列出常用命令。")
    print()

    # ── 1. 新用户从这里开始 ──
    print("  " + "─" * 60)
    print("  【新用户从这里开始】")
    print("  " + "─" * 60)
    print("  python novel.py init                初始化项目（目录 + 数据库 + 配置）")
    print("  python novel.py status              检查环境状态（Python/配置/文件完整性）")
    print("  python novel.py status --detail     详细诊断模式")
    print("  python novel.py demo                运行演示流水线（创建示例章节并跑全部守卫）")
    print("  python novel.py pre <章节号>         生成写前任务卡（上下文/伏笔/规则）")
    print("  python novel.py post <章节号>        写后守卫检查 + 入库")
    print("  python novel.py board               只读项目看板（总览状态）")
    print()

    # ── 2. 大纲管理 ──
    print("  " + "─" * 60)
    print("  【大纲管理】outline")
    print("  " + "─" * 60)
    print("  python novel.py outline add <文件>       添加大纲（自动相似度检测）")
    print("  python novel.py outline import <文件>    导入大纲（--title 必须指定标题）")
    print("  python novel.py outline list             列出当前工作区所有大纲")
    print("  python novel.py outline current          显示当前激活大纲")
    print("  python novel.py outline switch <id>      切换激活大纲")
    print("  python novel.py outline diff <id1> <id2> 对比两个大纲（相似度分析）")
    print("  python novel.py outline rollback <id>    回滚大纲到上一版本")
    print("  python novel.py outline compare <文件>    对比文件与当前激活大纲")
    print("  python novel.py outline delete <id>      删除指定大纲")
    print()

    # ── 3. 数据库管理 ──
    print("  " + "─" * 60)
    print("  【数据库管理】db")
    print("  " + "─" * 60)
    print("  python novel.py db init              初始化 workspace 目录结构")
    print("  python novel.py db list              列出所有 DB slot（★=当前活跃）")
    print("  python novel.py db current           显示当前活跃 DB slot")
    print("  python novel.py db info              显示当前 slot 详细信息")
    print("  python novel.py db new --name <名>    创建新 DB slot")
    print("  python novel.py db use <slot_id>     切换 DB slot")
    print("  python novel.py db backup            备份当前 slot 的 project.json")
    print("  python novel.py db delete <slot_id>  删除指定 DB slot（不能删当前活跃的）")
    print("  python novel.py db restore <slot_id> 从备份恢复 DB slot")
    print()

    # ── 4. Agent 陪审团 ──
    print("  " + "─" * 60)
    print("  【Agent 陪审团】agents")
    print("  " + "─" * 60)
    print("  python novel.py agents review <章> --mode light   轻量模式审查（快）")
    print("  python novel.py agents review <章> --mode full    完整模式审查（详细）")
    print("  python novel.py agents review <章> --genre xianxia  指定题材风格")
    print()

    # ── 5. Story Contract ──
    print("  " + "─" * 60)
    print("  【Story Contract 故事合同系统】story")
    print("  " + "─" * 60)
    print("  python novel.py story init                 初始化 .story/ 目录")
    print("  python novel.py story contract <章>         生成章节合同（约束 + 伏笔）")
    print("  python novel.py story commit <章>           生成章节提交记录")
    print("  python novel.py story health                故事链健康检查")
    print("  python novel.py post <章> --story           写后守卫 + 自动生成 commit")
    print()

    # ── 6. 记忆与规则 ──
    print("  " + "─" * 60)
    print("  【记忆与规则】query / learn")
    print("  " + "─" * 60)
    print("  python novel.py query <问题>        查询项目记忆（角色/伏笔/世界观）")
    print("  python novel.py learn list          列出已学写作规则")
    print("  python novel.py learn add <规则>    添加写作规则")
    print("  python novel.py learn remove <编号> 删除写作规则")
    print()

    # ── 7. 导出与报告 ──
    print("  " + "─" * 60)
    print("  【导出与报告】report / export")
    print("  " + "─" * 60)
    print("  python novel.py report                  显示最近守卫报告")
    print("  python novel.py guards                  列出注册的守卫及状态")
    print("  python novel.py check <文件>            对指定章节文件运行守卫检查")
    print("  python novel.py export --slug <id>      导出为 Markdown（默认）")
    print("  python novel.py export --slug <id> --format txt  导出为纯文本")
    print("  python novel.py wc <章节号|文件>         统计中文字数")
    print()

    # ── 8. 其他工具 ──
    print("  " + "─" * 60)
    print("  【其他工具】genre / style / rag / review")
    print("  " + "─" * 60)
    print("  python novel.py genre list              列出可用题材包")
    print("  python novel.py genre show <id>         查看题材包详情")
    print("  python novel.py style list              列出可用风格包")
    print("  python novel.py style show <id>         查看风格包详情")
    print("  python novel.py rag status              查看 RAG 状态（向量/全文搜索）")
    print("  python novel.py rag query <问题>        语义搜索小说数据库")
    print("  python novel.py review <章>             运行守卫审查")
    print()

    # ── 9. 常见问题 ──
    print("  " + "━" * 60)
    print("  【常见问题 FAQ】")
    print("  " + "━" * 60)
    print()
    print("  Q: 为什么 pre/post/write 提示「没有激活的大纲」？")
    print("  A: 必须先添加大纲才能开始写作。")
    print("     1) 把大纲 .txt 文件放到「大纲」文件夹（如 D:\\小说\\大纲\\）")
    print("     2) 执行: python novel.py outline add D:\\小说\\大纲\\大纲.txt")
    print("     或在 Hermes 里直接说「添加大纲」")
    print()
    print("  Q: 如何开始一部新小说？")
    print("  A: 推荐流程：")
    print("     1) 在 D:\\小说\\大纲\\ 下创建小说大纲 .txt 文件")
    print("     2) python novel.py outline add <大纲路径>    # 自动检测相似度，不同小说自动创建新 slot")
    print("     3) python novel.py pre 1                      # 生成第1章任务卡")
    print("     4) python novel.py post 1                     # 写完后入库 + 守卫检查")
    print()
    print("  Q: outline upgrade 和 db new 有什么区别？")
    print("  A: 同一部小说的新大纲用 outline add（自动检测相似度，建议升级）")
    print("     不同小说用 db new 创建独立工作区（数据互不干扰）")
    print()
    print("  Q: 数据库文件在哪里？")
    print("  A: 每个 DB slot 在 workspace/<slot_id>/ 下有独立的 novel.db。")
    print("     例如当前活跃 slot 的数据库: workspace/<active_slot>/novel.db")
    print("     config.json 中 db_path 字段也可以指定自定义路径。")
    print()
    print("  Q: 如何查看完整帮助？")
    print("  A: python novel.py --help      查看所有命令列表")
    print("     python novel.py <命令> --help 查看具体命令的用法")
    print("     python novel.py menu         进入交互式菜单")
    print()
    print("  " + "━" * 60)
    print("  使用 python novel.py menu 进入交互式菜单")
    print("  " + "━" * 60)
    print()
    return 0


# ═══════════════════════════════════════════════════════════════
#  menu — 交互式文本菜单
# ═══════════════════════════════════════════════════════════════

def _menu_show_header():
    """显示菜单顶部信息栏（当前 slot + 大纲）。"""
    v = get_version()
    print()
    print("=" * 64)
    print(f"  小说写作引擎 Novel Forge {v}")
    print("=" * 64)

    # 当前 DB slot
    try:
        import json as _json
        ws_dir = PROJECT_ROOT / "workspace"
        reg = ws_dir / "registry.json"
        if reg.exists():
            data = _json.loads(reg.read_text(encoding="utf-8"))
            active = data.get("active_slot", "")
            slot_name = ""
            for s in data.get("slots", []):
                if s.get("id") == active:
                    slot_name = s.get("name", "")
                    break
            print(f"  DB Slot: {active} ({slot_name})" if slot_name else f"  DB Slot: {active}")
        else:
            print("  DB Slot: (未初始化)")
    except Exception:
        print("  DB Slot: (读取失败)")

    # 当前大纲
    try:
        mgr = _get_outline_manager()
        cur = mgr.current_outline()
        if cur:
            print(f"  大纲: {cur.get('title', '')} [{cur.get('id', '')}]  "
                  f"{cur.get('chapter_count', 0)}章/{cur.get('volume_count', 1)}卷")
        else:
            print("  大纲: (未设定)")
    except Exception:
        print("  大纲: (不可用)")

    print("-" * 64)


def _menu_confirm_dangerous(prompt_text="确认执行此操作？"):
    """危险操作确认：要求输入 YES。"""
    print()
    print(f"  ⚠️  {prompt_text}")
    answer = input("  输入 YES 确认，其他任意键取消: ").strip()
    return answer == "YES"


def _menu_db_management():
    """子菜单：数据库管理。"""
    while True:
        print()
        print("  " + "─" * 50)
        print("  【数据库管理】")
        print("  " + "─" * 50)
        print("  [1] db list        列出所有 DB slot")
        print("  [2] db current     显示当前活跃 slot")
        print("  [3] db info        显示当前 slot 详细信息")
        print("  [4] db new         创建新 DB slot")
        print("  [5] db use         切换 DB slot")
        print("  [6] db backup      备份当前 slot")
        print("  [7] db delete      删除 DB slot")
        print("  [8] db restore     从备份恢复")
        print("  [0] 返回主菜单")
        print()
        choice = input("  请选择 [0-8]: ").strip()

        if choice == "1":
            _db_list()
        elif choice == "2":
            _db_current()
        elif choice == "3":
            _db_info()
        elif choice == "4":
            name = input("  请输入新 slot 名称: ").strip()
            if name:
                desc = input("  描述（可选）: ").strip()
                _db_new(name, desc)
            else:
                print("  ❌ 名称不能为空。")
        elif choice == "5":
            slot_id = input("  请输入 slot ID（如 slot_002）: ").strip()
            if slot_id:
                _db_use(slot_id)
        elif choice == "6":
            _db_backup()
        elif choice == "7":
            slot_id = input("  请输入要删除的 slot ID: ").strip()
            if slot_id and _menu_confirm_dangerous(f"将删除 slot {slot_id}。此操作不可逆！"):
                _db_delete(slot_id)
        elif choice == "8":
            slot_id = input("  请输入要恢复的 slot ID: ").strip()
            if slot_id:
                _db_restore(slot_id)
        elif choice == "0":
            break
        else:
            print("  无效选择，请重试。")


def _menu_outline_management():
    """子菜单：大纲管理。"""
    while True:
        print()
        print("  " + "─" * 50)
        print("  【大纲管理】")
        print("  " + "─" * 50)
        print("  [1] outline add       添加大纲")
        print("  [2] outline import    导入大纲（指定标题）")
        print("  [3] outline list      列出所有大纲")
        print("  [4] outline current   显示当前激活大纲")
        print("  [5] outline switch    切换激活大纲")
        print("  [6] outline diff      对比两个大纲")
        print("  [7] outline rollback  回滚大纲版本")
        print("  [8] outline compare   对比文件与当前大纲")
        print("  [9] outline delete    删除大纲")
        print("  [0] 返回主菜单")
        print()
        choice = input("  请选择 [0-9]: ").strip()

        if choice == "1":
            fp = input("  大纲文件路径: ").strip()
            if fp:
                title = input("  标题（可选）: ").strip()
                genre = input("  题材（可选）: ").strip()
                style = input("  风格（可选）: ").strip()
                _outline_add(fp, title, genre, style)
        elif choice == "2":
            fp = input("  大纲文件路径: ").strip()
            if fp:
                title = input("  标题（必填）: ").strip()
                if not title:
                    print("  ❌ 标题不能为空。")
                else:
                    genre = input("  题材（可选）: ").strip()
                    style = input("  风格（可选）: ").strip()
                    _outline_import(fp, title, genre, style)
        elif choice == "3":
            _outline_list()
        elif choice == "4":
            _outline_current()
        elif choice == "5":
            oid = input("  大纲 ID: ").strip()
            if oid:
                _outline_switch(oid)
        elif choice == "6":
            id1 = input("  大纲1 ID: ").strip()
            id2 = input("  大纲2 ID: ").strip()
            if id1 and id2:
                _outline_diff(id1, id2)
        elif choice == "7":
            oid = input("  大纲 ID: ").strip()
            if oid:
                _outline_rollback(oid)
        elif choice == "8":
            fp = input("  文件路径: ").strip()
            if fp:
                _outline_compare(fp)
        elif choice == "9":
            oid = input("  大纲 ID: ").strip()
            if oid and _menu_confirm_dangerous(f"将删除大纲 {oid}。"):
                _outline_delete(oid)
        elif choice == "0":
            break
        else:
            print("  无效选择，请重试。")


def _menu_writing_flow():
    """子菜单：写作流程。"""
    while True:
        print()
        print("  " + "─" * 50)
        print("  【写作流程】")
        print("  " + "─" * 50)
        print("  [1] pre <章>        生成写前任务卡")
        print("  [2] post <章>       写后守卫检查 + 入库")
        print("  [3] post <章> --story  写后守卫 + 自动生成 story commit")
        print("  [4] review <章>     运行守卫审查")
        print("  [5] check <文件>    对指定文件运行守卫检查")
        print("  [6] wc <章|文件>    统计中文字数")
        print("  [0] 返回主菜单")
        print()
        choice = input("  请选择 [0-6]: ").strip()

        if choice == "1":
            ch = input("  章节号: ").strip()
            if ch:
                cmd_pre(ch)
        elif choice == "2":
            ch = input("  章节号: ").strip()
            if ch:
                cmd_post(ch)
        elif choice == "3":
            ch = input("  章节号: ").strip()
            if ch:
                cmd_post(ch, story=True)
        elif choice == "4":
            ch = input("  章节号: ").strip()
            if ch:
                cmd_review(ch)
        elif choice == "5":
            fp = input("  文件路径: ").strip()
            if fp:
                cmd_check(fp)
        elif choice == "6":
            fp = input("  章节号或文件路径: ").strip()
            if fp:
                cmd_wc(fp)
        elif choice == "0":
            break
        else:
            print("  无效选择，请重试。")


def _menu_agents():
    """子菜单：Agent 陪审团。"""
    while True:
        print()
        print("  " + "─" * 50)
        print("  【Agent 陪审团】")
        print("  " + "─" * 50)
        print("  [1] light 模式审查（快速）")
        print("  [2] full 模式审查（详细）")
        print("  [0] 返回主菜单")
        print()
        choice = input("  请选择 [0-2]: ").strip()

        if choice in ("1", "2"):
            ch = input("  章节号: ").strip()
            if ch:
                mode = "light" if choice == "1" else "full"
                try:
                    from scripts.agents.orchestrator import run_agent_review
                    slug = _get_default_slug()
                    novels_root = Path(_get_novels_root())
                    ch_dir = novels_root / slug / "第01卷"
                    candidates = list(ch_dir.glob(f"第{ch}章*.txt"))
                    content = ""
                    if candidates:
                        content = candidates[0].read_text(encoding="utf-8")
                    result = run_agent_review(content, int(ch), mode=mode)
                    print(f"  Score: {result.get('overall_score', 'N/A')}")
                    print(f"  Status: {result.get('status', 'N/A')}")
                    chief = result.get("chief_editor", {})
                    for cat in ["must_fix", "should_fix", "keep"]:
                        items = chief.get(cat, [])
                        if items:
                            print(f"  {cat}: {len(items)} items")
                except Exception as e:
                    print(f"  [ERROR] Agent review failed: {e}")
        elif choice == "0":
            break
        else:
            print("  无效选择，请重试。")


def _menu_story_contract():
    """子菜单：Story Contract。"""
    while True:
        print()
        print("  " + "─" * 50)
        print("  【Story Contract 故事合同】")
        print("  " + "─" * 50)
        print("  [1] story init          初始化 .story/")
        print("  [2] story contract      生成章节合同")
        print("  [3] story commit        生成章节提交记录")
        print("  [4] story health        故事链健康检查")
        print("  [0] 返回主菜单")
        print()
        choice = input("  请选择 [0-4]: ").strip()

        if choice == "1":
            if _story_exists():
                print("  .story/ 目录已存在。如需重建请先删除。")
            else:
                try:
                    from scripts.story import story_init
                    result = story_init.init_story(PROJECT_ROOT)
                    print(f"  [OK] .story/ 已初始化")
                    for item in result.get("created", []):
                        print(f"    + {item}")
                except Exception as e:
                    print(f"  [ERROR] {e}")
        elif choice == "2":
            if not _story_exists():
                print(f"  {_story_missing_msg()}")
            else:
                ch = input("  章节号: ").strip() or "1"
                try:
                    from scripts.story import contract_builder
                    contract = contract_builder.build_contract(PROJECT_ROOT, int(ch))
                    saved = contract_builder.save_contract(PROJECT_ROOT, int(ch), contract)
                    print(f"  [OK] 第{ch}章合同已生成: {saved}")
                except Exception as e:
                    print(f"  [ERROR] {e}")
        elif choice == "3":
            if not _story_exists():
                print(f"  {_story_missing_msg()}")
            else:
                ch = input("  章节号: ").strip() or "1"
                try:
                    from scripts.story import commit_builder
                    commit = commit_builder.build_commit(PROJECT_ROOT, int(ch), chapter_title=f"第{ch}章")
                    saved = commit_builder.save_commit(PROJECT_ROOT, int(ch), commit)
                    print(f"  [OK] 第{ch}章提交记录已生成: {saved}")
                except Exception as e:
                    print(f"  [ERROR] {e}")
        elif choice == "4":
            if not _story_exists():
                print(f"  {_story_missing_msg()}")
            else:
                try:
                    from scripts.story import story_health
                    report = story_health.check_health(PROJECT_ROOT)
                    print(f"  状态: {report['status']}")
                    print(f"  合同数: {report.get('contract_count', 0)}")
                    print(f"  提交数: {report.get('commit_count', 0)}")
                    print(f"  事件数: {report.get('event_count', 0)}")
                except Exception as e:
                    print(f"  [ERROR] {e}")
        elif choice == "0":
            break
        else:
            print("  无效选择，请重试。")


def _menu_reports_exports():
    """子菜单：报告与导出。"""
    while True:
        print()
        print("  " + "─" * 50)
        print("  【报告与导出】")
        print("  " + "─" * 50)
        print("  [1] report        显示最近守卫报告")
        print("  [2] guards        列出注册守卫")
        print("  [3] export MD     导出为 Markdown")
        print("  [4] export TXT    导出为纯文本")
        print("  [0] 返回主菜单")
        print()
        choice = input("  请选择 [0-4]: ").strip()

        if choice == "1":
            cmd_report()
        elif choice == "2":
            cmd_guards()
        elif choice == "3":
            slug = input("  小说 slug: ").strip()
            if slug:
                cmd_export(slug, "md")
        elif choice == "4":
            slug = input("  小说 slug: ").strip()
            if slug:
                cmd_export(slug, "txt")
        elif choice == "0":
            break
        else:
            print("  无效选择，请重试。")


def _menu_advanced():
    """子菜单：高级命令。"""
    while True:
        print()
        print("  " + "─" * 50)
        print("  【高级命令】")
        print("  " + "─" * 50)
        print("  [1] genre list         列出可用题材包")
        print("  [2] style list         列出可用风格包")
        print("  [3] rag status         查看 RAG 状态")
        print("  [4] rag query          语义搜索数据库")
        print("  [5] query <问题>       查询项目记忆")
        print("  [6] learn list         列出已学规则")
        print("  [7] learn add          添加写作规则")
        print("  [8] wc <章|文件>       统计中文字数")
        print("  [9] board              项目看板")
        print("  [0] 返回主菜单")
        print()
        choice = input("  请选择 [0-9]: ").strip()

        if choice == "1":
            try:
                from scripts.genre.genre_loader import list_genres
                genres = list_genres()
                print(f"  Available genres ({len(genres)}):")
                for g in genres:
                    print(f"    {g}")
            except Exception as e:
                print(f"  [ERROR] {e}")
        elif choice == "2":
            try:
                from scripts.genre.style_loader import list_styles
                styles = list_styles()
                print(f"  Available styles ({len(styles)}):")
                for s in styles:
                    print(f"    {s}")
            except Exception as e:
                print(f"  [ERROR] {e}")
        elif choice == "3":
            try:
                from scripts.rag.rag_config import load_rag_config, get_rag_mode
                cfg = load_rag_config()
                mode = get_rag_mode(cfg)
                print(f"  RAG Mode: {mode}")
            except Exception as e:
                print(f"  RAG: FTS5 (default). Vector: unavailable ({e})")
        elif choice == "4":
            q = input("  问题: ").strip()
            if q:
                try:
                    from scripts.rag.rag_query import rag_query
                    result = rag_query(q)
                    print(f"  Mode: {result.get('mode', 'fts5')}")
                    for r in result.get("results", [])[:5]:
                        print(f"    [{r.get('chapter_no', '?')}] {r.get('evidence', '')[:80]}")
                except Exception as e:
                    print(f"  [ERROR] {e}")
        elif choice == "5":
            q = input("  问题: ").strip()
            if q:
                # Build a simple args-like object for cmd_query
                class _Args:
                    pass
                a = _Args()
                a.question = [q]
                cmd_query(a)
        elif choice == "6":
            class _Args:
                pass
            a = _Args()
            a.action = "list"
            a.rule = []
            cmd_learn(a)
        elif choice == "7":
            rule = input("  规则内容: ").strip()
            if rule:
                class _Args:
                    pass
                a = _Args()
                a.action = "add"
                a.rule = [rule]
                cmd_learn(a)
        elif choice == "8":
            fp = input("  章节号或文件路径: ").strip()
            if fp:
                cmd_wc(fp)
        elif choice == "9":
            cmd_board(None)
        elif choice == "0":
            break
        else:
            print("  无效选择，请重试。")


def cmd_chapters():
    """v0.6.5-clean7: 列出当前活跃 slot 的所有章节及字数."""
    import json as _json, sqlite3 as _sql
    ws = PROJECT_ROOT / "workspace"
    reg_file = ws / "registry.json"
    if not reg_file.exists():
        print("  workspace 未初始化。")
        return 1

    reg = _json.loads(reg_file.read_text(encoding="utf-8"))
    active = reg.get("active_slot", "")
    if not active:
        print("  没有活跃 slot。")
        return 1

    slot_dir = ws / active
    db_path = slot_dir / "novel.db"
    if not db_path.exists():
        print(f"  {active} 没有 novel.db")
        return 1

    conn = _sql.connect(str(db_path))
    conn.row_factory = _sql.Row
    rows = conn.execute(
        "SELECT chapter_no, title, word_count, status, created_at FROM chapters ORDER BY chapter_no"
    ).fetchall()
    # Also get novel title
    novel_row = conn.execute("SELECT title FROM novels LIMIT 1").fetchone()
    novel_title = novel_row["title"] if novel_row else active
    conn.close()

    print()
    print(f"  📖 {novel_title} ({active})")
    print(f"  " + "─" * 50)
    if not rows:
        print("  (暂无章节)")
    else:
        total_wc = 0
        for r in rows:
            total_wc += r["word_count"] or 0
            print(f"  第{r['chapter_no']:02d}章  {r['title'] or '(无标题)':20s}  {r['word_count'] or 0:>5,}字  [{r['status']}]")
        print(f"  " + "─" * 50)
        print(f"  共 {len(rows)} 章，{total_wc:,} 字")
    print()
    return 0


def cmd_menu_show():
    """v0.6.5-clean8: 普通用户菜单（纯文本）"""
    from scripts.hermes_menu import get_project_status, render_main_menu
    status = get_project_status()
    print(render_main_menu(status))
    return 0


def cmd_menu_text():
    """v0.6.5-clean8: 输出项目状态 JSON，供 Hermes 静默调用"""
    import json as _json
    from scripts.hermes_menu import get_project_status
    status = get_project_status()
    print(_json.dumps(status, ensure_ascii=False))
    return 0


def cmd_setup():
    """v0.6.5-clean7: 交互式设置 — 引导用户配置小说文件夹路径."""
    import json as _json
    cfg_file = PROJECT_ROOT / "config.json"

    print()
    print("  " + "=" * 55)
    print("  📁 项目设置 — 配置小说文件夹")
    print("  " + "=" * 55)
    print()

    # Read current
    try:
        cfg = _json.loads(cfg_file.read_text(encoding="utf-8"))
    except Exception:
        cfg = {"novels_root": "./novels", "paths": {}}

    current = cfg.get("novels_root", "未设置")
    print(f"  当前小说文件夹: {current}")
    print()
    print("  你的小说章节文件放在哪个文件夹？")
    print("  例如: D:\\小说  或  E:\\我的小说")
    print()
    print("  提示:")
    print("  · 文件夹下会自动创建「大纲/」「导出/」子目录")
    print("  · 每部小说会有自己的子文件夹")
    print("  · 可以随时修改")
    print()

    try:
        new_path = input("  请输入路径 (回车保留当前): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return 0

    if not new_path:
        print("  已取消，保持原设置。")
        return 0

    # Validate
    from pathlib import Path
    p = Path(new_path)
    if not p.is_absolute():
        print(f"  ⚠️ 请输入完整路径（如 D:\\小说），不要用相对路径。")
        return 1

    # Create directory if needed
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"  ⚠️ 无法创建目录: {e}")

    # Save
    if "paths" not in cfg:
        cfg["paths"] = {}
    cfg["novels_root"] = str(p)
    cfg["paths"]["novels_root"] = str(p)
    cfg_file.write_text(_json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"  ✅ 小说文件夹已设置为: {p}")
    print(f"     每部小说一个子文件夹，大纲、章节、导出都在里面")
    print()
    print(f"  现在把大纲.txt放到小说文件夹（如 {p / '旧楼深处/大纲.txt'}），")
    print(f"  然后运行 python novel.py outline add")
    print()
    return 0


def cmd_menu():
    """交互式文本菜单 — 用 input() 实现的纯终端菜单。"""
    while True:
        _menu_show_header()

        print("  主菜单:")
        print("  " + "─" * 40)
        print("  [1] 新手检查      项目初始化、状态诊断、演示")
        print("  [2] 数据库管理    DB slot 创建/切换/备份/恢复")
        print("  [3] 大纲管理      添加/列出/切换/对比/回滚")
        print("  [4] 写作流程      pre → 写作 → post → review")
        print("  [5] Agent 陪审团   AI 审查（light / full 模式）")
        print("  [6] Story Contract 故事合同系统")
        print("  [7] 报告与导出    守卫报告、导出小说")
        print("  [8] 操作手册      打印完整中文手册")
        print("  [9] 高级命令      genre/style/RAG/learn/query")
        print("  [S] 项目设置      设置小说文件夹路径")
        print("  [0] 退出")
        print()
        choice = input("  请选择 [0-9/S]: ").strip()

        if choice == "1":
            # 新手检查
            while True:
                print()
                print("  " + "─" * 50)
                print("  【新手检查】")
                print("  " + "─" * 50)
                print("  [1] init        初始化项目")
                print("  [2] status      环境诊断")
                print("  [3] status --detail  详细诊断")
                print("  [4] demo        运行演示")
                print("  [5] board       项目看板")
                print("  [0] 返回主菜单")
                print()
                sub = input("  请选择 [0-5]: ").strip()
                if sub == "1":
                    cmd_init()
                elif sub == "2":
                    cmd_status(detail=False)
                elif sub == "3":
                    cmd_status(detail=True)
                elif sub == "4":
                    cmd_demo()
                elif sub == "5":
                    cmd_board(None)
                elif sub == "0":
                    break
                else:
                    print("  无效选择，请重试。")

        elif choice == "2":
            _menu_db_management()

        elif choice == "3":
            _menu_outline_management()

        elif choice == "4":
            _menu_writing_flow()

        elif choice == "5":
            _menu_agents()

        elif choice == "6":
            _menu_story_contract()

        elif choice == "7":
            _menu_reports_exports()

        elif choice == "8":
            print()
            cmd_scc_help()

        elif choice == "9":
            _menu_advanced()

        elif choice.upper() == "S":
            cmd_setup()

        elif choice.upper() == "C":
            cmd_chapters()

        elif choice == "0":
            print()
            print("  再见！")
            print()
            break

        else:
            print("  无效选择，请重试。")

    return 0

