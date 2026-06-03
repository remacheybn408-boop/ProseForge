# 系统架构

## 总览

Hermes Novel Engine 是一个用于 AI Agent 辅助长篇小说创作的工程化系统。它解决的核心问题不是"怎么写"，而是"怎么保证写对"——通过 SQLite 长期记忆底座和 8 步门禁流水线强制执行写作纪律。

## 架构分层

```
┌──────────────────────────────────────────────────┐
│                   Agent Layer                     │
│         (Hermes / Claude / GPT — 执行写作)         │
└────────────────────┬─────────────────────────────┘
                     │ pre → task_card → write
                     │ → word_count → continuity
                     │ → scene → anti_ai → ingest
                     │
┌────────────────────┴─────────────────────────────┐
│               Pipeline Layer                      │
│           chapter_pipeline.py (V3)                │
│  8 步流水线 + 6 道门禁 + 3 项执行补丁            │
└────────────────────┬─────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
┌───────────┐ ┌───────────┐ ┌───────────────┐
│ SQLite DB │ │  TXT Files │ │ Pipeline      │
│ 15 tables │ │  Chapters  │ │ State (JSON)  │
└───────────┘ └───────────┘ └───────────────┘
```

## 核心组件

### 1. SQLite 长期记忆底座 (hermes_memory.db)

单一数据库文件，包含 15 张表，分为三层：

**通用记忆层**（任何项目共用）：
- `memories` / `memory_fts` — 长期记忆 + FTS5 全文检索
- `projects` — 项目管理
- `settings` — 系统配置
- `memory_logs` — 操作审计日志

**小说业务层**（小说专用）：
- `novels` — 小说项目
- `volumes` — 分卷
- `chapters` / `chapter_chunks` — 章节 + 自动切片
- `characters` — 人物设定
- `worldbuilding` — 世界观
- `plot_threads` — 伏笔追踪
- `writing_rules` — 写作规则
- `chapter_summaries` — 章节摘要
- `continuity_checks` — 连续性检查记录
- `novel_logs` — 小说操作日志

**版本与承诺层**（长期稳定）：
- `chapter_versions` — 章节版本快照（不可覆盖）
- `reader_promises` — 读者期待/爽点/承诺追踪

### 2. 8 步流水线 (chapter_pipeline.py)

```
pre ──→ task_card ──→ write ──→ word_count
                                    │
                                    ▼
ingest ←── anti_ai ←── scene ←── continuity
```

#### 门禁机制

| 门禁 | 类型 | 失败处理 |
|------|------|----------|
| `pipeline_state.json` | 文件锁 | pre 未完成则禁止 post |
| `word_count_gate` | 字数 | < 3000 红灯失败，3000-3300 黄灯检查 |
| `continuity_gate` | 承接 | 与上章结尾比对关键词+人物 |
| `scene_quality_gate` | 防水文 | ≥ 3 有效场景，对话/动作/无总结腔 |
| `anti_ai_style_gate` | 防 AI 腔 | 10 项检测（禁止句式/总结腔/解释腔） |
| `patch_suspect` | 防凑数 | 版本 ≥ 3 且黄灯 → 拦截，要求重铺场景 |

#### 字数标准

| 章节类型 | 范围 | 初稿目标 |
|----------|------|----------|
| normal（普通） | 3300-4200 | 3500-3800 |
| climax（高潮/打斗/实验） | 4200-5000 | - |
| final（卷末） | 4500-6000 | - |
| short（特批短章） | 3000-3300 | - |

### 3. FTS5 全文检索

全文检索覆盖以下表：
- `memory_fts` — 通用记忆检索
- `novel_chapter_fts` — 章节正文检索
- `novel_chunk_fts` — 章节切片检索
- `novel_character_fts` — 人物设定检索（含自动同步触发器）
- `novel_world_fts` — 世界观设定检索（含自动同步触发器）
- `novel_plot_fts` — 伏笔检索（含自动同步触发器）

FTS5 检索失败时自动回退到 LIKE 搜索。

### 4. 版本管理系统

每次 `ingest` 自动在 `chapter_versions` 表保存版本快照：

```
v1: 初稿 (draft)
v2: 扩写稿 (expanded)
v3: 修订稿 (revised)
v4: 门禁通过稿 (checked)
vN: 定稿 (final)
```

旧版本永不物理删除，只标记为 `deprecated`。

### 5. Pipeline State 文件锁

`pre` 完成后生成 JSON 状态文件：

```json
{
  "chapter_no": 4,
  "pre_done": true,
  "previous_tail_loaded": true,
  "recent_summaries_loaded": true,
  "sqlite_search_logged": true,
  "reader_promises_checked": true,
  "allowed_to_write": true
}
```

`post` 执行前检查此文件，`allowed_to_write` 不为 `true` 则拒绝执行。

## 数据流

```
写作前:
  SQLite → pre → context_pack + task_card → Agent

写作中:
  Agent → write → TXT 文件

写作后:
  TXT 文件 → post → word_count → continuity → scene → anti_ai
  → ingest → SQLite (chapters + versions + chunks + FTS + summaries + logs)

复盘:
  SQLite → review (每 3 章)
```

## 设计决策

1. **单数据库文件**：不拆分 novel.db，统一备份
2. **不拆 18 个独立脚本**：全部合并到 `chapter_pipeline.py`（~500 行）
3. **分阶段落地**：第一阶段 8 步 + 2 张新表，第二阶段（10 章后）再加 4 张状态表
4. **硬性门禁 > 自觉遵守**：门禁是代码级别的，不是口头约定
5. **简洁优先**：不做 Web UI、不做 FastAPI、不做向量数据库
