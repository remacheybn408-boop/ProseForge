from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> dict[str, object]:
    return {"status": "ready", "checks": {"api": "ok"}}


@router.get("/report")
async def report() -> dict[str, object]:
    return {"status": "ready", "checks": {"api": "ok"}}


@router.post("/run")
async def run() -> dict[str, object]:
    return await report()
