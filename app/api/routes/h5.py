from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_h5_member_auth_service,
    get_db_session,
    get_review_service,
    get_runtime_state_service,
    get_task_proof_storage_service,
    get_task_service,
    get_task_submission_service,
    get_ticket_service,
)
from app.constants.h5_templates import DEFAULT_H5_TEMPLATE_ID
from app.core.settings import Settings, get_settings
from app.core.platform_enums import TicketStatus
from app.db.models import AppUser, H5Site, H5SiteConfig
from app.schemas.task_workflow import (
    H5BootstrapResponse,
    H5SiteSummaryResponse,
    H5UserSummaryResponse,
    TaskProofFileResponse,
    TaskSubmissionCreateRequest,
    TaskSubmissionResponse,
    TicketCreateRequest,
    TicketMessageCreateRequest,
    TicketMessageResponse,
    TicketResponse,
)
from app.services.h5_member_auth_service import H5MemberAuthService
from app.services.runtime_state import RuntimeStateStore
from app.services.review_service import ReviewService
from app.services.task_proof_storage_service import TaskProofStorageService
from app.services.task_service import TaskService
from app.services.task_submission_service import TaskSubmissionService
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/api/h5", tags=["h5"])
H5_OPEN_TICKET_STATUSES = {"open", "in_progress", "pending_user"}


def _normalize_h5_ticket_status_filter(status: str | None) -> str | None:
    if status is None:
        return None
    if status == TicketStatus.WAITING_USER.value:
        raise ValueError("Unsupported ticket status 'waiting_user'. Use 'pending_user' instead.")
    return status


@router.get(
    "/bootstrap",
    summary="H5 bootstrap",
    description="Returns H5 bootstrap data including site info, user tasks, and open ticket count.",
    tags=["h5"],
)
async def get_h5_bootstrap(
    request: Request,
    site_key: str | None = None,
    public_user_id: str | None = None,
    session: Session = Depends(get_db_session),
    task_service: TaskService = Depends(get_task_service),
    ticket_service: TicketService = Depends(get_ticket_service),
    auth_service: H5MemberAuthService = Depends(get_h5_member_auth_service),
    settings: Settings = Depends(get_settings),
) -> H5BootstrapResponse:
    user, site = await _resolve_h5_context_with_auth(
        session=session,
        request=request,
        settings=settings,
        auth_service=auth_service,
        site_key=site_key,
        public_user_id=public_user_id,
    )
    tasks = [
        item.model_dump(mode="json")
        for item in await task_service.list_task_instances(user_id=user.id)
        if item.site_id == site.id
    ]
    tickets = await ticket_service.list_tickets(public_user_id=user.public_user_id)
    scoped_tickets = [ticket for ticket in tickets if ticket.site_id == site.id]
    open_ticket_count = sum(1 for ticket in scoped_tickets if ticket.status in H5_OPEN_TICKET_STATUSES)
    return H5BootstrapResponse(
        site=H5SiteSummaryResponse(
            id=site.id,
            account_id=site.account_id,
            site_key=site.site_key,
            brand_name=site.brand_name,
            domain=site.domain,
            default_language=site.default_language,
        ),
        user=H5UserSummaryResponse(
            id=user.id,
            public_user_id=user.public_user_id,
            display_name=user.display_name,
            language_code=user.language_code,
        ),
        tasks=tasks,
        open_ticket_count=open_ticket_count,
    )


@router.get(
    "/tasks",
    summary="List H5 tasks",
    description="List task instances for the authenticated H5 user.",
    tags=["h5"],
)
async def list_h5_tasks(
    request: Request,
    site_key: str | None = None,
    public_user_id: str | None = None,
    session: Session = Depends(get_db_session),
    task_service: TaskService = Depends(get_task_service),
    auth_service: H5MemberAuthService = Depends(get_h5_member_auth_service),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, object]]:
    user, site = await _resolve_h5_context_with_auth(
        session=session,
        request=request,
        settings=settings,
        auth_service=auth_service,
        site_key=site_key,
        public_user_id=public_user_id,
    )
    return [
        item.model_dump(mode="json")
        for item in await task_service.list_task_instances(user_id=user.id)
        if item.site_id == site.id
    ]


@router.get(
    "/tasks/{task_instance_id}",
    summary="Get H5 task detail",
    description="Get task instance detail with latest submission and review decision.",
    tags=["h5"],
)
async def get_h5_task_detail(
    task_instance_id: str,
    request: Request,
    site_key: str | None = None,
    public_user_id: str | None = None,
    session: Session = Depends(get_db_session),
    task_service: TaskService = Depends(get_task_service),
    review_service: ReviewService = Depends(get_review_service),
    auth_service: H5MemberAuthService = Depends(get_h5_member_auth_service),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    user, site = await _resolve_h5_context_with_auth(
        session=session,
        request=request,
        settings=settings,
        auth_service=auth_service,
        site_key=site_key,
        public_user_id=public_user_id,
    )
    try:
        task = await task_service.get_task_instance(task_instance_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if task.user_id != user.id or task.site_id != site.id:
        raise HTTPException(status_code=403, detail="Task instance is outside the current H5 scope.")

    detail = task.model_dump(mode="json")
    detail["latest_submission"] = None
    detail["latest_review_decision"] = None
    if task.latest_submission_id:
        try:
            review_detail = await review_service.get_submission_detail(task.latest_submission_id)
        except LookupError:
            return detail
        detail["latest_submission"] = review_detail.submission.model_dump(mode="json")
        detail["latest_review_decision"] = (
            review_detail.latest_decision.model_dump(mode="json")
            if review_detail.latest_decision is not None
            else None
        )
    return detail


@router.post(
    "/task-proofs",
    summary="Upload task proof",
    description="Upload a proof file for a task instance.",
    tags=["h5"],
)
async def upload_task_proof(
    request: Request,
    task_instance_id: str = Form(...),
    public_user_id: str | None = Form(default=None),
    site_id: str | None = Form(default=None),
    site_key: str | None = Form(default=None),
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
    proof_storage_service: TaskProofStorageService = Depends(get_task_proof_storage_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    auth_service: H5MemberAuthService = Depends(get_h5_member_auth_service),
    settings: Settings = Depends(get_settings),
) -> TaskProofFileResponse:
    user, site = await _resolve_h5_context_with_auth(
        session=session,
        request=request,
        settings=settings,
        auth_service=auth_service,
        public_user_id=public_user_id,
        site_id=site_id,
        site_key=site_key,
    )
    try:
        proof = await proof_storage_service.upload_proof(
            task_instance_id=task_instance_id,
            public_user_id=user.public_user_id,
            site_id=site.id,
            site_key=site.site_key,
            original_filename=file.filename or "proof.bin",
            content_type=file.content_type or "application/octet-stream",
            content=await file.read(),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    finally:
        await file.close()

    runtime_state.add_audit_log(
        account_id=proof.account_id,
        actor_type="h5_user",
        actor_id=user.public_user_id,
        action="task_proof_uploaded",
        target_type="task_instance",
        target_id=task_instance_id,
        payload={"proof_file_id": proof.id},
    )
    runtime_state.commit()
    return proof


@router.post(
    "/tasks/{task_instance_id}/submit",
    summary="Submit H5 task",
    description="Submit a task with proof files and optional notes.",
    tags=["h5"],
)
async def submit_h5_task(
    task_instance_id: str,
    payload: TaskSubmissionCreateRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    submission_service: TaskSubmissionService = Depends(get_task_submission_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    auth_service: H5MemberAuthService = Depends(get_h5_member_auth_service),
    settings: Settings = Depends(get_settings),
) -> TaskSubmissionResponse:
    user, site = await _resolve_h5_context_with_auth(
        session=session,
        request=request,
        settings=settings,
        auth_service=auth_service,
        public_user_id=payload.public_user_id,
        site_id=payload.site_id,
        site_key=payload.site_key,
    )
    try:
        submission = await submission_service.create_submission(
            task_instance_id=task_instance_id,
            payload=TaskSubmissionCreateRequest(
                public_user_id=user.public_user_id,
                site_id=site.id,
                site_key=site.site_key,
                proof_file_ids=payload.proof_file_ids,
                notes=payload.notes,
                payload_json=payload.payload_json,
            ),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=submission.account_id,
        actor_type="h5_user",
        actor_id=user.public_user_id,
        action="task_submission_created",
        target_type="task_submission",
        target_id=submission.id,
        payload={
            "task_instance_id": task_instance_id,
            "proof_file_ids": payload.proof_file_ids,
        },
    )
    runtime_state.commit()
    return submission


@router.get(
    "/tickets",
    summary="List H5 tickets",
    description="List support tickets for the authenticated H5 user with optional status filter.",
    tags=["h5"],
)
async def list_h5_tickets(
    request: Request,
    site_key: str | None = None,
    public_user_id: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_db_session),
    ticket_service: TicketService = Depends(get_ticket_service),
    auth_service: H5MemberAuthService = Depends(get_h5_member_auth_service),
    settings: Settings = Depends(get_settings),
) -> list[TicketResponse]:
    user, site = await _resolve_h5_context_with_auth(
        session=session,
        request=request,
        settings=settings,
        auth_service=auth_service,
        site_key=site_key,
        public_user_id=public_user_id,
    )
    try:
        return await ticket_service.list_tickets(
            public_user_id=user.public_user_id,
            site_id=site.id,
            status=_normalize_h5_ticket_status_filter(status),
            include_internal_messages=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/tickets",
    summary="Create H5 ticket",
    description="Create a new support ticket for the authenticated H5 user.",
    tags=["h5"],
)
async def create_h5_ticket(
    payload: TicketCreateRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    ticket_service: TicketService = Depends(get_ticket_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    auth_service: H5MemberAuthService = Depends(get_h5_member_auth_service),
    settings: Settings = Depends(get_settings),
) -> TicketResponse:
    user, site = await _resolve_h5_context_with_auth(
        session=session,
        request=request,
        settings=settings,
        auth_service=auth_service,
        public_user_id=payload.public_user_id,
        site_id=payload.site_id,
        site_key=payload.site_key,
    )
    try:
        ticket = await ticket_service.create_ticket(
            TicketCreateRequest(
                account_id=user.account_id,
                public_user_id=user.public_user_id,
                site_id=site.id,
                site_key=site.site_key,
                ticket_type=payload.ticket_type,
                title=payload.title,
                body_text=payload.body_text,
                linked_task_instance_id=payload.linked_task_instance_id,
                linked_submission_id=payload.linked_submission_id,
                priority=payload.priority,
                attachments_json=payload.attachments_json,
            )
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit_action, target_type, target_id = _build_ticket_create_audit(ticket)
    runtime_state.add_audit_log(
        account_id=ticket.account_id,
        actor_type="h5_user",
        actor_id=user.public_user_id,
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


@router.get(
    "/tickets/{ticket_id}",
    summary="Get H5 ticket",
    description="Get a support ticket detail for the authenticated H5 user.",
    tags=["h5"],
)
async def get_h5_ticket(
    ticket_id: str,
    request: Request,
    site_key: str | None = None,
    public_user_id: str | None = None,
    session: Session = Depends(get_db_session),
    ticket_service: TicketService = Depends(get_ticket_service),
    auth_service: H5MemberAuthService = Depends(get_h5_member_auth_service),
    settings: Settings = Depends(get_settings),
) -> TicketResponse:
    user, site = await _resolve_h5_context_with_auth(
        session=session,
        request=request,
        settings=settings,
        auth_service=auth_service,
        site_key=site_key,
        public_user_id=public_user_id,
    )
    try:
        ticket = await ticket_service.get_ticket(ticket_id, include_internal_messages=False)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if ticket.public_user_id != user.public_user_id:
        raise HTTPException(status_code=403, detail="Ticket is outside the current H5 scope.")
    if ticket.site_id != site.id:
        raise HTTPException(status_code=403, detail="Ticket is outside the current H5 site scope.")
    return ticket


@router.post(
    "/tickets/{ticket_id}/messages",
    summary="Create H5 ticket message",
    description="Add a message to a support ticket from the authenticated H5 user.",
    tags=["h5"],
)
async def create_h5_ticket_message(
    ticket_id: str,
    request: Request,
    site_key: str | None = None,
    public_user_id: str | None = None,
    body_text: str = Form(...),
    ticket_service: TicketService = Depends(get_ticket_service),
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    auth_service: H5MemberAuthService = Depends(get_h5_member_auth_service),
    settings: Settings = Depends(get_settings),
) -> TicketMessageResponse:
    user, site = await _resolve_h5_context_with_auth(
        session=session,
        request=request,
        settings=settings,
        auth_service=auth_service,
        site_key=site_key,
        public_user_id=public_user_id,
    )
    try:
        ticket = await ticket_service.get_ticket(ticket_id, include_internal_messages=False)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if ticket.public_user_id != user.public_user_id:
        raise HTTPException(status_code=403, detail="Ticket is outside the current H5 scope.")
    if ticket.site_id != site.id:
        raise HTTPException(status_code=403, detail="Ticket is outside the current H5 site scope.")
    try:
        message = await ticket_service.add_message(
            ticket_id,
            TicketMessageCreateRequest(
                sender_type="user",
                sender_id=user.public_user_id,
                body_text=body_text,
                attachments_json=[],
                is_internal=False,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=ticket.account_id,
        actor_type="h5_user",
        actor_id=user.public_user_id,
        action="ticket_message_added",
        target_type="ticket",
        target_id=ticket_id,
        payload={"sender_type": "user"},
    )
    runtime_state.commit()
    return message


def _resolve_h5_context(*, session: Session, site_key: str, public_user_id: str) -> tuple[AppUser, H5Site]:
    site = session.scalars(select(H5Site).where(H5Site.site_key == site_key)).first()
    if site is None:
        raise HTTPException(status_code=404, detail=f"Site '{site_key}' was not found.")
    user = session.scalars(select(AppUser).where(AppUser.public_user_id == public_user_id)).first()
    if user is None:
        raise HTTPException(status_code=404, detail=f"Public user '{public_user_id}' was not found.")
    if user.registration_site_id is None:
        raise HTTPException(status_code=403, detail="User is not bound to an H5 site.")
    if user.registration_site_id != site.id:
        raise HTTPException(status_code=403, detail="User is outside the current H5 site scope.")
    if user.account_id is not None and site.account_id is not None and user.account_id != site.account_id:
        raise HTTPException(status_code=403, detail="User is outside the current H5 account scope.")
    return user, site


def _resolve_h5_context_for_submission(
    *,
    session: Session,
    public_user_id: str,
    site_id: str | None,
    site_key: str | None,
) -> tuple[AppUser, H5Site]:
    site = _resolve_site(session, site_id, site_key)
    if site is None:
        raise HTTPException(status_code=404, detail="H5 request requires a valid site.")
    return _resolve_h5_context(session=session, site_key=site.site_key, public_user_id=public_user_id)


def _resolve_site(session: Session, site_id: str | None, site_key: str | None) -> H5Site | None:
    if site_id is not None:
        return session.get(H5Site, site_id)
    if site_key is not None:
        return session.scalars(select(H5Site).where(H5Site.site_key == site_key)).first()
    return None


async def _resolve_h5_context_with_auth(
    *,
    session: Session,
    request: Request,
    settings: Settings,
    auth_service: H5MemberAuthService,
    public_user_id: str | None,
    site_id: str | None = None,
    site_key: str | None = None,
) -> tuple[AppUser, H5Site]:
    session_token = request.cookies.get(settings.h5_member_session_cookie_name)
    if session_token:
        try:
            context = await auth_service.resolve_context(session_token=session_token)
        except LookupError as exc:
            raise HTTPException(status_code=401, detail="H5 member authentication is required.") from exc
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        if public_user_id is not None and public_user_id != context.user.public_user_id:
            raise HTTPException(status_code=403, detail="User is outside the current H5 member scope.")
        if site_id is not None and site_id != context.site.id:
            raise HTTPException(status_code=403, detail="User is outside the current H5 site scope.")
        if site_key is not None and site_key != context.site.site_key:
            raise HTTPException(status_code=403, detail="User is outside the current H5 site scope.")
        return context.user, context.site

    if not (settings.test_mode or not settings.auth_required):
        raise HTTPException(status_code=401, detail="H5 member authentication is required.")
    if public_user_id is None:
        raise HTTPException(status_code=401, detail="H5 member authentication is required.")
    return _resolve_h5_context_for_submission(
        session=session,
        public_user_id=public_user_id,
        site_id=site_id,
        site_key=site_key,
    )


def _build_ticket_create_audit(ticket: TicketResponse) -> tuple[str, str, str]:
    if ticket.ticket_type == "appeal" and ticket.linked_task_instance_id is not None:
        return "appeal_ticket_created", "task_instance", ticket.linked_task_instance_id
    if ticket.ticket_type == "help":
        return "help_ticket_created", "ticket", ticket.id
    if ticket.ticket_type == "complaint":
        return "complaint_ticket_created", "ticket", ticket.id
    return "ticket_created", "ticket", ticket.id

@router.get(
    "/sites/{site_key}/brand-config",
    summary="Get H5 site brand config",
    description="Returns brand configuration for a site (template JS startup API).",
    tags=["h5"],
)
async def get_site_brand_config(
    site_key: str,
    session: Session = Depends(get_db_session),
) -> dict:
    """Return brand config for template startup."""
    site = session.execute(
        select(H5Site).where(H5Site.site_key == site_key)
    ).scalar_one_or_none()
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")

    metadata_template_id = None
    if site.metadata_json:
        metadata_template_id = site.metadata_json.get("template_id")
    template_id = (
        metadata_template_id
        if metadata_template_id == DEFAULT_H5_TEMPLATE_ID
        else DEFAULT_H5_TEMPLATE_ID
    )
    site_config = session.execute(
        select(H5SiteConfig).where(H5SiteConfig.site_id == site.id)
    ).scalar_one_or_none()

    return {
        "brand_name": site.brand_name,
        "logo_url": site_config.logo_url if site_config and site_config.logo_url else site.logo_url,
        "favicon_url": site_config.favicon_url if site_config else None,
        "site_key": site.site_key,
        "default_language": site.default_language,
        "template_id": template_id,
        "primary_color": site_config.primary_color if site_config else None,
        "font_family": site_config.font_family if site_config else None,
        "footer_text": site_config.footer_text if site_config else None,
    }
