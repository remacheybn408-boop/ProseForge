# ProseForge Web v1 incremental Docker validation

Date: 2026-07-16

All commands below were executed in Docker containers.

- Playwright browser smoke: `1 passed`
- API/contract/unit regression: final Docker API `522 passed, 1 skipped`; contract `17 passed`
- Legacy top-level regression isolated from Web/API integration tests: `408 passed in 209.28s`
- Frontend Vitest: `3 passed`; Vite production build passed
- Backup archive verification passed
- Backup database restore completed into PostgreSQL `proseforge_staging`; `alembic_version` exists and application tables were created
- `proseforge --version` works inside the rebuilt API image
- API, Worker, and Scheduler run as UID/GID `10001`
- Provider contracts: `17 passed` including domestic Chat Completions adapters and native Ollama NDJSON
- Native Cohere V2 contract: `1 passed`; Settings connection probe is covered by browser E2E
- Capability validation: `3 passed` for modality, structured output, reasoning, max output, and context overflow
- Fault injection and interrupted-stream recovery: `2 passed`; unavailable PostgreSQL/Redis returns readiness `503`
- Workflow recovery migration and repository tests: `13 passed`; leases, checkpoints, cost limits, and expired-run recovery verified
- Docker API/unit/provider/fault regression after workflow changes: `38 passed`; backup/recovery suite: `4 passed`
- Conversation idempotency and branch persistence: `3 passed`; duplicate client requests reuse the existing assistant task
- Durable SSE replay and concurrent event publication: `2 passed`; per-conversation event IDs remain unique and ordered
- Affected API/provider/fault regression after event-stream changes: `33 passed`
- Context snapshot persistence/control and file ownership flows: `2 + 10 passed`; snapshot validation/download and file download/delete paths are covered
- Auth session controls and project archive/restore: `10 + 3 passed`; CLI reports release version `1.0.0`
- Chapter version activation and unified diff controls: `11 passed`; ownership and version selection are covered
- Reversible context deduplication, structured summary validation, and compiler fallback coverage: `4 passed`; raw source blocks remain available
- Conversation branch isolation: `4 passed`; fork points are now constrained to the requested conversation and owner
- Chat stop/retry/continue and partial-stream continuation: `5 passed`; recovery resumes at the next durable chunk index
- Worker continuation request compilation passed in Docker; saved partial assistant text is included as continuation context
- Writer/Editor profile roles and frontend settings build: Vitest `2 passed`; Vite production build passed
- Durable Novel Writer task and streamed chapter collection: `5 passed`; empty provider output is rejected and successful chapters activate only after persistence
- Structured Editor review gate and rewrite-loop integration: `5 passed`; invalid review output cannot commit a chapter; Ruff passed
- Legacy database migration repair: API upgraded an existing database missing workflow tables and reached healthy state; migration coverage `2 passed`
- Concurrent chapter version allocation: `3 passed`; PostgreSQL advisory locking prevents duplicate version numbers
- Full rebuilt Docker browser flow: Playwright `1 passed` in `5.3s`; frontend now waits for durable chat completion and restores the selected project after refresh
- Startup health round-trip, migration, and workflow-table checks: recovery `2 passed`, API health `3 passed`; BlobStore probe is removed after verification
- Export request contract and Writing Studio Markdown download control: Web Vitest `2 passed` + Vite build; API/unit regression `10 passed`
- Manual future-model registration and catalog retention: `3 passed`; custom models are marked manual and protected from sync disappearance
- Final rebuilt API/worker/scheduler production stack: all services healthy, readiness `ok`, Celery `pong`
- Docker E2E was rerun after forced recreation of API/worker/web against the isolated test volume: `1 passed`
- Production readiness after returning to the base Compose stack: API/blob/backup/database/redis all `ok`; Celery `inspect ping` returned `pong`
- After API container recreation, the Web/Nginx proxy still served `/api/v1/health/live` successfully via Docker DNS resolution
- Compose services were healthy after rebuild/restart
- Final Docker API regression: `522 passed, 1 skipped`; test entrypoint now runs Alembic plus schema bootstrap before pytest
- Final Docker contract/migration/recovery suites: `17 passed`, `22 passed`, and `5 passed`
- Final Docker frontend validation: Vitest `3 passed`, Vite production build passed, and Playwright E2E `1 passed`
- Frontend draft durability and reconnectable conversation SSE: Vitest `3 passed`; browser E2E remained green after the streaming client change
- Writing Studio now reloads the active chapter version from PostgreSQL after project/chapter navigation; Docker build and E2E remained green after the persistence fix
- Readiness now verifies master-key validity, pgvector availability, partial-message visibility, and expired workflow leases; bootstrap repairs missing PostgreSQL extensions idempotently
- Live Docker fault injection: stopping Redis made `/api/v1/health/ready` return `503`; restarting Redis restored `200` and all readiness checks to `ok`
- Rebuilt production API/worker/scheduler/web images after health changes; production readiness returned `200` with `pgvector`, `master_key`, `partial_messages`, and `expired_workflows` checks
- Final Docker gate rerun: legacy `408 passed`; API `522 passed, 1 skipped`; contract `17 passed`; migration `22 passed`; recovery `5 passed`; web `3 passed`; E2E `1 passed`
- Full repository Ruff gate: `All checks passed` for `proseforge` and `tests` inside the Docker test image
- Backup restore regression: `3 passed`; tampered members are rejected and database restore requires an explicit staging target
- Runtime container contract: `2 passed`; API/worker/scheduler run as UID/GID `10001` and Nginx SSE buffering is disabled
- Same-production-Compose `down`/`up` persistence probe preserved PostgreSQL data; the temporary probe table was removed afterward
