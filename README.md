# Novel Pipeline - Write Engine

> AI 长篇小说工程化写作流水线：SQLite 长期记忆 + 8 步门禁 Pipeline

## 当前阶段

本项目处于 **早期原型阶段**。已提供写作规则、Skill 文档和基础 chapter_pipeline 原型。
完整数据库初始化、volume_plans、chapter_plans 等功能正在逐步落地中。
详见 [Roadmap](docs/ROADMAP.md)。

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
# 1. Clone 仓库
git clone <repo-url>
cd novel-pipeline

# 2. 复制配置文件
cp config.example.json config.json
# 编辑 config.json，修改 db_path 和 novels_root

# 3. 初始化数据库
python scripts/init_db.py --config config.json

# 4. 写作前准备 (pre)
python scripts/chapter_pipeline.py pre 1 --config config.json --novel-slug demo_novel

# 5. 写入 TXT 文件后，执行后处理 (post)
python scripts/chapter_pipeline.py post 1 --config config.json --novel-slug demo_novel
```

## 配置

所有路径通过 `config.json` 和命令行参数管理，不再使用硬编码路径。

示例 `config.example.json`：

```json
{
  "db_path": "./data/novel_memory.db",
  "novels_root": "./novels",
  "exports_root": "./exports",
  "word_count": {
    "hard_min": 3300,
    "ideal_min": 3500,
    "ideal_max": 3900,
    "normal_max": 4200,
    "special_max": 5000
  },
  "scene_quality": {
    "min_effective_scenes": 4
  }
}
```

## 8 步流水线

```
pre → task_card → write → word_count → continuity → scene → anti_ai → ingest
```

| 步骤 | 功能 | 门禁 |
|------|------|------|
| pre | 读上章结尾 + 查 SQLite + 生成 context_pack | pipeline_state 文件锁 |
| task_card | 生成任务卡 | 缺失则停止 |
| write | 场景块展开（≥4 场景，3500-3900 字初稿） | - |
| word_count | 字数门禁 | < 3300 红灯失败 |
| continuity | 与上章结尾比对 | 关键词 + 人物承接 |
| scene | 场景质量（防水文） | ≥ 4 有效场景 |
| anti_ai | 反 AI 腔（10 项检测） | ≤ 2 处轻微可过 |
| ingest | 入库 + 切片 + FTS + 版本 + 摘要 + 日志 | 失败禁止下一章 |

## 字数门禁

- **< 3300**：红灯失败，必须重写
- **3300 ~ 4200**：正常通过
- **3500 ~ 3900**：最佳区间
- **4200 ~ 5000**：仅适合特殊章（高潮/卷末）
- **> 5000**：仅适合卷终章，需特殊理由

详见 [docs/skills/long_novel_writing_SKILL.md](docs/skills/long_novel_writing_SKILL.md)

## 目录结构

```
novel-pipeline/
├── config.example.json           ← 示例配置
├── config.json                   ← 用户本地配置（gitignore）
├── scripts/
│   └── chapter_pipeline.py       ← 总控流水线（当前可用）
├── database/                     ← [规划中] SQLite schema
├── data/                         ← [规划中] 运行时数据
├── novels/                       ← [规划中] 小说项目目录
├── docs/
│   ├── architecture.md           ← 系统架构
│   ├── behavior-spec.md          ← 行为规范
│   ├── database.md               ← 数据库 Schema 文档
│   ├── pipeline.md               ← 流水线实现参考
│   ├── setup-guide.md            ← 部署指南
│   ├── ROADMAP.md                ← 路线图
│   └── skills/
│       └── long_novel_writing_SKILL.md  ← 长篇写作行为规范
└── .gitignore
```

> 注：带 [规划中] 标记的目录/文件尚未实现，详见 ROADMAP。

## Skills

- [docs/skills/long_novel_writing_SKILL.md](docs/skills/long_novel_writing_SKILL.md) — 通用长篇小说连续写作执行规则
  - 3300 字红线
  - 3500 ~ 3900 最佳区间
  - 章章入库 / 卷卷入库
  - post 后自动 pre 下一章
  - 全书标题骨架入库
  - volume_plans / chapter_plans / title_history 表建议

## 文档

- [系统架构](docs/architecture.md)
- [行为规范（完整版）](docs/behavior-spec.md)
- [数据库 Schema](docs/database.md)
- [流水线实现参考](docs/pipeline.md)
- [部署指南](docs/setup-guide.md)
- [路线图](docs/ROADMAP.md)

## License

MIT
