# 系统架构

## 总览

HermesForgeN (v0.8) 是一个 AI Agent 辅助的长篇小说工程化系统，跑在 Hermes Agent Writer Profile 中。核心思路不是"怎么写"，而是"怎么保证写对"——门禁系统强制执行写作纪律，30+ 守卫检查每一章。

```
┌─────────────────────────────────────────────────────────────────┐
│                 Hermes Agent (Writer Profile)                     │
│                         Plugin 层                                 │
│    nf_pipeline (pre/post/review/batch/volume)                    │
│    nf_project  (init/create/list/status/outline/export)          │
│    通过 bios.execute() 分派到 pipeline 子系统                      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────┴──────────────────────────────────┐
│                       Pipeline 层 (src/pipeline/)                 │
│                                                                   │
│  pre.py ──→ post.py ──→ volume.py ──→ export_novel.py            │
│       │            │             │                                │
│       │    ┌───────┴───────┐     │                                │
│       │    │ guard_        │     │                                │
│       │    │ orchestrator  │     │                                │
│       │    │ (全门禁串联)    │     │                                │
│       │    └───────────────┘     │                                │
│       │                          │                                │
│  task_card_builder.py       ingest.py                             │
│  chapter_context.py         stage_review                          │
│                              revision_task_generator.py           │
│                              revision_diff_report.py              │
│                              report_deduplicator.py               │
│                              final_submission_report.py           │
└──────────────────────────────┬──────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌──────────────────┐ ┌────────────────┐ ┌────────────────────────┐
│  Guard 系统        │ │  Rewriter        │ │  Revision Planner      │
│  (src/guards/)     │ │  (src/rewriter)  │ │  (src/revision_       │
│                    │ │                  │ │   planner/)            │
│  3 种模式:         │ │  FIXER_REGISTRY  │ │                        │
│  draft (5 guards) │ │  - pattern_fix   │ │  planner.py            │
│  standard (8)     │ │  - insert_fix    │ │  executor.py           │
│  submission (10)  │ │  - rewrite_fix   │ │  schema.py             │
│                    │ │  - db_fix        │ │  adapters/             │
│  guard_registry.py │ │                  │ │                        │
│  = 唯一入口         │ │  输出 .revised   │ │  修法规划 → 执行      │
│                    │ │  .txt, 不覆盖    │ │                        │
│  每章报告 JSON     │ │  原文件           │ │                        │
└────────┬─────────┘ └────────┬───────┘ └───────────┬────────────┘
         │                    │                      │
         ▼                    ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                     数据 & 存储层                                  │
│                                                                   │
│  SQLite (workspace/<slot>/novel.db)                               │
│   ├─ novels / volumes / chapters / chapter_chunks                 │
│   ├─ characters / worldbuilding / plot_threads                    │
│   ├─ chapter_versions (快照, 不覆盖)                               │
│   ├─ reader_promises / writing_rules                              │
│   ├─ memories + memory_fts (FTS5全文检索)                          │
│   ├─ continuity_checks / chapter_summaries / novel_logs           │
│   └─ 多张 FTS5 虚拟表 (chapter/character/world/plot/vchunk)       │
│                                                                   │
│  TXT 文件                                                         │
│   └─ D:\作品\小说\<书名>\第N章.txt                                  │
│   └─ .revised.txt (rewriter输出, 不覆盖原文件)                     │
│                                                                   │
│  RAG 层 (src/rag/)                                                │
│   ├─ fts5_retriever.py   (FTS5 全文检索)                          │
│   ├─ vector_retriever.py (向量检索, ChromaDB)                     │
│   ├─ hybrid_retriever.py (混合检索)                                │
│   └─ rag_indexer.py      (索引管理)                               │
│                                                                   │
│  Config                                                            │
│   ├─ config.json / config.example.json                            │
│   ├─ configs/agents.yaml                                          │
│   ├─ configs/genre_config.example.yaml                            │
│   ├─ configs/human_texture/genre_presets.yaml                     │
│   └─ configs/jury/* (评审配置)                                     │
│                                                                   │
│  Packs                                                             │
│   ├─ packs/genre/    (题材模板)                                    │
│   ├─ packs/style/    (风格规则)                                    │
│   ├─ packs/voice/    (人设声音包)                                  │
│   └─ packs/templates/ (章节模板)                                   │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│                  审读模块 — Review Agents (src/agents/)             │
│                                                                   │
│  纯规则引擎（regex），不调 LLM。用于 nf_pipeline review action。     │
│                                                                   │
│  基类:  base_agent.py                                             │
│  主协调: orchestrator.py → run_agent_review()                     │
│                                                                   │
│  6 个审读角色 (AGENT_REGISTRY):                                    │
│    continuity   — 承接检查 / 关键物品/伤势/冲突延续                  │
│    character    — 人物声线 / 对白模式 / 旁白主观                    │
│    prose        — AI腔 / 套路句 / 禁句式                           │
│    plot         — 情节推进 / 冲突 / 伏笔兑现                       │
│    reader       — 读者卷入 / 钩子 / 微回报                         │
│    detail       — 动作细节 / 感官 / 站桩对白                        │
│                                                                   │
│  汇总: chief_editor_agent.py (ChiefEditor)                        │
│    — 去重 / 排序 / 分类 must_fix/should_fix/keep                   │
│    — 纯规则，不调 LLM                                              │
│                                                                   │
│  2 种模式: light (3 agents) / full (6 agents)                     │
└─────────────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. Hermes Plugin 入口

`plugin/hermes-forgen-engine/__init__.py` 注册 2 个工具：

| 工具 | 说明 | Action 参数 |
|------|------|-------------|
| `nf_pipeline` | 写作流水线 | pre / post / review / batch / volume |
| `nf_project` | 项目管理 | init / create / list / status / outline / export |

入口调用 `src/bios.execute(action, ...)` 分派到对应的 pipeline 模块。

### 2. Pipeline 流水线

纯函数入口，无 CLI 依赖（CLI 已全部清理）。

**pre** (`src/pipeline/pre.py`)
- 从 DB/outline/story_state/人设卡/上章数据 构建上下文
- 输出：task_card + context_pack + pipeline_state 锁

**post** (`src/pipeline/post.py`)
- 字数门禁 (word_count_gate)
- 全门禁串联 (guard_orchestrator)
- human_texture 检查
- 去重 revision tasks
- ingest 入库 + stage_review

**volume** (`src/pipeline/volume.py`)
- 卷级统计 + 状态 + 下一卷承接报告
- deviation scoring

**export** (`src/pipeline/export_novel.py`)
- 导出整本小说为 txt/md

### 3. Guard 系统 (src/guards/)

唯一入口：`run_standard_guards()` (在 `guard_registry.py`)

三种模式：

| 模式 | 守卫数 | 包含 |
|------|--------|------|
| `draft` | 5 | continuity_evidence, canon_evidence, hallucination, narrative_rhythm, reader_engagement |
| `standard` | 8 | 上 + scene_delta, scene_grounding, dialogue_quality |
| `submission` | 10 | 上 + prose_authenticity, compliance_selfcheck |

核心守卫：
- `continuity_evidence_guard` — 与上章衔接检查
- `canon_evidence_guard` — 设定/证据一致性
- `hallucination_guard` — 幻觉/捏造事实
- `scene_delta_guard` — 场景差异
- `scene_grounding_guard` — 场景落地
- `narrative_rhythm_guard` — 叙事节奏
- `dialogue_quality_guard` — 对话质量
- `reader_engagement_guard` — 读者卷入度
- `prose_authenticity_guard` — 文笔真实感
- `compliance_selfcheck_guard` — 自我合规

每章输出 JSON 报告到 `reports/` 目录。

#### human_texture 子模块 (src/guards/human_texture/)

额外11个守卫，专注"人类质感"检测：
- `life_texture_guard` — 日常细节
- `cliche_sentence_guard` — 套路句检测
- `water_density_guard` — 水密度
- `rhythm_guard` — 节奏检测
- `voice_diversity_guard` — 语态多样性
- `conflict_pressure_guard` — 冲突压力
- `plot_pacing_controller` — 节奏控制器
- `character_psychology_guard` — 人物心理
- `prompt_specificity_guard` — 提示词具体性
- `emotion_summary_guard` — 情绪总结检测
- `character_psychology_crud` — 心理 CRUD

### 4. Legacy Rewriter (src/rewriter.py)

这是遗留改写实现。`nf_pipeline` 已不再公开 `rewrite` 动作，但仓库仍保留该模块供历史产物兼容与内部演进参考。
通过 `guard_name` 查表分派修法，同一 fixer 函数可处理多个 guard 的 findings。

10 个唯一修法函数：

| 函数 | 用途 |
|------|------|
| `_fix_hallucination` | 幻觉/证据捏造修正 |
| `_fix_continuity` | 承接/伏笔/连续性修复 |
| `_fix_concrete_anchor` | 具体物件锚点/感官细节插入 |
| `_fix_padding` | 充水段落/节奏松散裁剪 |
| `_fix_dialogue_structure` | 对白结构/人物声线修整 |
| `_fix_anti_ai` | AI腔综合检测修复 |
| `_fix_cliche` | 套路句替换 |
| `_fix_rhythm` | 节奏失衡修复 |
| `_fix_show_not_tell` | Show不Tell重写+情感冲击 |
| `_fix_life_texture` | 生活质感/日常细节强化 |

输出 `.revised.txt`，不覆盖原文件。

### 5. Revision Planner (src/revision_planner/)

两条路：

- `planner.py` — 分析问题 → 生成修法计划
- `executor.py` — 执行修法计划
- `schema.py` — 修法数据模型
- `adapters/anti_ai.py` — AI腔检测适配

### 6. SQLite 存储

单一数据库 (`workspace/<slot>/novel.db`)，约 20+ 张表。三层：

- **通用层**：memories, memory_fts, projects, settings, memory_logs
- **小说层**：novels, volumes, chapters, chapter_chunks, characters, worldbuilding, plot_threads, writing_rules, chapter_summaries, continuity_checks, novel_logs
- **版本层**：chapter_versions (快照, 永不删除), reader_promises

FTS5 全文检索覆盖 chapter/character/world/plot/chunk 等。

### 7. 审读模块 — Review Agents (src/agents/)

6 个纯规则审读模块 + 1 个汇总器。**不调 LLM**，全凭 regex 模式匹配做章节质量审读。

- `orchestrator.py` — `run_agent_review()` 是 nf_pipeline review action 的入口
- 2 种模式：`light`（continuity + prose + plot，3 agents），`full`（全部 6 agents）
- `ChiefEditor` — 纯规则汇总，去重/排序/分类 must_fix/should_fix/keep

### 8. 字数标准

从 `config.example.json` 读取，按 chapter_type 差异化：

| 类型 | min | best_min | best_max | max |
|------|-----|----------|----------|-----|
| normal | 1900 | 1900 | 2800 | 3300 |
| relationship | 1900 | 1900 | 2800 | 3300 |
| investigation | 1900 | 1900 | 2800 | 3300 |
| experiment | 1900 | 2200 | 3200 | 4200 |
| conflict | 1900 | 2200 | 3300 | 4200 |
| key | 1900 | 2200 | 3300 | 4200 |
| climax | 1900 | 2300 | 3800 | 5500 |
| volume_finale | 1900 | 2300 | 4200 | 5500 |
| authorized_short | 300 | 500 | 900 | 1000 |
| fragment | 300 | 500 | 900 | 1000 |

## 数据流

```
写作前:
  Hermes Agent → nf_pipeline action=pre
    → SQLite/Outline/人设 → context_pack + task_card → pipeline_state lock

写作中:
  Hermes Agent → AI 生成章节 TXT → 写入 D:\作品\小说\<书名>\

写作后:
  Hermes Agent → nf_pipeline action=post
    → word_count_gate → guard_orchestrator (8~10 guards)
    → human_texture 检查 → ingest → SQLite (所有表)
    → stage_review → revision_task_generator
    → 报告到 reports/

修正:
  Hermes Agent → nf_pipeline action=review
    → review findings / planner follow-up

卷级:
  Hermes Agent → nf_pipeline action=volume
    → volume_post() → 统计 + 承接报告

评审:
  Hermes Agent → nf_pipeline action=review
    → orchestrator.run_agent_review() → Agent 层评审
```

## 设计决策

1. **单一数据库**：不拆分，统一备份
2. **无 CLI 入口**：全走 Hermes Plugin（2 个工具，共 12 个 action）
3. **门禁 > 自觉**：守卫是代码级别的，不是口头约定
4. **版本不可覆盖**：`chapter_versions` 快照永不物理删除
5. **无 Web UI / API Server / MCP**：走 headless engine + CLI 路线
6. **src/ 标准结构**：所有代码放 `src/` 下
