# 部署指南

在任何操作系统上从零搭建 Novel Pipeline - Write Engine。

## 环境要求

- Python 3.8+
- SQLite 3（Python 自带）
- 可用磁盘空间 ≥ 500MB

## 第一步：克隆项目

```bash
git clone <your-repo-url>
cd novel-pipeline
```

## 第二步：配置路径

```bash
cp config.example.json config/config.json
```

编辑 `config/config.json`，设置三个核心路径：

```json
{
  "project_root": "/home/user/novel-pipeline",
  "novel_dir": "/home/user/novels",
  "database_path": "/home/user/novel-pipeline/database/hermes_memory.db",
  "default_novel_slug": "my_novel",
  "default_novel_name": "我的小说"
}
```

**Windows 示例：**
```json
{
  "project_root": "D:\\novel-pipeline",
  "novel_dir": "D:\\novels",
  "database_path": "D:\\novel-pipeline\\database\\hermes_memory.db"
}
```

**Linux/macOS 示例：**
```json
{
  "project_root": "/home/user/novel-pipeline",
  "novel_dir": "/home/user/novels",
  "database_path": "/home/user/novel-pipeline/database/hermes_memory.db"
}
```

## 第三步：创建目录结构

```bash
mkdir -p database config novels exports backups logs
```

## 第四步：初始化基础记忆底座

```bash
python scripts/init_db.py
```

输出：
```
HermesMemoryBase 初始化完成。
数据库位置：<your-path>/database/hermes_memory.db
```

## 第五步：初始化小说模块

```bash
python novel_module/init_novel_module.py
```

输出：
```
11 张基础表创建完成。
5 个 FTS5 检索表创建成功。
Novel Module 初始化完成
```

## 第六步：健康检查

```bash
python novel_module/check_novel_health.py
python scripts/check_health.py
```

确认所有表（memories, novels, chapters, characters, worldbuilding, plot_threads, writing_rules, chapter_summaries, continuity_checks, chapter_versions, reader_promises 等）和目录存在。

## 第七步：创建小说目录

```bash
mkdir -p <novel_dir>/<你的小说名>/第一卷_卷名/chapters
```

修改 `novel_module/chapter_pipeline.py` 中的 `CHAPTERS_DIR` 指向你的小说目录：

```python
CHAPTERS_DIR = Path("<novel_dir>/<你的小说名>/第一卷_卷名")
```

## 第八步：开始写第一章

```bash
# 1. 写作前准备（必须——读上章结尾 + 查 SQLite）
python novel_module/chapter_pipeline.py pre 1 --type normal

# 2. 撰写正文到 TXT 文件
# 保存到: <novel_dir>/<小说名>/第一卷_卷名/第1章_标题.txt

# 3. 门禁检查 + 入库（字数/连续性/场景/AI腔/版本）
python novel_module/chapter_pipeline.py post 1 --type normal
```

## 部署后目录结构

```
novel-pipeline/                   ← 项目根目录
├── config/config.json            ← 路径配置
├── database/hermes_memory.db     ← SQLite 数据库
├── novel_module/                 ← 小说模块
│   ├── chapter_pipeline.py       ← 总控流水线
│   ├── init_novel_module.py
│   ├── search_novel.py
│   ├── build_context_pack.py
│   ├── check_novel_health.py
│   └── export_novel_summary.py
├── scripts/                      ← 基础脚本
│   ├── init_db.py
│   ├── memory_cli.py
│   ├── backup_db.py
│   └── check_health.py
├── novels/<小说名>/              ← 小说项目
│   ├── 第一卷_卷名/
│   │   ├── 第1章_标题.txt
│   │   └── ...
│   └── exports/
│       └── pipeline_state/       ← 状态文件锁
├── exports/                      ← 导出
├── backups/                      ← 备份
├── logs/                         ← 日志
└── docs/                         ← 文档
```

## 常用命令

```bash
# 写作前：加载上下文
python novel_module/chapter_pipeline.py pre <章节号> --type normal

# 写作后：门禁 + 入库
python novel_module/chapter_pipeline.py post <章节号> --type normal

# 高潮章（4200-5000 字）
python novel_module/chapter_pipeline.py pre 10 --type climax

# 3 章复盘
python novel_module/chapter_pipeline.py review 6

# 搜索
python novel_module/search_novel.py <关键词> <slug> <数量>

# 上下文包
python novel_module/build_context_pack.py <slug> <关键词> <章节号>

# 导入 TXT
python novel_module/import_chapter_txt.py <slug> <章节号> <标题> <TXT路径>

# 健康检查
python novel_module/check_novel_health.py

# 备份
python scripts/backup_db.py
```

## 故障排查

### "pipeline_state 缺失"

```
⛔ pipeline_state缺失
   必须先运行: python novel_module/chapter_pipeline.py pre <N>
```

每次写新章节必须先执行 `pre`。

### "字数不达标"

```
⛔ 红灯失败 (< 3000) — 必须重写
```

扩写场景动作、对话冲突、环境压力、实验过程、失败代价。**不要**末尾补空泛心理独白。

### "疑似 patch 凑数"

```
⛔ 疑似patch凑数 — 必须重铺缺失场景
```

回到 task_card 找缺失场景，从最早缩水处重铺。不要继续 patch。

## 迁移到其他机器

```bash
# 1. 复制整个目录
cp -r novel-pipeline /new/location/

# 2. 复制小说文件
cp -r <novel_dir>/<小说名> /new/location/novels/

# 3. 修改 config/config.json 中的路径
# 4. 修改 novel_module/chapter_pipeline.py 中的路径
```
