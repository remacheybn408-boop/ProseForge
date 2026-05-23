# Novel Pipeline - Write Engine

> AI 长篇小说工程化写作流水线：SQLite 长期记忆 + 8 步门禁 Pipeline

## 这是什么

一套 AI Agent 撰写百万字长篇小说的工程流程规范与工具系统。不是写作建议——是**可执行、可验证、可回滚**的硬性流程。

## 核心问题

| 病症 | 症状 | 根因 |
|------|------|------|
| 上下文断裂 | Ch2 开头接不上 Ch1 结尾 | 只看大纲，不读上一章 |
| SQLite 忘用 | 10 章后丢设定 | 凭记忆写，不检索数据库 |
| 字数缩水 | Ch1 4000 字 → Ch17 2400 字 | "任务模式"取代"创作模式" |

## 解决方案

```
SQLite 负责记住 → 门禁负责不偷懒 → 摘要负责不迷路 → 版本负责能回滚
```

## 快速开始

```bash
git clone <repo-url>
cd novel-pipeline

# 配置路径（编辑 config.json）
cp config.example.json config.json

# 初始化数据库 + 小说模块
python scripts/init_db.py
python novel_module/init_novel_module.py

# 写第一章
python novel_module/chapter_pipeline.py pre 1
# [撰写正文到 TXT 文件]
python novel_module/chapter_pipeline.py post 1
```

## 配置

所有路径集中在 `config/config.json`：

```json
{
  "project_root": "/your/path/novel-pipeline",
  "novel_dir": "/your/path/novels",
  "database_path": "/your/path/novel-pipeline/database/hermes_memory.db"
}
```

## 8 步流水线

```
pre → task_card → write → word_count → continuity → scene → anti_ai → ingest
```

| 步骤 | 功能 | 门禁 |
|------|------|------|
| pre | 读上章结尾 + 查 SQLite + 生成 context_pack | pipeline_state 文件锁 |
| task_card | 22 项字段的任务卡 | 缺失则停止 |
| write | 场景块展开（≥4 场景，3500-3800 字初稿） | - |
| word_count | 字数门禁 | < 3300 红灯 |
| continuity | 与上章结尾比对 | 关键词 + 人物承接 |
| scene | 场景质量（防水文） | ≥ 4 有效场景 |
| anti_ai | 反 AI 腔（10 项检测） | ≤ 2 处轻微可过 |
| ingest | 入库 + 切片 + FTS + 版本 + 摘要 + 日志 | 失败禁止下一章 |

## 数据库

单文件 SQLite，15 张表（通用记忆 + 小说业务 + 版本承诺），6 个 FTS5 全文索引。

详见 [docs/database.md](docs/database.md)

## 目录结构

```
novel-pipeline/
├── config/
│   └── config.json              ← 全局路径配置
├── database/
│   └── hermes_memory.db         ← SQLite 数据库
├── novel_module/
│   ├── chapter_pipeline.py      ← 总控流水线
│   ├── init_novel_module.py     ← 初始化
│   ├── search_novel.py          ← FTS 全文检索
│   ├── build_context_pack.py    ← 写作上下文包
│   └── ...
├── scripts/
│   ├── init_db.py               ← 基础底座初始化
│   ├── memory_cli.py            ← 记忆管理 CLI
│   └── backup_db.py             ← 数据库备份
├── novels/                      ← 小说项目目录
├── exports/                     ← 导出 + pipeline_state
├── backups/                     ← 数据库备份
├── logs/                        ← 运行日志
└── docs/                        ← 文档
```

## 文档

- [系统架构](docs/architecture.md)
- [行为规范（完整版）](docs/behavior-spec.md)
- [数据库 Schema](docs/database.md)
- [流水线实现参考](docs/pipeline.md)
- [部署指南](docs/setup-guide.md)
- [长篇写作规范 Skill](docs/skills/long_novel_writing_SKILL.md) ← Agent 写作行为规范（门禁/连续性/卷序/标题骨架/入库规则）

## License

MIT
