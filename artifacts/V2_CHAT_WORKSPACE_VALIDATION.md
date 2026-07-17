# V2 Chat Workspace Validation

Status: **BLOCKED — V2-010 release gate is not fully green**  
Local runtime: Podman  
Execution date: 2026-07-18  
Current master SHA: `5e88c32`

Implemented in order: V2-001 shell, V2-002 immutable conversation metadata, V2-003 branch semantics, V2-004 reasoning capabilities, V2-005 Story Bible, V2-006 selection-aware editor fallback, V2-007 review/revision proposal primitives, V2-008 workflow studio primitives, V2-009 PWA/export/i18n surfaces.

## Evidence

- Podman backend API/integration/migration slice: **76 passed**.
- Earlier full backend matrix with PostgreSQL/Redis on the Podman network: **645 passed, 1 optional RAG test skipped** (`chromadb` unavailable), 3 warnings.
- Podman frontend Vitest: **18 files / 27 tests passed**.
- Podman TypeScript `tsc --noEmit`: passed.
- Podman Vite production build to the served `proseforge-web-dist` volume: passed.
- Real Podman API flow: migrations to `0012_review_revision`, login, project, conversation, Story Bible, branch and ownership paths passed.
- Real Playwright ordinary-user flow: **1 passed**; it covered login, project creation, provider credential masking/probe, outline intake, workflow generation, chapter version save, chat, fork and reload.
- The five additional lightweight Playwright protection/shell tests passed when run with the same Podman stack.

## Remaining blockers

- The blueprint’s V2-010 ten-step professional flow is not implemented as a test in the current tree: message editing/regeneration, review/rewrite approval, workflow recovery controls, and Markdown/DOCX/EPUB hash verification remain unverified end to end.
- The required axe-core visual accessibility suite is absent from `apps/web/e2e`; it is not tested.
- The checked-in test image is stale and omits declared `aiosqlite`; rebuilding it was blocked by the container’s invalid inherited pip proxy. The repository was not changed to bypass this dependency.
- Native macOS/Windows evidence remains unavailable on this Windows host.

V2 is therefore not marked complete, not tagged, and not pushed as a release.
