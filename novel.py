#!/usr/bin/env python3
"""
novel.py — CLI entry point v0.7.2

Thin CLI parser. All command implementations live in src/cli/.
"""
import sys
import argparse
from pathlib import Path

# ── Path setup ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent

# ── Import command modules ──────────────────────────────────
from version import get_version
from src.cli.shared import _load_project_config
from src.cli.commands_status import main as status_main
from src.cli.commands_core import (
    cmd_report, cmd_guards, cmd_check, cmd_wc, cmd_init,
    cmd_genre, cmd_style,
)
from src.cli.commands_demo import cmd_demo
from src.cli.commands_pipeline import cmd_pre, cmd_post, cmd_review, cmd_export, cmd_revise
from src.cli.commands_agents import cmd_agents
from src.cli.commands_memory import cmd_rag, cmd_query, cmd_learn
from src.cli.commands_story import cmd_story
from src.cli.commands_diagnostic import cmd_board, cmd_stability_check
from src.cli.commands_menu import (
    cmd_scc_help, cmd_menu_show, cmd_menu_text, cmd_menu,
    cmd_chapters, cmd_setup,
)
from src.cli.commands_db import cmd_db
from src.cli.commands_outline import cmd_outline
from src.cli.commands_voice import cmd_voice
from src.cli.commands_character import cmd_character
from src.cli.commands_texture import cmd_texture
from src.cli.commands_context import cmd_context
from src.cli.commands_worldbuilding import cmd_worldbuilding
from src.cli.commands_plot_threads import cmd_plot_threads
from src.cli.commands_promises import cmd_promises
from src.cli.commands_arc import cmd_arc


# ── CLI Parser ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description=f"Novel Forge - 小说引擎 {get_version()} CLI",
    )
    parser.add_argument('--version', action='version',
                        version=f'Novel Forge - 小说引擎 {get_version()}')
    sub = parser.add_subparsers(dest="command", help="Command to run")

    # status / doctor
    p_status = sub.add_parser("status", help="Run environment diagnostics")
    p_status.add_argument("--detail", action="store_true", help="Show detailed output")
    p_doctor = sub.add_parser("doctor", help="Run detailed environment diagnostics (alias for status --detail)")
    p_doctor.add_argument("--detail", action="store_true", default=True)

    # demo / init / setup / chapters
    sub.add_parser("demo", help="Run demo pipeline")
    sub.add_parser("init", help="Initialize project directories and database")
    sub.add_parser("setup", help="Set novel folder path")
    sub.add_parser("chapters", help="List all chapters of current novel")

    # pre / post / review
    p_pre = sub.add_parser("pre", help="Generate pre-write task card")
    p_pre.add_argument("chapter_no", nargs="?", help="Chapter number")
    p_pre.add_argument("--slug", help="Novel slug")
    p_pre.add_argument("--volume", help="Volume number")

    p_post = sub.add_parser("post", help="Post-write: run guards and ingest")
    p_post.add_argument("chapter_no", nargs="?", help="Chapter number")
    p_post.add_argument("--slug", help="Novel slug")
    p_post.add_argument("--volume", help="Volume number")
    p_post.add_argument("--file", help="Direct chapter file path")
    p_post.add_argument("--story", action="store_true", help="Auto-generate story commit after post")
    p_post.add_argument("--no-jury", action="store_true", help="Skip auto agent jury after post")
    p_post.add_argument("--skip-pre", action="store_true", help="Skip pre gate entirely (chapter already written)")

    p_review = sub.add_parser("review", help="Run guard review on a chapter")
    p_review.add_argument("chapter_no", nargs="?", help="Chapter number")
    p_review.add_argument("--slug", help="Novel slug")
    p_review.add_argument("--volume", help="Volume number")

    p_revise = sub.add_parser("revise", help="修订系统: 自动改稿 (从告警→改稿→diff)")
    p_revise.add_argument("chapter_no", nargs="?", help="Chapter number")
    p_revise.add_argument("--mode", default="controlled", choices=["controlled", "suggest"],
                          help="controlled=全闭环改写, suggest=仅生成任务不改写")
    p_revise.add_argument("--approve", action="store_true",
                          help="跳过人工确认, 自动覆盖原文 (谨慎使用)")
    p_revise.add_argument("--slug", help="Novel slug")
    p_revise.add_argument("--volume", help="Volume number")

    # report / guards / check / wc
    sub.add_parser("report", help="Show recent guard reports")
    sub.add_parser("guards", help="List registered guards")
    p_check = sub.add_parser("check", help="Run guard checks on a chapter file")
    p_check.add_argument("file_path", help="Path to chapter TXT file")
    p_wc = sub.add_parser("wc", help="Count Chinese characters in a chapter file")
    p_wc.add_argument("file_path", nargs="?", help="Path to chapter TXT file")

    # agents
    p_agents = sub.add_parser("agents", help="Multi-agent review board")
    p_agents_sub = p_agents.add_subparsers(dest="agents_action")
    p_agents_review = p_agents_sub.add_parser("review", help="Run agent review on a chapter")
    p_agents_review.add_argument("chapter_no", nargs="?", help="Chapter number")
    p_agents_review.add_argument("--mode", default="light", choices=["light", "full"])
    p_agents_review.add_argument("--slug", help="Novel slug")
    p_agents_review.add_argument("--genre", help="Genre pack ID")
    p_agents_review.add_argument("--style", default=None, help="Style pack ID")
    p_agents_list = p_agents_sub.add_parser("list", help="List all available agents")
    p_agents_list.add_argument("--mode", default=None, help="Filter by mode")

    # rag
    p_rag = sub.add_parser("rag", help="Vector RAG (optional)")
    p_rag_sub = p_rag.add_subparsers(dest="rag_action")
    p_rag_sub.add_parser("status", help="Check RAG status")
    p_rag_query = p_rag_sub.add_parser("query", help="Query the novel database")
    p_rag_query.add_argument("question", nargs="*", help="Question to ask")

    # export
    p_export = sub.add_parser("export", help="Export novel to single file")
    p_export.add_argument("--slug", help="Novel slug to export")
    p_export.add_argument("--format", default="md", choices=["txt", "md"])

    # db
    p_db = sub.add_parser("db", help="Multi-DB workspace management")
    p_db_sub = p_db.add_subparsers(dest="db_action")
    p_db_sub.add_parser("list", help="列出所有 DB slot")
    p_db_sub.add_parser("current", help="显示当前活跃 DB slot")
    p_db_sub.add_parser("info", help="显示当前 slot 详细信息")
    p_db_new = p_db_sub.add_parser("new", help="创建新 DB slot")
    p_db_new.add_argument("--name", required=True, help="Slot 名称")
    p_db_new.add_argument("--description", default="", help="Slot 描述")
    p_db_use = p_db_sub.add_parser("use", help="切换到指定 DB slot")
    p_db_use.add_argument("slot_id", help="Slot ID (如 slot_001)")
    p_db_delete = p_db_sub.add_parser("delete", help="安全删除 DB slot (移至回收站)")
    p_db_delete.add_argument("slot_id", help="Slot ID")
    p_db_delete.add_argument("--yes", action="store_true", help="确认删除")
    p_db_sub.add_parser("trash", help="查看回收站中的 slot")
    p_db_restore = p_db_sub.add_parser("restore", help="从备份或回收站恢复 DB slot")
    p_db_restore.add_argument("slot_id", help="Slot ID 或回收站项目名")
    p_db_restore.add_argument("--backup-id", help="备份 ID")
    p_db_restore.add_argument("--from-trash", action="store_true", help="从回收站恢复")
    p_db_purge = p_db_sub.add_parser("purge", help="永久删除回收站中的 slot")
    p_db_purge.add_argument("trash_name", nargs="?", default=None, help="回收站项目名")
    p_db_backup = p_db_sub.add_parser("backup", help="备份当前 DB slot")
    p_db_backup.add_argument("--slot", help="Slot ID (默认当前活跃)")
    p_db_init = p_db_sub.add_parser("init", help="初始化 workspace 目录结构")
    p_db_init.add_argument("--force", action="store_true", help="强制重新初始化")

    # outline
    p_outline = sub.add_parser("outline", help="大纲管理")
    p_outline_sub = p_outline.add_subparsers(dest="outline_action")
    p_outline_add = p_outline_sub.add_parser("add", help="添加大纲")
    p_outline_add.add_argument("outline_file", nargs="?", default="", help="大纲文件路径")
    p_outline_add.add_argument("--title", default="", help="大纲标题")
    p_outline_add.add_argument("--genre", default="", help="题材")
    p_outline_add.add_argument("--style", default="", help="风格")
    p_outline_add.add_argument("--replace-current", action="store_true", help="替换当前激活大纲")
    p_outline_add.add_argument("--keep-inactive", action="store_true", help="保存但不激活")
    p_outline_add.add_argument("--dry-run", action="store_true", help="仅显示相似度分析")
    p_outline_import = p_outline_sub.add_parser("import", help="导入大纲")
    p_outline_import.add_argument("outline_file", help="大纲文件路径")
    p_outline_import.add_argument("--title", required=True, help="大纲标题")
    p_outline_import.add_argument("--genre", default="", help="题材")
    p_outline_import.add_argument("--style", default="", help="风格")
    p_outline_sub.add_parser("list", help="列出所有大纲")
    p_outline_sub.add_parser("current", help="显示当前激活大纲")
    p_outline_switch = p_outline_sub.add_parser("switch", help="切换激活大纲")
    p_outline_switch.add_argument("outline_id", help="大纲 ID")
    p_outline_diff = p_outline_sub.add_parser("diff", help="对比两个大纲")
    p_outline_diff.add_argument("id1", help="大纲1 ID")
    p_outline_diff.add_argument("id2", help="大纲2 ID")
    p_outline_rollback = p_outline_sub.add_parser("rollback", help="回滚大纲")
    p_outline_rollback.add_argument("outline_id", help="大纲 ID")
    p_outline_compare = p_outline_sub.add_parser("compare", help="对比文件与当前大纲")
    p_outline_compare.add_argument("compare_file", help="文件路径")
    p_outline_delete = p_outline_sub.add_parser("delete", help="删除大纲")
    p_outline_delete.add_argument("delete_id", help="大纲 ID")
    p_outline_sub.add_parser("undo", help="撤销最近一次添加")
    p_outline_sub.add_parser("mental-scan", help="从大纲扫描角色精神状态")

    # story
    p_story = sub.add_parser("story", help="Story contract system")
    p_story_sub = p_story.add_subparsers(dest="story_action")
    p_story_sub.add_parser("init", help="Initialize .story/ directory")
    p_story_sub_contract = p_story_sub.add_parser("contract", help="Generate chapter contract")
    p_story_sub_contract.add_argument("chapter_no", nargs="?", default="1")
    p_story_sub_commit = p_story_sub.add_parser("commit", help="Generate chapter commit")
    p_story_sub_commit.add_argument("chapter_no", nargs="?", default="1")
    p_story_sub.add_parser("health", help="Check story chain health")
    # story arc — cross-chapter continuity tracking
    p_story_arc = p_story_sub.add_parser("arc", help="Story arc continuity tracking")
    p_arc_sub = p_story_arc.add_subparsers(dest="arc_action")
    p_arc_check = p_arc_sub.add_parser("check", help="Run full arc break detection")
    p_arc_check.add_argument("--min", dest="min_chapter", type=int, default=1, help="Start chapter")
    p_arc_check.add_argument("--max", dest="max_chapter", type=int, default=None, help="End chapter")
    p_arc_check.add_argument("--type", dest="check_type", help="Check types: physical,emotional,item,promise,thread")
    p_arc_show = p_arc_sub.add_parser("show", help="Show arc state for a chapter")
    p_arc_show.add_argument("chapter_no", help="Chapter number")
    p_arc_char = p_arc_sub.add_parser("character", help="Show character arc timeline")
    p_arc_char.add_argument("character_name", help="Character name")
    p_arc_item = p_arc_sub.add_parser("item", help="Track item lifecycle")
    p_arc_item.add_argument("item_name", help="Item name")
    p_arc_sub.add_parser("timeline", help="Show combined arc timeline")
    p_arc_sub.add_parser("report", help="Generate arc health report")

    # query / learn / board
    p_query = sub.add_parser("query", help="Query project memory")
    p_query.add_argument("question", nargs="*", help="Natural language question")
    p_learn = sub.add_parser("learn", help="Writing rules learned")
    p_learn.add_argument("action", nargs="?", default="list")
    p_learn.add_argument("rule", nargs="*", help="Rule text to add")
    sub.add_parser("board", help="Readonly status board")

    # genre / style
    p_genre = sub.add_parser("genre", help="Genre pack management")
    p_genre_sub = p_genre.add_subparsers(dest="genre_action")
    p_genre_sub.add_parser("list", help="List available genres")
    p_genre_show = p_genre_sub.add_parser("show", help="Show genre pack details")
    p_genre_show.add_argument("genre_id", help="Genre ID")
    p_style = sub.add_parser("style", help="Style pack management")
    p_style_sub = p_style.add_subparsers(dest="style_action")
    p_style_sub.add_parser("list", help="List available styles")
    p_style_show = p_style_sub.add_parser("show", help="Show style pack details")
    p_style_show.add_argument("style_id", help="Style ID")

    # help / menu / aliases
    sub.add_parser("scc-help", help="打印中文操作手册")
    sub.add_parser("help", help="打印中文操作手册 (同 scc-help)")
    sub.add_parser("menu", help="进入交互式文本菜单")
    p_sc = sub.add_parser("stability-check", help="运行稳定性自检")
    p_sc.add_argument("--full", action="store_true", help="完整模式")
    sub.add_parser("menu-show", help="显示普通用户菜单")
    sub.add_parser("menu-text", help="输出项目状态 JSON")
    # voice 声纹卡管理
    p_voice = sub.add_parser("voice", help="角色声纹卡管理")
    p_voice_sub = p_voice.add_subparsers(dest="voice_action")
    p_voice_sub.add_parser("list", help="列出当前小说所有声纹卡")
    p_voice_show = p_voice_sub.add_parser("show", help="查看声纹卡详情")
    p_voice_show.add_argument("character_name", help="角色名")
    p_voice_create = p_voice_sub.add_parser("create", help="创建声纹卡")
    p_voice_create.add_argument("character_name", help="角色名")
    p_voice_delete = p_voice_sub.add_parser("delete", help="删除声纹卡")
    p_voice_delete.add_argument("character_name", help="角色名")
    p_voice_check = p_voice_sub.add_parser("check", help="检测章节声纹一致性")
    p_voice_check.add_argument("chapter_no", help="章节号")
    p_voice_set = p_voice_sub.add_parser("set", help="声纹卡组管理")

    p_voice_set_sub = p_voice_set.add_subparsers(dest="voice_set_action")
    p_voice_set_sub.add_parser("list", help="列出声纹卡组")
    p_voice_set_use = p_voice_set_sub.add_parser("use", help="切换声纹卡组")
    p_voice_set_use.add_argument("set_name", help="卡组名")
    p_voice_outline_check = p_voice_sub.add_parser("outline-check", help="从大纲检查所有角色声纹状态")
    p_voice_outline_check.add_argument("--create", action="store_true", dest="create_missing",
                                       help="同时为缺失声纹卡的角色创建默认声纹卡")
    # character 角色综合管理
    p_char = sub.add_parser("character", help="角色综合管理（声纹+性格+做事风格）")
    p_char_sub = p_char.add_subparsers(dest="character_action")
    p_char_sub.add_parser("list", help="列出所有角色卡")
    p_char_show = p_char_sub.add_parser("show", help="查看完整角色卡")
    p_char_show.add_argument("character_name", help="角色名")
    p_char_create = p_char_sub.add_parser("create", help="创建默认角色卡")
    p_char_create.add_argument("character_name", help="角色名")
    p_char_delete = p_char_sub.add_parser("delete", help="删除角色卡")
    p_char_delete.add_argument("character_name", help="角色名")
    p_char_edit = p_char_sub.add_parser("edit", help="编辑角色字段")
    p_char_edit.add_argument("character_name", help="角色名")
    p_char_edit.add_argument("field", help="字段名（如 core / habits / dialect）")
    p_char_edit.add_argument("value", help="字段值")
    p_char_oc = p_char_sub.add_parser("outline-check", help="从大纲检查所有角色卡状态")
    p_char_oc.add_argument("--create", action="store_true", dest="create_missing",
                           help="同时为缺失角色卡的角色创建默认卡")
    # character: relate
    p_relate = p_char_sub.add_parser("relate", help="设置角色关系")
    p_relate.add_argument("char_a", help="角色A")
    p_relate.add_argument("char_b", help="角色B")
    p_relate.add_argument("relation_type", help="关系类型（如 知己/对立/师徒）")
    # character: unrelate
    p_unrelate = p_char_sub.add_parser("unrelate", help="删除角色关系")
    p_unrelate.add_argument("char_a", help="角色A")
    p_unrelate.add_argument("char_b", help="角色B")
    # character: relation-graph
    p_char_sub.add_parser("relation-graph", help="文本角色关系图谱")
    # character: export
    p_export = p_char_sub.add_parser("export", help="导出角色卡")
    p_export.add_argument("character_name", help="角色名")
    p_export.add_argument("output_path", nargs="?", default="", help="输出文件路径")
    # character: import
    p_import = p_char_sub.add_parser("import", help="导入角色卡")
    p_import.add_argument("input_path", help="JSON文件路径")
    # character: focus
    p_focus = p_char_sub.add_parser("focus", help="设置角色聚焦状态")
    p_focus.add_argument("character_name", help="角色名")
    p_focus.add_argument("focus_state", help="活跃/暂离/退场")
    # character: arc-check
    p_char_sub.add_parser("arc-check", help="弧线进度检查")
    # character: sync-story
    p_char_sub.add_parser("sync-story", help="同步角色卡到故事合同系统")
    # character: chapters
    p_char_chapters = p_char_sub.add_parser("chapters", help="查角色在哪些章节出场")
    p_char_chapters.add_argument("character_name", help="角色名")
    # character: check (综合风格检测)
    p_char_check = p_char_sub.add_parser("check", help="综合角色风格检测（6项弹性检查）")
    p_char_check.add_argument("chapter_no", help="章节号")
    p_char_check.add_argument("--intensity", default="normal",
                              choices=["light", "normal", "strict"],
                              help="检测强度: light/normal/strict")
    # character: mental 精神状态管理
    p_char_mental = p_char_sub.add_parser("mental", help="角色精神状态管理（第四层）")
    p_char_mental.add_argument("character_name", nargs="?", default="", help="角色名")
    p_char_mental.add_argument("mental_action", nargs="?", default="show",
                               help="操作: show/set/onset/trigger/manifest/check")
    p_char_mental.add_argument("mental_arg1", nargs="?", default="", help="类别或章节号")
    p_char_mental.add_argument("mental_arg2", nargs="?", default="", help="严重度或文本")
    # character: mental-scan
    p_char_sub.add_parser("mental-scan", help="从大纲扫描推荐角色精神状态")
    # texture 人工味质量层
    p_tx = sub.add_parser("texture", help="人工味质量层检测")
    p_tx_sub = p_tx.add_subparsers(dest="texture_action")
    p_tx_check = p_tx_sub.add_parser("check", help="对章节运行全部质量检测")
    p_tx_check.add_argument("chapter_no", help="章节号")
    p_tx_check.add_argument("--genre", default=None, help="题材类型，如 xianxia/romance/urban")
    p_tx_check.add_argument("--pace", default="normal",
                          choices=["breathing","setup","normal","accelerate","climax"],
                          help="章节速度: breathing/setup/normal/accelerate/climax")
    # worldbuilding 世界观管理
    p_wb = sub.add_parser("worldbuilding", help="世界观管理")
    p_wb_sub = p_wb.add_subparsers(dest="worldbuilding_action")
    p_wb_sub.add_parser("list", help="列出所有世界观条目")
    p_wb_show = p_wb_sub.add_parser("show", help="查看完整世界观条目")
    p_wb_show.add_argument("title", help="条目标题")
    p_wb_add = p_wb_sub.add_parser("add", help="添加世界观条目")
    p_wb_add.add_argument("title", help="条目标题")
    p_wb_add.add_argument("--category", default="", help="分类 (如 地理/修炼体系)")
    p_wb_add.add_argument("--content", default="", help="详细描述")
    p_wb_add.add_argument("--importance", type=int, default=3, choices=range(1, 6), help="重要度 1-5")
    p_wb_add.add_argument("--tags", default="", help="逗号分隔标签")
    p_wb_edit = p_wb_sub.add_parser("edit", help="编辑世界观条目")
    p_wb_edit.add_argument("title", help="条目标题")
    p_wb_edit.add_argument("field", help="字段名 (category/content/importance/tags)")
    p_wb_edit.add_argument("value", help="字段值")
    p_wb_delete = p_wb_sub.add_parser("delete", help="删除世界观条目")
    p_wb_delete.add_argument("title", help="条目标题")
    p_wb_sub.add_parser("outline-scan", help="从大纲扫描世界观关键词")
    # plot-threads 情节线管理
    p_pt = sub.add_parser("plot-threads", help="情节线管理")
    p_pt_sub = p_pt.add_subparsers(dest="plot_threads_action")
    p_pt_sub.add_parser("list", help="列出所有情节线索")
    p_pt_show = p_pt_sub.add_parser("show", help="查看完整情节线索")
    p_pt_show.add_argument("title", help="线索名称")
    p_pt_create = p_pt_sub.add_parser("create", help="创建情节线索")
    p_pt_create.add_argument("title", help="线索名称")
    p_pt_create.add_argument("--type", dest="thread_type", default="伏笔", help="类型 (伏笔/主线/支线/感情线/成长线)")
    p_pt_create.add_argument("--content", default="", help="详细描述")
    p_pt_create.add_argument("--importance", type=int, default=3, choices=range(1, 6), help="重要度 1-5")
    p_pt_create.add_argument("--chapter", type=int, default=None, help="起始章号")
    p_pt_edit = p_pt_sub.add_parser("edit", help="编辑情节线索")
    p_pt_edit.add_argument("title", help="线索名称")
    p_pt_edit.add_argument("field", help="字段名 (thread_type/content/importance/introduced_chapter/resolved_chapter)")
    p_pt_edit.add_argument("value", help="字段值")
    p_pt_close = p_pt_sub.add_parser("close", help="标记线索已完结")
    p_pt_close.add_argument("title", help="线索名称")
    p_pt_close.add_argument("--chapter", type=int, default=None, help="完结章号")
    p_pt_advance = p_pt_sub.add_parser("advance", help="标记某章推进了该线索")
    p_pt_advance.add_argument("chapter_no", help="章号")
    p_pt_advance.add_argument("title", help="线索名称")
    p_pt_sub.add_parser("timeline", help="线索时间线")
    # promises 读者承诺管理
    p_pr = sub.add_parser("promises", help="读者承诺管理")
    p_pr_sub = p_pr.add_subparsers(dest="promises_action")
    p_pr_list = p_pr_sub.add_parser("list", help="列出读者承诺")
    p_pr_list.add_argument("--status", default="open", choices=["open", "all"], help="过滤状态 (默认 open)")
    p_pr_add = p_pr_sub.add_parser("add", help="添加读者承诺")
    p_pr_add.add_argument("description", help="承诺描述")
    p_pr_add.add_argument("--chapter", type=int, default=None, help="提出章号")
    p_pr_add.add_argument("--importance", type=int, default=3, choices=range(1, 6), help="重要度 1-5")
    p_pr_fulfill = p_pr_sub.add_parser("fulfill", help="标记承诺已兑现")
    p_pr_fulfill.add_argument("id", help="承诺 ID")
    p_pr_fulfill.add_argument("chapter_no", help="兑现章号")
    p_pr_break = p_pr_sub.add_parser("break", help="标记承诺已作废")
    p_pr_break.add_argument("id", help="承诺 ID")
    p_pr_check = p_pr_sub.add_parser("check", help="检查长期未兑现的承诺")
    p_pr_check.add_argument("--threshold", type=int, default=20, help="章数阈值 (默认 20)")
    # context 章节上下文管理
    p_ctx = sub.add_parser("context", help="章节上下文管理")
    p_ctx_sub = p_ctx.add_subparsers(dest="context_action")
    p_ctx_show = p_ctx_sub.add_parser("show", help="查看某章上下文")
    p_ctx_show.add_argument("chapter_no", nargs="?", default=None, help="章节号（默认最新）")
    p_ctx_sub.add_parser("pack", help="生成全部章节压缩包")
    p_ctx_sub.add_parser("gap", help="检测上下文断层")

    # ── Dispatch ────────────────────────────────────────────
    args = parser.parse_args()

    if args.command is None:
        print("=" * 50)
        print(f"  Novel Forge - 小说引擎 {get_version()}")
        print("=" * 50)
        print()
        print("  你现在可以：")
        print()
        print("  0. 首次使用   →  python novel.py setup     # 设置小说文件夹")
        print("  详细帮助 →  python novel.py help")
        print("  交互菜单 →  python novel.py menu")
        print("=" * 50)
        return

    dispatch = {
        "status": lambda: sys.exit(status_main()),
        "doctor": lambda: sys.exit(status_main()),
        "demo": lambda: sys.exit(cmd_demo()),
        "init": lambda: sys.exit(cmd_init()),
        "setup": lambda: sys.exit(cmd_setup()),
        "chapters": lambda: sys.exit(cmd_chapters()),
        "pre": lambda: sys.exit(cmd_pre(
            getattr(args, "chapter_no", None),
            getattr(args, "slug", None),
            getattr(args, "volume", None))),
        "post": lambda: sys.exit(cmd_post(
            getattr(args, "chapter_no", None),
            getattr(args, "slug", None),
            getattr(args, "volume", None),
            getattr(args, "file", None),
            getattr(args, "story", False),
            getattr(args, "no_jury", False),
            getattr(args, "skip_pre", False))),
        "review": lambda: sys.exit(cmd_review(
            getattr(args, "chapter_no", None),
            getattr(args, "slug", None),
            getattr(args, "volume", None))),
        "revise": lambda: sys.exit(cmd_revise(
            getattr(args, "chapter_no", None),
            getattr(args, "mode", "controlled"),
            getattr(args, "approve", False),
            getattr(args, "slug", None),
            getattr(args, "volume", None))),
        "report": lambda: sys.exit(cmd_report()),
        "guards": lambda: sys.exit(cmd_guards()),
        "check": lambda: sys.exit(cmd_check(args.file_path)),
        "wc": lambda: sys.exit(cmd_wc(getattr(args, "file_path", None))),
        "agents": lambda: sys.exit(cmd_agents(args)),
        "rag": lambda: sys.exit(cmd_rag(args)),
        "export": lambda: sys.exit(cmd_export(getattr(args, "slug", None), getattr(args, "format", "md"))),
        "story": lambda: sys.exit(cmd_story(args)),
        "query": lambda: sys.exit(cmd_query(args)),
        "learn": lambda: sys.exit(cmd_learn(args)),
        "board": lambda: sys.exit(cmd_board(args)),
        "genre": lambda: sys.exit(cmd_genre(args)),
        "style": lambda: sys.exit(cmd_style(args)),
        "db": lambda: sys.exit(cmd_db(args)),
        "outline": lambda: sys.exit(cmd_outline(args)),
        "scc-help": lambda: sys.exit(cmd_scc_help()),
        "help": lambda: sys.exit(cmd_scc_help()),
        "menu": lambda: sys.exit(cmd_menu()),
        "stability-check": lambda: sys.exit(cmd_stability_check(args)),
        "menu-show": lambda: sys.exit(cmd_menu_show()),
        "menu-text": lambda: sys.exit(cmd_menu_text()),
        "voice": lambda: sys.exit(cmd_voice(args)),
        "character": lambda: sys.exit(cmd_character(args)),
        "texture": lambda: sys.exit(cmd_texture(args)),
        "context": lambda: sys.exit(cmd_context(args)),
        "worldbuilding": lambda: sys.exit(cmd_worldbuilding(args)),
        "plot-threads": lambda: sys.exit(cmd_plot_threads(args)),
        "promises": lambda: sys.exit(cmd_promises(args)),
    }

    if args.command in dispatch:
        dispatch[args.command]()
    else:
        print(f"未知命令: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass
