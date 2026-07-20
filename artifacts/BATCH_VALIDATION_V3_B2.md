# V3 B2 Batch

> 本文件取代 2026-07-18 被撤销的旧版（旧版缺逐条命令、退出码、镜像 digest 与 `down -v` 证据）。按蓝图批次划分（B2=V3-004/005），本批与 B1/B3/B4 合并于 2026-07-20 的 V3 L2 一次执行中验证，全程日志见 `artifacts/v3-l2-run.log`，发布门禁结论见 `artifacts/V3_FINAL_VALIDATION.md`。

Tasks: V3-004 / V3-005（真实执行器、有界并行与 checkpoint；artifact 服务器校验与哈希）。

## 实现落点

- `f49e893`：执行器接真实 provider 调用（非占位 JSON）：有界并行（16）、lease 过期/心跳、executor version、实测预算结算、checkpoint 持久化与恢复。
- artifact 服务端 schema 校验 + content hash（sha256）+ provenance 关联 + allowlist。

## 环境

| 项 | 值 |
|---|---|
| Git commit | `bd87c9dac263e69edf9b34b0040a8a9ec88011e7`（git archive 快照） |
| Docker / Compose | 29.6.2（server, Linux x86_64）/ v5.3.1 |
| Worker image ID | `sha256:cb8b358264d2892b7ef331a27f6e9da8511a9c586df6aaf42ff3a4d6b1117b2c` |
| 执行窗口 | 2026-07-20T23:34:14+08:00 → 23:41:56+08:00 |

## 证据（合并 pass 内与本批相关的断言）

命令形式：`docker compose -f compose.yaml -f compose.test.yaml -f tmp-remote/compose.ecs.yaml <args>`。

| 步骤 | 退出码 | 本批相关结果 |
|---|:---:|---|
| `run --rm api-test` | 0 | 940 passed，其中 `tests/agents/test_agent_executor.py` 8、`test_checkpoint_parallel.py` 1、`test_artifact_memory.py` 1、`tests/test_run_artifacts.py` 1（`artifacts/api-pytest.xml`） |
| `run --rm recovery-test` | 0 | 5 passed（进程/worker 故障后 checkpoint 与游标恢复，`artifacts/recovery-pytest.xml`） |
| `run --rm e2e` | 0 | `v3-fault-injection.spec.ts` 2 项通过：确定性故障模式持久终结、worker 在 artifact 提交后崩溃可重放安全 |
| `run --rm e2e` | 0 | `v3-agent-swarm.spec.ts` 断言新建 artifact 返回合法 sha256（64 位 hex） |
| `down -v`（前置与证据后） | 0 | 两次均 0 残留（日志首尾） |
