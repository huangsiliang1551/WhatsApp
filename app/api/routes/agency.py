"""Agency CRUD and member management API routes."""

from http import HTTPStatus
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_settings, get_strict_request_actor, require_permission
from app.api.routes.agency_billing import (
    LineItem,
    build_agency_billing_list_stmt,
    ensure_billing_matches_agency_scope,
    get_agency_billing_or_404,
    parse_billing_date,
    serialize_agency_billing,
    validate_billing_status_transition,
)
from app.core.auth import RequestActor
from app.core.settings import Settings
from app.services.agency_service import AgencyService
from app.services.notification_service import NotificationService
from app.db.models import AgencyBilling

router = APIRouter(prefix="/api/agents", tags=["agents"])


# --- Request/Response models ---

class AgencyCreateRequest(BaseModel):
    name: str
    username: str
    password: str
    brand_name: str | None = None
    logo_url: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None


class AgencyUpdateRequest(BaseModel):
    name: str | None = None
    brand_name: str | None = None
    logo_url: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None


class AgencySelfUpdateRequest(BaseModel):
    brand_name: str | None = None
    logo_url: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str


class AddMemberRequest(BaseModel):
    username: str
    password: str
    role: str


class UpdateMemberRoleRequest(BaseModel):
    role: str
    password: str | None = None


class UpdateStatusRequest(BaseModel):
    status: str


class UpdateAgencyGrantedPermissionsRequest(BaseModel):
    permissions: list[str]


class CreateAgencyBillingRequest(BaseModel):
    billing_type: str
    amount: float
    billing_period_start: str | None = None
    billing_period_end: str | None = None
    line_items: list[LineItem] | None = None


class UpdateAgencyBillingRequest(BaseModel):
    billing_type: str | None = None
    amount: float | None = None
    status: str | None = None
    billing_period_start: str | None = None
    billing_period_end: str | None = None
    line_items: list[LineItem] | None = None


def _require_granted_permission_read_access(actor: RequestActor, agency_id: str) -> RequestActor:
    if actor.is_super_admin:
        return actor
    if actor.agency_id != agency_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="You do not have access to this agency's permissions.",
        )
    if actor.has_permission("agents.permissions") or actor.has_permission("roles.view"):
        return actor
    actor.require_permission("roles.view")
    return actor


def _require_granted_permission_write_access(actor: RequestActor, agency_id: str) -> RequestActor:
    if not actor.is_super_admin and actor.agency_id != agency_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="You do not have access to this agency's permissions.",
        )
    actor.require_permission("agents.permissions")
    return actor


# --- Agency CRUD ---


@router.get("/check-username")
async def check_username(
    username: str,
    session: Session = Depends(get_db_session),
) -> dict:
    """Check if an agency username is already taken."""
    svc = AgencyService(session)
    existing = svc.get_agency_by_username(username)
    return {"exists": existing is not None}

@router.post("")
async def create_agency(
    data: AgencyCreateRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("agents.create")),
) -> dict:
    svc = AgencyService(session)
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    try:
        agency = svc.create_agency(
            name=data.name,
            username=data.username,
            password=data.password,
            brand_name=data.brand_name,
            logo_url=data.logo_url,
            contact_name=data.contact_name,
            contact_phone=data.contact_phone,
            contact_email=data.contact_email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Notify agency creation
    NotificationService(session).create_notification(
        account_id=None, type="agency", category="system",
        title="代理商创建成功",
        message=f"代理商 {agency.name} 已创建",
        severity="info",
    )

    return {
        "id": agency.id,
        "name": agency.name,
        "username": agency.username,
        "brand_name": agency.brand_name,
        "logo_url": agency.logo_url,
        "contact_name": agency.contact_name,
        "contact_phone": agency.contact_phone,
        "contact_email": agency.contact_email,
        "status": agency.status,
    }


@router.get("")
async def list_agencies(
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("agents.view")),
) -> list[dict]:
    svc = AgencyService(session)
    agencies = svc.list_agencies()
    return [
        {
            "id": item.agency.id,
            "name": item.agency.name,
            "username": item.agency.username,
            "brand_name": item.agency.brand_name,
            "logo_url": item.agency.logo_url,
            "contact_name": item.agency.contact_name,
            "contact_phone": item.agency.contact_phone,
            "contact_email": item.agency.contact_email,
            "status": item.agency.status,
            "member_count": item.member_count,
            "role_count": item.role_count,
            "granted_permission_count": item.granted_permission_count,
            "created_at": item.agency.created_at.isoformat() if item.agency.created_at else None,
            "updated_at": item.agency.updated_at.isoformat() if item.agency.updated_at else None,
        }
        for item in agencies
    ]


@router.get("/{agency_id}")
async def get_agency(
    agency_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("agents.view")),
) -> dict:
    svc = AgencyService(session)
    try:
        agency = svc.get_agency(agency_id)
    except LookupError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc
    return {
        "id": agency.id,
        "name": agency.name,
        "username": agency.username,
        "brand_name": agency.brand_name,
        "logo_url": agency.logo_url,
        "contact_name": agency.contact_name,
        "contact_phone": agency.contact_phone,
        "contact_email": agency.contact_email,
        "status": agency.status,
        "created_at": agency.created_at.isoformat() if agency.created_at else None,
        "updated_at": agency.updated_at.isoformat() if agency.updated_at else None,
    }


@router.get("/{agency_id}/granted-permissions")
async def get_agency_granted_permissions(
    agency_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(get_strict_request_actor),
) -> dict:
    _require_granted_permission_read_access(actor, agency_id)
    svc = AgencyService(session)
    try:
        permissions = svc.get_permission_grants(agency_id)
    except LookupError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc
    return {
        "agency_id": agency_id,
        "permissions": permissions,
    }


@router.put("/{agency_id}/granted-permissions")
async def update_agency_granted_permissions(
    agency_id: str,
    data: UpdateAgencyGrantedPermissionsRequest,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(get_strict_request_actor),
) -> dict:
    _require_granted_permission_write_access(actor, agency_id)
    svc = AgencyService(session)
    try:
        permissions = svc.update_permission_grants(
            agency_id,
            data.permissions,
            actor_id=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        detail = exc.args[0] if exc.args else "Invalid granted permissions."
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=detail) from exc
    session.commit()
    return {
        "agency_id": agency_id,
        "permissions": permissions,
    }


@router.patch("/me")
async def update_agency_self(
    data: AgencySelfUpdateRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Agent updates own profile (brand_name, contacts, logo) using JWT token."""
    from app.api.routes.agent_auth import _get_agent_from_token
    agency = _get_agent_from_token(request, settings)
    svc = AgencyService(session)
    agency = svc.update_agency(
        agency.id,
        brand_name=data.brand_name,
        logo_url=data.logo_url,
        contact_name=data.contact_name,
        contact_phone=data.contact_phone,
        contact_email=data.contact_email,
    )
    return {
        "id": agency.id,
        "name": agency.name,
        "brand_name": agency.brand_name,
        "contact_name": agency.contact_name,
        "contact_phone": agency.contact_phone,
        "contact_email": agency.contact_email,
    }


@router.patch("/{agency_id}")
async def update_agency(
    agency_id: str,
    data: AgencyUpdateRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("agents.edit")),
) -> dict:
    svc = AgencyService(session)
    try:
        agency = svc.update_agency(
            agency_id,
            name=data.name,
            brand_name=data.brand_name,
            logo_url=data.logo_url,
            contact_name=data.contact_name,
            contact_phone=data.contact_phone,
            contact_email=data.contact_email,
        )
    except LookupError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc
    return {
        "id": agency.id,
        "name": agency.name,
        "status": agency.status,
    }


@router.patch("/{agency_id}/status")
async def update_agency_status(
    agency_id: str,
    data: UpdateStatusRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("agents.edit")),
) -> dict:
    """Update agency status: active / suspended / archived."""
    valid = {"active", "suspended", "archived"}
    if data.status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status, must be one of: {', '.join(sorted(valid))}")
    svc = AgencyService(session)
    try:
        agency = svc.update_agency(agency_id, status=data.status)
    except LookupError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc
    return {"id": agency.id, "status": agency.status}


@router.post("/{agency_id}/restore")
async def restore_agency(
    agency_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("agents.edit")),
) -> dict:
    """Restore an archived/suspended agency back to active."""
    svc = AgencyService(session)
    try:
        agency = svc.update_agency(agency_id, status="active")
    except LookupError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc
    return {"id": agency.id, "status": agency.status}


@router.delete("/{agency_id}")
async def delete_agency(
    agency_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("agents.delete")),
) -> dict:
    svc = AgencyService(session)
    try:
        svc.delete_agency(agency_id)
    except LookupError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc
    return {"message": "Agency archived"}


@router.post("/{agency_id}/reset-password")
async def reset_agency_password(
    agency_id: str,
    data: ResetPasswordRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("agents.reset_password")),
) -> dict:
    """Super admin resets an agency's password."""
    svc = AgencyService(session)
    try:
        svc.reset_password(agency_id, data.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc
    return {"message": "Password reset successfully"}


# --- Member management ---

@router.post("/{agency_id}/members")
async def add_member(
    agency_id: str,
    data: AddMemberRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("agents.members")),
) -> dict:
    svc = AgencyService(session)
    try:
        member = svc.add_member(agency_id, username=data.username, password=data.password, role=data.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Notify member addition
    NotificationService(session).create_notification(
        account_id=None, type="agency_member", category="system",
        title="新下属成员加入",
        message=f"用户 {data.username} 被添加为 {data.role}",
        severity="info",
    )

    return {
        "id": member.id,
        "agency_id": member.agency_id,
        "user_id": member.user_id,
        "role": member.role,
    }


@router.patch("/{agency_id}/members/{member_id}")
async def update_member_role(
    agency_id: str,
    member_id: str,
    data: UpdateMemberRoleRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("agents.members_role")),
) -> dict:
    svc = AgencyService(session)
    try:
        member = svc.update_member_role(member_id, role=data.role)
        if data.password:
            svc.update_member_password(member_id, data.password)
    except ValueError as exc:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc
    return {
        "id": member.id,
        "agency_id": member.agency_id,
        "user_id": member.user_id,
        "role": member.role,
    }


@router.delete("/{agency_id}/members/{member_id}")
async def remove_member(
    agency_id: str,
    member_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("agents.members")),
) -> dict:
    svc = AgencyService(session)
    try:
        svc.remove_member(member_id)
    except LookupError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc

    NotificationService(session).create_notification(
        account_id=None, type="agency_member", category="system",
        title="下属成员已移除",
        message=f"成员 {member_id} 已从代理商移除",
        severity="warning",
    )

    return {"message": "Member removed"}


@router.get("/{agency_id}/members")
async def list_members(
    agency_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("agents.members")),
) -> list[dict]:
    svc = AgencyService(session)
    members = svc.list_members(agency_id)
    return [
        {
            "id": item.member.id,
            "agency_id": item.member.agency_id,
            "user_id": item.member.user_id,
            "username": item.username,
            "display_name": item.display_name,
            "status": item.status,
            "role": item.member.role,
            "created_at": item.member.created_at.isoformat() if item.member.created_at else None,
        }
        for item in members
    ]


# --- Billing management (AF-BE-004) ---


@router.get("/{agency_id}/billing")
async def list_agency_billing(
    agency_id: str,
    status: str | None = Query(default=None),
    billing_type: str | None = Query(default=None),
    period_start: str | None = Query(default=None),
    period_end: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("agents.billing")),
) -> list[dict]:
    """List billing records for a specific agency."""
    stmt = build_agency_billing_list_stmt(
        agency_id=agency_id,
        status=status,
        billing_type=billing_type,
        period_start=parse_billing_date(period_start),
        period_end=parse_billing_date(period_end),
    )
    records = list(session.execute(stmt).scalars().all())
    return [serialize_agency_billing(record) for record in records]


@router.get("/{agency_id}/billing/{billing_id}")
async def get_agency_billing(
    agency_id: str,
    billing_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("agents.billing")),
) -> dict[str, Any]:
    billing = ensure_billing_matches_agency_scope(
        get_agency_billing_or_404(session, billing_id),
        agency_id,
    )
    return serialize_agency_billing(billing)


@router.post("/{agency_id}/billing", status_code=HTTPStatus.CREATED)
async def create_agency_billing(
    agency_id: str,
    data: CreateAgencyBillingRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("agents.billing_verify")),
) -> dict[str, Any]:
    billing = AgencyBilling(
        id=str(uuid4()),
        agency_id=agency_id,
        billing_type=data.billing_type,
        amount=data.amount,
        billing_period_start=parse_billing_date(data.billing_period_start),
        billing_period_end=parse_billing_date(data.billing_period_end),
        status="draft",
        line_items=[item.model_dump() for item in data.line_items] if data.line_items else [],
    )
    session.add(billing)
    session.flush()
    session.commit()
    session.refresh(billing)
    return serialize_agency_billing(billing)


@router.patch("/{agency_id}/billing/{billing_id}")
async def update_agency_billing(
    agency_id: str,
    billing_id: str,
    data: UpdateAgencyBillingRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("agents.billing_verify")),
) -> dict[str, Any]:
    billing = ensure_billing_matches_agency_scope(
        get_agency_billing_or_404(session, billing_id),
        agency_id,
    )
    if "billing_type" in data.model_fields_set and data.billing_type is not None:
        billing.billing_type = data.billing_type
    if "amount" in data.model_fields_set and data.amount is not None:
        billing.amount = data.amount
    if data.status is not None:
        validate_billing_status_transition(billing.status, data.status)
        billing.status = data.status
    if "billing_period_start" in data.model_fields_set:
        billing.billing_period_start = parse_billing_date(data.billing_period_start)
    if "billing_period_end" in data.model_fields_set:
        billing.billing_period_end = parse_billing_date(data.billing_period_end)
    if "line_items" in data.model_fields_set:
        billing.line_items = (
            [item.model_dump() for item in data.line_items]
            if data.line_items is not None
            else []
        )
    session.flush()
    session.commit()
    session.refresh(billing)
    return serialize_agency_billing(billing)


@router.delete("/{agency_id}/billing/{billing_id}")
async def delete_agency_billing(
    agency_id: str,
    billing_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("agents.billing_verify")),
) -> dict[str, Any]:
    billing = ensure_billing_matches_agency_scope(
        get_agency_billing_or_404(session, billing_id),
        agency_id,
    )
    if billing.status not in {"draft", "pending"}:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=f"Billing record in status '{billing.status}' cannot be cancelled.",
        )
    validate_billing_status_transition(billing.status, "cancelled")
    billing.status = "cancelled"
    session.flush()
    session.commit()
    session.refresh(billing)
    return serialize_agency_billing(billing)


@router.post("/{agency_id}/billing/{billing_id}/verify")
async def verify_billing_payment(
    agency_id: str,
    billing_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("agents.billing_verify")),
) -> dict:
    """Verify/approve a billing payment (mark as paid)."""
    billing = ensure_billing_matches_agency_scope(
        get_agency_billing_or_404(session, billing_id),
        agency_id,
    )
    validate_billing_status_transition(billing.status, "paid")
    billing.status = "paid"
    session.flush()
    session.commit()
    session.refresh(billing)

    NotificationService(session).create_notification(
        account_id=None, type="billing", category="system",
        title="账单已核销",
        message=f"代理商 {agency_id} 账单 ¥{float(billing.amount)} 已核销",
        severity="success",
    )

    return {
        "id": billing.id,
        "agency_id": billing.agency_id,
        "status": billing.status,
        "message": "Payment verified successfully",
    }
