# 部署指南

在任何操作系统上从零搭建 Novel Forge - 小说引擎。

## 环境要求

- Python 3.8+ (推荐 3.10+)
- SQLite 3（Python 自带）
- 可用磁盘空间 ≥ 500MB
- Windows / macOS / Linux

## 第一步：克隆项目

```bash
git clone <your-repo-url>
cd ProseForge
```

## 第二步：配置路径

```bash
cp config.example.json config.json
```

编辑 `config.json`，设置核心路径：

```json
{
  "project_root": "/home/user/novel-pipeline-write-engine",
  "novel_dir": "/home/user/novels",
  "database_path": "/home/user/novel-pipeline-write-engine/database/hermes_memory.db",
  "default_novel_slug": "my_novel",
  "default_novel_name": "我的小说"
}
```

**路径说明** — 所有路径使用 pathlib 风格（正斜杠），跨平台兼容：

| 平台 | 示例路径 |
|------|----------|
| Linux | `/home/user/novel-pipeline-write-engine` |
| macOS | `/Users/<username>/novel-pipeline-write-engine` |
| Windows | `C:/Users/<username>/novel-pipeline-write-engine` |

> **注意**: 在 Windows 上，pathlib 和 Python 会自动处理路径分隔符。配置中使用正斜杠 `/` 即可，无需使用 `\\`。

## 第三步：安装

### Linux / macOS

```bash
chmod +x install.sh
./install.sh
```

或者手动安装：

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖（依赖声明在 pyproject.toml；RAG 可选：pip install -e .[rag]）
pip install -e .

# 初始化 workspace (已迁移至 Hermes: nf_初化)
```

### Windows

手动安装（仓库未提供 install.bat）：

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -e .
# (已迁移至 Hermes: nf_初化)
```

## 第四步：验证安装

```bash
# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

# 检查状态 (已迁移至 Hermes: nf_状态)
```

预期输出：
```
============================================================
  Novel Forge - 小说引擎 v0.7.1
  状态检查 (标准)
============================================================

  [OK] OS: ...
  [OK] Python 3.11
  [OK] config.json
  [OK] src/guards/reader_pull_guard.py
  ...
  All checks passed. Ready to write.
```

## 第五步：初始化工作区

在 Hermes Writer profile 中调用 `nf_初化` 完成初始化。
然后调用 `nf_新建` 创建新小说槽位。

## 第六步：开始写第一章

### 写作前准备
在 Hermes 中调用：`nf_预写(slug="<slug>", title="<小说名>", vol_no=1, chapter_no=1)`

### 撰写正文
保存到: `novels/<小说名>/第01卷/第1章_标题.txt`

### 门禁检查 + 入库
在 Hermes 中调用：`nf_续写(slug="<slug>", title="<小说名>", vol_no=1, chapter_no=1)`

## 部署后目录结构

```
novel-pipeline-write-engine/       ← 项目根目录
├── config.json                    ← 路径配置
├── install.sh                     ← 安装脚本（Linux/macOS）
├── pyproject.toml                 ← Python 依赖与打包声明
├── workspace/                     ← 工作区（Multi-DB）
│   ├── registry.json              ← 注册表
│   ├── slot_001/                  ← 默认工作区
│   │   ├── novel.db               ← 项目数据库
│   │   ├── project.json           ← 项目配置
│   │   ├── outlines/
│   │   ├── chapters/
│   │   ├── reports/
│   │   ├── exports/
│   │   └── backups/
│   ├── slot_002/
│   ├── slot_003/
│   └── _trash/                    ← 回收站
├── scripts/                       ← 核心脚本
│   ├── db/
│   │   ├── slot_manager.py
│   │   └── registry.py
│   ├── outline/
│   ├── story/
│   └── fts_health.py
├── src/guards/                    ← 门禁检查
├── configs/                       ← 配置
├── novels/<小说名>/               ← 小说项目
│   ├── 第01卷/
│   │   ├── 第1章_标题.txt
│   │   └── ...
│   └── exports/
├── docs/                          ← 文档
└── voice_packs/                   ← 风格包
```

## Hermes 工具（替代 CLI）

通过 Hermes Agent hermes-forgen-engine 插件直接调用：

| 工具 | 功能 |
|------|------|
| `nf_状态` | 环境/状态诊断 |
| `nf_初化` | 初始化工作区 |
| `nf_新建` | 创建新小说槽位 |
| `nf_列表` | 列出所有槽位 |
| `nf_大纲` | 大纲管理（add/list/switch） |
| `nf_预写` | 写前准备（任务卡生成） |
| `nf_续写` | 写后门禁 + 入库 |
| `nf_流水` | 批量审稿 |
| `nf_审稿` | 章节复盘 |
| `nf_改写` | 统一改写器 |
| `nf_卷管` | 卷总结 |
| `nf_导出` | 导出小说 |

## 迁移到其他机器

```bash
# 1. 复制整个项目目录
cp -r novel-pipeline-write-engine /new/location/

# 2. 复制小说文件
cp -r novels/<小说名> /new/location/novels/

# 3. 修改 config.json 中的路径（使用 pathlib 风格正斜杠）
# 4. 重新安装依赖: pip install -e .
```

## 故障排查

### "workspace/ 未初始化"

在 Hermes 中调用 `nf_初化` 完成初始化。

### "字数不达标"

```
⛔ 红灯失败 (< 3000) — 必须重写
```

扩写场景动作、对话冲突、环境压力。**不要**末尾补空泛心理独白。

### 跨平台路径问题

- 配置文件中的路径统一使用正斜杠 `/`
- Windows 上 Python pathlib 自动处理路径转换
- 不要使用硬编码的盘符（如 `D:\`）
- 使用相对路径时基于项目根目录（`PROJECT_ROOT`）
