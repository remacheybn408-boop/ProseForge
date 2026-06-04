"""server.py — MCP 服务器入口

注册 10 个安全工具，通过 stdio 运行 MCP 协议。

启动方式（在项目根目录）：
  python -m mcp_server.server

测试连接方式（第二个终端）：
  python -c "
  import asyncio
  from mcp import StdioServerParameters
  from mcp.stdio_client import stdio_client

  async def test():
      async with stdio_client(StdioServerParameters(
          command='python', args=['-m', 'mcp_server.server']
      )) as (read, write):
          print('✅ MCP 服务器连接成功')

  asyncio.run(test())
  "
"""

import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import tools


mcp = FastMCP(
    name="novel-forge-mcp",
    instructions="小说引擎 MCP 桥接层 — 通过中文自然语言操作小说写作流水线",
)


# ── 注册 10 个安全工具 ──
# 使用 add_tool 注册现有函数，保留原始参数类型签名供 MCP 客户端自动识别。
mcp.add_tool(
    tools.novel_menu,
    name="novel_menu",
    description="显示小说引擎中文菜单。返回版本号、功能列表、当前项目状态。当用户说「菜单」「帮助」「怎么用」「开始」时调用。",
)
mcp.add_tool(
    tools.novel_status,
    name="novel_status",
    description="查看当前小说引擎状态。返回版本号、slot 信息、数据库状态、大纲和章节概览。当用户说「查看状态」「现在项目怎么样」时调用。",
)
mcp.add_tool(
    tools.novel_db_list,
    name="novel_db_list",
    description="列出所有小说档案库。当用户说「有哪些小说」「列出数据库」「我有几个档案库」「我的作品」时调用。",
)
mcp.add_tool(
    tools.novel_outline_list,
    name="novel_outline_list",
    description="列出当前小说的大纲版本。当用户说「大纲列表」「有哪些大纲」「查看大纲」时调用。",
)
mcp.add_tool(
    tools.novel_outline_add,
    name="novel_outline_add",
    description="添加小说大纲。当用户说「添加大纲」「导入大纲」「上传大纲」时调用。安全机制：需要两次确认（preview + confirm_action=true）。参数：outline_text（正文）、title（可选标题）、confirm_action（确认开关）。",
)
mcp.add_tool(
    tools.novel_chapters,
    name="novel_chapters",
    description="查看当前小说的章节列表。当用户说「有哪些章节」「章节列表」「看章节」时调用。",
)
mcp.add_tool(
    tools.novel_agents_review,
    name="novel_agents_review",
    description="调用 AI Agent 陪审团审稿。当用户说「审稿」「检查第几章」「Agent 审稿」时调用。参数：chapter（章节号）、mode（light=轻量/full=完整）。",
)
mcp.add_tool(
    tools.novel_story_health,
    name="novel_story_health",
    description="查看 Story Contract 健康状态。当用户说「故事链健康」「story health」「合同检查」时调用。",
)
mcp.add_tool(
    tools.novel_report,
    name="novel_report",
    description="查看最近的质量报告和审稿摘要。当用户说「报告」「审稿结果」「质量报告」时调用。",
)
mcp.add_tool(
    tools.novel_export_txt,
    name="novel_export_txt",
    description="导出小说文件（纯文本或 Markdown）。当用户说「导出」「导出 TXT」「导出 Markdown」「生成全文」时调用。参数：slug（可选小说标识）、format（txt/md）。",
)


def main():
    """启动 MCP 服务器（stdio 模式）。

    使用标准输入/输出传输协议，适合嵌入 AI 客户端。
    启动后等待客户端发送 MCP 请求，处理完返回结果。
    """
    try:
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        sys.stderr.write("\nMCP 服务器已停止。\n")
    except Exception as e:
        sys.stderr.write(f"\nMCP 服务器异常：{e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
