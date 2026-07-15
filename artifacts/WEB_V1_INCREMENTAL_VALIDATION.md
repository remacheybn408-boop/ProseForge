# ProseForge Web v1 incremental Docker validation

Date: 2026-07-16

All commands below were executed in Docker containers.

- Playwright browser smoke: `1 passed`
- API/contract/unit regression: `37 passed`
- Legacy full regression: `483 passed`
- Frontend Vitest: `2 passed`; Vite production build passed
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
- Final rebuilt API/worker/scheduler production stack: all services healthy, readiness `ok`, Celery `pong`
- Docker E2E was rerun after forced recreation of API/worker/web against the isolated test volume: `1 passed`
- Production readiness after returning to the base Compose stack: API/blob/backup/database/redis all `ok`; Celery `inspect ping` returned `pong`
- After API container recreation, the Web/Nginx proxy still served `/api/v1/health/live` successfully via Docker DNS resolution
- Compose services were healthy after rebuild/restart
