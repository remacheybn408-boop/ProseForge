# V3 B1 Batch

> 本文件取代 2026-07-18 被撤销的旧版（旧版缺逐条命令、退出码、镜像 digest 与 `down -v` 证据）。按蓝图批次划分（B1=V3-001~003），本批与 B2/B3/B4 合并于 2026-07-20 的 V3 L2 一次执行中验证，全程日志见 `artifacts/v3-l2-run.log`，发布门禁结论见 `artifacts/V3_FINAL_VALIDATION.md`。

Tasks: V3-001 / V3-002 / V3-003（agent runtime ports、角色与策略系统、任务图引擎与校验）。

## 实现落点

- `be9011d`：`policy.authorize` 改 fail-closed（未知角色/动作默认拒绝），服务端签名策略快照（版本化），图校验（环、未知角色、schema、深度/扇出、预算上限）。
- `f49e893`：真实执行器落地时接入校验后的图定义（graph_revision 校验）。

## 环境

| 项 | 值 |
|---|---|
| Git commit | `bd87c9dac263e69edf9b34b0040a8a9ec88011e7`（git archive 快照） |
| Docker / Compose | 29.6.2（server, Linux x86_64）/ v5.3.1 |
| API-test image ID | `sha256:1f2ec28107b211d915a1ecc7c3213291afe212a162d60309b2939efb12c8fb1f` |
| 执行窗口 | 2026-07-20T23:34:14+08:00 → 23:41:56+08:00 |

## 证据（合并 pass 内与本批相关的断言）

命令形式：`docker compose -f compose.yaml -f compose.test.yaml -f tmp-remote/compose.ecs.yaml <args>`。

| 步骤 | 退出码 | 本批相关结果 |
|---|:---:|---|
| `run --rm api-test` | 0 | 940 passed，其中 `tests/agents/test_policy_failclosed.py` 11、`test_role_policy.py` 1、`test_role_handlers.py` 5、`test_task_graph.py` 1、`test_orchestrator_port.py` 1、`tests/test_agents_smoke.py` 6、`tests/architecture/test_external_agent_surfaces_removed.py` 1（`artifacts/api-pytest.xml`） |
| `run --rm api-test`（图校验 422） | 0 | `tests/api/test_agent_endpoints.py` 10 含环/未知角色/非法 schema/预算滥用的 422 断言 |
| `run --rm e2e` | 0 | `v3-concurrency-fault.spec.ts` 通过（唯一审计游标，策略并发面） |
| `down -v`（前置与证据后） | 0 | 两次均 0 残留（日志首尾） |
