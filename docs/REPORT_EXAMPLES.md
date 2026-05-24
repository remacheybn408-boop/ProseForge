# 报告样例 (Report Examples)

v0.4.0 每个门禁都会输出 JSON evidence report。以下是关键报告样例。

---

## 1. Guard Orchestrator Report

`orchestrator_report.json` — 门禁总控报告

```json
{
  "guard": "guard_orchestrator",
  "version": "v0.4.0",
  "run_mode": "standard",
  "executed_guards": ["continuity_evidence_guard", "padding_guard", "anti_ai_guard", ...],
  "warning_count": 3,
  "final_status": "NEED_REVISION"
}
```

## 2. Deduplicated Report

`deduplicated_report.json` — 去重合并后的修改任务

```json
{
  "version": "v0.4.0",
  "merged_issues": [
    {
      "merged_issue": "抽象总结过多，具体锚点不足",
      "severity": "medium",
      "confidence": 0.84,
      "reported_by": ["anti_ai_guard", "show_dont_tell_guard", "concrete_anchor_guard", "qgp_guard"],
      "revision_task": "把抽象总结改成具体动作、物件、停顿或代价。"
    },
    {
      "merged_issue": "场景缺少明确代价",
      "severity": "medium",
      "confidence": 0.78,
      "reported_by": ["scene_causality_guard", "dialogue_beat_guard"],
      "revision_task": "每场关键冲突后加入可见损失：物件破损、关系恶化、身体受伤。"
    }
  ],
  "top_revision_tasks": [
    {
      "rank": 1,
      "issue": "抽象总结过多，具体锚点不足",
      "why_it_matters": "4 个门禁共同发现此问题",
      "fix": "把抽象总结改成具体动作、物件、停顿、误会或代价。",
      "confidence": 0.84
    }
  ]
}
```

## 3. Revision Loop Output

运行 `revision_loop_controller.py --mode controlled` 后生成：

```
reports/revision_loop/
├── revision_tasks.json          ← 修改任务
├── patch_plan.json              ← 补丁计划
├── chapter.revised.txt          ← 改稿草案
├── rewrite_log.json             ← 改动记录
├── revision_diff_report.json    ← 改前/改后对比
└── rerun_guards/                ← 复查门禁结果
```

### revision_diff_report.json

```json
{
  "version": "v0.4.0",
  "chapter_no": 3,
  "summary": {
    "changed_paragraphs": 4,
    "unchanged_ratio": 0.74,
    "added_chars": 312,
    "removed_chars": 128,
    "net_chars": 184
  },
  "recommendation": "REVIEW_BEFORE_ACCEPT"
}
```

## 4. QGP Perplexity Report

`perplexity_quality_report.json` — 困惑度质量门禁

```json
{
  "guard": "perplexity_quality_guard",
  "version": "v0.3.1-qgp",
  "status": "WARNING",
  "summary": {
    "avg_qgp_score": 38.7,
    "template_risk_ratio": 0.42,
    "rhythm_flatness": 0.77,
    "dialogue_variation_score": 0.14,
    "concrete_anchor_ratio": 0.21
  },
  "flags": [
    {"level": "WARNING", "type": "LOW_SURPRISE_TEMPLATE_RISK",
     "message": "连续多段低惊讶度，可能存在模板化叙述。"}
  ],
  "hard_fail": false
}
```

## 5. Character Voice Report

`character_voice_report.json` — 角色口吻门禁

```json
{
  "guard": "character_voice_guard",
  "version": "v0.4.0",
  "status": "WARNING",
  "dialect_density": {"周砚": 0, "老矿头": 2, "管事": 1},
  "wenyan_density": {"周砚": 1, "沈师姐": 2, "管事": 1},
  "forbidden_words_found": [{"speaker": "老矿头", "words": ["因此", "显然"]}],
  "hard_fail": false
}
```

## 6. Concrete Anchor Report

`concrete_anchor_report.json` — 具体锚点门禁

```json
{
  "guard": "concrete_anchor_guard",
  "version": "v0.4.0",
  "status": "WARNING",
  "total_windows": 12,
  "windows_with_object": 8,
  "windows_with_body": 7,
  "windows_with_scene": 5,
  "window_pass_rate": 0.58,
  "missing_types": ["scene_anchor"],
  "hard_fail": false
}
```
