from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from proseforge.infrastructure.security.credential_cipher import CredentialCipher
from proseforge.operations.startup_check import run_startup_check

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict[str, object]:
    report = run_startup_check(request.app.state.settings.blob_root, request.app.state.settings.backup_root)
    checks = {"api": "ok", **report.checks}
    master_key = request.app.state.settings.master_key.get_secret_value()
    if master_key.startswith("replace-with-") and request.app.state.settings.environment.lower() not in {"production", "prod"}:
        checks["master_key"] = "ok"
    else:
        try:
            import base64

            CredentialCipher(base64.b64decode(master_key, validate=True))
            checks["master_key"] = "ok"
        except (ValueError, TypeError):
            checks["master_key"] = "error"
    try:
        async with request.app.state.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            migration = await connection.scalar(text("SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1"))
            workflow_table = await connection.scalar(text("SELECT to_regclass('workflow_runs')"))
            pgvector = await connection.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')"))
            partial_messages = await connection.scalar(text("SELECT count(*) FROM messages WHERE status = 'PARTIAL'"))
            expired_workflows = await connection.scalar(text("SELECT count(*) FROM workflow_runs WHERE status IN ('RUNNING', 'RECOVERING') AND lease_expires_at IS NOT NULL AND lease_expires_at < now()"))
        checks["database"] = "ok"
        checks["migration"] = "ok" if migration else "error"
        checks["workflow_recovery"] = "ok" if workflow_table else "error"
        checks["pgvector"] = "ok" if pgvector else "error"
        checks["partial_messages"] = "ok" if (partial_messages or 0) >= 0 else "error"
        checks["expired_workflows"] = "ok" if (expired_workflows or 0) == 0 else "warning"
    except Exception:
        checks["database"] = "error"
        checks["migration"] = "error"
        checks["workflow_recovery"] = "error"
        checks["pgvector"] = "error"
        checks["partial_messages"] = "error"
        checks["expired_workflows"] = "error"
    redis_client = Redis.from_url(request.app.state.settings.redis_url)
    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
    finally:
        await redis_client.aclose()
    ready_state = all(value == "ok" for value in checks.values())
    payload = {"status": "ready" if ready_state else "not_ready", "checks": checks}
    if not ready_state:
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.get("/report")
async def report(request: Request) -> dict[str, object]:
    return await ready(request)


@router.post("/run")
async def run(request: Request) -> dict[str, object]:
    return await report(request)
