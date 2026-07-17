# V3 Fault Injection Status

Execution runtime: Podman CLI.

| Scenario | Current evidence | Status |
|---|---|---|
| Worker stopped | API live remained 200; worker restarted | PASS |
| Redis unavailable | readiness 503, then 200 after restart | PASS |
| PostgreSQL unavailable | readiness 503, then 200 after restart | PASS |
| Concurrent event/control writes | Playwright audit cursor test passed; no duplicate sequences | PASS |
| Provider timeout | Development-only persisted fault mode terminates the worker run as FAILED | PASS (injected boundary) |
| Malformed model JSON | Development-only malformed JSON mode terminates the worker run as FAILED | PASS (injected boundary) |
| Budget exhaustion terminal state | Development-only mode terminates as BUDGET_EXHAUSTED; per-task budgets are persisted | PASS (injected boundary) |
| Worker crash after artifact commit | Restart smoke exists; exact after-commit kill/replay scenario remains | PARTIAL |

The V3 release gate remains open until the exact worker kill-after-artifact replay harness is complete and native platform limits are reconciled.
