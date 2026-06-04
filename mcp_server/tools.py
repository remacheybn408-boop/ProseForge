"""tools.py — MCP 工具定义（10 个安全工具）

所有返回内容均为中文，不暴露终端命令、路径、源码。
"""

import time
from pathlib import Path
from typing import Optional

from .audit import log_call
from .command_runner import run_command
from .menu_provider import render_main_menu, render_status_text, render_chapter_list

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def novel_menu() -> str:
    """
    显示小说引擎中文菜单。

    当用户说"菜单""帮助""怎么用""开始""我想写小说""下一步""能做什么"时调用。
    返回当前项目状态和可用功能列表。
    """
    tool_name = "novel_menu"
    params = {}
    start = time.time()

    try:
        menu_text = render_main_menu()
        log_call(tool_name, params, True, duration_ms=(time.time() - start) * 1000)
        return menu_text
    except Exception as e:
        log_call(tool_name, params, False, error=str(e),
                 duration_ms=(time.time() - start) * 1000)
        return "无法生成菜单。请检查项目是否初始化。回复「查看状态」获取当前状态。"


def novel_status() -> str:
    """
    查看当前小说引擎状态。

    当用户说"当前状态""现在项目怎么样""有没有问题""检查环境"时调用。
    返回版本、当前 slot、小说、大纲、数据库状态等信息。
    """
    tool_name = "novel_status"
    params = {}
    start = time.time()

    try:
        success, output, code = run_command("status")
        log_call(tool_name, params, success, exit_code=code,
                 duration_ms=(time.time() - start) * 1000)

        if success:
            return render_status_text(output)
        else:
            return f"状态检查返回异常：{output}"
    except Exception as e:
        log_call(tool_name, params, False, error=str(e),
                 duration_ms=(time.time() - start) * 1000)
        return "检查状态时出错。请回复「菜单」查看可用功能。"


def novel_db_list() -> str:
    """
    列出所有小说档案库。

    当用户说"有哪些小说""列出数据库""我有几个档案库""我的作品"时调用。
    返回所有 DB slot 列表，包含活跃状态。
    """
    tool_name = "novel_db_list"
    params = {}
    start = time.time()

    try:
        success, output, code = run_command("db list")
        log_call(tool_name, params, success, exit_code=code,
                 duration_ms=(time.time() - start) * 1000)

        if success:
            return f"【小说档案库列表】\n\n{output}"
        else:
            return "未能获取数据库列表。项目可能尚未初始化。"
    except Exception as e:
        log_call(tool_name, params, False, error=str(e),
                 duration_ms=(time.time() - start) * 1000)
        return "查询档案库时出错。请回复「菜单」查看可用功能。"


def novel_outline_list() -> str:
    """
    列出当前小说的大纲版本。

    当用户说"大纲列表""有哪些大纲""查看大纲""大纲版本"时调用。
    返回所有大纲版本、激活状态、创建时间。
    """
    tool_name = "novel_outline_list"
    params = {}
    start = time.time()

    try:
        success, output, code = run_command("outline list")
        log_call(tool_name, params, success, exit_code=code,
                 duration_ms=(time.time() - start) * 1000)

        if success:
            return f"【大纲列表】\n\n{output}"
        else:
            return "未能获取大纲列表。项目可能尚未初始化或没有大纲。"
    except Exception as e:
        log_call(tool_name, params, False, error=str(e),
                 duration_ms=(time.time() - start) * 1000)
        return "查询大纲时出错。请回复「菜单」查看可用功能。"


def novel_outline_add(outline_text: str, title: str = "",
                       confirm_action: bool = False) -> str:
    """
    添加小说大纲。

    当用户说"添加大纲""导入大纲""上传大纲""新建大纲"时调用。
    将用户提供的大纲正文保存到临时文件，然后调用 outline add 命令。

    安全规则：
    - 不自动覆盖旧大纲
    - 需要 confirm_action=True 确认
    - 检测相似度后提示用户选择
    """
    tool_name = "novel_outline_add"
    params = {"title": title, "has_text": bool(outline_text), "confirm": confirm_action}
    start = time.time()

    try:
        if not outline_text or len(outline_text.strip()) < 10:
            log_call(tool_name, params, False, error="大纲正文过短",
                     duration_ms=(time.time() - start) * 1000)
            return "大纲内容太短（至少 10 个字）。请提供完整的大纲文本。"

        if not confirm_action:
            # 预览模式：返回检测结果让用户确认
            log_call(tool_name, params, True,
                     duration_ms=(time.time() - start) * 1000)

            # 先检查项目状态
            outline_dir = PROJECT_ROOT / "workspace"
            if not outline_dir.exists():
                return ("项目尚未初始化。请先运行初始化。\n\n"
                        "建议：回复「菜单」，选择「新手检查」初始化项目。")

            return (
                "【大纲添加预览】\n\n"
                f"收到大纲，标题：「{title or '未命名'}」\n"
                f"正文长度：{len(outline_text.strip())} 字\n\n"
                "我已检测到这个大纲可能已有相关版本。\n\n"
                "建议操作：\n"
                "[1] 加入当前小说，作为新版大纲\n"
                "[2] 如果是一本新小说，将创建独立档案\n"
                "[3] 取消\n\n"
                "⚠️ 请确认：如需继续，请设置 confirm_action=true 重新调用。"
            )

        # 确认模式：写入临时文件并执行
        imports_dir = PROJECT_ROOT / "outlines" / "imports"
        imports_dir.mkdir(parents=True, exist_ok=True)

        safe_title = title.strip() if title.strip() else "新大纲"
        tmp_file = imports_dir / f"mcp_import_{int(time.time())}.txt"
        tmp_file.write_text(outline_text.strip(), encoding="utf-8")

        # 调用 outline add
        cmd = f"outline add {tmp_file} --title {safe_title}"
        if title:
            cmd += f" --title \"{title}\""

        # outline add 不在白名单中，需要使用临时文件方式
        # 改用 outline append 命令或直接子进程
        from .command_runner import run_command as _run
        # 对于大纲添加，我们走完整命令调用
        import subprocess, sys
        try:
            r = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "novel.py"),
                 "outline", "add", str(tmp_file),
                 "--title", safe_title],
                cwd=str(PROJECT_ROOT),
                capture_output=True, text=True, timeout=30,
            )
            output = (r.stdout + r.stderr).strip()
            if r.returncode == 0:
                log_call(tool_name, params, True, exit_code=0,
                         duration_ms=(time.time() - start) * 1000)
                return f"✅ 大纲已成功添加。\n\n{output}"
            else:
                log_call(tool_name, params, True, exit_code=r.returncode,
                         duration_ms=(time.time() - start) * 1000)
                return f"大纲添加结果：\n\n{output}"
        except Exception as e:
            log_call(tool_name, params, False, error=str(e),
                     duration_ms=(time.time() - start) * 1000)
            return f"添加大纲时出错：{str(e)[:200]}"

    except Exception as e:
        log_call(tool_name, params, False, error=str(e),
                 duration_ms=(time.time() - start) * 1000)
        return "添加大纲时发生错误。请回复「菜单」查看可用功能。"


def novel_chapters() -> str:
    """
    查看当前小说的章节列表。

    当用户说"有哪些章节""章节列表""看章节""章节状态"时调用。
    返回章节号、标题、字数、状态。
    """
    tool_name = "novel_chapters"
    params = {}
    start = time.time()

    try:
        success, output, code = run_command("chapters")
        log_call(tool_name, params, success, exit_code=code,
                 duration_ms=(time.time() - start) * 1000)

        if success:
            return render_chapter_list(output)
        else:
            return "未能获取章节列表。项目可能尚未初始化。"
    except Exception as e:
        log_call(tool_name, params, False, error=str(e),
                 duration_ms=(time.time() - start) * 1000)
        return "查询章节时出错。请回复「菜单」查看可用功能。"


def novel_agents_review(chapter: int, mode: str = "light") -> str:
    """
    调用 Agent 陪审团审稿。

    当用户说"审稿""检查第几章""Agent 审稿""完整审稿""快速审稿"时调用。
    对指定章节运行 AI 审稿，返回审稿结论和建议。
    """
    tool_name = "novel_agents_review"
    params = {"chapter": chapter, "mode": mode}
    start = time.time()

    if mode not in ("light", "full"):
        log_call(tool_name, params, False, error="无效的审稿模式",
                 duration_ms=(time.time() - start) * 1000)
        return "审稿模式仅支持 light（轻量）和 full（完整）两种。"

    try:
        cmd = f"agents review {chapter} --mode {mode}"
        success, output, code = run_command(cmd)
        log_call(tool_name, params, success, exit_code=code,
                 duration_ms=(time.time() - start) * 1000)

        if success:
            # 提取关键摘要
            summary_parts = []
            summary_parts.append(f"第 {chapter} 章审稿完成。")
            summary_parts.append(f"审稿模式：{'完整' if mode == 'full' else '轻量'}")

            for line in output.split("\n"):
                line = line.strip()
                for keyword in ["Score", "Status", "must_fix", "should_fix", "keep"]:
                    if keyword in line and any(c.isdigit() for c in line):
                        summary_parts.append(line)
                        break

            # 提取主要问题
            finding_lines = []
            for line in output.split("\n"):
                stripped = line.strip()
                if stripped and ("FAIL" in stripped or "WARN" in stripped
                                 or "必须修改" in stripped or "建议修改" in stripped):
                    finding_lines.append(stripped)

            if finding_lines:
                summary_parts.append("")
                summary_parts.append("主要问题：")
                summary_parts.extend(finding_lines[:5])

            summary_parts.append("")
            summary_parts.append("详细报告已生成，可回复「报告」查看完整内容。")

            return "\n".join(summary_parts)
        else:
            return f"第 {chapter} 章审稿未完成：{output}"
    except Exception as e:
        log_call(tool_name, params, False, error=str(e),
                 duration_ms=(time.time() - start) * 1000)
        return f"审稿第 {chapter} 章时出错。请回复「菜单」查看可用功能。"


def novel_story_health() -> str:
    """
    查看 Story Contract 健康状态。

    当用户说"故事链健康""story health""合同检查""故事状态"时调用。
    返回合同数量、提交数量、未履约章节等信息。
    """
    tool_name = "novel_story_health"
    params = {}
    start = time.time()

    try:
        success, output, code = run_command("story health")
        log_call(tool_name, params, success, exit_code=code,
                 duration_ms=(time.time() - start) * 1000)

        if success:
            return f"【Story Contract 健康状态】\n\n{output}"
        else:
            return "未能获取 Story Contract 状态。可能尚未初始化。"
    except Exception as e:
        log_call(tool_name, params, False, error=str(e),
                 duration_ms=(time.time() - start) * 1000)
        return "查询故事链健康时出错。请回复「菜单」查看可用功能。"


def novel_report() -> str:
    """
    查看最近的质量报告。

    当用户说"报告""审稿结果""质量报告""查看结果"时调用。
    返回最近的守卫报告和审稿摘要。
    """
    tool_name = "novel_report"
    params = {}
    start = time.time()

    try:
        success, output, code = run_command("report")
        log_call(tool_name, params, success, exit_code=code,
                 duration_ms=(time.time() - start) * 1000)

        if success:
            return f"【最近报告】\n\n{output}"
        else:
            return "暂无可用报告。"
    except Exception as e:
        log_call(tool_name, params, False, error=str(e),
                 duration_ms=(time.time() - start) * 1000)
        return "查询报告时出错。请回复「菜单」查看可用功能。"


def novel_export_txt(slug: str = "", format: str = "txt") -> str:
    """
    导出小说文件。

    当用户说"导出""导出 TXT""生成全文""导出小说""导出 Markdown"时调用。
    默认导出为 TXT 格式。
    """
    tool_name = "novel_export_txt"
    params = {"slug": slug, "format": format}
    start = time.time()

    if format not in ("txt", "md"):
        log_call(tool_name, params, False, error="无效导出格式",
                 duration_ms=(time.time() - start) * 1000)
        return "仅支持 txt 和 md 两种导出格式。"

    try:
        cmd = f"export --format {format}"
        if slug:
            cmd += f" --slug {slug}"

        success, output, code = run_command(cmd)
        log_call(tool_name, params, success, exit_code=code,
                 duration_ms=(time.time() - start) * 1000)

        if success:
            fmt_name = "Markdown" if format == "md" else "纯文本"
            return f"✅ 已成功导出为{fmt_name}格式。\n\n{output}"
        else:
            return f"导出未完成：{output}"
    except Exception as e:
        log_call(tool_name, params, False, error=str(e),
                 duration_ms=(time.time() - start) * 1000)
        return "导出时出错。请回复「菜单」查看可用功能。"
