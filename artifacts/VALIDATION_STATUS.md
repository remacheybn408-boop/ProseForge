# ProseForge 验证状态事实源

> 本文件是三个版本验证状态的唯一事实源（2026-07-18 全量排查后建立）。任何与本文件冲突的历史验证文档，以本文件为准。蓝图：`D:\引擎备份\PROSEFORGE_ENGINEERING_EXECUTION_BLUEPRINT`。
>
> 最近状态更新：2026-07-20。V2-010 完整 L2 已在 ECS Docker 执行并全绿（12 步证据见 `artifacts/v2-l2-run.log`、`V2_FINAL_VALIDATION.md`），V2 发布门禁 PASS。V3 重实现完成，V3-010 发布门禁同日在 ECS Docker 执行并全绿（14 步证据见 `artifacts/v3-l2-run.log`、`V3_FINAL_VALIDATION.md`），V3 发布门禁 PASS。

## 版本真实状态

| 版本 | 真实状态 | 说明 |
|---|---|---|
| V1.5 Native Runtime | **Windows/Linux 达成；macOS BLOCKED**（2026-07-18） | V15-008/009/010 已按蓝图实现并实测：PyInstaller onedir（钉版 3.12）、Inno 安装器（安装/卸载留数据实测）、deb/rpm/pkg 脚本、CLI `web`/真实 `upgrade`、L2 全矩阵绿。macOS 安装验证待 macOS runner |
| V2 Chat Workspace | **达成（2026-07-20）** | V2-001～010 全部进入 `master`；发布门禁已执行：ECS Docker L2 12 步全绿（legacy 408 / api 864 / contract 43 / migration 24 / recovery 5 / web 105 / e2e 12+2skip / ruff / OpenAPI 111 paths），真实 10 步 E2E 与导出/请求证据齐全，见 `artifacts/V2_FINAL_VALIDATION.md`、`artifacts/BATCH_VALIDATION_V2_B4.md`。Known unvalidated 如实记录在案（全量 i18n 文案、真实 provider、macOS） |
| V3 Agent Swarm | **达成（2026-07-20）** | V3-001～010 重实现全部进入 `master`（fail-closed 策略+签名快照、真实有界执行器、评审集群、approval-bound Chief Editor、记忆/扩图/评测、限流/审计/并发上限、前端面板、真实 E2E）；发布门禁已执行：ECS Docker L2 14 步全绿（legacy 408 / api 940 / contract 43 / migration 24 / recovery 5 / web 110 / e2e 14 含 5 个 v3 测试 / eval-ab / ruff / OpenAPI 117 paths），见 `artifacts/V3_FINAL_VALIDATION.md`、`artifacts/BATCH_VALIDATION_V3_B4.md`。Known unvalidated 如实记录在案（mock provider 确定性产出、A/B 仅装置验证、共享账号隔离方案、macOS） |
| 主分支 | **CI 已修复，待推送验证** | ruff 0 错；trivy 弃用遭攻陷 action 改钉 digest 容器扫描；pnpm audit corepack 修复；Playwright e2e 已接入 workflow |

## 已撤销/降级的历史文档

| 文档 | 处置 |
|---|---|
| `V2_FINAL_VALIDATION.md` | 撤销 PASS，改写为 REVOKED 并附撤销依据 |
| `V3_FINAL_VALIDATION.md` | 纠正为"实现未完成"，原"仅 native 平台阻塞"结论不成立 |
| `V1_5_NATIVE_VALIDATION.md` | 维持 BLOCKED，标注失效证据行（源码包≠安装器） |
| `BATCH_VALIDATION_*.md` ×12 | 文首加"证据不可信"横幅（缺命令/退出码/digest/`down -v` 证据） |

## 主要缺口 → 蓝图条目对照

### V1.5（本计划收尾范围）
- V15-008：PyInstaller onedir（钉版 Python 3.12）+ Windows Inno Setup/macOS pkg/Linux deb-rpm 真实安装器 + OS 服务 + CLI `web` 入口
- V15-009：`proseforge upgrade` 真实执行（锁→备份→停队列→迁移→健康检查→失败回滚+脱敏报告）
- V15-010：L2 全矩阵 + 原生安装生命周期实测（macOS 在无 Mac 环境下必须保持 BLOCKED，不得谎称绿）

### V2（另立专项计划）
- V2-005：`generate_chat` 接 ContextSnapshot + Story Bible 触发注入 + 完整分支历史
- V2-006：Tiptap/ProseMirror 编辑器 + SelectionToolbar（替换 textarea）
- V2-008：React Flow Workflow Studio + runs 恢复（补迁移 0013）
- V2-007：proposal approve 幂等 + 行锁（修并发多 ChapterVersion 风险）
- V2-009：导出 manifest 持久化（补迁移 0014/0015）、PWA/a11y/i18n
- V2-010：真实 10 步 E2E（蓝图明令 401/#root 不算数）+ v2-openapi.json + v2-schema-check.txt
- 依赖：Tiptap/ProseMirror/React Flow/TanStack Router/Zustand 入 package.json

### V3（另立专项计划）
- V3-002：`policy.authorize` 改 fail-closed + 服务端签名策略快照
- V3-004：执行器接真实模型/provider + `bounded_parallel` 有界并行 + lease expiry/heartbeat/executor version/checkpoint
- V3-005：artifact 服务器 schema 校验 + content hash + allowlist
- V3-006/007：独立评审集群 + Chief Editor 只产 V2 RevisionProposal（去掉占位文字）
- V3-008：有界动态扩图 + 评测装置
- V3-009：审计七要素 + metrics + rate limit + prompt-injection 测试
- 数据完整性：run idempotency_key 唯一约束；resume 遇 FAILED 不得直接 COMPLETED
- V3-010：真实 E2E（不得用 API 手工造 artifact/review 冒充 worker 产出）

### 横向
- 迁移 0013–0015 缺失：在任何发布前补齐（趁 0016+ 未发布可重排）
- 版本号五处不一致 → 本计划对齐 1.5.0
- 仓库仅 0.8.0 tag，无 V1.5/V2/V3 发布 tag 与 release workflow：门禁全绿后再议

## 修复路线（用户确认次序）

1. ✅ 状态纠正（本文档）+ 环境清理（`down -v` + 删 `.pnpm-web-*`）
2. ✅ CI 修复（ruff / trivy 弃用遭攻陷 action 改直跑镜像 / pnpm audit corepack / 接入 e2e；另修复 nginx resolver Podman 不兼容、pnpm store 卷、exports tmpfs）
3. ✅ V15-008 / V15-009 / V15-010（蓝图 V1.5_NATIVE_RUNTIME）——Windows/Linux 绿，macOS BLOCKED 待 runner；证据见 `V1_5_NATIVE_VALIDATION.md` 与 `BATCH_VALIDATION_V1.5_B4.md`
4. ✅ V2-001～010 补齐——V2-010 发布门禁已执行并 PASS（2026-07-20，ECS Docker L2，证据见 `V2_FINAL_VALIDATION.md` / `BATCH_VALIDATION_V2_B4.md`）
5. ✅ V3-001～010 重实现——V3-010 发布门禁已执行并 PASS（2026-07-20，ECS Docker L2，证据见 `V3_FINAL_VALIDATION.md` / `BATCH_VALIDATION_V3_B1..B4.md`）；e2e skip 已恢复（V3-010）：`v3-agent-swarm.spec.ts`、`v3-execution-proposal.spec.ts` 已按真实执行器重写并在容器内首跑通过；`/api/v1/auth/setup` 为一次性 owner 端点（后端不允许第二账号），共享账号不可消除，改为唯一幂等键/项目 slug + RUN_CONCURRENCY_LIMIT 有界重试 + `compose.test.yaml` 放宽 e2e 堆栈 /api/v3 限流桶（写 60/读 240，中间件默认值不变、仍由 api 测试断言 429）

## 证据标准（蓝图 `TEST_EXECUTION_POLICY.md` §五）

- 一切测试在 Podman 容器内跑（`compose.test.yaml` 唯一编排），L1 批次一次 up、串行 exec、`down -v`
- 每批产出 `BATCH_VALIDATION_<版本>_<批号>.md`：任务清单 + 逐条命令 + 退出码 + 测试计数 + `down -v` 确认
- L2 记录 `podman version` 输出与镜像 digest
- 没有命令、退出码、测试数量和产物路径证据，不得写"完成"
