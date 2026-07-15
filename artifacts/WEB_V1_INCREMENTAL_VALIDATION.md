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
- After API container recreation, the Web/Nginx proxy still served `/api/v1/health/live` successfully via Docker DNS resolution
- Compose services were healthy after rebuild/restart
