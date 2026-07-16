# ProseForge Grok Product Completion — Stage 0 Baseline Audit

Audit date: 2026-07-16 (Asia/Tokyo)

## Revision and required inputs

- `origin/master`: `8efcf91f07feed4f76366e5e19abaa08f2d4e316`
- Audit branch: `feat/grok-product-completion`
- Baseline source commit: `8efcf91f07feed4f76366e5e19abaa08f2d4e316`
- Baseline fix commit: `7e90b5f7b3a11adfefdd7d49ba10ae69549924d0`
- `docs/plans/PROSEFORGE_WEB_V1_CODEX_PLAN.md`: present and read
- `docs/plans/PROSEFORGE_WEB_V1_1_INK_USAGE_REMEDIATION_PLAN.md`: present and read
- `docs/plans/PROSEFORGE_GROK_PRODUCT_COMPLETION_PLAN.md`: **missing from latest master**
- `.github/workflows/ci.yml`: **missing**

The missing Grok plan is a blocking input for strict stage 1–11 execution. No README,
CHANGELOG, or commit message was used as a substitute.

## Docker baseline commands

| Command | Exit code | Result |
| --- | ---: | --- |
| `docker compose -f compose.yaml -f compose.test.yaml config --quiet` | 0 | pass |
| `docker compose -f compose.yaml -f compose.test.yaml build` | 0 | pass; legacy image build required the full legacy/RAG dependency set |
| `docker compose -f compose.yaml -f compose.test.yaml run --rm api-test` | 0 | 554 passed, 1 skipped before legacy image; after backup fix |
| `docker compose -f compose.yaml -f compose.test.yaml run --rm contract-test` | 0 | 19 passed |
| `docker compose -f compose.yaml -f compose.test.yaml run --rm migration-test` | 0 | 24 passed |
| `docker compose -f compose.yaml -f compose.test.yaml run --rm recovery-test` | 0 | 5 passed |
| `docker compose -f compose.yaml -f compose.test.yaml run --rm web-test` | 0 | 12 files / 22 tests passed; typecheck and production build passed |
| `docker compose -f compose.yaml -f compose.test.yaml run --rm legacy-test` | 0 | 408 passed |
| `docker compose -f compose.yaml -f compose.test.yaml run --rm e2e` | 0 | 6 passed |
| `docker compose -f compose.yaml -f compose.test.yaml exec -T api python -m proseforge.operations.startup_check` | 0 | pass; command emitted no report text |
| `docker compose -f compose.yaml -f compose.test.yaml exec -T worker celery -A proseforge.workflows.celery_app inspect ping --timeout=5` | 0 | 1 worker online, pong |

## Real runtime backup/restore

Initial production-layout attempt exposed a bug: when `/data/backups` was inside
the `/data` source tree, the archive included itself and `backup verify` failed.
A TDD regression test was added, the minimal exclusion was implemented, and commit
`7e90b5f` was created after `git diff --check` passed.

After rebuilding the current API image:

- `backup create --source /data --root /data/backups --include-database`: exit 0
- `backup verify /data/backups/proseforge-20260716T112230Z.tar.gz`: exit 0
- restore into `proseforge_staging`: exit 0
- live `projects` count: 1
- staging `projects` count: 1

## Current evidence gaps

- Only `ordinary-user-smoke.spec.ts` is a real authenticated browser flow. It covers
  setup/login, provider setup, project creation, outline intake, workflow creation,
  generated chapter, save, chat, branch, and refresh. The other five E2E tests are
  shell/protection checks; three only assert unauthenticated 401 responses.
- No CI workflow evidence exists because `.github/workflows/ci.yml` is absent.
- `apps/web/src/main.tsx` remains a large business-logic monolith.
- Version values are inconsistent: `VERSION=1.1.0`, Python package `1.0.0`, API
  `1.0.0`, and Web package `1.0.0`.
- Context route/UI still defaults to a fixed `128000` context window.
- The required Grok plan is unavailable, so the priority list cannot yet be mapped
  to authoritative numbered tasks and commit messages.

This file is an audit record, not a completion claim.
