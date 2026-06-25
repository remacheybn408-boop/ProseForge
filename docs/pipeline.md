# Pipeline — v0.8.0 完整流程

ProseForge 写作流水线。纯函数入口，无 CLI；全部经 `nf_pipeline` 工具的 action 驱动，
wrapper 直接调 `src/pipeline/*` 的入口函数。

## 入口对照

| action | 入口函数 | 文件 |
|--------|----------|------|
| `pre` | `run_pre` | `src/pipeline/pre.py` |
| `post` | `run_post` | `src/pipeline/post.py` |
| `review` | `run_agent_review` | `src/agents/orchestrator.py` |
| `batch` | 循环 `run_post` | `src/pipeline/post.py` |
| `volume` | `volume_post` | `src/pipeline/volume.py` |
| `rewrite` / `accept` | `run_rewrite` / `run_accept` | `src/pipeline/rewrite.py`（见 REVISION_LOOP.md） |
| `export`（nf_project） | `export_novel` | `src/pipeline/export_novel.py` |

## 流程

```
pre   → 从 DB/大纲/story_state/人设/上章 构建上下文
        产出: task_card + context_pack + pipeline_state 锁

[Agent host 生成正文 TXT → 写入 chapters 目录]   ← 不经内核

post  → 字数门禁 (word_count_gate)
        → 全门禁串联 (guard_orchestrator → run_standard_guards, 10 守卫)
        → human_texture 检查 (平行路径, 11 守卫)
        → 去重 revision tasks (report_deduplicator)
        → ingest 入库 (含 chapter_versions 快照) + stage_review

[可选改写闭环]  rewrite → Agent 写 revised → accept   （详见 REVISION_LOOP.md）

volume → 卷级统计 + 状态 + 下一卷承接报告 + deviation scoring
export → 导出整本为 txt/md
```

## 门禁体系（v0.8.0）

唯一入口 `run_standard_guards()`（`src/guards/guard_registry.py`）。三种模式：

| 模式 | 守卫数 | 含 |
|------|--------|----|
| `draft` | 5 | continuity_evidence, canon_evidence, hallucination, narrative_rhythm, reader_engagement |
| `standard` | 9 | 上 + scene_delta, scene_grounding, dialogue_quality, prose_authenticity |
| `submission` | 10 | 上 + compliance_selfcheck |

- 分层：L1 结构安全(4) + L2 质量聚合(5) + L3 合规(1)。registry 真实派发就是这 10 个。
- L2 任何 FAIL 被强制降级为 WARN（`LEVEL2_CANNOT_FAIL`）。
- 旧版独立 gate（scene_quality / anti_ai / padding 等 ~21 项）已折叠为 5 个 L2 聚合器的**子检查**，不再单独注册。
- `human_texture/` 是平行路径（11 守卫），不走 registry，产出 `*_texture_report.json` 供跨章消费。

### L1 证据门禁（硬结构）

| L1 守卫 | 证明内容 |
|---------|----------|
| continuity_evidence | 本章承接上一章结尾，context 连续 |
| canon_evidence | 每个硬事实可追溯到 plan/state/instruction |
| hallucination | 无无依据新设定、无矛盾、无遗忘状态 |
| scene_delta | 每场景有实质推进，非灌水（注：draft 模式不跑） |

## Chunked Writing Mode（写作约定）

- chunk 是写作单位，chapter 是入库单位
- 每章建议 4~7 个 chunks；chunk 失败只重写该 chunk，不重写整章
- assembled_chapter 字数不足时补缺失场景，**禁止补水文**

chunk 合格条件：1.明确地点 2.明确人物 3.具体动作 4.冲突/信息推进
5.推进主线/人物/伏笔/承诺/世界观/情绪之一 6.不只解释设定 7.不只心理独白 8.不复述前文

## 字数门禁

按 chapter_type 分级（来源 `config.example.json` 的 `word_count`），类型只决定上限：

| 类型 | min | best | max |
|------|-----|------|-----|
| normal | 1300 | 1900–2800 | 3300 |
| key | 1300 | 1900–3300 | 4200 |
| climax | 1300 | 2300–3800 | 5500 |
| volume_finale | 1300 | 2300–4200 | 5500 |
| authorized_short / fragment | 300 | 500–900 | 1000 |

高潮不代表字多，短而完整优先通过。

## 输出文件（exports/ 下）

| 阶段 | 输出 |
|------|------|
| pre | `pipeline_state/chapter_NNN_state.json`、context_pack；task_card 到 `outputs/task_cards/` |
| post | `chapter_briefs/chapter_NNN_brief.json`、`run_reports/chapter_NNN_run_report.json`、`reports/chapter_NNN_{guard}_report.json`、`reports/chapter_NNN_guard_summary.json`、`reports/chapter_NNN_orchestrator_report.json`、`reports/chapter_NNN_texture_report.json`、`reports/chapter_NNN_deduplicated_report.json` |
| rewrite/accept | `outputs/rewrite_cards/chapter_NNN_rewrite_card.md`、`reports/chapter_NNN_revision_tasks.json`、`reports/chapter_NNN_revision_diff_report.json`、`reports/chapter_NNN_rewrite_log.json` |
| volume | `volume_reports/volume_NN_report.json` |

## 调用示例

```bash
# Codex CLI（Claude 面也复用这套脚本）
python plugin/proseforge-codex/scripts/nf_pipeline.py --action pre    --slug demo_novel --title "Demo" --vol-no 1 --chapter-no 1
python plugin/proseforge-codex/scripts/nf_pipeline.py --action post   --slug demo_novel --title "Demo" --vol-no 1 --chapter-no 1
python plugin/proseforge-codex/scripts/nf_pipeline.py --action review --slug demo_novel --vol-no 1 --chapter-no 1 --mode full
python plugin/proseforge-codex/scripts/nf_pipeline.py --action volume --slug demo_novel --title "Demo" --vol-no 1
```

Hermes 面则通过 `nf_pipeline` 工具传 `action=pre|post|review|batch|volume|rewrite|accept`。
