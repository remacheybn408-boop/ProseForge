# ProseForge 验证状态事实源

> 本文件是三个版本验证状态的唯一事实源（2026-07-18 全量排查后建立）。任何与本文件冲突的历史验证文档，以本文件为准。蓝图：`D:\引擎备份\PROSEFORGE_ENGINEERING_EXECUTION_BLUEPRINT`。
>
> 最近状态更新：2026-07-20。V2-010 的测试与证据模板已准备，但完整 L2 尚未执行，因此 V2 不得标记为完成或 PASS。

## 版本真实状态

| 版本 | 真实状态 | 说明 |
|---|---|---|
| V1.5 Native Runtime | **Windows/Linux 达成；macOS BLOCKED**（2026-07-18） | V15-008/009/010 已按蓝图实现并实测：PyInstaller onedir（钉版 3.12）、Inno 安装器（安装/卸载留数据实测）、deb/rpm/pkg 脚本、CLI `web`/真实 `upgrade`、L2 全矩阵绿。macOS 安装验证待 macOS runner |
| V2 Chat Workspace | **实施中；发布门禁未运行** | V2-005～007 已进入 `master`；V2-008/V2-009 仍在并行收尾。V2-010 已准备真实 10 步 E2E、OpenAPI 导出脚本和 schema 检查表，但完整 Podman L2、OpenAPI 产物与最终证据均未执行/生成 |
| V3 Agent Swarm | **实现未完成** | 有表、基础路由和 UI 壳；执行器是占位（串行、不调模型、固定 JSON）、权限 fail-open、无评审集群/记忆/扩图/评测/安全边界 |
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
4. 🔄 V2-001～010 补齐中——V2-010 非重叠测试/文档已准备，仍须等待 V2-008/V2-009 收尾后执行完整 Podman L2
5. ⬜ V3-001～010 重实现（另立计划）——注意恢复 e2e skip：`v3-agent-swarm.spec.ts`、`v3-execution-proposal.spec.ts`；修共享账号 fixture 隔离

## 证据标准（蓝图 `TEST_EXECUTION_POLICY.md` §五）

- 一切测试在 Podman 容器内跑（`compose.test.yaml` 唯一编排），L1 批次一次 up、串行 exec、`down -v`
- 每批产出 `BATCH_VALIDATION_<版本>_<批号>.md`：任务清单 + 逐条命令 + 退出码 + 测试计数 + `down -v` 确认
- L2 记录 `podman version` 输出与镜像 digest
- 没有命令、退出码、测试数量和产物路径证据，不得写"完成"
