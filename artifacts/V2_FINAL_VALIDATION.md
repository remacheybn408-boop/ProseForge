# V2 Final Validation

Status: **REVOKED — 门禁未达成（2026-07-18 撤销）**

## 撤销依据（2026-07-18 全量排查）

此前"PASS"认定不成立，对照蓝图 `V2_CHAT_WORKSPACE` 实测如下：

1. **E2E 证据不合格**。蓝图红线：只证明 401、`#root` 或页面存在的 E2E 一律不算数。实际 `apps/web/e2e/localization.spec.ts` 只查 `#root`，`editor-draft-and-export.spec.ts`/`workflow-control.spec.ts` 只查 401，`responsive-assistant.spec.ts` 只查页面 HTTP 成功。蓝图要求的 10 步专业流程（建项目→发消息→编辑旧消息→分支对比→Story Bible→选区审改→partial hunk→工作流恢复→导出校验）不存在。
2. **聊天未使用上下文**。`proseforge/workflows/tasks.py::generate_chat` 只把最近一条用户消息发给模型：无完整分支历史、无 ContextSnapshot、无 Story Bible 触发注入、`system_blocks` 为空，违反 V2-005 核心要求。
3. **专业编辑器未实现**。`apps/web/src/features/editor/ManuscriptEditor.tsx` 仍是 `<textarea>`，无 Tiptap/ProseMirror、无 SelectionToolbar（V2-006）。
4. **Workflow Studio 未实现**。`apps/web/src/features/workflows/WorkflowCanvas.tsx` 只是按钮列表，非 React Flow 画布（V2-008）。
5. **依赖缺失**。`apps/web/package.json` 无 Tiptap、ProseMirror、React Flow、TanStack Router、Zustand 等蓝图要求依赖。
6. **要求的证据工件不存在**：`artifacts/v2-openapi.json`、`artifacts/v2-schema-check.txt` 未产出。

## 历史记录（不可信，仅存档）

> V2-010 is complete on local `master` commit `7e55abb`; later V3 commits preserve this gate.
>
> The release gate was executed in Podman and passed: 645 Python tests, 18 frontend test files / 27 tests, TypeScript, Vite build, 8 Playwright tests, and axe-core with zero serious or critical violations. The professional flow persisted assistant completion and provider usage, created and approved an immutable revision proposal, generated a new version, and exported a selected-version snapshot with manifest and SHA-256 evidence.
>
> One optional RAG test is skipped because `chromadb` is not installed. Native OS packaging remains a separate V1.5 platform limitation.

说明：测试数量通过 ≠ 功能完整。上述数字即便属实，也不覆盖蓝图 V2-001～010 的功能验收项。

V2 将按蓝图 V2-001～010 逐项补齐后重新执行 V2-010 发布门禁，证据标准见 `artifacts/VALIDATION_STATUS.md`。
