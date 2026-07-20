# V3 Final Validation

Status: **PASS — executed on 2026-07-20 (Asia/Shanghai, UTC+08:00)**

Executed on the ECS test host (36.213.79.118) with native Linux Docker; the run log is `artifacts/v3-l2-run.log`. The 2026-07-18 "V3 incomplete" assessment is superseded: the V3 rework (agent swarm, bounded executor, review cluster, approval-bound chief editor, memory, expansion, evaluation harness, security/observability) is implemented and this ledger records its release-gate execution. Every value below is copied from captured command output.

Two earlier attempts of this same pass failed fast and were fixed at the root cause, then the full pass was re-run from scratch on the final commit: (1) evaluation fixture hashes drifted because `git archive` on Windows converted fixture txt files to CRLF — fixed in `fbb1f4f` (`.gitattributes` pins `tests/evaluation/fixtures/*.txt` to LF); (2) `v3-agent-swarm.spec.ts` raced the sign-in request (`page.goto` before the session landed) and under-budgeted its 90 s timeout — fixed in `bd87c9d` (wait for the signed-in shell, 180 s budget; the spec passes standalone in 7.7 s).

## Scope executed

- Full L2 matrix on the V3 rework commits `be9011d`…`bd87c9d` (9 implementation commits + 2 test-hardening fixes).
- Real Playwright v3 specs (no longer skipped): `v3-agent-swarm.spec.ts`, `v3-execution-proposal.spec.ts`, plus `v3-concurrency-fault.spec.ts` and `v3-fault-injection.spec.ts` (2 tests).
- Evaluation A/B harness: `scripts/eval_ab_seed.py` executed against the live API (deterministic mock provider).
- Deterministic OpenAPI exporter: `scripts/dump_openapi.py` → `artifacts/v3-openapi.json` (117 paths, 17 under `/api/v3/`).
- The v3 specs disable Playwright tracing because traces can retain manuscript text; per blueprint §09 no `testInfo.attach` evidence files are required for V3.

## L2 environment evidence

| Evidence | Recorded value |
|---|---|
| Git commit | `bd87c9dac263e69edf9b34b0040a8a9ec88011e7` (git archive snapshot) |
| Docker | 29.6.2 (Server, Linux x86_64, ECS Ubuntu kernel 6.8.0-134) |
| Compose | Docker Compose v5.3.1 |
| API image ID | `sha256:4ec120a619b034827c89b18791e19da137a2f26b5c54f4c7c5e8d12b4aa1a913` |
| Worker image ID | `sha256:cb8b358264d2892b7ef331a27f6e9da8511a9c586df6aaf42ff3a4d6b1117b2c` |
| API-test image ID | `sha256:1f2ec28107b211d915a1ecc7c3213291afe212a162d60309b2939efb12c8fb1f` |
| Web image ID | `sha256:8d0aed1416c3f5cefa48c91344bb533481f0dadfcbfa427b39343c2001928656` |
| Playwright image ID | `sha256:be22982d683fe55ef44f66e042a08be636fa5db61de7479b7a7ddbefb2da6407` (v1.61.1-noble) |
| Start timestamp / timezone | 2026-07-20T23:34:14+08:00 / Asia/Shanghai |
| End timestamp | 2026-07-20T23:41:56+08:00 |

Images are locally built (no registry push), so image IDs are recorded in place of repo digests.

## Command ledger

Compose invocation: `docker compose -f compose.yaml -f compose.test.yaml -f tmp-remote/compose.ecs.yaml` (the extra file only adds the 21559/3000 web port mapping and npm mirror env; it does not change test semantics). Full output: `artifacts/v3-l2-run.log`.

| # | Command (compose args) | Exit | Count/result | Evidence path |
|---:|---|---:|---|---|
| 1 | `down -v` (pre-pass reset) | 0 | stack/volumes removed | `artifacts/v3-l2-run.log` |
| 2 | `up -d --build --wait postgres redis provider-mock api worker web` | 0 | all healthy | same |
| 3 | image digests recorded | 0 | 5 IDs above | same |
| 4 | `run --rm legacy-test` | 0 | 408 passed | `artifacts/pytest.xml` |
| 5 | `run --rm api-test` | 0 | 940 passed | `artifacts/api-pytest.xml` |
| 6 | `run --rm contract-test` | 0 | 43 passed | `artifacts/contract-pytest.xml` |
| 7 | `run --rm migration-test` | 0 | 24 passed | `artifacts/migration-pytest.xml` |
| 8 | `run --rm recovery-test` | 0 | 5 passed | `artifacts/recovery-pytest.xml` |
| 9 | `run --rm web-test` | 0 | tsc + 110 vitest (33 files) + build 603 ms | `artifacts/v3-l2-run.log` |
| 10 | `run --rm e2e` | 0 | 14 passed, 0 failed (incl. 5 v3 tests) | `artifacts/v3-l2-run.log` |
| 11 | `run --rm api-test python scripts/eval_ab_seed.py` | 0 | run A COMPLETED (budget 12), run B COMPLETED (budget 24), comparison `cmp-e74aabc413d7eb1f7d5d36f7` | `artifacts/v3-l2-run.log` |
| 12 | `run --rm api-test ruff check proseforge tests` | 0 | All checks passed | `artifacts/v3-l2-run.log` |
| 13 | `run --rm api-test python scripts/dump_openapi.py --output /app/artifacts/v3-openapi.json` | 0 | 117 paths (17 v3) | `artifacts/v3-openapi.json` |
| 14 | `down -v` (evidence teardown) | 0 | volumes removed | `artifacts/v3-l2-run.log` |

Fault-injection tests run inside the API matrix (`tests/fault_injection`) and as e2e specs (`v3-fault-injection.spec.ts`: deterministic fault modes terminate durably, no raw prompt in redacted surfaces; worker crash after artifact commit is replay-safe). V1.5 native regressions run with the legacy suite (408); macOS packaging remains the documented platform limitation.

## Evaluation A/B evidence

From the eval-ab step output (`artifacts/v3-l2-run.log`): run A `18c409c4a1b608ce00000000` → COMPLETED (budget_used=12), run B `18c409c4df71c83000000000` → COMPLETED (budget_used=24); artifact hashes run A: `7f260793b29b…8701bb0` (1 artifact), run B: `7f260793b29b…8701bb0`, `477f20f5315d…b567858a` (2 artifacts); comparison id `cmp-e74aabc413d7eb1f7d5d36f7` with per-dimension scores. Under the deterministic mock provider this proves the harness (seed → bounded runs → artifacts → scored comparison); it is not a model-quality judgement.

## Thirteen-item release gate

- [x] Roles and policies are server-controlled and versioned. (fail-closed `policy.authorize` + signed policy snapshots, `be9011d`; `tests/agents/test_policy_failclosed.py` 11, `test_role_policy.py`, `test_role_handlers.py` 5)
- [x] Graph validation blocks cycles, unknown roles, invalid schemas, depth/fanout and budget abuse. (`tests/agents/test_task_graph.py`; API 422s in `tests/api/test_agent_endpoints.py` 10)
- [x] Native/server executors are bounded and restartable. (real executor: bounded parallel 16, lease expiry/heartbeat, measured budgets, `f49e893`; `tests/agents/test_agent_executor.py` 8)
- [x] Checkpoints and event cursors recover after worker/process failure. (`tests/agents/test_checkpoint_parallel.py`; `tests/api/test_recovery*.py` 5; e2e worker-crash replay)
- [x] Artifacts are schema-validated, hashed and provenance-linked. (`tests/agents/test_artifact_memory.py`, `tests/test_run_artifacts.py`; e2e asserts `sha256` format on created artifact)
- [x] Shared memory is scoped and candidate facts need approval. (`tests/agents/test_memory_service.py` 5)
- [x] Review swarm retains conflicts and evidence. (`c79284c`; `tests/agents/test_review_swarm.py`, `test_review_handlers.py` 5; e2e asserts CONFLICT + `conflict_group` persisted)
- [x] Chief Editor can create only a V2 RevisionProposal. (`e8120ba`; `tests/agents/test_chief_approval.py`, `test_chief_handler.py` 5; direct ChapterVersion write → 422)
- [x] Only user approval creates ChapterVersion. (approval-bound proposal flow; e2e `v3-execution-proposal.spec.ts` produces only a V2 proposal)
- [x] Dynamic expansion is bounded, auditable and budgeted. (`tests/agents/test_expand_graph_runtime.py` 12)
- [x] Injection and tool abuse tests pass. (`tests/api/test_agent_security.py` 8, `tests/agents/test_security.py`; e2e redaction assertions)
- [x] E2E proves pause/reload/retry/reject/approve/cancel. (`v3-agent-swarm.spec.ts`: pause→resume→retry→task-retry→CONFLICT review→cancel + UI panel; `v3-execution-proposal.spec.ts`: pause/resume across worker boundaries, proposal-only output)
- [x] V1.5 and V2 gates remain green. (legacy 408; full V2 matrix incl. `v2-professional-flow.spec.ts` in the same pass)

## Known unvalidated areas

- Provider traffic used the deterministic mock (`provider-mock`); model output is therefore deterministic and no real provider credentials were exercised.
- The evaluation A/B run verifies the harness mechanics (seeding, bounded execution, artifact hashing, scored comparison), not comparative model quality.
- The product allows exactly one account (`/api/v1/auth/setup` is one-shot), so all e2e specs share the suite account; isolation is via unique idempotency keys, unique project slugs, bounded RUN_CONCURRENCY_LIMIT retries, and relaxed `/api/v3` rate buckets in the test stack (write 60/read 240; middleware defaults unchanged and still asserted by API tests).
- macOS native packaging remains BLOCKED (no macOS runner), unchanged from V1.5.
- Browser manual QA (human visual inspection) is not part of this ledger; automated axe/responsive/localization specs are the evidence.

Final decision: **PASS** (2026-07-20, ECS Docker L2, commit `bd87c9d`; pass executed clean from `down -v` to `down -v` with all 14 ledger steps exit 0).
