# Agent 迭代预算保护规则

Hermes Agent 每轮工具调用存在上限（典型 90 次）。执行 GitHub 项目修改时必须进行预算管理，防止工具耗尽导致项目半改。

## 预算分级

| 剩余预算 | 模式 | 允许操作 |
|----------|------|----------|
| > 50 | 正常开发 | 自由修改 |
| 30–50 | 收缩模式 | 只做当前阶段内修改，不许新增大目标 |
| 15–30 | 收尾模式 | 只修当前文件、跑关键测试、输出报告 |
| < 15 | 冻结模式 | 禁止开始新 patch，输出当前状态和 NEXT_PROMPT |
| < 8 | 只读模式 | 禁止 patch、禁止测试，只输出接续方案 |

## 核心规则

1. 每轮最多只做一个主题。
2. 不允许一轮同时改 README + pipeline + scripts + tests + ROADMAP + skills 六大块。
3. 大任务必须拆成 Phase，每个 Phase 独立提交。
4. 工具预算耗尽前必须保存状态，不让项目半残。

## 每轮结束必须输出

```
changed_files:      [...]
completed_items:    [...]
pending_items:      [...]
tests_run:          [...]
tests_not_run:      [...]
next_prompt:        "请继续执行 Phase N：xxx"
remaining_budget:   N
```

## Phase 拆分示例

```
Phase 1：只改 README + ROADMAP
Phase 2：只改 pipeline.md + skills
Phase 3：只改 chapter_pipeline.py + agent_run_guard.py
Phase 4：只改 tests
Phase 5：统一 grep 旧规则 + 跑 pytest
```

## 冻结/只读模式输出格式

```
[NEXT_PROMPT]
继续执行 Phase N。
当前已完成：[...]
待完成：[...]
最后提交：<commit sha>
测试状态：[N/N passed]
```
