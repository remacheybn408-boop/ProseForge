# V3 Final Validation

Status: **NOT READY — worker crash replay/native platform gate remains open**

Current master under validation: HEAD after the durable executor, migration `0024_agent_fault_mode`, event cursor locking, and resume/retry requeue fixes.

Fresh Podman evidence:

- Full Python suite: **645 passed, 1 skipped, 3 warnings**.
- Full Playwright suite: **13 passed**.
- Frontend Vitest: previously verified **18 files / 27 tests passed**; this rerun was blocked by the Podman dependency volume missing the Linux `rolldown` optional native binding.
- TypeScript and Vite build: previously passed; this rerun was blocked by the same dependency-volume issue.
- Redis/PG readiness interruption: **503 → 200** after restart.
- Worker interruption: live API remained **200** and worker recovered.
- Concurrent event/control audit: **1 passed**, unique cursors.
- Deterministic fault E2E covers provider timeout, malformed JSON, and budget exhaustion terminal states.
- Worker-child crash-after-artifact E2E passed: one artifact, one commit event, one task attempt, and durable replay completion.

Open release-gate items:

- Native macOS/Windows installer/signing execution is unavailable on this Windows host.

This artifact deliberately does not mark V3 green.
