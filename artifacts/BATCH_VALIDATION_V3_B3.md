# V3 B3 Batch

> 本文件取代 2026-07-18 被撤销的旧版（旧版缺逐条命令、退出码、镜像 digest 与 `down -v` 证据）。按蓝图批次划分（B3=V3-006/007/008），本批与 B1/B2/B4 合并于 2026-07-20 的 V3 L2 一次执行中验证，全程日志见 `artifacts/v3-l2-run.log`，发布门禁结论见 `artifacts/V3_FINAL_VALIDATION.md`。

Tasks: V3-006 / V3-007 / V3-008（独立评审集群与 Chief Editor；共享记忆；有界动态扩图与评测装置）。

## 实现落点

- `c79284c`：评审集群 handlers，评审结论与 CONFLICT + `conflict_group` 持久化（冲突不覆盖、证据保留）。
- `e8120ba`：Chief Editor 只产 approval-bound V2 RevisionProposal；任何直接写 ChapterVersion 的路径 422。
- `09cc048`：共享记忆（按作用域隔离，候选事实需批准）、有界动态扩图（审计+预算）、评测装置（rubric/打分维度）。
- `b67cbef`：A/B 种子脚本 `scripts/eval_ab_seed.py`（真实 API 驱动两个有界 run 并产出打分对比）。

## 环境

| 项 | 值 |
|---|---|
| Git commit | `bd87c9dac263e69edf9b34b0040a8a9ec88011e7`（git archive 快照） |
| Docker / Compose | 29.6.2（server, Linux x86_64）/ v5.3.1 |
| API image ID | `sha256:4ec120a619b034827c89b18791e19da137a2f26b5c54f4c7c5e8d12b4aa1a913` |
| 执行窗口 | 2026-07-20T23:34:14+08:00 → 23:41:56+08:00 |

## 证据（合并 pass 内与本批相关的断言）

命令形式：`docker compose -f compose.yaml -f compose.test.yaml -f tmp-remote/compose.ecs.yaml <args>`。

| 步骤 | 退出码 | 本批相关结果 |
|---|:---:|---|
| `run --rm api-test` | 0 | 940 passed，其中 `tests/agents/test_review_handlers.py` 5、`test_review_swarm.py` 1、`test_chief_handler.py` 5、`test_chief_approval.py` 1、`test_memory_service.py` 5、`test_expand_graph_runtime.py` 12、`test_evaluation.py` 1、`tests/evaluation/test_rubric.py` 7（`artifacts/api-pytest.xml`） |
| `run --rm api-test python scripts/eval_ab_seed.py` | 0 | run A `18c409c4a1b608ce00000000` COMPLETED（budget 12），run B `18c409c4df71c83000000000` COMPLETED（budget 24），对比 `cmp-e74aabc413d7eb1f7d5d36f7` 含分维度评分与 artifact 哈希 |
| `run --rm e2e` | 0 | `v3-agent-swarm.spec.ts` 断言 CONFLICT 评审与 `conflict_group=scene-merge` 持久化可读回；`v3-execution-proposal.spec.ts` 断言执行只产 V2 proposal |
| `down -v`（前置与证据后） | 0 | 两次均 0 残留（日志首尾） |

注：mock provider 下模型产出是确定性的，A/B 对比验证的是评测装置机制（种子→有界执行→artifact 哈希→打分对比），非模型质量结论。
