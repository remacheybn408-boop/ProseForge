# Guard Registry — 门禁统一注册系统

## 概述

Guard Registry 是 v0.4.5 引入的门禁统一执行入口。所有 guard 调用（post、orchestrator、CI、Agent 自检）必须通过 registry，不允许零散调用。

## 数据结构

```
GuardFinding  →  单条问题：guard, severity, code, message, evidence
GuardResult   →  单个 guard 的完整输出：status, findings, metrics
GuardSummary  →  全章门禁汇总：overall_status, fail/warn/pass_count
```

## 门禁级别

| Level | Guards | 规则 |
|-------|--------|------|
| 1 (硬门禁) | continuity_evidence, canon_evidence, hallucination, scene_delta | 可 FAIL，阻止入库 |
| 2 (质量门禁) | anti_ai, padding, show_dont_tell, character_voice, dialogue_beat, classical_register, perplexity_quality, editor_revision, concrete_anchor, scene_causality, dialogue_naturalness, style_variation | WARNING only，不阻止入库 |
| 3 (合规) | compliance_selfcheck | 可 BLOCK |

## 模式

| 模式 | 包含 Guards |
|------|------------|
| draft | continuity_evidence, canon_evidence, hallucination, padding |
| standard | 以上 + scene_delta, anti_ai, show_dont_tell, character_voice, concrete_anchor, scene_causality, dialogue_naturalness |
| submission | 以上全部 + dialogue_beat, classical_register, perplexity_quality, editor_revision, style_variation, compliance_selfcheck |

## 证据门禁

| Gate | 证据文件 | 证明内容 |
|------|----------|----------|
| Continuity | `continuity_evidence_report.json` | 章与章之间的承接关系有据可查 |
| Anti-padding | `padding_score` + `scene_delta_report.json` | 每场景有实质推进，无凑字/灌水 |
| Anti-hallucination | `canon_evidence_map.json` + `hard_claims_without_source` | 每个硬事实有明确来源 |
| Volume bridge | `volume_bridge_report.json` | 卷与卷之间的衔接有据可查 |
| Execution proof | `execution_receipt.json` | 命令确实执行过，工具调用可审计 |
| QGP | `perplexity_quality_report.json` | 文本平滑度、模板风险、节奏异常 |
| Editor Revision | `editor_revision_report.json` | 审稿痕迹检查，发现初稿感 |
| Concrete Anchor | `concrete_anchor_report.json` | 具体物件/动作/场景锚点密度 |
| Scene Causality | `scene_causality_report.json` | 场景因果链 CARCRH |
| Dialogue Naturalness | `dialogue_naturalness_report.json` | 对白自然度/打断/称呼差异 |
| Style Variation | `style_variation_report.json` | 句式变化/开头重复/抽象词 |
| Compliance | `compliance_selfcheck_report.json` | 投稿合规风险自查 |
| Final Submission | `final_submission_report.json` | 汇总所有门禁，给出投稿建议 |
