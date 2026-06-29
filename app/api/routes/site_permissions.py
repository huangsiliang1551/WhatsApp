from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.services.effective_access_service import EffectiveAccessService
from app.services.site_permission_service import SitePermissionService

router = APIRouter(prefix="/api/h5", tags=["h5-permissions"])


class GrantPermissionRequest(BaseModel):
    user_id: str
    site_id: str
    role: str  # admin/editor/analyst/support


class UpdateRoleRequest(BaseModel):
    role: str


def _perm_to_dict(p: object) -> dict:
    return {
        "id": getattr(p, "id"),
        "user_id": getattr(p, "user_id"),
        "site_id": getattr(p, "site_id"),
        "role": getattr(p, "role"),
        "created_at": getattr(p, "created_at").isoformat() if getattr(p, "created_at") else None,
    }


@router.get("/users/{user_id}/permissions")
async def get_user_permissions(
    user_id: str,
    actor: RequestActor = Depends(require_permission("sites.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = SitePermissionService(session)
    perms = svc.get_user_permissions(user_id)
    return {"items": [_perm_to_dict(p) for p in perms], "total": len(perms)}


@router.get("/sites/{site_id}/permissions")
async def get_site_permissions(
    site_id: str,
    actor: RequestActor = Depends(require_permission("sites.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = SitePermissionService(session)
    perms = svc.get_site_permissions(site_id)
    return {"items": [_perm_to_dict(p) for p in perms], "total": len(perms)}


@router.post("/permissions", status_code=201)
async def grant_permission(
    payload: GrantPermissionRequest,
    actor: RequestActor = Depends(require_permission("sites.edit")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = SitePermissionService(session)
    try:
        perm = svc.grant_permission(
            user_id=payload.user_id,
            site_id=payload.site_id,
            role=payload.role,
        )
        return _perm_to_dict(perm)
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/permissions/{permission_id}", status_code=204)
async def revoke_permission(
    permission_id: str,
    actor: RequestActor = Depends(require_permission("sites.edit")),
    session: Session = Depends(get_db_session),
) -> None:
    svc = SitePermissionService(session)
    try:
        svc.revoke_permission(permission_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/permissions/{permission_id}")
async def update_permission_role(
    permission_id: str,
    payload: UpdateRoleRequest,
    actor: RequestActor = Depends(require_permission("sites.edit")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = SitePermissionService(session)
    try:
        perm = svc.update_role(permission_id, payload.role)
        return _perm_to_dict(perm)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/sites/{site_id}/effective-access")
async def get_site_effective_access(
    site_id: str,
    actor: RequestActor = Depends(require_permission("sites.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    actor.require_permission("data_scope.view")
    access = EffectiveAccessService(session)
    scope = access.get_data_scope(actor)
    return {
        "site_id": site_id,
        "in_scope": scope.all_access or site_id in scope.site_ids,
        "effective_permissions": sorted(access.get_effective_permissions(actor)),
        "delegatable_permissions": sorted(access.get_delegatable_permissions(actor)),
    }
