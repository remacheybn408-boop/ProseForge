# V3 Final Validation

Status: **NOT READY — fault-injection gate remains open**

Current master under validation: HEAD after the durable executor, migration `0023_agent_task_budget`, event cursor locking, and resume/retry requeue fixes.

Fresh Podman evidence:

- Full Python suite: **645 passed, 1 skipped, 3 warnings**.
- Full Playwright suite: **11 passed**.
- Frontend Vitest: **18 files / 27 tests passed**.
- TypeScript and Vite build: passed.
- Redis/PG readiness interruption: **503 → 200** after restart.
- Worker interruption: live API remained **200** and worker recovered.
- Concurrent event/control audit: **1 passed**, unique cursors.

Open release-gate items:

- Provider timeout and malformed provider JSON have no V3 provider execution path yet.
- Budget-exhaustion needs a dynamic-expansion or injected-runtime end-to-end case.
- Exact worker kill after artifact commit and replay needs a deterministic harness.
- Native macOS/Windows installer/signing execution is unavailable on this Windows host.

This artifact deliberately does not mark V3 green.
