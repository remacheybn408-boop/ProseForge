# V2 Final Validation

Status: **NOT RUN — V2-010 release gate pending**

Prepared on 2026-07-20 (Asia/Tokyo). This file is an evidence ledger, not evidence by itself. The previous V2 PASS remains revoked. No command, exit code, test count, image digest, request/trace ID, or download hash has been invented during preparation.

## Scope prepared

- Real authenticated 10-step Playwright flow: `apps/web/e2e/v2-professional-flow.spec.ts`.
- Deterministic OpenAPI exporter: `scripts/dump_openapi.py`.
- Contract review worksheet: `artifacts/v2-schema-check.txt`.
- `artifacts/v2-openapi.json` is deliberately absent until the L2 command actually generates it.
- The professional-flow spec disables Playwright tracing because traces can retain manuscript text. It attaches only request IDs and export manifest/hash evidence to the ephemeral Playwright result directory.

## L2 environment evidence

| Evidence | Recorded value |
|---|---|
| Git commit | PENDING |
| `podman version` | NOT RUN |
| Compose implementation/version | NOT RUN |
| API image ID and repo digest | NOT RUN |
| Web image ID and repo digest | NOT RUN |
| Worker image ID and repo digest | NOT RUN |
| Playwright image ID and repo digest | NOT RUN |
| Start timestamp / timezone | PENDING / Asia/Tokyo |
| End timestamp | PENDING |

## Planned command ledger

All rows below are **NOT RUN**. Replace placeholders only from captured command output.

| # | Command | Exit | Count/result | Evidence path |
|---:|---|---:|---|---|
| 1 | `podman version` | NOT RUN | PENDING | PENDING |
| 2 | `podman compose -f compose.yaml -f compose.test.yaml up -d --wait postgres redis provider-mock api worker web` | NOT RUN | PENDING | PENDING |
| 3 | `podman compose -f compose.yaml -f compose.test.yaml run --rm legacy-test` | NOT RUN | PENDING | `artifacts/pytest.xml` |
| 4 | `podman compose -f compose.yaml -f compose.test.yaml run --rm api-test` | NOT RUN | PENDING | `artifacts/api-pytest.xml` |
| 5 | `podman compose -f compose.yaml -f compose.test.yaml run --rm contract-test` | NOT RUN | PENDING | `artifacts/contract-pytest.xml` |
| 6 | `podman compose -f compose.yaml -f compose.test.yaml run --rm migration-test` | NOT RUN | PENDING | `artifacts/migration-pytest.xml` |
| 7 | `podman compose -f compose.yaml -f compose.test.yaml run --rm recovery-test` | NOT RUN | PENDING | `artifacts/recovery-pytest.xml` |
| 8 | `podman compose -f compose.yaml -f compose.test.yaml run --rm web-test` | NOT RUN | PENDING | PENDING |
| 9 | `podman compose -f compose.yaml -f compose.test.yaml run --rm e2e` | NOT RUN | PENDING | ephemeral `apps/web/test-results` |
| 10 | `podman compose -f compose.yaml -f compose.test.yaml run --rm api-test ruff check proseforge tests scripts` | NOT RUN | PENDING | PENDING |
| 11 | `podman compose -f compose.yaml -f compose.test.yaml run --rm api-test python scripts/dump_openapi.py --output artifacts/v2-openapi.json` | NOT RUN | PENDING | `artifacts/v2-openapi.json` (not generated yet) |
| 12 | Manual/static endpoint review against `artifacts/v2-schema-check.txt` | NOT RUN | PENDING | `artifacts/v2-schema-check.txt` |
| 13 | `podman compose -f compose.yaml -f compose.test.yaml down -v` | NOT RUN | PENDING | PENDING |

Fault-injection tests under `tests/fault_injection` run with the full API matrix. V1.5 native regressions run with the legacy/full Python suites; macOS packaging remains a separately recorded platform limitation unless a macOS runner supplies new evidence.

## Professional-flow evidence

| Step | Required observation | Result | Evidence |
|---:|---|---|---|
| 1 | UI creates a project in the real database | NOT RUN | PENDING |
| 2 | UI creates a conversation and sends a message | NOT RUN | PENDING |
| 3 | Assistant is durably `COMPLETED`; final usage is attributable to its message | NOT RUN | PENDING |
| 4 | Editing an earlier user message creates a new branch; old branch is byte-for-byte unchanged | NOT RUN | PENDING |
| 5 | Regeneration persists a second candidate and the UI switches/compares candidates | NOT RUN | PENDING |
| 6 | UI creates and pins a Story Bible fact; the next context snapshot contains its ID | NOT RUN | PENDING |
| 7 | UI manuscript selection requests review and rewrite without mutating the active version | NOT RUN | PENDING |
| 8 | UI diff accepts selected hunks and creates exactly one immutable version | NOT RUN | PENDING |
| 9 | UI starts, pauses, reload-recovers, resumes, retries and cancels a durable workflow | NOT RUN | PENDING |
| 10 | UI requests Markdown/DOCX/EPUB; API verifies manifest source IDs/content hashes and download SHA-256 | NOT RUN | PENDING |

Request/trace IDs: PENDING.

Markdown SHA-256: PENDING.

DOCX SHA-256: PENDING.

EPUB SHA-256: PENDING.

## Twelve-item release gate

- [ ] Desktop/tablet/narrow-mobile chat shell.
- [ ] Immutable edit/regenerate/fork/compare/archive history.
- [ ] Truthful model catalog and reasoning controls.
- [ ] Context Inspector included/omitted reasons and token budget.
- [ ] Structured, pinned, versioned, ownership-safe Story Bible.
- [ ] Proposal-only writers/reviewers/revisers; approval creates a version.
- [ ] Usage attribution at user/project/conversation/message/workflow levels.
- [ ] Workflow SSE replay/refresh and idempotent controls.
- [ ] Export source version IDs and hashes.
- [ ] PWA excludes credentials, API responses and manuscripts from cache.
- [ ] Chinese/English parity, keyboard, focus and reduced-motion behavior.
- [ ] V1.5 native/server gates remain green within documented platform limits.

## Known unvalidated areas

- The complete Podman L2 matrix has not been executed.
- The OpenAPI JSON has not been generated or reviewed.
- Browser rendering, console health, accessibility, responsive viewports and PWA cache behavior have not been revalidated in this preparation pass.
- Workflow timing/race behavior and real download artifacts remain unverified until the professional flow runs against the final V2-008/V2-009 implementation.

Final decision: **PENDING**.
