# V3 Fault Injection Status

Execution runtime: Podman CLI.

| Scenario | Current evidence | Status |
|---|---|---|
| Worker stopped | API live remained 200; worker restarted | PASS |
| Redis unavailable | readiness 503, then 200 after restart | PASS |
| PostgreSQL unavailable | readiness 503, then 200 after restart | PASS |
| Concurrent event/control writes | Playwright audit cursor test passed; no duplicate sequences | PASS |
| Provider timeout | V3 executor currently uses deterministic worker candidates, not a provider call | NOT IMPLEMENTED |
| Malformed model JSON | No provider response is parsed in the V3 executor yet | NOT IMPLEMENTED |
| Budget exhaustion terminal state | Per-task token budgets are now persisted and runtime terminal state is implemented; an end-to-end dynamic-expansion injector is still missing | PARTIAL |
| Worker crash after artifact commit | Restart smoke exists; exact after-commit kill/replay scenario remains | PARTIAL |

The V3 release gate remains open until the NOT IMPLEMENTED/PARTIAL rows have deterministic tests and terminal-state evidence.
