from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from app.api.deps import get_runtime_state_service, get_ticket_service, require_permission
from app.core.platform_enums import TicketStatus
from app.core.auth import RequestActor, filter_account_scoped_items, get_effective_account_ids
from app.schemas.task_workflow import (
    LegacyTicketCreateRequest,
    TicketCreateRequest,
    TicketMessageCreateRequest,
    TicketMessageResponse,
    TicketResponse,
    TicketStatusUpdateRequest,
)
from app.services.runtime_state import RuntimeStateStore
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/api/tickets", tags=["tickets"])



@router.get(
    "",
    summary="List tickets",
    description="List support tickets with optional filters.",
    tags=["tickets"],
)
async def list_tickets(
    request: Request,
    account_id: str | None = None,
    ticket_type: str | None = None,
    status: str | None = None,
    public_user_id: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    sort: str | None = Query(default="-created_at"),
    search: str | None = None,
    ticket_service: TicketService = Depends(get_ticket_service),
    actor: RequestActor = Depends(require_permission("tickets.view")),
) -> dict | list[TicketResponse]:
    if account_id is not None:
        actor.require_account_access(account_id)
    try:
        resolved_status = _normalize_ticket_status_contract(status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    items = await ticket_service.list_tickets(
        account_id=account_id,
        ticket_type=ticket_type,
        status=resolved_status,
        public_user_id=public_user_id,
        allowed_account_ids=get_effective_account_ids(actor),
    )
    items = filter_account_scoped_items(actor, items, lambda item: item.account_id)
    if search:
        lower = search.lower()
        items = [
            item for item in items
            if (item.subject and lower in item.subject.lower())
            or (item.description and lower in item.description.lower())
        ]
    if sort:
        reverse = sort.startswith("-")
        field = sort.lstrip("-")
        items.sort(key=lambda item: getattr(item, field, None) or "", reverse=reverse)
    total = len(items)
    start = (page - 1) * size
    items_on_page = items[start:start + size]
    if not any(key in request.query_params for key in ("page", "size", "sort", "search")):
        return items_on_page
    return {"items": items_on_page, "total": total, "page": page, "size": size}


@router.get(
    "/{ticket_id}",
    summary="Get ticket",
    description="Get a specific support ticket by ID.",
    tags=["tickets"],
)
async def get_ticket(
    ticket_id: str,
    ticket_service: TicketService = Depends(get_ticket_service),
    actor: RequestActor = Depends(require_permission("tickets.view")),
) -> TicketResponse:
    try:
        ticket = await ticket_service.get_ticket(ticket_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(ticket.account_id)
    return ticket


@router.post(
    "",
    summary="Create ticket",
    description="Create a new support ticket.",
    tags=["tickets"],
)
async def create_ticket(
    payload: TicketCreateRequest | LegacyTicketCreateRequest = Body(...),
    ticket_service: TicketService = Depends(get_ticket_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tickets.create")),
) -> TicketResponse:
    normalized_payload = payload
    if isinstance(payload, LegacyTicketCreateRequest):
        try:
            normalized_payload = await ticket_service.build_create_request_from_legacy(payload)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    try:
        actor.require_account_access(await ticket_service.resolve_create_account_id(normalized_payload))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        ticket = await ticket_service.create_ticket(normalized_payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    audit_action, target_type, target_id = _build_ticket_create_audit(ticket)
    runtime_state.add_audit_log(
        account_id=ticket.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action=audit_action,
        target_type=target_type,
        target_id=target_id,
        payload={
            "ticket_id": ticket.id,
            "ticket_type": ticket.ticket_type,
            "linked_task_instance_id": ticket.linked_task_instance_id,
            "linked_submission_id": ticket.linked_submission_id,
            "review_decision_id": ticket.review_decision_id,
        },
    )
    runtime_state.commit()
    return ticket


@router.post(
    "/{ticket_id}/messages",
    summary="Add ticket message",
    description="Add a message to an existing support ticket.",
    tags=["tickets"],
)
async def add_ticket_message(
    ticket_id: str,
    payload: TicketMessageCreateRequest,
    ticket_service: TicketService = Depends(get_ticket_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tickets.reply")),
) -> TicketMessageResponse:
    if payload.sender_id is None:
        payload.sender_id = actor.actor_id
    try:
        actor.require_account_access((await ticket_service.get_ticket(ticket_id)).account_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        message = await ticket_service.add_message(ticket_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=message.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="ticket_message_added",
        target_type="ticket",
        target_id=ticket_id,
        payload={
            "sender_type": message.sender_type,
            "is_internal": message.is_internal,
        },
    )
    runtime_state.commit()
    return message


@router.post(
    "/{ticket_id}/status",
    summary="Update ticket status",
    description="Update the status of a support ticket.",
    tags=["tickets"],
)
async def update_ticket_status(
    ticket_id: str,
    payload: TicketStatusUpdateRequest,
    ticket_service: TicketService = Depends(get_ticket_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tickets.status")),
) -> TicketResponse:
    try:
        payload.status = _normalize_ticket_status_contract(payload.status) or payload.status
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        actor.require_account_access((await ticket_service.get_ticket(ticket_id)).account_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        ticket = await ticket_service.update_status(ticket_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=ticket.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="ticket_status_updated",
        target_type="ticket",
        target_id=ticket_id,
        payload={"status": ticket.status},
    )
    runtime_state.commit()
    return ticket


def _build_ticket_create_audit(ticket: TicketResponse) -> tuple[str, str, str]:
    if ticket.ticket_type == "appeal" and ticket.linked_task_instance_id is not None:
        return "appeal_ticket_created", "task_instance", ticket.linked_task_instance_id
    if ticket.ticket_type == "help":
        return "help_ticket_created", "ticket", ticket.id
    if ticket.ticket_type == "complaint":
        return "complaint_ticket_created", "ticket", ticket.id
    return "ticket_created", "ticket", ticket.id


def _normalize_ticket_status_contract(status: str | None) -> str | None:
    if status is None:
        return None
    if status == TicketStatus.WAITING_USER.value:
        raise ValueError(
            "Unsupported ticket status 'waiting_user'. Use 'pending_user' instead."
        )
    normalized_status = status
    supported_statuses = {item.value for item in TicketStatus if item is not TicketStatus.WAITING_USER}
    if normalized_status not in supported_statuses:
        raise ValueError(
            f"Unsupported ticket status '{status}'. Supported statuses: {', '.join(sorted(supported_statuses))}."
        )
    return normalized_status
