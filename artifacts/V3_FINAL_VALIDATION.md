# V3 Final Validation

Status: **NOT READY - native platform gate remains open**

Current master under validation: durable executor, migration `0024_agent_fault_mode`, event cursor locking, resume/retry requeue, and worker-crash replay safety.

Fresh Podman evidence:

- Full Python suite: **645 passed, 1 skipped, 3 warnings**.
- Frontend Vitest: **18 files / 27 tests passed**.
- TypeScript: passed.
- Vite production build: passed using a dedicated Podman dist volume.
- Full Playwright suite: **13 passed**.
- Redis/PG readiness interruption: **503 -> 200** after restart.
- Worker interruption: live API remained **200** and worker recovered.
- Concurrent event/control audit: unique cursors verified.
- Deterministic fault E2E covers provider timeout, malformed JSON, and budget exhaustion.
- Worker-child crash-after-artifact E2E passed: one artifact, one commit event, one task attempt, and durable replay completion.

Open release-gate item:

- Native macOS/Windows installer and signing execution is unavailable on this Windows host.

This artifact deliberately does not mark V3 green until native platform validation is supplied.
