# Novel Forge - 小说引擎 v0.4.0

[![Test](https://github.com/remacheybn408-boop/novel-pipeline-write-engine/actions/workflows/test.yml/badge.svg)](https://github.com/remacheybn408-boop/novel-pipeline-write-engine/actions/workflows/test.yml)

AI 长篇小说工程化写作流水线：SQLite 长期记忆 + 拟人审稿质量套件 + 门禁总控 + 自动改稿闭环。

> **当前稳定版：v0.4.0 Human-Grade Revision Suite。** 支持 20+ 质量门禁、4 模式调度、自动改稿闭环。241 测试通过。

---

## 快速开始

```bash
git clone https://github.com/remacheybn408-boop/novel-pipeline-write-engine.git
cd novel-pipeline-write-engine
cp config.example.json config.json

# 正式写作前建议手动运行备份
python scripts/backup_db.py --config config.json

# 初始化数据库
python scripts/init_db.py --config config.json

# 导入 Demo 标题骨架
python scripts/import_outline_skeleton.py --config config.json --input examples/demo_novel/outline_skeleton.json

# 写作前准备（pre — 自动读取标题骨架）
python scripts/chapter_pipeline.py pre 1 --config config.json --novel-slug demo_novel

# 正文写作 — 必须走 novel-factory skill（详见 novel_factory_router_SKILL.md）
# 禁止普通聊天模式直接生成章节正文

# 写完 TXT 后入库（post — 自动生成 brief + run_report）
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
|   ├── chapter_pipeline.py          ← v0.4.0 拟人审稿流水线（argparse + config 驱动）
│   ├── import_outline_skeleton.py   ← JSON 标题骨架 → SQLite
│   ├── init_db.py                   ← 一键建库
│   └── check_schema.py              ← Schema 完整性检查
│
├── examples/
│   └── demo_novel/
│   └── outline_skeleton.json    ← 完整 demo：25 章标题骨架
│
├── tests/                           ← 31 个测试
├── docs/                            ← 架构 / 规范 / 文档
│   └── skills/
│       ├── novel_factory_router_SKILL.md
│       └── long_novel_writing_SKILL.md
│
├── .github/workflows/test.yml       ← CI（pytest 自动跑）
└── README.md
```

---

## 当前已完成

| 模块 | 说明 |
|------|------|
| `chapter_pipeline.py` | v0.4.0 拟人审稿流水线（pre / post / review / volume），argparse + config 驱动 |
| pre 标题骨架 | 自动从 volume_plans / chapter_plans 读取，TASK CARD 展示指引 |
| pre 读取上章 brief | 读取上一章 ending_state / next_chapter_hooks / 标题变更 |
| chapter_brief | post 后生成 chapter_XXX_brief.json + 写入 chapter_summaries |
| volume_post | 卷级总结 + volume_report.json |
| title_history | 标题变更自动记录 |
| chapter_plans 状态 | planned → written → ingested，同步 actual_word_count |
| 字数门禁 | 按类型: 普通1900-3300, 重点1900-4200, 高潮1900-5500, 短章300-1000 |
| 场景门禁 | ≥ 4 有效场景 |
| `schema.sql` | 26 表 + 6 FTS5 索引，含 volume_plans / chapter_plans / title_history |
| `init_db.py` | 一键建库 |
| `check_schema.py` | Schema 完整性检查 |
| `import_outline_skeleton.py` | JSON 标题骨架导入（校验 chapter_goal / conflict_point / ending_hook_direction） |
| `agent_run_guard.py` | chapter_run_report.json 自检（PASS/FAIL） |
| `hallucination_guard.py` | 幻觉拦截：阻止无依据新设定/矛盾/遗忘状态 |
| `continuity_evidence_guard.py` | 章章连续证据：hard/soft 状态分层 + 钩子分层 + 任务信号检测 |
| `canon_evidence_guard.py` | 来源证据：每个硬事实必须绑定来源 |
| `scene_delta_guard.py` | 场景推进证据：连续叙事支持 narrative beat 拆分 |
| `padding_guard.py` | 反水文：凑字/重复/灌水检测 |
| `backup_db.py` | 一键备份 SQLite 数据库（online backup） |
| `guard_contract_utils.py` | Guard 接口契约：统一 guard_passed() / normalize_chapter_no() |
| `character_voice_guard.py` | [新] 角色口吻：方言/文言浓度 + 禁用词检测 (Phase 2: WARNING) |
| `classical_register_guard.py` | [新] 文言语体：古文块后反应检测 + 可读性风险 (Phase 2: WARNING) |
| `show_dont_tell_guard.py` | [新] AI 总结句：30+ 禁用模式检测 (Phase 2: WARNING) |
| `concrete_hook_guard.py` | [新] 具体钩子：结尾必须绑定 object/person/location/relationship/cost |
| `dialogue_beat_guard.py` | [新] 对白节拍：每场景 ≥2 项动作/停顿/误会/代价 (Phase 2: WARNING) |
| `perplexity_quality_guard.py` | [新] QGP 困惑度质量：ngram 惊讶度/模板风险/节奏异常 (WARNING only) |
| `qgp_baseline.py` | [新] QGP 基线构建：从作者样本建立风格基线 |
| `novel_factory_router_SKILL.md` | Agent 模式路由：NOVEL_WRITE_MODE / PLAN_MODE 触发词 + 执行头 |
| [v0.4.0] `editor_revision_guard.py` | [新] 审稿痕迹检查：检测过度解释/初稿感 (WARNING only) |
| [v0.4.0] `concrete_anchor_guard.py` | [新] 具体锚点密度：物件/动作/场景锚点 (WARNING only) |
| [v0.4.0] `scene_causality_guard.py` | [新] 场景因果链 CARCRH：原因/行动/阻力/代价/结果 (WARNING only) |
| [v0.4.0] `dialogue_naturalness_guard.py` | [新] 对白自然度：打断/未完成句/动作节拍 (WARNING only) |
| [v0.4.0] `style_variation_guard.py` | [新] 句式变化：开头重复/抽象词/句长变化度 (WARNING only) |
| [v0.4.0] `compliance_selfcheck_guard.py` | [新] 投稿合规自查：高风险可BLOCK入库 |
| [v0.4.0] `final_submission_report.py` | [新] 最终投稿报告：汇总门禁 + 投稿建议 |
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
| write | 场景展开（≥4 场景） | Chunked Writing 分段 |
| word_count | 字数门禁 | 按类型: 普通1900-3300, 重点1900-4200, 高潮1900-5500 |
| continuity | 上章结尾比对 | 关键词 + 人物承接 |
| hallucination | 幻觉拦截 | 阻止无依据新设定/矛盾 |
| scene | 场景质量 | ≥ 4 有效场景 |
| anti_ai | 反 AI 腔（10 项检测） | ≤ 2 轻微 |
| padding | 反水文 | 阻止凑字/重复/灌水 |
| voice_guards | 角色口吻+动作证据 (Phase 2: WARNING) | character_voice / classical_register / show_dont_tell / concrete_hook / dialogue_beat |
| qgp | QGP 困惑度质量 (WARNING only) | ngram 惊讶度/模板风险/节奏异常/对白变化度 |
| hgr | v0.4.0 拟人审稿 (WARNING only, 合规可BLOCK) | editor_revision / concrete_anchor / scene_causality / dialogue_naturalness / style_variation / compliance_selfcheck / final_submission |
| ingest | 入库 + 切片 + FTS + 版本 + 摘要 + 日志 | 失败禁止下一章 |

---

## Evidence Gates (v0.3.1+)

| Gate | 证据文件 | 证明内容 |
|------|----------|----------|
| Continuity | `continuity_evidence_report.json` | 章与章之间的承接关系有据可查 |
| Anti-padding | `padding_score` + `scene_delta_report.json` | 每场景有实质推进，无凑字/灌水 |
| Anti-hallucination | `canon_evidence_map.json` + `hard_claims_without_source` | 每个硬事实有明确来源 |
| Volume bridge | `volume_bridge_report.json` | 卷与卷之间的衔接有据可查 |
| Execution proof | `execution_receipt.json` | 命令确实执行过，工具调用可审计 |
| QGP Perplexity Quality | `perplexity_quality_report.json` | 检测文本平滑度、模板风险、节奏异常，只 WARNING 不硬拦 |
| Editor Revision | `editor_revision_report.json` | 审稿痕迹检查，发现初稿感 |
| Concrete Anchor | `concrete_anchor_report.json` | 具体物件/动作/场景锚点密度 |
| Scene Causality | `scene_causality_report.json` | 场景因果链 CARCRH |
| Dialogue Naturalness | `dialogue_naturalness_report.json` | 对白自然度/打断/称呼差异 |
| Style Variation | `style_variation_report.json` | 句式变化/开头重复/抽象词 |
| Compliance Selfcheck | `compliance_selfcheck_report.json` | 投稿合规风险自查 (可BLOCK) |
| Final Submission | `final_submission_report.json` | 汇总所有门禁，给出投稿建议 |

### 硬规则

- **No commands_run** = 未执行
- **No run_report** = 章节未完成
- **No PASS_NOVEL_WRITE_GUARD** = 未通过
- **No ingest_done** = 未入库
- **No previous_tail_used** = 上下文不连续
- **No volume_bridge_report** = 卷不连续
- **No execution_receipt** = 执行未证明

---

## v0.3.1 Quality Guard Patch

本补丁在 v0.3.1 证据门禁基础上增加两类能力：

### 1. 误判校准

- **hard_state / soft_state 分层**: 受伤/被困/生死危机 ≠ 普通情绪/地点变化
- **任务钩子防误触发**: ≥2 信号才算 real_task_hook，排除否定/抽象/已完成/非剧情
- **连续叙事支持**: scene_delta_guard 不再因 scene_count=1 直接 FAIL，支持 narrative beat 拆分
- **Guard 接口契约统一**: guard_passed() / normalize_chapter_no() / 统一返回 dict

### 2. 角色口吻与动作证据 (Phase 2: WARNING only)

| 新门禁 | 功能 | 报告文件 |
|--------|------|----------|
| `character_voice_guard` | 角色口吻一致性、方言/文言浓度、禁用词 | `character_voice_report.json` |
| `classical_register_guard` | 文言/古雅语体合理性、可读性风险 | `classical_register_report.json` |
| `show_dont_tell_guard` | AI 总结句检测（"他终于明白"/"命运的齿轮"/空泛危机） | `show_dont_tell_report.json` |
| `concrete_hook_guard` | 结尾钩子必须绑定 object/person/location/relationship/cost | `concrete_hook_report.json` |
| `dialogue_beat_guard` | 重要场景 ≥2 项：动作/停顿/误会/代价 | `dialogue_beat_report.json` |

### 核心原则

> 门禁不能只硬，还要准。角色不能同声，结尾不能空喊，情绪不能只靠总结。

详见 [角色口吻与动作证据系统](docs/character_voice_action_proof_system.md)

### 3. QGP 困惑度质量门禁 (V5.1, WARNING only)

v0.3.1-qgp 增加 QGP（Quality Guard Perplexity）。通过 ngram 惊讶度、句长节奏、重复短语、抽象总结密度、具体锚点密度、对白变化度，辅助发现章节过度模板化、节奏过平或异常混乱。

**QGP 不是 AI 检测器**，不输出 AI 率，不承诺平台检测结果。默认 ngram 后端，无需 GPU/联网。只 WARNING，不硬拦入库。

详见 [QGP 文档](docs/PERPLEXITY_QGP.md)

---

## v0.4.0 Human-Grade Revision Suite

v0.4.0 增加拟人审稿质量套件。通过具体锚点、场景因果、对白自然度、句式变化、审稿痕迹、合规自查和最终投稿报告，提升小说稿件的自然度、原创感、连续性和投稿前可检查性。

本项目不提供 AI 率、人类率或平台过检率。

详见 [拟人审稿质量套件](docs/HUMAN_GRADE_REVISION_SUITE.md)

### Revision Loop 自动改稿闭环

v0.4.0 增加自动改稿闭环。把最终投稿报告中的高优先级问题转换成修改任务，在 controlled 模式下生成可审阅的 revised draft 和 diff report。

默认不会覆盖原文。默认不会自动入库。默认最多改 2 轮。默认只修 Top 5 高置信度问题。如果改稿导致连续性、角色口吻、合规或反水文指标变差，系统会标记 REVISION_REJECTED。

本项目不承诺平台检测结果。Revision Loop 不是自动洗稿工具。它的目标是辅助作者审稿和改稿。

详见 [改稿闭环文档](docs/REVISION_LOOP.md)

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
pipeline = pre → task_card → scene_plan → write_chunks → assemble_chapter → word_count → continuity → hallucination → scene → anti_ai → padding → voice_guards → qgp → editor_revision → concrete_anchor → scene_causality → dialogue_naturalness → style_variation → compliance_selfcheck → final_submission → ingest
```

如果 novel-factory skill 不可用，必须停止并报错：

```
ERROR: novel-factory skill not available.
Refuse to write novel正文 in normal chat mode.
```

详见 [novel-factory Router Skill](docs/skills/novel_factory_router_SKILL.md)

---

## Skills

- [novel-factory Router](docs/skills/novel_factory_router_SKILL.md) — **正文写作前必读**：模式路由 / NOVEL_WRITE_MODE 触发词 / 执行头 / 失败判定
- [长篇写作行为规范](docs/skills/long_novel_writing_SKILL.md) — 1900 底线 / 弹性字数规则 / 防幻觉 / 防水文 / 章章入库 / 卷卷入库 / 标题骨架规则

## 文档

- [架构](docs/architecture.md)
- [行为规范](docs/behavior-spec.md)
- [数据库 Schema](docs/database.md)
- [流水线](docs/pipeline.md)
- [部署指南](docs/setup-guide.md)
- [路线图](docs/ROADMAP.md)
- [Agent 迭代预算保护规则](docs/agent_iteration_budget.md)

## License

MIT
