# Guard 接口契约

版本: v0.3.1 Quality Guard Patch

> ⚠️ **v0.8.0 更新**：生产运行时的权威入口是**进程内** `src/guards/guard_registry.py::run_standard_guards`，
> 返回 `GuardResult` / `GuardSummary`（定义见 `src/utils/guard_result.py`，字段为 `guard/status/findings/metrics/report_path/error`），
> **不是**下文描述的旧扁平 dict（`status/final_decision/errors/warnings`）。各 guard 文件在 `src/guards/`（多数仍带 argparse 可单独跑），
> 但 `scripts/<guard>.py` 路径与 `guard_contract_utils` 模块均**已不存在**。下文保留为 v0.3.1 历史契约，新代码以 `guard_result.py` 为准。

## 基本原则

1. **运行时入口是 guard_registry（进程内）**。各 guard 文件在 `src/guards/<guard>.py`，多数仍带 `argparse` 可单独调用调试，参数通过 `--arg value` 传递。
2. **内部函数不是稳定接口**。直接 `import` guard 内部函数可能导致类型不兼容、参数签名变化等问题。
3. **Hermes Agent 优先调用 CLI**。除非明确知道内部函数的签名和返回格式，否则一律用 CLI。
4. **统一返回格式**。所有 guard 的返回必须是 `dict`（不是 `tuple`），且包含以下字段。

## 统一返回格式

```json
{
  "status": "PASS",
  "final_decision": "PASS",
  "errors": [],
  "warnings": [],
  "report_path": ""
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | `"PASS"` / `"FAIL"` | 门禁状态（主要判断字段） |
| `final_decision` | `"PASS"` / `"FAIL"` | 最终决策（与 status 一致） |
| `errors` | `list[str]` | 致命错误列表（导致 FAIL 的原因） |
| `warnings` | `list[str]` | 非致命警告列表 |
| `report_path` | `string` | 报告文件保存路径（可选） |

额外字段由各 guard 自行定义，不影响契约兼容性。

## 统一判断（v0.8.0 实际做法）

> 历史上曾计划用 `guard_contract_utils.guard_passed()` / `normalize_chapter_no()`，**该模块已不存在**。

现在 guard 返回 `GuardResult`（见 `src/utils/guard_result.py`），直接判断 `status`：

```python
result = run_xxx_guard(...)          # 返回 GuardResult
if result.status == "PASS":
    print("通过")
# result.findings 为 GuardFinding 列表；result.fail_count / result.warn_count 为便捷计数
```

整章汇总用 `GuardSummary`（`run_standard_guards` 的返回），它是"唯一真相源"。
章号规范化用 `src/pipeline/_base.py` 的 `_arabic_to_chinese_numeral` 等工具按需处理。

## 调用规则

1. ✅ **调试可单独跑**: `python src/guards/continuity_evidence_guard.py --chapter-no 5 --content-file ch5.txt`（生产路径走 guard_registry）
2. ⚠️ **必要时 import**: 仅在确认接口契约后使用 `from xx import run_xx_check`
3. ❌ **禁止解包 tuple**: 不得写 `ok, report = run_guard(...)`，除非该函数文档明确返回 tuple
4. ❌ **禁止无防护调用**: 所有外部输入（chapter_no、文件路径、JSON 内容）必须做容错处理

## 兼容性处理

当 guard 缺少某些上下文参数时（如 prev_brief、chapter_plan），应使用空 dict / 空 list / 空字符串作为默认值：

```python
report = run_guard(
    content,
    chapter_no,
    prev_tail=prev_tail or "",
    prev_brief=prev_brief or {},
    chapter_plan=chapter_plan or {},
)
```

## 审计脚本兼容性

所有审计脚本（verify_execution_receipt 等）在调用 guard 时，必须兼容缺少可选上下文的情况：

- `prev_brief` 缺失 → `{}`
- `chapter_plan` 缺失 → `{}`
- `task_card` 缺失 → `{}`
- `known_facts` 缺失 → `[]`
- `worldbuilding` 缺失 → `[]`

## 修改历史

- v0.3.1-qgp: 初始版本，统一所有 guard 接口契约
