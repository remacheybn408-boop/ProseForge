# 改写闭环 — rewrite / accept（v0.8.0）

## 1. 什么是改写闭环

改写闭环把门禁发现的问题转成**受约束、可审核、可入库**的改稿产物。它由 `nf_pipeline`
的两个 action 组成，中间夹一段由 **Agent host** 执行的实际改写：

```
post（产 chapter_NNN_deduplicated_report.json）
  → rewrite   内核读原文 + 去重报告 → 生成「改写卡」+ revision_tasks.json
  → [Agent host 按卡改写 → 写 chapter_NNN_revised.txt]
  → accept    内核 原文 vs revised → diff 报告（recommendation + 风险标记）；--ingest 时入库
```

**关键：Python 内核不调 LLM。** 正文改写由 Agent host（Hermes/Codex/Claude）执行，
内核只负责"给约束（改写卡）"和"验收（diff/入库）"。这与 `pre`/`post` 同构。

> 注：v0.4.0 曾有一个内核自动改稿的 `scripts/revision_loop_controller.py`（suggest/controlled/
> aggressive 模式），v0.8.0 已**移除**——它违反"确定性内核 / Agent 持有模型"的架构。现在的
> rewrite/accept 是它的替代，复用了同一批任务/对比模块。

## 2. 为什么不自动覆盖原文

改稿不等于洗稿。闭环遵循以下原则：

- **不覆盖原文**：`rewrite` 不动原稿；`accept --ingest` 也只向 `chapter_versions` **追加快照**，永不物理删除/覆盖原稿
- **不整章洗稿**：改写卡只圈出 Top 问题段落（默认 ≤5 个任务，置信度 < 0.70 不进入）
- **不追求 WARNING 清零**：只修高置信度问题
- **不改风格**：改写卡的 `must_keep` / `avoid` 清单强制保留方言、文言、角色口癖、伏笔和结尾钩子

## 3. 第一步：rewrite — 生成改写卡

```bash
# Codex CLI
python plugin/proseforge-codex/scripts/nf_pipeline.py \
  --action rewrite --slug demo_novel --title "Demo" --vol-no 1 --chapter-no 3
```

（Hermes：`nf_pipeline action=rewrite slug=... title=... vol_no=1 chapter_no=3`）

输入：
- 章节 TXT（`workspace/<slot>/chapters/...` 或 `novels_root/<slug>/...`）
- `exports/reports/chapter_NNN_deduplicated_report.json`（**由 post 产出**，含 `top_revision_tasks`）

产物：
- `outputs/rewrite_cards/chapter_NNN_rewrite_card.md` — 给 Agent 看的改写卡：每个任务的
  问题/指令/段落范围 + 待改**段落原文** + must_keep/avoid 总则
- `exports/reports/chapter_NNN_revision_tasks.json` — 结构化任务（供 accept 复用）

复用模块：`src/pipeline/revision_task_generator.py::generate_tasks`。

## 4. 中间：Agent 按卡改写

Agent host 读改写卡，只改圈定段落，把**全章**（已改 + 未改段落）写入改写卡里指明的
`revised_expected_path`，即原稿同目录的 `chapter_NNN_revised.txt`。这一步不经内核。

## 5. 第三步：accept — 对比审核（可选入库）

```bash
# 只出 diff，不入库
python plugin/proseforge-codex/scripts/nf_pipeline.py \
  --action accept --slug demo_novel --title "Demo" --vol-no 1 --chapter-no 3

# 审核通过则入库（追加版本快照，不覆盖原稿）
python plugin/proseforge-codex/scripts/nf_pipeline.py \
  --action accept --slug demo_novel --title "Demo" --vol-no 1 --chapter-no 3 --ingest
```

（Hermes：`nf_pipeline action=accept ... ingest=true`）

产物（都在 `exports/reports/`）：

| 文件 | 说明 |
|------|------|
| `chapter_NNN_revision_diff_report.json` | 改前/改后对比 |
| `chapter_NNN_rewrite_log.json` | 改动记录（`changed_ranges`） |

复用模块：`src/pipeline/revision_diff_report.py::generate_diff_report`。

## 6. 如何读 diff report

`chapter_NNN_revision_diff_report.json` 关键字段：

- `summary.changed_paragraphs`：被修改的段落数
- `summary.unchanged_ratio`：未改动比例（越高越保守）
- `task_results`：每个任务 APPLIED / SKIPPED
- `risk_flags`：改动风险提示
- `recommendation`：`REVIEW_BEFORE_ACCEPT` / `REVIEW_CAREFULLY` / `REVISION_REJECTED`

## 7. recommendation 与 risk_flags 规则

- `REVIEW_BEFORE_ACCEPT`：`unchanged_ratio >= 0.65` 且无"对白丢失/超改"风险
- `REVIEW_CAREFULLY`：`unchanged_ratio >= 0.50`
- `REVISION_REJECTED`：其余（`accept --ingest` 遇此**拒绝入库**）

风险标记触发条件：
- 改动比例超过 35%（`unchanged_ratio < 0.65`）
- 对白段落显著丢失（引号段落 < 原文 80%）
- 章节结尾两段被改动（钩子可能丢失）

## 8. 入库语义（--ingest）

仅当 `--ingest` 且 recommendation 非 `REVISION_REJECTED` 时：
1. 把 `chapter_NNN_revised.txt` 提升为该章 canonical TXT
2. 调 `src/pipeline/ingest.py::ingest` 入库 —— 向 `chapter_versions` **追加一条新版本快照**

旧稿的快照在 post 阶段已写入 `chapter_versions`，提升+再入库只是新增 `version_no`，
**原稿永不丢失**。

## 9. 为什么不追求 WARNING 清零

- 方言、文言、角色口癖等"异常"是小说合法艺术手段
- 短章节、过渡章天然会触发某些门禁
- 过度修改会破坏作者风格
- 门禁是审稿助手，不是考试判卷
