from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from proseforge.api.dependencies import current_user, require_admin, unit_of_work
from proseforge.application.auth.service import AuthUser
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork
from proseforge.infrastructure.blob.local import LocalBlobStore
from proseforge.operations.maintenance import record_maintenance_audit, verify_attachment_blobs

router = APIRouter(prefix="/api/v1/maintenance", tags=["maintenance"])


@router.post("/workflows/recover-expired")
async def recover_expired_workflows(
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, object]:
    require_admin(user)
    async with uow:
        recovered = await uow.workflows.recover_expired()
        record_maintenance_audit(uow, user.id, "recover_expired_workflows", {"recovered": recovered})
        await uow.commit()
    return {"status": "ok", "recovered": recovered}


@router.post("/blobs/verify")
async def verify_blobs(
    request: Request,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, object]:
    require_admin(user)
    async with uow:
        result = await verify_attachment_blobs(uow, LocalBlobStore(request.app.state.settings.blob_root))
        record_maintenance_audit(uow, user.id, "verify_blobs", result)
        await uow.commit()
    return {"status": "ok", **result}
