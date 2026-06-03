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
cd novel-pipeline-write-engine
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

# 安装依赖
pip install -r requirements.txt

# 初始化 workspace
python novel.py db init
```

### Windows

```cmd
install.bat
```

或者手动安装：

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python novel.py db init
```

## 第四步：验证安装

```bash
# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

# 检查状态
python novel.py status
```

预期输出：
```
============================================================
  Novel Forge - 小说引擎 v0.6.5
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

```bash
python novel.py db init
```

输出：
```
  [OK] workspace/registry.json 已创建
  [OK] slot_001/ 目录已创建
  [OK] slot_002/ 目录已创建
  [OK] slot_003/ 目录已创建

  workspace 初始化完成！
  活跃 slot: slot_001
```

## 第六步：创建小说目录

```bash
# 创建章节目录
mkdir -p novels/<你的小说名>/第01卷
```

## 第七步：开始写第一章

```bash
# 1. 写作前准备（任务卡片 + 上下文）
python novel.py pre 1 --slug <你的小说名>

# 2. 撰写正文到 TXT 文件
# 保存到: novels/<小说名>/第01卷/第1章_标题.txt

# 3. 门禁检查 + 入库
python novel.py post 1 --slug <你的小说名>
```

## 部署后目录结构

```
novel-pipeline-write-engine/       ← 项目根目录
├── config.json                    ← 路径配置
├── install.sh / install.bat       ← 安装脚本
├── novel.py                       ← CLI 入口
├── requirements.txt               ← Python 依赖
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

## 常用命令

```bash
# 工作区管理
python novel.py db list              # 列出所有工作区
python novel.py db new --name "项目名"  # 新建工作区
python novel.py db use <slot_id>      # 切换工作区
python novel.py db backup             # 备份当前工作区
python novel.py db delete <slot_id> --yes  # 安全删除（移至回收站）
python novel.py db trash              # 查看回收站
python novel.py db restore --from-trash <名称>  # 从回收站恢复

# 写作流程
python novel.py pre <章节号> --slug <slug>     # 写作前准备
python novel.py post <章节号> --slug <slug>    # 写作后门禁 + 入库
python novel.py review <章节号> --slug <slug>  # 复盘

# 报告与导出
python novel.py report                        # 查看报告
python novel.py export --slug <slug>          # 导出小说

# 诊断
python novel.py status                        # 环境诊断
python novel.py doctor                        # 详细诊断

# 字数统计
python novel.py wc <章节号>                   # 统计汉字数
```

## 迁移到其他机器

```bash
# 1. 复制整个项目目录
cp -r novel-pipeline-write-engine /new/location/

# 2. 复制小说文件
cp -r novels/<小说名> /new/location/novels/

# 3. 修改 config.json 中的路径（使用 pathlib 风格正斜杠）
# 4. 重新安装依赖: pip install -r requirements.txt
```

## 故障排查

### "workspace/ 未初始化"

运行初始化命令：
```bash
python novel.py db init
```

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
