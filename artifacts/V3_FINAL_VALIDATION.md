# V3 Final Validation

Status: **实现未完成（2026-07-18 纠正）**

## 纠正说明

此前版本把唯一开放项写成"native 平台门禁"，给人以"V3 核心已完成"的印象。2026-07-18 全量排查证实：**V3 核心执行器仍是占位实现**，与平台验证无关。真实缺口：

1. **执行器不执行**（`proseforge/workflows/tasks.py::execute_agent_run`）：每次只选一个任务串行执行；无任务 lease 到期时间与真正的并行 claim；**不调用任何模型/provider**；输出固定 JSON（`task_key`/`role`/`goal_hash`）；Chief Editor 只追加 `[Agent candidate: task-key]` 占位文字；无独立 reviewer、冲突合并、动态扩图、记忆选择与评测。`application/agents/parallel.py::bounded_parallel` 存在但未被 worker 使用。
2. **权限 fail-open**（`proseforge/domain/agents/policy.py::authorize`）：只拒绝三个已知 capability 中被显式设为 false 的操作，任何未知 capability 直接放行；蓝图要求 fail-closed + 服务端签名策略。
3. **Artifact API 无校验**（`api/routes/agent_runs.py`）：接受任意 artifact type 与任意 JSON，无服务器 schema、角色、task 归属与 allowlist 校验；Review API 接受任意 `reviewer_role`。
4. **审计/观测缺失**：audit API 只是事件列表，无 actor/decision/reason/policy decision；无 metrics、rate limit、prompt-injection 测试。
5. **数据完整性缺口**：run 的 `idempotency_key` 无数据库唯一约束；agent task 无 lease expiry/heartbeat/executor version/checkpoint；含 FAILED task 且无 PENDING task 的 run 执行 `resume` 可能被直接标 COMPLETED。
6. **迁移跳号**：蓝图要求的 0013/0014/0015 不存在，从 0012 直接跳到 0016。
7. **E2E 不可信**：`tests/e2e/v3-agent-swarm.spec.ts` 只查标题；且通过 API 手工创建 artifact/review，无法证明 worker 或 Agent Swarm 真实产出。

## 历史记录（不可信，仅存档）

> Status: NOT READY - native platform gate remains open
>
> Full Python suite: 645 passed, 1 skipped. Frontend Vitest: 18 files / 27 tests passed. TypeScript: passed. Vite production build: passed. Full Playwright suite: 13 passed. Redis/PG readiness interruption: 503 -> 200 after restart. Worker interruption: live API remained 200 and worker recovered. Concurrent event/control audit: unique cursors verified. Deterministic fault E2E covers provider timeout, malformed JSON, and budget exhaustion. Worker-child crash-after-artifact E2E passed.

说明：上述测试数字即便属实，验证的也只是占位执行器的持久化/恢复机制，不构成蓝图 V3-001～010 的功能验收。13 个 Playwright"通过"不含任何真实 Agent Swarm 行为断言。

V3 将按蓝图 V3-001～010 重新实现后重新执行发布门禁，证据标准见 `artifacts/VALIDATION_STATUS.md`。
