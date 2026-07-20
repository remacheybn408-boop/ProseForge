# V2 Final Validation

Status: **PASS — executed on 2026-07-20 (Asia/Shanghai, UTC+08:00)**

Executed on the ECS test host (36.213.79.118) with native Linux Docker; the run log is `artifacts/v2-l2-run.log`. The previously revoked V2 PASS is superseded by this ledger. Every value below is copied from captured command output; nothing has been filled from memory.

## Scope executed

- Real authenticated 10-step Playwright flow: `apps/web/e2e/v2-professional-flow.spec.ts`.
- Deterministic OpenAPI exporter: `scripts/dump_openapi.py` → `artifacts/v2-openapi.json` (111 paths).
- Contract review worksheet: `artifacts/v2-schema-check.txt` (filled in the same pass window).
- The professional-flow spec disables Playwright tracing because traces can retain manuscript text. Export manifest/hash evidence and request IDs were attached via `testInfo.attach` and harvested from a dedicated spec re-run (same commit, same environment, JSON reporter to preserve attachment bodies).

## L2 environment evidence

| Evidence | Recorded value |
|---|---|
| Git commit | `0687ed5a36a459f1bd637eb865074532e6f0de1d` (git archive snapshot) |
| Docker | 29.6.2 (Server, Linux x86_64, ECS Ubuntu kernel 6.8.0-134) |
| Compose | Docker Compose v5.3.1 |
| API image ID | `sha256:978070f676eb767fa4c94359b13a8ad43238cd5ca226bc0f9fef07cea01f0a71` |
| Web image ID | `sha256:eb7140cbc6ab1e293ed41f3e07d408852484bce6bac10cacf451fbdd0126a0d2` |
| Worker image ID | `sha256:e19991dfe4061e978297d2cca0ddd0098c3545a08bfb8ef1ac96b099f51b9233` |
| Playwright image ID | `sha256:be22982d683fe55ef44f66e042a08be636fa5db61de7479b7a7ddbefb2da6407` (v1.61.1-noble) |
| Start timestamp / timezone | 2026-07-20T14:57:36+08:00 / Asia/Shanghai |
| End timestamp | 2026-07-20T15:06:58+08:00 |

Images are locally built (no registry push), so image IDs are recorded in place of repo digests.

## Command ledger

Compose invocation: `docker compose -f compose.yaml -f compose.test.yaml -f tmp-remote/compose.ecs.yaml` (the extra file only adds the 21559/3000 web port mapping and npm mirror env; it does not change test semantics). Full output: `artifacts/v2-l2-run.log`.

| # | Command (compose args) | Exit | Count/result | Evidence path |
|---:|---|---:|---|---|
| 1 | `docker version` (log header) | 0 | 29.6.2 | `artifacts/v2-l2-run.log` |
| 2 | `up -d --build --wait postgres redis provider-mock api worker web` | 0 | all healthy | same |
| 3 | `run --rm legacy-test` | 0 | 408 passed | `artifacts/pytest.xml` |
| 4 | `run --rm api-test` | 0 | 864 passed, 3 skipped | `artifacts/api-pytest.xml` |
| 5 | `run --rm contract-test` | 0 | 43 passed | `artifacts/contract-pytest.xml` |
| 6 | `run --rm migration-test` | 0 | 24 passed | `artifacts/migration-pytest.xml` |
| 7 | `run --rm recovery-test` | 0 | 5 passed | `artifacts/recovery-pytest.xml` |
| 8 | `run --rm web-test` | 0 | typecheck + 105 vitest (33 files) + build | `artifacts/v2-l2-run.log` |
| 9 | `run --rm e2e` | 0 | 12 passed, 2 skipped (v3 deferred specs), 0 failed | `artifacts/v2-l2-run.log` |
| 10 | `run --rm api-test ruff check proseforge tests` | 0 | All checks passed | `artifacts/v2-l2-run.log` |
| 11 | `run --rm api-test python scripts/dump_openapi.py --output /app/artifacts/v2-openapi.json` | 0 | 111 paths | `artifacts/v2-openapi.json` |
| 12 | Endpoint contract review against `artifacts/v2-schema-check.txt` | 0 | PASS (see worksheet) | `artifacts/v2-schema-check.txt` |
| 13 | `down -v` | 0 | 0 containers/images/volumes left | `artifacts/v2-l2-run.log` |

Fault-injection tests under `tests/fault_injection` run inside the API matrix (864). The v3 concurrency-fault and fault-injection e2e specs ran and passed; the two v3 deferred specs (`v3-agent-swarm`, `v3-execution-proposal`) remain skipped by design pending the V3 rework plan. V1.5 native regressions run with the legacy suite (408); macOS packaging remains the documented platform limitation.

## Professional-flow evidence

Executed end-to-end green twice: once inside the pass e2e suite (12 passed) and once in the attachment-harvest re-run (1 expected, 0 unexpected, 16.9s).

| Step | Required observation | Result | Evidence |
|---:|---|---|---|
| 1 | UI creates a project in the real database | PASS | spec step 1, `artifacts/v2-l2-run.log` e2e section |
| 2 | UI creates a conversation and sends a message | PASS | spec step 2 |
| 3 | Assistant is durably `COMPLETED`; final usage is attributable to its message | PASS | spec step 3 (usage record `is_final`, `total_tokens > 0`) |
| 4 | Editing an earlier user message creates a new branch; old branch byte-for-byte unchanged | PASS | spec step 4 (old branch deep-equal) |
| 5 | Regeneration persists a second candidate and the UI switches/compares candidates | PASS | spec step 5 (`/2` counter) |
| 6 | UI creates and pins a Story Bible fact; the next context snapshot contains its ID | PASS | spec step 6 |
| 7 | UI manuscript selection requests review and rewrite without mutating the active version | PASS | spec step 7 (versions unchanged) |
| 8 | UI diff accepts selected hunks and creates exactly one immutable version | PASS | spec step 8 |
| 9 | UI starts, pauses, reload-recovers, resumes, retries and cancels a durable workflow | PASS | spec step 9 (PAUSED→QUEUED→RUNNING→RETRYING→RUNNING→CANCELLED; `mock-slow` keeps transitions observable; lease handoff fixed in `5053c5e`) |
| 10 | UI requests Markdown/DOCX/EPUB; API verifies manifest source IDs/content hashes and download SHA-256 | PASS | spec step 10 + `artifacts/v2-export-evidence.json` |

Request/correlation IDs: `artifacts/v2-request-ids.json` (19 IDs, header `x-correlation-id`).

Markdown SHA-256: `4262536417e6aef25e795f3e6b932958f47a7c02d1bf775f4dbd0f907c18617f`

DOCX SHA-256: `65f8b42105fbd5419970a9986815c27b7a4c218d7f0140dd8d9946ab783401d2`

EPUB SHA-256: `fab2e5052df28555915269b237cb57cdf0a8cbd733b788a91615c4d5eefdfeef`

(Each value equals its manifest `file_sha256`; see `artifacts/v2-export-evidence.json`.)

## Twelve-item release gate

- [x] Desktop/tablet/narrow-mobile chat shell. (`responsive-assistant.spec.ts`, `visual-a11y.spec.ts` in pass e2e)
- [x] Immutable edit/regenerate/fork/compare/archive history. (steps 4/5; `tests/api/test_conversation_branches.py`)
- [x] Truthful model catalog and reasoning controls. (`tests/api/test_model_capabilities.py`; catalog-first fallback recorded via `context.budget` event)
- [x] Context Inspector included/omitted reasons and token budget. (step 6; `context.budget` run event)
- [x] Structured, pinned, versioned, ownership-safe Story Bible. (step 6; `tests/api/test_story_bible.py`)
- [x] Proposal-only writers/reviewers/revisers; approval creates a version. (steps 7/8; `tests/api/test_reviews_revisions.py`, Idempotency-Key on approve)
- [x] Usage attribution at user/project/conversation/message/workflow levels. (step 3; `tests/api/test_usage.py`, bounded `limit 1..500`)
- [x] Workflow SSE replay/refresh and idempotent controls. (step 9; `tests/api/test_sse_reconnect.py`, `test_workflow_definitions.py`, control idempotency tests)
- [x] Export source version IDs and hashes. (step 10; `tests/api/test_export_manifests.py`; evidence JSON)
- [x] PWA excludes credentials, API responses and manuscripts from cache. (`apps/web/src/lib/pwa/sw.test.ts`: `/api/` bypass, GET-only, static destinations only, no credentials/messages/manuscript)
- [x] Chinese/English parity, keyboard, focus and reduced-motion behavior. (`localization.spec.ts`, `visual-a11y.spec.ts` axe: no critical/serious; full copy review noted below)
- [x] V1.5 native/server gates remain green within documented platform limits. (legacy 408 passed; macOS packaging stays BLOCKED pending a macOS runner)

## Known unvalidated areas

- Full Chinese/English copy proofread is not done; parity is validated at shell/route level plus locale fixtures, not per-string.
- Provider traffic used the deterministic mock (`provider-mock`); no real provider credentials were exercised in this pass.
- macOS native packaging remains BLOCKED (no macOS runner), unchanged from V1.5.
- Browser manual QA (visual inspection by a human) is not part of this ledger; automated axe/responsive/localization specs are the evidence.
- The two deferred v3 specs stay skipped; V3 rework is a separate plan.

Final decision: **PASS** (2026-07-20, ECS Docker L2, commit `0687ed5`; evidence-collection-only spec header fix `x-correlation-id` committed afterwards as it changes no assertion).
