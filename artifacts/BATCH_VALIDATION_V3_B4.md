# V3 B4 Batch

> 本文件取代 2026-07-18 被撤销的旧版（旧版缺逐条命令、退出码、镜像 digest 与 `down -v` 证据，且以"等价 Podman CLI"搪塞 compose 执行）。按蓝图批次划分（B4=V3-009/010），本批与 B1/B2/B3 合并于 2026-07-20 的 V3 L2 一次执行中验证，全程日志见 `artifacts/v3-l2-run.log`，发布门禁结论见 `artifacts/V3_FINAL_VALIDATION.md`。

Tasks: V3-009 / V3-010（安全、审计与可观测；真实 E2E 与发布门禁）。

## 实现落点

- `c00ac17`：/api/v3 限流桶、审计七要素、每用户活跃 run 并发上限（RUN_CONCURRENCY_LIMIT）、迁移 0025。
- `a38fc04`：前端 Agent Swarm 面板（运行台账、任务/事件/评审/artifact 视图、控制按钮不直接写 ChapterVersion）。
- `a5efdaf`：两个 v3 e2e 取消 skip 并按真实执行器重写 + mock 角色分支 + API 测试。
- `fbb1f4f`：评测 fixture 钉 LF（修 Windows 归档 CRLF 致哈希漂移）。
- `bd87c9d`：`v3-agent-swarm` 登录竞态修复 + 超时 180s（修复后单跑 7.7s 通过）。

## 环境

| 项 | 值 |
|---|---|
| Git commit | `bd87c9dac263e69edf9b34b0040a8a9ec88011e7`（git archive 快照） |
| Docker / Compose | 29.6.2（server, Linux x86_64）/ v5.3.1 |
| API image ID | `sha256:4ec120a619b034827c89b18791e19da137a2f26b5c54f4c7c5e8d12b4aa1a913` |
| Web image ID | `sha256:8d0aed1416c3f5cefa48c91344bb533481f0dadfcbfa427b39343c2001928656` |
| Playwright image ID | `sha256:be22982d683fe55ef44f66e042a08be636fa5db61de7479b7a7ddbefb2da6407`（v1.61.1-noble） |
| 执行窗口 | 2026-07-20T23:34:14+08:00 → 23:41:56+08:00 |

## 证据（合并 pass 内与本批相关的断言）

命令形式：`docker compose -f compose.yaml -f compose.test.yaml -f tmp-remote/compose.ecs.yaml <args>`。

| 步骤 | 退出码 | 本批相关结果 |
|---|:---:|---|
| `run --rm api-test` | 0 | 940 passed，其中 `tests/api/test_agent_endpoints.py` 10、`tests/api/test_agent_security.py` 8（注入/工具滥用/限流 429）、`tests/agents/test_security.py` 1、`tests/fault_injection/test_readiness_dependencies.py` 1（`artifacts/api-pytest.xml`） |
| `run --rm web-test` | 0 | tsc 无错 + 110 vitest（33 文件）+ 构建 603ms |
| `run --rm e2e` | 0 | 14 passed / 0 failed：含 `v3-agent-swarm`（幂等/重放/评审/UI 面板六动作）、`v3-execution-proposal`（暂停恢复、只产 proposal）、`v3-concurrency-fault`、`v3-fault-injection` ×2 |
| `run --rm api-test ruff check proseforge tests` | 0 | All checks passed |
| `run --rm api-test python scripts/dump_openapi.py` | 0 | 117 paths（17 个 /api/v3/），`artifacts/v3-openapi.json` |
| `down -v`（前置与证据后） | 0 | 两次均 0 残留（日志首尾） |

共享账号说明：产品单账号限制（`/api/v1/auth/setup` 一次性），e2e 各 spec 共享套件账号，以唯一幂等键/项目 slug + RUN_CONCURRENCY_LIMIT 有界重试 + 测试栈 /api/v3 限流放宽（写 60/读 240）隔离；中间件默认值不变，仍由 API 测试断言 429。
