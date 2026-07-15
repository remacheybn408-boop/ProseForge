Exit code: 0
Wall time: 0.2 seconds
Output:
# 系统架构

## 总览

ProseForge (v0.8.0) 是一个 AI Agent 辅助的长篇小说工程化系统，提供 Hermes / Codex / Claude 三个插件表面，共享同一个 Python 内核。核心思路不是"怎么写"，而是"怎么保证写对"——门禁系统强制执行写作纪律，registry 派发 10 个守卫检查每一章（另有 human_texture 平行路径 11 个守卫）。

```
┌─────────────────────────────────────────────────────────────────┐
│           Hermes / Codex / Claude Plugin Surface                  │
│    nf_pipeline (pre/post/review/batch/volume/rewrite/accept)     │
│    nf_project  (init/create/list/status/outline/export)          │
│    wrapper 解析参数后直接调 src/pipeline/* 入口函数               │
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
                               │
                               ▼
┌──────────────────────────────────────────────┐
│  Guard 系统 (src/guards/)                      │
│  4 种模式: draft / standard / submission +     │
│            自定义 custom_guards               │
│  L1 结构安全 (4) + L2 质量聚合 (5) + L3 合规 (1) │
│  guard_registry.py = 唯一注册中心              │
│  入口: run_orchestrated (legacy dict)         │
│        run_standard_guards (GuardSummary)     │
│  每章报告 JSON                                 │
└────────┬─────────────────────────────────────┘
         │
         ▼
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
│   └─ workspace/<slot>/chapters/第NN卷/第N章.txt                    │
│                                                                   │
│  RAG 层 (src/rag/)                                                │
│   ├─ fts5_retriever.py   (FTS5 全文检索)                          │
│   ├─ vector_retriever.py (向量检索, ChromaDB)                     │
│   ├─ hybrid_retriever.py (混合检索)                                │
│   └─ rag_indexer.py      (索引管理)                               │
│      pre.py 的世界观提醒现通过 search_worldbuilding 做语义匹配     │
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

`plugin/proseforge-Hermes/__init__.py` 注册 2 个工具：

| 工具 | 说明 | Action 参数 |
|------|------|-------------|
| `nf_pipeline` | 写作流水线 | pre / post / review / batch / volume / rewrite / accept |
| `nf_project` | 项目管理 | init / create / list / status / outline / export |

Wrapper 解析 action / 参数后，直接 import `src.pipeline.pre.run_pre`、`src.pipeline.post.run_post`、`src.pipeline.volume.volume_post` 等函数调用。路径与上下文由 `src/runtime.py` 的 `ProjectPaths` / `PipelineContext` dataclass 统一构建。

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
| `standard` | 9 | 上 + scene_delta, scene_grounding, dialogue_quality, prose_authenticity |
| `submission` | 10 | 上 + compliance_selfcheck |

> 注：`draft` 模式**不含** `scene_delta_guard`（虽然它是 L1 结构守卫）；它只在 standard/submission 跑。
> registry 真实派发的就是这 10 个守卫（4 L1 + 5 L2 聚合器 + 1 L3）；L2 任何 FAIL 会被强制降级为 WARN。

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

### 4. 改写闭环（rewrite / accept）

改写以两个 `nf_pipeline` action 接回时序，**内核不调 LLM**——正文改写由 Agent host（Hermes/Codex/Claude）执行，与 `pre`/`post` 同构：

```
post（产 chapter_NNN_deduplicated_report.json）
  → rewrite   内核读原文+去重报告 → generate_tasks → 写「改写卡」(outputs/rewrite_cards/) + revision_tasks.json
  → [Agent 按卡改写 → 写 chapter_NNN_revised.txt]
  → accept    内核 原文 vs revised → generate_diff_report（recommendation + 风险标记）；--ingest 时审核通过则入库
```

入口：`src/pipeline/rewrite.py::run_rewrite` / `run_accept`。复用 `revision_task_generator.generate_tasks`（自带 must_keep/avoid）、`revision_diff_report.generate_diff_report`、`ingest.ingest`。原则不变：改稿是增量产物——`accept --ingest` 只向 `chapter_versions` 追加快照，永不覆盖原稿。

### 5. SQLite 存储

单一数据库 (`workspace/<slot>/novel.db`)，约 20+ 张表。三层：

- **通用层**：memories, memory_fts, projects, settings, memory_logs
- **小说层**：novels, volumes, chapters, chapter_chunks, characters, worldbuilding, plot_threads, writing_rules, chapter_summaries, continuity_checks, novel_logs
- **版本层**：chapter_versions (快照, 永不删除), reader_promises

FTS5 全文检索覆盖 chapter/character/world/plot/chunk 等。

### 6. 审读模块 — Review Agents (src/agents/)

6 个纯规则审读模块 + 1 个汇总器。**不调 LLM**，全凭 regex 模式匹配做章节质量审读。

- `orchestrator.py` — `run_agent_review()` 是 nf_pipeline review action 的入口
- 2 种模式：`light`（continuity + prose + plot，3 agents），`full`（全部 6 agents）
- `ChiefEditor` — 纯规则汇总，去重/排序/分类 must_fix/should_fix/keep

### 7. 字数标准

从 `config.example.json` 读取，按 chapter_type 差异化：

| 类型 | min | best_min | best_max | max |
|------|-----|----------|----------|-----|
| normal | 1300 | 1900 | 2800 | 3300 |
| relationship | 1300 | 1900 | 2800 | 3300 |
| investigation | 1300 | 1900 | 2800 | 3300 |
| experiment | 1300 | 1900 | 3200 | 4200 |
| conflict | 1300 | 1900 | 3300 | 4200 |
| key | 1300 | 1900 | 3300 | 4200 |
| climax | 1300 | 2300 | 3800 | 5500 |
| volume_finale | 1300 | 2300 | 4200 | 5500 |
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
2. **无 CLI 入口**：全走插件（2 个工具，共 13 个 action：nf_pipeline 7 + nf_project 6）
3. **门禁 > 自觉**：守卫是代码级别的，不是口头约定
4. **版本不可覆盖**：`chapter_versions` 快照永不物理删除
5. **无 Web UI / API Server / MCP**：走 headless engine + CLI 路线
6. **src/ 标准结构**：所有代码放 `src/` 下
7. **两套相反的失败哲学（刻意为之）**：
   - **守卫系统 = fail-open**：单个守卫崩溃 → `run_single_guard` 捕获并降级为 `WARN`（`guard_registry.py`），L2 聚合器任何 FAIL 也强制降为 WARN。理由：质量门禁不应因一个守卫的 bug 就阻断整条流水线、把作者卡死。代价是"守卫悄悄不设防"——为此 `GuardSummary.crashed_guards` 显式记账，post 输出会打印 `[WARN] N guard(s) 崩溃→降级 WARN`，让失防可见。真正能 BLOCK 的只有 L1 与 L3 合规。
   - **审读 Agent = fail-closed**：某个 Agent 崩溃 → `orchestrator.py` 给它 `status=FAIL, score=100`（问题分，越高越差），从而把 `overall_status` 推成 FAIL。理由：审读是"建议性复查"，宁可显式报红引起注意，也不要把崩溃悄悄当通过。
   - 两者方向相反是有意的：门禁卡 ingest（要稳，故 fail-open），审读只给建议（要醒目，故 fail-closed）。调用方据此理解为何同样"崩溃"在两处结局不同。
   - **分数方向**：审读 `overall_score` 是**问题分，越低越好**（`base_agent`: higher = more issues），报告里带 `score_direction: "lower_is_better"` 显式标注，避免误读成"越高越好"。

