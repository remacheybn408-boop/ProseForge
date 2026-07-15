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
- Final rebuilt API/worker/scheduler production stack: all services healthy, readiness `ok`, Celery `pong`
- Docker E2E was rerun after forced recreation of API/worker/web against the isolated test volume: `1 passed`
- Production readiness after returning to the base Compose stack: API/blob/backup/database/redis all `ok`; Celery `inspect ping` returned `pong`
- After API container recreation, the Web/Nginx proxy still served `/api/v1/health/live` successfully via Docker DNS resolution
- Compose services were healthy after rebuild/restart
