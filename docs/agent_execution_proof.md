# Agent Execution Proof (v0.3.1+)

本文档定义什么算真实执行、什么算虚假执行，以及执行证据的强制要求。

---

## 一、什么算真实执行

以下条件**全部满足**才算真实执行：

| 条件 | 说明 |
|------|------|
| `commands_run` 不为空 | 至少执行了 pre、post、agent_run_guard、pytest、git status/diff 之一 |
| `exit_code` 已记录 | 每个命令的退出码明确记录 |
| `run_report` 存在 | `chapter_run_report.json` 已生成并可通过 agent_run_guard 校验 |
| Guard 通过 | `agent_run_guard` 返回 PASS（非 FAIL） |
| 文件已创建 | 必需的产出文件已写入磁盘 |

## 二、什么算虚假执行

以下情况判定为虚假执行：

| 情况 | 判定 |
|------|------|
| Agent 声称"已完成"但没有 commands_run | 虚假执行 |
| Agent 声称"已入库"但没有 ingest 命令 | 虚假执行 |
| Agent 声称"已通过门禁"但没有 run_report | 虚假执行 |
| Agent 声称"已测试"但没有 pytest 输出 | 虚假执行 |
| Agent 声称"上下文连续"但没有 previous_tail_used | 虚假执行 |
| Agent 声称"卷连续"但没有 volume_bridge_report | 虚假执行 |
| Agent 用自然语言描述执行过程但没有任何工具调用记录 | 虚假执行 |

## 三、必需命令

每章写作任务必须执行以下命令（记录于 `commands_run`）：

```
1. pre           — python scripts/chapter_pipeline.py pre <N>
2. post          — python scripts/chapter_pipeline.py post <N>
3. agent_run_guard — python scripts/agent_run_guard.py exports/run_reports/chapter_<N>_run_report.json
4. pytest        — pytest tests/ -v
5. git status    — git status
6. git diff      — git diff --stat
```

如果章节不需要 post（如仅 pre 阶段），至少需要 pre + git 命令。

## 四、必需文件

每章完成后必须产出以下文件：

| 文件 | 说明 |
|------|------|
| `chapter_run_report.json` | 章节运行报告，包含所有门禁结果 |
| `continuity_evidence_report.json` | 连续性证据：上章尾巴 → 本章开头的承接证明 |
| `scene_delta_report.json` | 场景增量：每场景推进了什么（防padding） |
| `canon_evidence_map.json` | 设定来源映射：每个硬事实追溯到 plan/state/instruction |
| `execution_receipt.json` | 执行收据：commands_run + exit_codes + timestamps |

## 五、run_report 最少字段

`chapter_run_report.json` 必须包含以下字段：

```json
{
  "chapter_no": 1,
  "title": "...",
  "word_count": 0,
  "word_count_gate": "PASS|FAIL",
  "continuity_gate": "PASS|FAIL",
  "continuity_evidence_gate": "PASS|FAIL",
  "canon_evidence_gate": "PASS|FAIL",
  "hallucination_gate": "PASS|FAIL",
  "scene_quality_gate": "PASS|FAIL",
  "scene_delta_gate": "PASS|FAIL",
  "padding_gate": "PASS|FAIL",
  "anti_ai_style_gate": "PASS|FAIL",
  "ingest_done": true,
  "previous_tail_used": true,
  "volume_bridge_report_exists": true,
  "execution_receipt_exists": true,
  "next_allowed": true,
  "next_action": "pre_next_chapter"
}
```

缺失任意字段视为 run_report 不完整，gate 判定 FAIL。

## 六、Guard PASS 要求

`agent_run_guard` 判定 PASS 的条件：

1. `run_report` 存在且字段完整
2. 所有门禁 gate 均为 PASS
3. `ingest_done` = true
4. `previous_tail_used` = true（非首章）
5. `volume_bridge_report_exists` = true（卷首章）
6. `execution_receipt_exists` = true
7. `commands_run` 不为空
8. 所有命令 `exit_code` = 0

如果任意条件不满足 → `agent_run_guard` 返回 FAIL → 章节不可声称完成。

## 七、失败交接

当门禁 FAIL 时，执行以下交接流程：

1. **记录失败原因**：写入 `run_report` 的具体 gate 字段
2. **禁止 ingest**：`ingest_done` 置 false，`next_allowed` 置 false
3. **禁止下一章**：`next_action` 置 `repair_current_chapter`
4. **输出修复指引**：明确哪些 gate 失败、需要修复什么
5. **保留执行收据**：即使失败也保留 `execution_receipt.json`，证明 Agent 确实尝试执行过
6. **失败不隐藏**：FAIL 状态明确写入报告，禁止用自然语言模糊描述掩盖失败
