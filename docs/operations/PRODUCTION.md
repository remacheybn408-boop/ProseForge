# ProseForge production operations

Production configuration is supplied only through environment variables. Do not copy development defaults into a production `.env` file.

Required values include PostgreSQL credentials, `PROSEFORGE_PUBLIC_URL`, async and sync database URLs, Redis URL, a base64-encoded 32-byte `PROSEFORGE_MASTER_KEY`, a 32-byte-or-longer `PROSEFORGE_JWT_SECRET`, and a non-default bootstrap password.

Start the stack with:

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

The API container runs Alembic migrations before startup. PostgreSQL and BlobStore volumes are durable; Redis is disposable and may be rebuilt.

Before a destructive restore, create a backup with `BackupService`, verify its archive and manifest, and restore only into a staging database. Promote the verified staging database using a separately reviewed operational change.

Useful checks:

```bash
docker compose ps
docker compose exec api python -m proseforge.operations.startup_check
docker compose exec worker celery -A proseforge.workflows.celery_app inspect ping --timeout=5
```
