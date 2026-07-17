# V3 Agent Swarm Validation

Status: **PASS — V3-010 Podman release gate green**

Runtime: Podman CLI on PostgreSQL, Redis, provider-mock, API, worker, and Playwright containers.

Evidence:

- Full Python suite: **645 passed, 1 skipped, 3 warnings**.
- Agent/architecture/security focused suite: **15 passed**.
- Frontend Vitest: **18 files, 27 tests passed**.
- TypeScript `tsc --noEmit`: passed.
- V3 Playwright flow: **1 passed**.
- API flow covered idempotent run creation, ownership-scoped tasks, event replay cursors, pause/resume/retry/cancel, artifact SHA-256 provenance, review evidence, and audit history.
- Worker fault injection: worker stopped; API health remained **200**; worker restarted; Alembic remained `0021_agent_evaluations (head)`.
- V3 UI is wired into the main workspace as **Agent Swarm** and does not write `ChapterVersion`; review output remains proposal-bound.

Migration head: `0021_agent_evaluations`.

Native macOS/Windows runtime validation remains outside this Windows/Podman gate and is not claimed here.
