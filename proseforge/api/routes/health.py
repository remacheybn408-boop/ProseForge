from fastapi import APIRouter, Request

from proseforge.operations.startup_check import run_startup_check

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict[str, object]:
    report = run_startup_check(request.app.state.settings.blob_root, request.app.state.settings.backup_root)
    return {"status": "ready" if report.ready else "not_ready", "checks": {"api": "ok", **report.checks}}


@router.get("/report")
async def report(request: Request) -> dict[str, object]:
    return await ready(request)


@router.post("/run")
async def run(request: Request) -> dict[str, object]:
    return await report(request)
