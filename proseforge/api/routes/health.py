from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from proseforge.operations.startup_check import run_startup_check

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict[str, object]:
    report = run_startup_check(request.app.state.settings.blob_root, request.app.state.settings.backup_root)
    checks = {"api": "ok", **report.checks}
    try:
        async with request.app.state.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            migration = await connection.scalar(text("SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1"))
            workflow_table = await connection.scalar(text("SELECT to_regclass('workflow_runs')"))
        checks["database"] = "ok"
        checks["migration"] = "ok" if migration else "error"
        checks["workflow_recovery"] = "ok" if workflow_table else "error"
    except Exception:
        checks["database"] = "error"
        checks["migration"] = "error"
        checks["workflow_recovery"] = "error"
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
