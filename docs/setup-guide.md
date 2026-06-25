# 部署指南

在任何操作系统上从零搭建 ProseForge（v0.8.0）。

## 环境要求

- Python 3.10+
- SQLite 3（Python 自带）
- 可用磁盘空间 ≥ 500MB
- Windows / macOS / Linux

## 第一步：克隆项目

```bash
git clone https://github.com/remacheybn408-boop/ProseForge.git
cd ProseForge
```

## 第二步：配置

```bash
cp config.example.json config.json
```

`config.json` 的核心结构（节选自 `config.example.json`，路径用正斜杠，跨平台兼容）：

```json
{
  "app": { "name": "Novel Forge - 小说引擎", "version": "0.8.0", "mode": "local" },
  "paths": {
    "db_path": "./data/novel_memory.db",
    "novels_root": "./novels",
    "exports_root": "./exports",
    "reports_root": "./exports/reports",
    "outputs_root": "./outputs",
    "tmp_root": "./tmp"
  },
  "novel": { "default_slug": "demo_novel", "default_title": "Demo Novel" }
}
```

> 数据库：`paths.db_path` 是默认回退路径；实际写作时引擎用**槽位数据库** `workspace/<slot>/novel.db`
> （由 `src/db/slot_manager.py` / `registry.py` 管理）。不存在 `hermes_memory.db`。

> Windows 上 pathlib 自动处理分隔符，配置里用 `/` 即可，无需 `\\`。

## 第三步：安装

### Linux / macOS
```bash
chmod +x install.sh
./install.sh
```

手动安装（任意平台）：
```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .                 # RAG 可选：pip install -e .[rag]
```

> 仓库未提供 `install.bat`；Windows 用上面的手动步骤。

## 第四步：初始化工作区

ProseForge 无 CLI 入口，全部经 2 个工具驱动。初始化：

- Hermes：`nf_project(action="init")`，再 `nf_project(action="status")` 验证
- Codex / Claude：
  ```bash
  python plugin/proseforge-codex/scripts/nf_project.py --action init
  python plugin/proseforge-codex/scripts/nf_project.py --action status
  ```

## 第五步：创建小说 + 开始写第一章

```
nf_project(action="create", slot_name="slot_004", title="我的小说")
nf_project(action="outline", sub_action="add", file_path="大纲.txt")
nf_pipeline(action="pre",  slug="<slug>", title="我的小说", vol_no=1, chapter_no=1)
# 写正文到 workspace/<slot>/chapters/第01卷/第1章_标题.txt
nf_pipeline(action="post", slug="<slug>", title="我的小说", vol_no=1, chapter_no=1)
```

详细流程见 [USER_GUIDE_CN.md](USER_GUIDE_CN.md) 与 [pipeline.md](pipeline.md)。

## 部署后目录结构（真实）

```
ProseForge/                        ← 项目根目录
├── config.json                    ← 路径配置
├── install.sh                     ← 安装脚本（Linux/macOS）
├── pyproject.toml                 ← Python 依赖与打包声明
├── database/                      ← 权威 schema（安装必需）
│   ├── schema.sql
│   └── migrations/
├── workspace/                     ← 工作区（Multi-DB，每槽位独立）
│   ├── registry.json              ← 注册表
│   └── <slot>/
│       ├── novel.db               ← 槽位数据库
│       ├── outlines/  chapters/  ...
├── src/                           ← 全部内核代码
│   ├── pipeline/                  ← pre/post/volume/rewrite/export 入口
│   ├── guards/                    ← 门禁（+ human_texture/）
│   ├── agents/                    ← 审读 agents
│   ├── rag/  db/  story/  outline/  utils/
│   └── runtime.py
├── plugin/                        ← 3 个插件面
│   ├── proseforge-Hermes/  proseforge-codex/  proseforge-claude/
├── scripts/                       ← 仅 migrate_slot_names.py（无核心脚本）
├── configs/  packs/  examples/  tests/  docs/
└── exports/  outputs/             ← 运行时产物
```

> 注意：`db/`、`outline/`、`story/`、`fts_health.py` 都在 **`src/`** 下
> （`src/db/`、`src/outline/`、`src/story/`、`src/utils/fts_health.py`），**不在 `scripts/`**。

## 工具一览（替代 CLI）

只有 2 个工具：

| 工具 | action |
|------|--------|
| `nf_project` | init / create / list / status / outline(add/list/switch) / export |
| `nf_pipeline` | pre / post / review / batch / volume / rewrite / accept |

## 迁移到其他机器

```bash
cp -r ProseForge /new/location/
# 修改 config.json 路径（正斜杠）；重新 pip install -e .
# 槽位数据在 workspace/ 下，随目录一起复制
```

## 故障排查

- **"workspace/ 未初始化"** → `nf_project(action="init")`
- **"字数不达标"** → 扩写场景动作/对话冲突/环境压力，**不要**末尾补空泛心理独白
- **跨平台路径** → 配置统一用正斜杠 `/`，不要硬编码盘符
