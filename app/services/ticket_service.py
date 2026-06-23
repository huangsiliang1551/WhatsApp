from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.metrics import tickets_created_total, tickets_status_transition_total
from app.core.platform_enums import (
    TaskInstanceStatus,
    TaskSubmissionStatus,
    TicketMessageSenderType,
    TicketStatus,
    TicketType,
)
from app.db.models import (
    AppUser,
    H5Site,
    TaskInstance,
    TaskReviewDecision,
    TaskSubmission,
    Ticket,
    TicketMessage,
    utc_now,
)
from app.schemas.task_workflow import (
    LegacyTicketCreateRequest,
    TicketCreateRequest,
    TicketMessageCreateRequest,
    TicketMessageResponse,
    TicketResponse,
    TicketStatusUpdateRequest,
)


ACTIVE_APPEAL_STATUSES = {"open", "in_progress", "pending_user"}
ACTIVE_TICKET_STATUSES = set(ACTIVE_APPEAL_STATUSES)
TERMINAL_TICKET_STATUSES = {"resolved", "rejected", "closed", "cancelled"}
SUPPORTED_TICKET_TYPES = {item.value for item in TicketType}
SUPPORTED_TICKET_STATUSES = {
    item.value for item in TicketStatus if item is not TicketStatus.WAITING_USER
}
SUPPORTED_SENDER_TYPES = {item.value for item in TicketMessageSenderType}
TICKET_STATUS_TRANSITIONS: dict[str, set[str]] = {
    TicketStatus.OPEN.value: {
        TicketStatus.IN_PROGRESS.value,
        TicketStatus.PENDING_USER.value,
        TicketStatus.RESOLVED.value,
        TicketStatus.REJECTED.value,
        TicketStatus.CANCELLED.value,
    },
    TicketStatus.IN_PROGRESS.value: {
        TicketStatus.PENDING_USER.value,
        TicketStatus.RESOLVED.value,
        TicketStatus.REJECTED.value,
        TicketStatus.CANCELLED.value,
    },
    TicketStatus.PENDING_USER.value: {
        TicketStatus.IN_PROGRESS.value,
        TicketStatus.RESOLVED.value,
        TicketStatus.REJECTED.value,
        TicketStatus.CANCELLED.value,
    },
    TicketStatus.RESOLVED.value: {
        TicketStatus.CLOSED.value,
        TicketStatus.IN_PROGRESS.value,
    },
    TicketStatus.REJECTED.value: {
        TicketStatus.CLOSED.value,
    },
    TicketStatus.CLOSED.value: set(),
    TicketStatus.CANCELLED.value: set(),
}


class TicketService:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    async def list_tickets(
        self,
        *,
        account_id: str | None = None,
        ticket_type: str | None = None,
        status: str | None = None,
        public_user_id: str | None = None,
        site_id: str | None = None,
        site_key: str | None = None,
        agency_id: str | None = None,
        allowed_account_ids: set[str] | None = None,
        include_internal_messages: bool = True,
    ) -> list[TicketResponse]:
        query = (
            select(Ticket)
            .options(joinedload(Ticket.user))
            .options(joinedload(Ticket.site))
            .options(joinedload(Ticket.messages))
            .order_by(Ticket.updated_at.desc(), Ticket.created_at.desc(), Ticket.id.desc())
        )
        if allowed_account_ids is not None:
            if not allowed_account_ids:
                return []
            query = query.where(Ticket.account_id.in_(sorted(allowed_account_ids)))
        if ticket_type is not None:
            query = query.where(Ticket.ticket_type == ticket_type)
        if account_id is not None:
            query = query.where(Ticket.account_id == account_id)
        if agency_id is not None:
            query = query.join(H5Site, H5Site.id == Ticket.site_id).where(H5Site.agency_id == agency_id)
        if status is not None:
            normalized_status = self._normalize_status(status)
            self._ensure_status_supported(normalized_status)
            if normalized_status == TicketStatus.PENDING_USER.value:
                query = query.where(
                    Ticket.status.in_(
                        [TicketStatus.PENDING_USER.value, TicketStatus.WAITING_USER.value]
                    )
                )
            else:
                query = query.where(Ticket.status == normalized_status)
        if public_user_id is not None:
            query = query.join(AppUser, AppUser.id == Ticket.user_id).where(AppUser.public_user_id == public_user_id)
        if site_id is not None:
            query = query.where(Ticket.site_id == site_id)
        elif site_key is not None:
            query = query.join(H5Site, H5Site.id == Ticket.site_id).where(H5Site.site_key == site_key)
        tickets = self._session.execute(query).unique().scalars().all()
        return [self._serialize_ticket(ticket, include_internal_messages=include_internal_messages) for ticket in tickets]

    async def get_ticket(self, ticket_id: str, *, include_internal_messages: bool = True) -> TicketResponse:
        ticket = self._ticket_query().where(Ticket.id == ticket_id)
        model = self._session.execute(ticket).unique().scalars().first()
        if model is None:
            raise LookupError(f"Ticket '{ticket_id}' was not found.")
        return self._serialize_ticket(model, include_internal_messages=include_internal_messages)

    async def create_ticket(self, payload: TicketCreateRequest) -> TicketResponse:
        (
            user,
            site,
            linked_task_instance,
            linked_submission,
            resolved_account_id,
        ) = self._prepare_create_context(payload)

        now = utc_now()
        ticket = Ticket(
            account_id=resolved_account_id,
            ticket_no=f"TKT-{uuid4().hex[:10].upper()}",
            ticket_type=payload.ticket_type,
            status="open",
            priority=payload.priority,
            site_id=site.id if site is not None else user.registration_site_id,
            site_key=site.site_key if site else None,
            user_id=user.id,
            linked_task_instance_id=linked_task_instance.id if linked_task_instance is not None else None,
            linked_submission_id=linked_submission.id if linked_submission is not None else None,
            review_decision_id=self._resolve_review_decision_id(linked_submission),
            title=payload.title,
            latest_reply_at=now,
            is_active=True,
            metadata_json=None,
        )
        self._session.add(ticket)
        if payload.ticket_type == TicketType.APPEAL.value and linked_task_instance is not None:
            linked_task_instance.status = TaskInstanceStatus.APPEALING.value
            self._session.add(linked_task_instance)
        self._session.flush()
        self._session.add(
            TicketMessage(
                ticket_id=ticket.id,
                sender_type="user",
                sender_id=user.public_user_id,
                body_text=payload.body_text,
                attachments_json=payload.attachments_json,
                is_internal=False,
                created_at=now,
            )
        )
        self._session.commit()
        tickets_created_total.labels(ticket_type=payload.ticket_type).inc()
        return await self.get_ticket(ticket.id)

    async def resolve_create_account_id(self, payload: TicketCreateRequest) -> str:
        (
            _user,
            _site,
            _linked_task_instance,
            _linked_submission,
            resolved_account_id,
        ) = self._prepare_create_context(payload)
        return resolved_account_id

    async def build_create_request_from_legacy(self, payload: LegacyTicketCreateRequest) -> TicketCreateRequest:
        task_instance = self._session.execute(
            select(TaskInstance)
            .options(joinedload(TaskInstance.user))
            .where(TaskInstance.id == payload.task_instance_id)
        ).unique().scalars().first()
        if task_instance is None:
            raise LookupError(f"Task instance '{payload.task_instance_id}' was not found.")

        linked_submission_id: str | None = None
        if payload.ticket_type == "appeal":
            linked_submission = self._resolve_latest_submission_for_task(task_instance.id)
            if (
                linked_submission is None
                or linked_submission.status != TaskSubmissionStatus.REJECTED.value
            ):
                raise ValueError(
                    "Appeal tickets require the latest submission for "
                    f"task instance '{task_instance.id}' to be rejected."
                )
            linked_submission_id = linked_submission.id

        return TicketCreateRequest(
            account_id=task_instance.account_id,
            public_user_id=task_instance.user.public_user_id,
            site_id=task_instance.site_id,
            ticket_type=payload.ticket_type,
            title=payload.title,
            body_text=payload.content,
            linked_task_instance_id=task_instance.id,
            linked_submission_id=linked_submission_id,
        )

    async def add_message(self, ticket_id: str, payload: TicketMessageCreateRequest) -> TicketMessageResponse:
        ticket = self._session.get(Ticket, ticket_id)
        if ticket is None:
            raise LookupError(f"Ticket '{ticket_id}' was not found.")
        self._validate_message_payload(payload)
        ticket.status = self._normalize_status(ticket.status)
        if ticket.status in {
            TicketStatus.CLOSED.value,
            TicketStatus.CANCELLED.value,
            TicketStatus.REJECTED.value,
        }:
            raise ValueError(f"Ticket '{ticket_id}' is {ticket.status} and does not accept new messages.")
        message = TicketMessage(
            ticket_id=ticket_id,
            sender_type=payload.sender_type,
            sender_id=payload.sender_id,
            body_text=payload.body_text,
            attachments_json=payload.attachments_json,
            is_internal=payload.is_internal,
        )
        ticket.latest_reply_at = message.created_at
        if payload.sender_type == TicketMessageSenderType.USER.value and ticket.status in {
            TicketStatus.PENDING_USER.value,
            TicketStatus.WAITING_USER.value,
        }:
            ticket.status = "in_progress"
            tickets_status_transition_total.labels(status="in_progress").inc()
        self._session.add(ticket)
        self._session.add(message)
        self._session.commit()
        self._session.refresh(message)
        return self._serialize_message(message, account_id=ticket.account_id)

    async def update_status(self, ticket_id: str, payload: TicketStatusUpdateRequest) -> TicketResponse:
        ticket = self._session.get(Ticket, ticket_id)
        if ticket is None:
            raise LookupError(f"Ticket '{ticket_id}' was not found.")
        current_status = self._normalize_status(ticket.status)
        target_status = self._normalize_status(payload.status)
        self._ensure_status_supported(target_status)
        self._ensure_transition_allowed(current_status=current_status, target_status=target_status)
        now = utc_now()
        ticket.status = target_status
        ticket.is_active = target_status in ACTIVE_TICKET_STATUSES
        if target_status == "resolved":
            ticket.resolved_at = now
            ticket.closed_at = None
        elif target_status == "closed":
            ticket.closed_at = now
        elif target_status == "rejected":
            ticket.resolved_at = None
            ticket.closed_at = None
        else:
            ticket.resolved_at = None
            ticket.closed_at = None
        self._sync_linked_appeal_state(ticket=ticket, target_status=target_status)
        self._session.add(ticket)
        self._session.commit()
        tickets_status_transition_total.labels(status=target_status).inc()
        return await self.get_ticket(ticket.id)

    def _ticket_query(self):
        return (
            select(Ticket)
            .options(joinedload(Ticket.user))
            .options(joinedload(Ticket.site))
            .options(joinedload(Ticket.messages))
        )

    def _prepare_create_context(
        self,
        payload: TicketCreateRequest,
    ) -> tuple[AppUser, H5Site | None, TaskInstance | None, TaskSubmission | None, str]:
        self._validate_ticket_payload(payload)
        user = self._require_user(payload.public_user_id)
        site = self._resolve_site(payload.site_id, payload.site_key)
        linked_task_instance = self._resolve_linked_task(payload.linked_task_instance_id)
        linked_submission = self._resolve_linked_submission(payload.linked_submission_id)
        if payload.ticket_type == TicketType.APPEAL.value and linked_submission is None and linked_task_instance is not None:
            linked_submission = self._resolve_latest_rejected_submission(linked_task_instance.id)
        resolved_account_id = self._require_resolved_account_scope(
            payload=payload,
            site=site,
            linked_task_instance=linked_task_instance,
            linked_submission=linked_submission,
            user=user,
        )

        if site is not None and user.registration_site_id not in {None, site.id}:
            raise PermissionError(
                f"Public user '{payload.public_user_id}' does not belong to site '{site.site_key}'."
            )
        if linked_task_instance is not None and linked_task_instance.user_id != user.id:
            raise PermissionError(
                f"Task instance '{linked_task_instance.id}' does not belong to public user '{payload.public_user_id}'."
            )
        if linked_submission is not None and linked_task_instance is not None:
            self._ensure_submission_matches_task(linked_task_instance, linked_submission)
        if linked_submission is not None and linked_submission.submitted_by_user_id != user.id:
            raise PermissionError(
                f"Task submission '{linked_submission.id}' does not belong to public user '{payload.public_user_id}'."
            )
        if linked_task_instance is not None and site is not None and linked_task_instance.site_id not in {None, site.id}:
            raise PermissionError(
                f"Task instance '{linked_task_instance.id}' does not belong to site '{site.site_key}'."
            )
        if payload.ticket_type == "appeal":
            latest_review_decision = self._resolve_latest_review_decision(linked_submission)
            self._validate_appeal_requirements(
                task_instance=linked_task_instance,
                submission=linked_submission,
                review_decision=latest_review_decision,
                account_id=resolved_account_id,
            )

        return user, site, linked_task_instance, linked_submission, resolved_account_id

    def _require_user(self, public_user_id: str) -> AppUser:
        user = self._session.scalars(select(AppUser).where(AppUser.public_user_id == public_user_id)).first()
        if user is None:
            raise LookupError(f"Public user '{public_user_id}' was not found.")
        return user

    def _resolve_site(self, site_id: str | None, site_key: str | None) -> H5Site | None:
        if site_id is not None:
            site = self._session.get(H5Site, site_id)
            if site is None:
                raise LookupError(f"Site '{site_id}' was not found.")
            return site
        if site_key is not None:
            site = self._session.scalars(select(H5Site).where(H5Site.site_key == site_key)).first()
            if site is None:
                raise LookupError(f"Site '{site_key}' was not found.")
            return site
        return None

    def _resolve_linked_task(self, task_instance_id: str | None) -> TaskInstance | None:
        if task_instance_id is None:
            return None
        task_instance = self._session.get(TaskInstance, task_instance_id)
        if task_instance is None:
            raise LookupError(f"Task instance '{task_instance_id}' was not found.")
        return task_instance

    def _resolve_linked_submission(self, submission_id: str | None) -> TaskSubmission | None:
        if submission_id is None:
            return None
        submission = self._session.get(TaskSubmission, submission_id)
        if submission is None:
            raise LookupError(f"Task submission '{submission_id}' was not found.")
        return submission

    def _resolve_latest_rejected_submission(self, task_instance_id: str) -> TaskSubmission | None:
        return self._session.execute(
            select(TaskSubmission)
            .where(
                TaskSubmission.task_instance_id == task_instance_id,
                TaskSubmission.status == "rejected",
            )
            .order_by(TaskSubmission.submission_no.desc(), TaskSubmission.created_at.desc(), TaskSubmission.id.desc())
        ).scalars().first()

    def _resolve_latest_submission_for_task(self, task_instance_id: str) -> TaskSubmission | None:
        return self._session.execute(
            select(TaskSubmission)
            .where(TaskSubmission.task_instance_id == task_instance_id)
            .order_by(TaskSubmission.submission_no.desc(), TaskSubmission.created_at.desc(), TaskSubmission.id.desc())
        ).scalars().first()

    def _validate_appeal_requirements(
        self,
        *,
        task_instance: TaskInstance | None,
        submission: TaskSubmission | None,
        review_decision: TaskReviewDecision | None,
        account_id: str,
    ) -> None:
        if task_instance is None or submission is None:
            raise ValueError("Appeal tickets require linked task_instance_id and linked_submission_id.")
        if submission.task_instance_id != task_instance.id:
            raise ValueError("Appeal ticket submission does not match the linked task instance.")
        if submission.account_id != account_id:
            raise ValueError("Appeal ticket account scope does not match the rejected submission.")
        if task_instance.status != "rejected" or submission.status != "rejected":
            raise ValueError("Appeal tickets can only be created for rejected submissions.")
        if review_decision is None:
            raise ValueError("Appeal tickets require a rejected review decision.")
        if review_decision.submission_id != submission.id or review_decision.task_instance_id != task_instance.id:
            raise ValueError("Appeal ticket review decision does not match the linked submission or task.")
        if review_decision.decision != "rejected":
            raise ValueError("Appeal tickets require the latest linked review decision to be rejected.")
        if review_decision.account_id != account_id:
            raise ValueError("Appeal ticket review decision account scope does not match the linked task.")
        latest_submission = self._resolve_latest_submission_for_task(task_instance.id)
        if latest_submission is None or latest_submission.id != submission.id:
            raise ValueError("Appeal tickets must bind to the latest submission for the linked task instance.")
        existing = self._session.scalars(
            select(Ticket).where(
                Ticket.linked_task_instance_id == task_instance.id,
                Ticket.ticket_type == "appeal",
                Ticket.is_active.is_(True),
            )
        ).first()
        if existing is not None:
            raise ValueError(f"Task instance '{task_instance.id}' already has an active appeal ticket.")

    @staticmethod
    def _resolve_scoped_account_id(
        *,
        site: H5Site | None,
        linked_task_instance: TaskInstance | None,
        linked_submission: TaskSubmission | None,
        user: AppUser,
        registration_site: H5Site | None,
    ) -> str | None:
        submission_account_id = linked_submission.account_id if linked_submission is not None else None
        task_account_id = linked_task_instance.account_id if linked_task_instance is not None else None
        site_account_id = site.account_id if site is not None else None
        user_account_id = user.account_id
        registration_site_account_id = registration_site.account_id if registration_site is not None else None
        return task_account_id or submission_account_id or site_account_id or user_account_id or registration_site_account_id

    def _require_resolved_account_scope(
        self,
        *,
        payload: TicketCreateRequest,
        site: H5Site | None,
        linked_task_instance: TaskInstance | None,
        linked_submission: TaskSubmission | None,
        user: AppUser,
    ) -> str:
        resolved_account_id = self._resolve_scoped_account_id(
            site=site,
            linked_task_instance=linked_task_instance,
            linked_submission=linked_submission,
            user=user,
            registration_site=user.registration_site,
        )
        if resolved_account_id is None:
            raise ValueError("Ticket requires a resolved account scope from payload, site, task, or user.")
        if payload.account_id is not None and resolved_account_id is not None and payload.account_id != resolved_account_id:
            raise ValueError("Ticket account_id does not match the linked site or task scope.")
        if site is not None and linked_task_instance is not None and site.account_id and linked_task_instance.account_id:
            if site.account_id != linked_task_instance.account_id:
                raise ValueError("Ticket site account scope does not match the linked task instance.")
        if linked_submission is not None and linked_task_instance is not None:
            if linked_submission.account_id and linked_task_instance.account_id:
                if linked_submission.account_id != linked_task_instance.account_id:
                    raise ValueError("Ticket linked submission account scope does not match the linked task instance.")
        return payload.account_id or resolved_account_id

    @staticmethod
    def _normalize_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _validate_ticket_payload(self, payload: TicketCreateRequest) -> None:
        if payload.ticket_type not in SUPPORTED_TICKET_TYPES:
            raise ValueError(f"Unsupported ticket_type '{payload.ticket_type}'.")
        if self._normalize_text(payload.title) is None:
            raise ValueError("Ticket title cannot be empty.")
        if self._normalize_text(payload.body_text) is None and not payload.attachments_json:
            raise ValueError("Ticket body_text or attachments_json is required.")

    def _validate_message_payload(self, payload: TicketMessageCreateRequest) -> None:
        if payload.sender_type not in SUPPORTED_SENDER_TYPES:
            raise ValueError(f"Unsupported sender_type '{payload.sender_type}'.")
        if self._normalize_text(payload.body_text) is None and not payload.attachments_json:
            raise ValueError("Ticket messages require body_text or attachments_json.")

    @staticmethod
    def _ensure_submission_matches_task(task_instance: TaskInstance, submission: TaskSubmission) -> None:
        if submission.task_instance_id != task_instance.id:
            raise ValueError("Ticket linked_submission_id does not match linked_task_instance_id.")

    @staticmethod
    def _resolve_latest_review_decision(submission: TaskSubmission | None) -> TaskReviewDecision | None:
        if submission is None:
            return None
        decisions = sorted(
            submission.review_decisions,
            key=lambda item: (item.created_at, item.id),
            reverse=True,
        )
        return decisions[0] if decisions else None

    @classmethod
    def _resolve_review_decision_id(cls, submission: TaskSubmission | None) -> str | None:
        latest = cls._resolve_latest_review_decision(submission)
        return latest.id if latest is not None else None

    def _ensure_status_supported(self, status: str) -> None:
        if status not in SUPPORTED_TICKET_STATUSES:
            raise ValueError(f"Unsupported ticket status '{status}'.")

    @staticmethod
    def _normalize_status(status: str) -> str:
        if status == TicketStatus.WAITING_USER.value:
            return TicketStatus.PENDING_USER.value
        return status

    def _ensure_transition_allowed(self, *, current_status: str, target_status: str) -> None:
        if current_status == target_status:
            return
        allowed_targets = TICKET_STATUS_TRANSITIONS.get(current_status)
        if allowed_targets is None or target_status not in allowed_targets:
            raise ValueError(f"Ticket status cannot transition from '{current_status}' to '{target_status}'.")

    def _sync_linked_appeal_state(self, *, ticket: Ticket, target_status: str) -> None:
        task_instance = ticket.task_instance
        if ticket.ticket_type != TicketType.APPEAL.value or task_instance is None:
            return
        if target_status in ACTIVE_TICKET_STATUSES:
            task_instance.status = TaskInstanceStatus.APPEALING.value
        elif task_instance.status == TaskInstanceStatus.APPEALING.value:
            task_instance.status = TaskInstanceStatus.REJECTED.value
        self._session.add(task_instance)

    def _serialize_ticket(self, ticket: Ticket, *, include_internal_messages: bool) -> TicketResponse:
        site = ticket.site
        messages = ticket.messages if include_internal_messages else [item for item in ticket.messages if not item.is_internal]
        return TicketResponse(
            id=ticket.id,
            account_id=ticket.account_id,
            ticket_no=ticket.ticket_no,
            ticket_type=ticket.ticket_type,
            status=self._normalize_status(ticket.status),
            priority=ticket.priority,
            site_id=ticket.site_id,
            site_key=site.site_key if site is not None else None,
            user_id=ticket.user_id,
            public_user_id=ticket.user.public_user_id,
            linked_task_instance_id=ticket.linked_task_instance_id,
            linked_submission_id=ticket.linked_submission_id,
            review_decision_id=ticket.review_decision_id,
            title=ticket.title,
            latest_reply_at=ticket.latest_reply_at,
            resolved_at=ticket.resolved_at,
            closed_at=ticket.closed_at,
            is_active=ticket.is_active,
            messages=[self._serialize_message(message, account_id=ticket.account_id) for message in messages],
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
        )

    @staticmethod
    def _serialize_message(message: TicketMessage, *, account_id: str | None) -> TicketMessageResponse:
        return TicketMessageResponse(
            id=message.id,
            account_id=account_id,
            ticket_id=message.ticket_id,
            sender_type=message.sender_type,
            sender_id=message.sender_id,
            body_text=message.body_text,
            attachments_json=message.attachments_json or [],
            is_internal=message.is_internal,
            created_at=message.created_at,
        )
