"""Permission management API for the canonical permission center.

Endpoints:
  1. GET    /api/permissions/definitions
  2. GET    /api/auth/permissions
  3. GET    /api/permissions/agency/{agency_id}
  4. PUT    /api/permissions/agency/{agency_id}
  5. DELETE /api/permissions/agency/{agency_id}/roles/{role_name}
  6. GET    /api/permissions/templates
  7. POST   /api/permissions/templates
  8. PUT    /api/permissions/templates/{template_id}
  9. DELETE /api/permissions/templates/{template_id}
  10. POST  /api/permissions/apply-template
  11. POST  /api/permissions/copy
  12. POST  /api/permissions/custom-role
"""

from __future__ import annotations

from collections import Counter
import re
from typing import Any
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_strict_request_actor
from app.core.auth import RequestActor
from app.core.permission_defs import (
    DEFAULT_TEMPLATES,
    PERMISSION_DEFINITIONS,
    derive_menu_pages,
    get_permissions_by_module,
)
from app.core.settings import get_settings
from app.db.models import Agency, AgencyMember, AgencyPermissionGrant, RolePermission

logger = structlog.get_logger()
router = APIRouter(tags=["permissions"])
KNOWN_PERMISSION_CODES = frozenset(p["code"] for p in PERMISSION_DEFINITIONS)
SUPER_ADMIN_ONLY_PERMISSION_CODES = frozenset(
    p["code"] for p in PERMISSION_DEFINITIONS if p.get("super_admin_only")
)


# ─── Unified Actor ────────────────────────────────────────────────────────────


class UnifiedActor(BaseModel):
    """Permission-center actor view built from the canonical shared actor."""

    user_id: str
    username: str
    user_type: str  # "super_admin" | "agent" | "agent_member"
    agency_id: str | None = None
    role: str | None = None
    permissions: list[str] = []


def require_actor(shared_actor: RequestActor = Depends(get_strict_request_actor)) -> UnifiedActor:
    """Build a permission-center actor from the canonical shared request actor."""
    user_type = "super_admin" if shared_actor.is_super_admin else shared_actor.role.value
    role_name = shared_actor.permission_role or shared_actor.role.value
    username = shared_actor.display_name or shared_actor.actor_id
    return UnifiedActor(
        user_id=shared_actor.actor_id,
        username=username,
        user_type=user_type,
        agency_id=shared_actor.agency_id,
        role=role_name,
        permissions=list(shared_actor.resolved_permissions),
    )


# ─── Helper: map module name → page id for menus ────────────────────────────


# ─── Pydantic request models ─────────────────────────────────────────────────


class UpdateAgencyPermissionsRequest(BaseModel):
    role_name: str
    permissions: list[str]


class ApplyTemplateRequest(BaseModel):
    agency_id: str
    template_id: str  # e.g. "standard_support"
    target_role: str  # e.g. "agent"


class CopyPermissionsRequest(BaseModel):
    source_agency_id: str
    target_agency_id: str


class CreateCustomRoleRequest(BaseModel):
    agency_id: str | None = None
    role_name: str  # must start with "custom_"
    permissions: list[str]


class CreatePermissionTemplateRequest(BaseModel):
    agency_id: str | None = None
    template_name: str
    template_key: str | None = None
    permissions: list[str]


class UpdatePermissionTemplateRequest(BaseModel):
    template_name: str
    permissions: list[str]


CREATABLE_PERMISSION_CENTER_ROLE_NAMES = {"agent", "support", "manager", "finance"}


def _normalize_permission_codes(
    permissions: list[str],
    *,
    reject_unknown: bool,
    context: str,
) -> list[str]:
    normalized: list[str] = []
    unknown: list[str] = []
    seen: set[str] = set()

    for raw_permission in permissions:
        code = raw_permission.strip()
        if not code:
            unknown.append(raw_permission)
            continue
        if code not in KNOWN_PERMISSION_CODES:
            unknown.append(code)
            continue
        if code in seen:
            continue
        seen.add(code)
        normalized.append(code)

    if unknown and reject_unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"Unknown permission codes in {context}.",
                "unknown_permissions": sorted(set(unknown)),
            },
        )

    if unknown:
        logger.warning(
            "ignored_unknown_permission_codes",
            context=context,
            unknown_permissions=sorted(set(unknown)),
        )

    return normalized


def _sanitize_response_permissions(
    permissions: list[str],
    *,
    context: str,
) -> list[str]:
    normalized = _normalize_permission_codes(
        permissions,
        reject_unknown=False,
        context=context,
    )
    filtered: list[str] = []
    removed: list[str] = []
    for code in normalized:
        if code in SUPER_ADMIN_ONLY_PERMISSION_CODES:
            removed.append(code)
            continue
        filtered.append(code)
    if removed:
        logger.warning(
            "permission_center.filtered_super_admin_only_response_permissions",
            context=context,
            removed_permissions=removed,
        )
    return filtered


def _normalize_template_role_name(
    template_name: str,
    template_key: str | None = None,
) -> str:
    source = template_key if template_key and template_key.strip() else template_name
    normalized = re.sub(r"[^a-z0-9]+", "_", source.strip().lower()).strip("_")
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template name must contain at least one letter or number.",
        )
    return f"custom_template_{normalized}"


def _normalize_target_role_name(role_name: str, *, field_name: str) -> str:
    normalized = role_name.strip()
    if normalized:
        return normalized
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"{field_name} is required.",
    )


def _validate_creatable_role_name(role_name: str) -> None:
    if role_name.startswith("custom_"):
        return
    if role_name in CREATABLE_PERMISSION_CENTER_ROLE_NAMES:
        return
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "New permission-center role configs must target a builtin role "
            "or a custom_* role key."
        ),
    )


def _resolve_target_agency_id(
    actor: UnifiedActor,
    requested_agency_id: str | None,
) -> str:
    if actor.user_type == "super_admin":
        if not requested_agency_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="agency_id is required for super admin permission-center writes.",
            )
        return requested_agency_id
    if not actor.agency_id:
        raise HTTPException(status_code=400, detail="Agency ID not found for this user.")
    if requested_agency_id and requested_agency_id != actor.agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this agency's permissions.",
        )
    return actor.agency_id


# ═══════════════════════════════════════════════════════════════════════════════
#  1. GET /api/permissions/definitions
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/api/permissions/definitions")
async def get_permission_definitions(
    actor: UnifiedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
) -> dict:
    """Return all 150 permission definitions grouped by module."""
    _require_actor_permission(session, actor, "roles.view")
    return {
        "total": len(PERMISSION_DEFINITIONS),
        "modules": get_permissions_by_module(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  2. GET /api/auth/permissions  — current user's permissions
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/api/auth/permissions")
async def get_current_user_permissions(
    actor: UnifiedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
) -> dict:
    """Return the current user's type, role, menus and permission codes."""
    user_permissions = _resolve_actor_permissions(session, actor)
    user_menus = _permissions_to_menus(user_permissions)

    return {
        "user_type": actor.user_type,
        "role": actor.role or (actor.user_type if actor.user_type == "agent" else "support"),
        "agency_id": actor.agency_id,
        "menus": sorted(set(user_menus)),
        "permissions": sorted(set(user_permissions)),
    }


def _permissions_to_menus(permissions: list[str]) -> list[str]:
    """Derive visible menu IDs from a list of permission codes."""
    return derive_menu_pages(permissions)


# ═══════════════════════════════════════════════════════════════════════════════
#  3. GET /api/permissions/agency/{agency_id}
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/api/permissions/agency/{agency_id}")
async def get_agency_permissions(
    agency_id: str,
    actor: UnifiedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
) -> dict:
    """Return all role-permission configurations for an agency.

    Super admin can see any agency; agent can only see their own.
    """
    _check_agency_access(actor, agency_id)
    _require_actor_permission(session, actor, "roles.view")

    rows = session.execute(
        select(RolePermission).where(
            RolePermission.agency_id == agency_id,
            RolePermission.is_template.is_(False),
        ).order_by(RolePermission.role_name),
    ).scalars().all()
    member_counts = Counter(
        session.execute(
            select(AgencyMember.role).where(AgencyMember.agency_id == agency_id),
        ).scalars().all()
    )

    roles = []
    configured_role_names: set[str] = set()
    for r in rows:
        configured_role_names.add(r.role_name)
        permissions = _sanitize_response_permissions(
            list(r.permissions or []),
            context=f"agency.{agency_id}.{r.role_name}",
        )
        roles.append({
            "id": r.id,
            "role_name": r.role_name,
            "is_template": r.is_template,
            "template_name": r.template_name,
            "permissions": permissions,
            "created_by": r.created_by,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "member_count": member_counts.get(r.role_name, 0),
        })

    for role_name, member_count in sorted(member_counts.items()):
        if role_name in configured_role_names:
            continue
        roles.append({
            "id": None,
            "role_name": role_name,
            "is_template": False,
            "template_name": None,
            "permissions": [],
            "created_by": None,
            "updated_at": None,
            "member_count": member_count,
        })

    return {"agency_id": agency_id, "roles": roles}


# ═══════════════════════════════════════════════════════════════════════════════
#  4. PUT /api/permissions/agency/{agency_id}  — update role permissions
# ═══════════════════════════════════════════════════════════════════════════════


@router.put("/api/permissions/agency/{agency_id}")
async def update_agency_permissions(
    agency_id: str,
    data: UpdateAgencyPermissionsRequest,
    actor: UnifiedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
) -> dict:
    """Update (or create) a role's permission list for an agency.

    Actors need canonical `roles.edit_perms` for the target agency. Writes an audit log entry.
    """
    _check_agency_access(actor, agency_id)
    _require_actor_permission(session, actor, "roles.edit_perms")

    # Validate the agency exists
    agency = session.get(Agency, agency_id)
    if agency is None:
        raise HTTPException(status_code=404, detail="Agency not found.")

    target_role = _normalize_target_role_name(data.role_name, field_name="role_name")

    permissions = _normalize_permission_codes(
        data.permissions,
        reject_unknown=True,
        context=f"agency.{agency_id}.{target_role}",
    )

    rp = session.execute(
        select(RolePermission).where(
            RolePermission.agency_id == agency_id,
            RolePermission.role_name == target_role,
        ),
    ).scalar_one_or_none()

    if rp is None:
        _require_actor_permission(session, actor, "roles.create")
        _validate_creatable_role_name(target_role)
    _ensure_actor_can_assign_permissions(
        session,
        actor,
        permissions,
        context=f"agency.{agency_id}.{target_role}",
    )
    _ensure_permissions_within_agency_grants(session, agency_id, permissions)

    # Upsert
    if rp is None:
        rp = RolePermission(
            id=str(uuid4()),
            agency_id=agency_id,
            role_name=target_role,
            is_template=False,
            template_name=None,
            permissions=permissions,
            created_by=actor.user_id,
        )
        session.add(rp)
        action = "created"
    else:
        if rp.is_template:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Template rows must be managed via the template endpoints.",
            )
        rp.permissions = permissions
        rp.template_name = None
        action = "updated"

    session.flush()

    # ── Audit log ──────────────────────────────────────────────────────────
    _write_audit_log(
        session=session,
        actor_type=actor.user_type,
        actor_id=actor.user_id,
        action=f"permissions.{action}",
        target_type="agency_role",
        target_id=f"{agency_id}/{target_role}",
        detail={
            "agency_id": agency_id,
            "role_name": target_role,
            "permission_count": len(permissions),
        },
    )
    session.commit()

    logger.info(
        "agency_permissions_updated",
        agency_id=agency_id,
        role_name=target_role,
        by=actor.user_id,
        count=len(permissions),
    )

    return {
        "status": "ok",
        "action": action,
        "role_name": target_role,
        "permissions": permissions,
    }


@router.delete("/api/permissions/agency/{agency_id}/roles/{role_name}")
async def delete_agency_role(
    agency_id: str,
    role_name: str,
    actor: UnifiedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
) -> dict:
    """Delete an agency custom role that is not currently assigned to members."""
    _check_agency_access(actor, agency_id)
    _require_actor_permission(session, actor, "roles.delete")

    rp = session.execute(
        select(RolePermission).where(
            RolePermission.agency_id == agency_id,
            RolePermission.role_name == role_name,
        ),
    ).scalar_one_or_none()
    if rp is None:
        raise HTTPException(status_code=404, detail="Role not found.")

    if rp.is_template or not role_name.startswith("custom_"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only custom roles can be deleted from the permission center.",
        )

    assigned_member = session.execute(
        select(AgencyMember).where(
            AgencyMember.agency_id == agency_id,
            AgencyMember.role == role_name,
        ),
    ).scalar_one_or_none()
    if assigned_member is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role '{role_name}' is assigned to agency members and cannot be deleted.",
        )

    permission_count = len(
        _normalize_permission_codes(
            list(rp.permissions or []),
            reject_unknown=False,
            context=f"delete_role.{agency_id}.{role_name}",
        )
    )
    session.delete(rp)
    session.flush()

    _write_audit_log(
        session=session,
        actor_type=actor.user_type,
        actor_id=actor.user_id,
        action="permissions.deleted",
        target_type="agency_role",
        target_id=f"{agency_id}/{role_name}",
        detail={
            "agency_id": agency_id,
            "role_name": role_name,
            "permission_count": permission_count,
        },
    )
    session.commit()

    logger.info(
        "agency_role_deleted",
        agency_id=agency_id,
        role_name=role_name,
        by=actor.user_id,
    )

    return {
        "status": "ok",
        "action": "deleted",
        "agency_id": agency_id,
        "role_name": role_name,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  5. GET /api/permissions/templates
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/api/permissions/templates")
async def get_permission_templates(
    actor: UnifiedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
) -> dict:
    """Return preset templates + agency custom templates (is_template=True)."""
    _require_actor_permission(session, actor, "roles.view")
    # Presets from code
    presets: list[dict[str, Any]] = []
    for tid, tpl in DEFAULT_TEMPLATES.items():
        permissions = _normalize_permission_codes(
            list(tpl["permissions"]),
            reject_unknown=True,
            context=f"template.{tid}",
        )
        presets.append({
            "id": tid,
            "name": tpl["name"],
            "description": tpl.get("description", ""),
            "is_preset": True,
            "permissions": permissions,
            "permission_count": len(permissions),
        })

    # Custom templates from DB (is_template=True, agency_id IS NOT NULL)
    custom_template_query = select(RolePermission).where(
        RolePermission.is_template.is_(True),
        RolePermission.agency_id.isnot(None),
    )
    if actor.user_type != "super_admin":
        if actor.agency_id:
            custom_template_query = custom_template_query.where(RolePermission.agency_id == actor.agency_id)
        else:
            custom_template_query = custom_template_query.where(False)
    custom_rows = session.execute(
        custom_template_query.order_by(RolePermission.template_name),
    ).scalars().all()

    custom = []
    for r in custom_rows:
        permissions = _sanitize_response_permissions(
            list(r.permissions or []),
            context=f"template.{r.id}",
        )
        custom.append({
            "id": r.id,
            "name": r.template_name or r.role_name,
            "agency_id": r.agency_id,
            "permissions": permissions,
            "permission_count": len(permissions),
        })

    return {"presets": presets, "custom": custom}


@router.post("/api/permissions/templates")
async def create_permission_template(
    data: CreatePermissionTemplateRequest,
    actor: UnifiedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
) -> dict:
    """Create an agency-scoped custom permission template."""
    agency_id = _resolve_target_agency_id(actor, data.agency_id)
    _check_agency_access(actor, agency_id)
    _require_actor_permission(session, actor, "roles.create")

    agency = session.get(Agency, agency_id)
    if agency is None:
        raise HTTPException(status_code=404, detail="Agency not found.")

    role_name = _normalize_template_role_name(data.template_name, data.template_key)
    permissions = _normalize_permission_codes(
        data.permissions,
        reject_unknown=True,
        context=f"template_create.{agency_id}.{role_name}",
    )
    _ensure_actor_can_assign_permissions(
        session,
        actor,
        permissions,
        context=f"template_create.{agency_id}.{role_name}",
    )
    _ensure_permissions_within_agency_grants(session, agency_id, permissions)

    existing = session.execute(
        select(RolePermission).where(
            RolePermission.agency_id == agency_id,
            RolePermission.role_name == role_name,
        ),
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template '{data.template_name}' already exists for this agency.",
        )

    rp = RolePermission(
        id=str(uuid4()),
        agency_id=agency_id,
        role_name=role_name,
        is_template=True,
        template_name=data.template_name.strip(),
        permissions=permissions,
        created_by=actor.user_id,
    )
    session.add(rp)
    session.flush()

    _write_audit_log(
        session=session,
        actor_type=actor.user_type,
        actor_id=actor.user_id,
        action="permissions.template_created",
        target_type="permission_template",
        target_id=rp.id,
        detail={
            "agency_id": agency_id,
            "role_name": role_name,
            "template_name": rp.template_name,
            "permission_count": len(permissions),
        },
    )
    session.commit()

    return {
        "status": "ok",
        "id": rp.id,
        "agency_id": agency_id,
        "role_name": role_name,
        "template_name": rp.template_name,
        "permissions": permissions,
        "permission_count": len(permissions),
    }


@router.put("/api/permissions/templates/{template_id}")
async def update_permission_template(
    template_id: str,
    data: UpdatePermissionTemplateRequest,
    actor: UnifiedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
) -> dict:
    """Update an agency-scoped custom permission template."""
    _require_actor_permission(session, actor, "roles.edit_perms")

    rp = session.get(RolePermission, template_id)
    if rp is None or not rp.is_template or not rp.agency_id:
        raise HTTPException(status_code=404, detail="Template not found.")
    _check_agency_access(actor, rp.agency_id)

    permissions = _normalize_permission_codes(
        data.permissions,
        reject_unknown=True,
        context=f"template_update.{rp.agency_id}.{rp.role_name}",
    )
    _ensure_actor_can_assign_permissions(
        session,
        actor,
        permissions,
        context=f"template_update.{rp.agency_id}.{rp.role_name}",
    )
    _ensure_permissions_within_agency_grants(session, rp.agency_id, permissions)

    rp.template_name = data.template_name.strip()
    rp.permissions = permissions
    session.flush()

    _write_audit_log(
        session=session,
        actor_type=actor.user_type,
        actor_id=actor.user_id,
        action="permissions.template_updated",
        target_type="permission_template",
        target_id=template_id,
        detail={
            "agency_id": rp.agency_id,
            "role_name": rp.role_name,
            "template_name": rp.template_name,
            "permission_count": len(permissions),
        },
    )
    session.commit()

    return {
        "status": "ok",
        "id": template_id,
        "agency_id": rp.agency_id,
        "role_name": rp.role_name,
        "template_name": rp.template_name,
        "permissions": permissions,
        "permission_count": len(permissions),
    }


@router.delete("/api/permissions/templates/{template_id}")
async def delete_permission_template(
    template_id: str,
    actor: UnifiedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
) -> dict:
    """Delete an agency-scoped custom permission template."""
    _require_actor_permission(session, actor, "roles.delete")

    rp = session.get(RolePermission, template_id)
    if rp is None or not rp.is_template or not rp.agency_id:
        raise HTTPException(status_code=404, detail="Template not found.")
    _check_agency_access(actor, rp.agency_id)

    permission_count = len(
        _sanitize_response_permissions(
            list(rp.permissions or []),
            context=f"template_delete.{rp.agency_id}.{rp.role_name}",
        )
    )
    role_name = rp.role_name
    agency_id = rp.agency_id
    template_name = rp.template_name
    session.delete(rp)
    session.flush()

    _write_audit_log(
        session=session,
        actor_type=actor.user_type,
        actor_id=actor.user_id,
        action="permissions.template_deleted",
        target_type="permission_template",
        target_id=template_id,
        detail={
            "agency_id": agency_id,
            "role_name": role_name,
            "template_name": template_name,
            "permission_count": permission_count,
        },
    )
    session.commit()

    return {
        "status": "ok",
        "id": template_id,
        "agency_id": agency_id,
        "role_name": role_name,
        "template_name": template_name,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  6. POST /api/permissions/apply-template
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/api/permissions/apply-template")
async def apply_permission_template(
    data: ApplyTemplateRequest,
    actor: UnifiedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
) -> dict:
    """Apply a preset template (or custom template) to an agency's role."""
    _check_agency_access(actor, data.agency_id)
    _require_actor_permission(session, actor, "roles.edit_perms")
    agency = session.get(Agency, data.agency_id)
    if agency is None:
        raise HTTPException(status_code=404, detail="Agency not found.")

    target_role = _normalize_target_role_name(data.target_role, field_name="target_role")

    # Resolve template permissions
    permissions: list[str] | None = None
    template_name: str | None = None

    if data.template_id in DEFAULT_TEMPLATES:
        permissions = _normalize_permission_codes(
            list(DEFAULT_TEMPLATES[data.template_id]["permissions"]),
            reject_unknown=True,
            context=f"template.{data.template_id}",
        )
        template_name = DEFAULT_TEMPLATES[data.template_id]["name"]
    else:
        # Look up custom template from DB
        tpl_row = session.get(RolePermission, data.template_id)
        if tpl_row and tpl_row.is_template:
            if tpl_row.agency_id != data.agency_id:
                tpl_row = None
            if tpl_row:
                permissions = _normalize_permission_codes(
                    list(tpl_row.permissions or []),
                    reject_unknown=True,
                    context=f"template.{data.template_id}",
                )
                template_name = tpl_row.template_name or tpl_row.role_name

    if permissions is None:
        raise HTTPException(status_code=404, detail="Template not found.")

    rp = session.execute(
        select(RolePermission).where(
            RolePermission.agency_id == data.agency_id,
            RolePermission.role_name == target_role,
        ),
    ).scalar_one_or_none()

    if rp is None:
        _require_actor_permission(session, actor, "roles.create")
        _validate_creatable_role_name(target_role)
    _ensure_actor_can_assign_permissions(
        session,
        actor,
        permissions,
        context=f"template_apply.{data.agency_id}.{target_role}",
    )
    _ensure_permissions_within_agency_grants(session, data.agency_id, permissions)

    # Upsert the target role
    if rp is None:
        rp = RolePermission(
            id=str(uuid4()),
            agency_id=data.agency_id,
            role_name=target_role,
            is_template=False,
            template_name=template_name,
            permissions=permissions,
            created_by=actor.user_id,
        )
        session.add(rp)
    else:
        if rp.is_template:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Template rows cannot be used as target roles.",
            )
        rp.permissions = permissions
        rp.template_name = template_name

    session.flush()

    # ── Audit log ──────────────────────────────────────────────────────────
    _write_audit_log(
        session=session,
        actor_type=actor.user_type,
        actor_id=actor.user_id,
        action="permissions.apply_template",
        target_type="agency_role",
        target_id=f"{data.agency_id}/{target_role}",
        detail={
            "template_id": data.template_id,
            "template_name": template_name,
            "agency_id": data.agency_id,
            "target_role": target_role,
            "permission_count": len(permissions),
        },
    )
    session.commit()

    logger.info(
        "template_applied",
        template_id=data.template_id,
        agency_id=data.agency_id,
        target_role=target_role,
        by=actor.user_id,
    )

    return {
        "status": "ok",
        "template_name": template_name,
        "target_role": target_role,
        "role_name": target_role,
        "permissions": permissions,
        "permission_count": len(permissions),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  7. POST /api/permissions/copy
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/api/permissions/copy")
async def copy_agency_permissions(
    data: CopyPermissionsRequest,
    actor: UnifiedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
) -> dict:
    """Copy all role-permission configs from source agency to target agency.

    Requires canonical `agents.permissions`.
    """
    _require_actor_permission(session, actor, "agents.permissions")

    # Verify both agencies exist
    source = session.get(Agency, data.source_agency_id)
    target = session.get(Agency, data.target_agency_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source agency not found.")
    if target is None:
        raise HTTPException(status_code=404, detail="Target agency not found.")

    # Fetch source roles
    source_roles = session.execute(
        select(RolePermission).where(RolePermission.agency_id == data.source_agency_id),
    ).scalars().all()

    if not source_roles:
        raise HTTPException(status_code=404, detail="Source agency has no permission configurations.")

    # Delete existing target roles (except templates)
    existing = session.execute(
        select(RolePermission).where(
            RolePermission.agency_id == data.target_agency_id,
            RolePermission.is_template.is_(False),
        ),
    ).scalars().all()
    for r in existing:
        session.delete(r)
    if existing:
        session.flush()

    # Copy each role
    copied_count = 0
    for src_role in source_roles:
        if src_role.is_template:
            continue
        permissions = _normalize_permission_codes(
            list(src_role.permissions or []),
            reject_unknown=True,
            context=f"copy.{data.source_agency_id}.{src_role.role_name}",
        )
        _reject_super_admin_only_permissions(
            permissions,
            context=f"copy.{data.source_agency_id}.{src_role.role_name}",
        )
        new_rp = RolePermission(
            id=str(uuid4()),
            agency_id=data.target_agency_id,
            role_name=src_role.role_name,
            is_template=False,
            template_name=None,
            permissions=permissions,
            created_by=actor.user_id,
        )
        session.add(new_rp)
        copied_count += 1

    session.flush()

    _write_audit_log(
        session=session,
        actor_type=actor.user_type,
        actor_id=actor.user_id,
        action="permissions.copy",
        target_type="agency",
        target_id=data.target_agency_id,
        detail={
            "source_agency_id": data.source_agency_id,
            "target_agency_id": data.target_agency_id,
            "roles_copied": copied_count,
        },
    )
    session.commit()

    logger.info(
        "permissions_copied",
        source=data.source_agency_id,
        target=data.target_agency_id,
        roles=copied_count,
        by=actor.user_id,
    )

    return {
        "status": "ok",
        "source_agency_id": data.source_agency_id,
        "target_agency_id": data.target_agency_id,
        "roles_copied": copied_count,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  8. POST /api/permissions/custom-role
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/api/permissions/custom-role")
async def create_custom_role(
    data: CreateCustomRoleRequest,
    actor: UnifiedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
) -> dict:
    """Agency creates a custom role (must be subset of own permissions).

    Requires canonical `roles.create` within the actor's own agency.
    """
    if not data.role_name.startswith("custom_"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Custom role name must start with 'custom_'.",
        )

    agency_id = _resolve_target_agency_id(actor, data.agency_id)
    _check_agency_access(actor, agency_id)
    _require_actor_permission(session, actor, "roles.create")
    agency = session.get(Agency, agency_id)
    if agency is None:
        raise HTTPException(status_code=404, detail="Agency not found.")

    permissions = _normalize_permission_codes(
        data.permissions,
        reject_unknown=True,
        context=f"custom_role.{data.role_name}",
    )
    _ensure_actor_can_assign_permissions(
        session,
        actor,
        permissions,
        context=f"custom_role.{data.role_name}",
    )
    _ensure_permissions_within_agency_grants(session, agency_id, permissions)

    # Check for duplicate role_name
    existing = session.execute(
        select(RolePermission).where(
            RolePermission.agency_id == agency_id,
            RolePermission.role_name == data.role_name,
        ),
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role '{data.role_name}' already exists for this agency.",
        )

    rp = RolePermission(
        id=str(uuid4()),
        agency_id=agency_id,
        role_name=data.role_name,
        is_template=False,
        template_name=None,
        permissions=permissions,
        created_by=actor.user_id,
    )
    session.add(rp)
    session.flush()

    _write_audit_log(
        session=session,
        actor_type=actor.user_type,
        actor_id=actor.user_id,
        action="permissions.created",
        target_type="agency_role",
        target_id=f"{agency_id}/{data.role_name}",
        detail={
            "agency_id": agency_id,
            "role_name": data.role_name,
            "permission_count": len(permissions),
        },
    )
    session.commit()

    logger.info(
        "custom_role_created",
        agency_id=agency_id,
        role_name=data.role_name,
        by=actor.user_id,
        count=len(permissions),
    )

    return {
        "status": "ok",
        "id": rp.id,
        "role_name": data.role_name,
        "permissions": permissions,
        "permission_count": len(permissions),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _check_agency_access(actor: UnifiedActor, target_agency_id: str) -> None:
    """Super admin can access any agency; agent only their own."""
    if actor.user_type == "super_admin":
        return
    if actor.agency_id and actor.agency_id == target_agency_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have access to this agency's permissions.",
    )


def _resolve_actor_permissions(session: Session, actor: UnifiedActor) -> list[str]:
    _ = session
    if actor.user_type == "super_admin":
        return [p["code"] for p in PERMISSION_DEFINITIONS]

    permissions = _normalize_permission_codes(
        list(actor.permissions or []),
        reject_unknown=False,
        context=f"actor.{actor.user_id}.permissions",
    )
    for permission_code in ("profile.view", "profile.edit", "profile.change_password"):
        if permission_code not in permissions:
            permissions.append(permission_code)

    return permissions


def _require_actor_permission(session: Session, actor: UnifiedActor, permission_code: str) -> None:
    if actor.user_type == "super_admin":
        return
    permissions = set(_resolve_actor_permissions(session, actor))
    if permission_code in permissions:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Actor '{actor.user_id}' cannot perform '{permission_code}'.",
    )


def _reject_super_admin_only_permissions(permissions: list[str], *, context: str) -> None:
    forbidden = sorted({code for code in permissions if code in SUPER_ADMIN_ONLY_PERMISSION_CODES})
    if not forbidden:
        return
    logger.warning(
        "permission_center.rejected_super_admin_only_permissions",
        context=context,
        forbidden_permissions=forbidden,
    )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "message": "Super-admin-only permissions cannot be assigned to agency roles.",
            "forbidden_permissions": forbidden,
        },
    )


def _ensure_actor_can_assign_permissions(
    session: Session,
    actor: UnifiedActor,
    permissions: list[str],
    *,
    context: str,
) -> None:
    _reject_super_admin_only_permissions(permissions, context=context)
    if actor.user_type == "super_admin":
        return
    actor_permissions = set(_resolve_actor_permissions(session, actor))
    disallowed = sorted(set(permissions) - actor_permissions)
    if not disallowed:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Cannot assign permissions you do not own: {disallowed}",
    )


def _ensure_permissions_within_agency_grants(
    session: Session,
    agency_id: str,
    permissions: list[str],
) -> None:
    grant = session.execute(
        select(AgencyPermissionGrant).where(AgencyPermissionGrant.agency_id == agency_id)
    ).scalar_one_or_none()
    if grant is None:
        return

    granted_permissions = set(
        _normalize_permission_codes(
            list(grant.permissions or []),
            reject_unknown=False,
            context=f"agency_grants.{agency_id}",
        )
    )
    disallowed_permissions = sorted(set(permissions) - granted_permissions)
    if not disallowed_permissions:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "message": "Permissions exceed agency granted permissions.",
            "disallowed_permissions": disallowed_permissions,
        },
    )


def _write_audit_log(
    session: Session,
    actor_type: str,
    actor_id: str,
    action: str,
    target_type: str,
    target_id: str,
    detail: dict[str, Any] | None = None,
) -> None:
    """Write an entry to the audit_log table."""
    from app.db.models import AuditLog

    log_entry = AuditLog(
        id=str(uuid4()),
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload=detail or {},
    )
    session.add(log_entry)
    session.flush()
