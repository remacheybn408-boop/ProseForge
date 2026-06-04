# MCP 中文菜单桥接层 — 用户指南 v0.7.0

## 概述

MCP（Model Context Protocol）中文菜单桥接层让支持 MCP 协议的 AI 工具（如 Claude、Cursor、Hermes）通过**中文自然语言**调用小说引擎功能，无需记忆终端命令。

### 核心原则

- **全中文交互**：所有输入输出均为中文
- **零命令暴露**：不暴露终端命令、文件路径、源码
- **白名单安全**：只允许预定义的 10 个安全操作
- **审计日志**：所有调用记录到 `logs/mcp_audit.log`

---

## 快速开始

### 启动服务器

```bash
# 在项目根目录运行
python -m mcp_server.server
```

服务器以 stdio 模式启动，等待 AI 客户端连接。

### 配置 AI 客户端

**Claude Code** 在项目 `.claude/settings.json` 中添加：

```json
{
  "mcpServers": {
    "novel-forge": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": {}
    }
  }
}
```

**Cursor** 在设置中配置 MCP 服务器路径为：

```
python -m mcp_server.server
```

---

## 10 个安全工具

### 1. `novel_menu` — 显示主菜单

**触发语**：菜单、帮助、怎么用、开始、我想写小说、下一步、能做什么

返回项目状态和 9 个功能选项：
```
[1] 新手检查     [2] 小说档案库   [3] 大纲管理
[4] 开始写作     [5] Agent 审稿    [6] Story Contract
[7] 报告与导出   [8] 角色管理     [9] 其他功能
```

### 2. `novel_status` — 查看引擎状态

**触发语**：当前状态、现在项目怎么样、有没有问题、检查环境

返回：版本号、当前 slot、小说标题、章节数量、数据库状态、大纲激活状态。

### 3. `novel_db_list` — 列出小说档案库

**触发语**：有哪些小说、列出数据库、我有几个档案库、我的作品

返回所有 DB slot 列表，包含活跃状态标识。

### 4. `novel_outline_list` — 查看大纲版本

**触发语**：大纲列表、有哪些大纲、查看大纲、大纲版本

返回当前小说的大纲版本列表，包含激活状态和创建时间。

### 5. `novel_outline_add` — 添加大纲

**触发语**：添加大纲、导入大纲、上传大纲、新建大纲

**安全机制**：
1. 第一次调用（`confirm_action=false`）→ 返回预览和相似度检测
2. AI 向用户展示预览，确认后设置 `confirm_action=true` 再次调用
3. 执行写入临时文件 → 调用 `outline add` 命令

**参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `outline_text` | string | 是 | 大纲正文（至少 10 字） |
| `title` | string | 否 | 大纲标题 |
| `confirm_action` | boolean | 否 | 确认执行，默认 false |

### 6. `novel_chapters` — 查看章节列表

**触发语**：有哪些章节、章节列表、看章节、章节状态

返回：章节号、标题、字数、状态。

### 7. `novel_agents_review` — AI 审稿

**触发语**：审稿、检查第几章、Agent 审稿、完整审稿、快速审稿

**参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `chapter` | integer | 是 | 章节号（如 1 表示第 1 章） |
| `mode` | string | 否 | `light`（轻量/默认）或 `full`（完整 18 Agent） |

返回：审稿模式、分数（Score）、状态（Status）、主要问题列表。

### 8. `novel_story_health` — 故事链健康检查

**触发语**：故事链健康、story health、合同检查、故事状态

返回：Story Contract 数量、提交数量、未履约章节等信息。

### 9. `novel_report` — 查看质量报告

**触发语**：报告、审稿结果、质量报告、查看结果

返回最近的守卫报告和审稿摘要。

### 10. `novel_export_txt` — 导出小说

**触发语**：导出、导出 TXT、生成全文、导出小说、导出 Markdown

**参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `slug` | string | 否 | 小说标识（默认当前小说） |
| `format` | string | 否 | `txt`（纯文本/默认）或 `md`（Markdown） |

---

## 安全设计

### 白名单机制
所有命令执行前经过 `safety.py` 正则匹配，只允许预定义的命令模式。
- ❌ 禁止：`rm`、`del`、`eval(`、`exec(`、shell 管道、重定向
- ❌ 禁止：任意 shell 执行、路径穿越、数据库直写
- ✅ 允许：10 个预定义安全操作

### 审计日志
所有工具调用记录到 `logs/mcp_audit.log`（JSON 格式）：
```json
{"tool": "novel_menu", "params": {}, "success": true, "duration_ms": 123.4}
```
- 不记录大纲全文、小说正文
- 不记录文件路径
- 参数值超过 100 字符自动截断

### 超时控制
| 操作类型 | 超时 |
|---------|------|
| 状态/列表查询 | 10 秒 |
| 审稿 | 60 秒 |
| 导出 | 60 秒 |
| 稳定性检查 | 300 秒 |

---

## 常见问题

**Q: 启动报错 "No module named 'mcp'"？**
A: 安装 MCP SDK：`pip install mcp`

**Q: AI 客户端连接失败？**
A: 确认服务器已启动（`python -m mcp_server.server`），终端显示等待连接。

**Q: 工具返回 "操作超时"？**
A: 审稿或导出操作耗时较长，等待 60 秒后自动超时。可先运行 `novel_status` 检查引擎状态。

**Q: 如何升级 MCP 桥接层？**
A: MCP 桥接层是项目内置模块，更新项目版本即可。

---

## 技术架构

```
AI 客户端 (Claude/Cursor/Hermes)
    │  MCP 协议 (stdio)
    ▼
mcp_server/server.py      ← FastMCP 服务器
    │
    ├── tools.py           ← 10 个工具函数
    ├── command_runner.py  ← 安全执行 novel.py
    ├── safety.py          ← 白名单 + 安全规则
    ├── menu_provider.py   ← 中文菜单生成
    ├── schemas.py         ← 参数结构定义
    ├── audit.py           ← 审计日志
    │
    ▼
novel.py → src/cli/*      ← 核心引擎（未修改）
```

MCP 桥接层是**薄层封装**，不修改核心引擎代码，不提供 Web UI，不部署本地模型。
