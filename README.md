# Novel Pipeline - Write Engine

[![Test](https://github.com/remacheybn408-boop/novel-pipeline-write-engine/actions/workflows/test.yml/badge.svg)](https://github.com/remacheybn408-boop/novel-pipeline-write-engine/actions/workflows/test.yml)

AI 长篇小说工程化写作流水线：SQLite 长期记忆 + 8 步门禁 Pipeline。

> **当前阶段：早期原型。** 基础流水线和数据库已可运行，高级功能逐步落地中。

---

## 快速开始

```bash
git clone https://github.com/remacheybn408-boop/novel-pipeline-write-engine.git
cd novel-pipeline-write-engine
cp config.example.json config.json

# 初始化数据库
python scripts/init_db.py --config config.json

# 导入 Demo 标题骨架
python scripts/import_outline_skeleton.py --config config.json --input examples/demo_novel/outline_skeleton.json

# 写作前准备（pre — 自动读取标题骨架）
python scripts/chapter_pipeline.py pre 1 --config config.json --novel-slug demo_novel

# 写完 TXT 后入库（post）
python scripts/chapter_pipeline.py post 1 --config config.json --novel-slug demo_novel

# 卷级总结
python scripts/chapter_pipeline.py volume --config config.json --novel-slug demo_novel --volume-no 1

# 跑测试
pip install pytest && pytest tests/ -v
```

---

## 目录结构

```
novel-pipeline-write-engine/
├── config.example.json              ← 配置模板
├── config.json                      ← 你的本地配置（gitignore）
├── skeleton.example.json            ← 示例骨架（单卷 25 章）
│
├── database/
│   └── schema.sql                   ← 完整 SQLite schema（26 表 + 6 FTS5）
├── data/                            ← 运行时数据库（gitignore，init_db 生成）
│
├── scripts/
│   ├── chapter_pipeline.py          ← 8 步流水线（argparse + config 驱动）
│   ├── import_outline_skeleton.py   ← JSON 标题骨架 → SQLite
│   ├── init_db.py                   ← 一键建库
│   └── check_schema.py              ← Schema 完整性检查
│
├── examples/
│   └── demo_novel/
│       └── outline_skeleton.json    ← 完整 demo：25 章标题骨架
│
├── tests/                           ← 14 个基础测试
├── docs/                            ← 架构 / 规范 / 文档
│   └── skills/
│       └── long_novel_writing_SKILL.md
│
├── .github/workflows/test.yml       ← CI（pytest 自动跑）
└── README.md
```

---

## 当前已完成

| 模块 | 说明 |
|------|------|
| `chapter_pipeline.py` | 8 步流水线（pre / post / review / volume），argparse + config 驱动 |
| pre 标题骨架 | 自动从 volume_plans / chapter_plans 读取，TASK CARD 展示指引 |
| pre 读取上章 brief | 读取上一章 ending_state / next_chapter_hooks / 标题变更 |
| chapter_brief | post 后生成 chapter_XXX_brief.json + 写入 chapter_summaries |
| volume_post | 卷级总结 + volume_report.json |
| title_history | 标题变更自动记录 |
| chapter_plans 状态 | planned → written → ingested，同步 actual_word_count |
| 字数门禁 | < 3300 失败，3500–3900 最佳 |
| 场景门禁 | ≥ 4 有效场景 |
| `schema.sql` | 26 表 + 6 FTS5 索引，含 volume_plans / chapter_plans / title_history |
| `init_db.py` | 一键建库 |
| `check_schema.py` | Schema 完整性检查 |
| `import_outline_skeleton.py` | JSON 标题骨架导入（校验 chapter_goal / conflict_point / ending_hook_direction） |
| Demo 项目 | `examples/demo_novel/` — 25 章骨架 + README |
| Skill 文档 | `docs/skills/long_novel_writing_SKILL.md`（通用版） |
| 测试 | 21 个测试 + GitHub Actions CI |

---

## Phase 3 规划

- [ ] scripts/create_novel.py — 创建新小说项目
- [ ] scripts/export_novel.py — 导出完整小说
- [ ] scripts/backup_db.py — 数据库备份
- Backlog：Web UI / FastAPI / 向量数据库

详见 [ROADMAP](docs/ROADMAP.md)

---

## 核心设计

```
SQLite 记住 → 门禁防偷懒 → 摘要防迷路 → 版本可回滚
```

| 步骤 | 功能 | 门禁 |
|------|------|------|
| pre | 读上章结尾 + 查 SQLite + context_pack | pipeline_state 锁 |
| task_card | 生成任务卡 | 缺失停止 |
| write | 场景展开（≥4 场景） | - |
| word_count | 字数门禁 | < 3300 红灯 |
| continuity | 上章结尾比对 | 关键词 + 人物承接 |
| scene | 场景质量 | ≥ 4 有效场景 |
| anti_ai | 反 AI 腔（10 项检测） | ≤ 2 轻微 |
| ingest | 入库 + 切片 + FTS + 版本 + 摘要 + 日志 | 失败禁止下一章 |

---

## Hermes Agent 正文写作强制规则

本项目的 8 步流水线不是普通提示词，而是 Agent 强制执行协议。

当用户要求写正文、续写、写第 N 章、下一章、写完本卷、继续整本书时，Hermes Agent 必须进入 NOVEL_WRITE_MODE，并调用 novel-factory skill。

禁止使用普通聊天模式直接生成章节正文。

正文写作前必须输出执行头：

```
mode = NOVEL_WRITE_MODE
required_skill = novel-factory
skill_called = true
pipeline = pre → task_card → write → word_count → continuity → scene → anti_ai → ingest
```

如果 novel-factory skill 不可用，必须停止并报错：

```
ERROR: novel-factory skill not available.
Refuse to write novel正文 in normal chat mode.
```

详见 [novel-factory Router Skill](docs/skills/novel_factory_router_SKILL.md)

---

## Skills

- [长篇写作行为规范](docs/skills/long_novel_writing_SKILL.md) — 3300 红线 / 4 场景 / 章章入库 / 卷卷入库 / 标题骨架规则

## 文档

- [架构](docs/architecture.md)
- [行为规范](docs/behavior-spec.md)
- [数据库 Schema](docs/database.md)
- [流水线](docs/pipeline.md)
- [部署指南](docs/setup-guide.md)
- [路线图](docs/ROADMAP.md)

## License

MIT
