from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    AppUser,
    H5Site,
    MemberNotification,
    MemberProfile,
    MemberWhatsAppBindingRequest,
    UserIdentity,
    utc_now,
)
from app.schemas.platform_member_whatsapp_bindings import (
    PlatformMemberWhatsAppBindingResponse,
    PlatformMemberWhatsAppBindingStatus,
)

TERMINAL_MEMBER_WHATSAPP_BINDING_STATUSES = {"bound"}
MEMBER_WHATSAPP_BINDING_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"bound", "failed"},
    "failed": {"pending", "bound"},
    "bound": set(),
}


class PlatformMemberWhatsAppBindingService:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    async def list_requests(
        self,
        *,
        account_id: str | None = None,
        allowed_account_ids: set[str] | None = None,
        status: PlatformMemberWhatsAppBindingStatus | None = None,
    ) -> list[PlatformMemberWhatsAppBindingResponse]:
        query = (
            select(MemberWhatsAppBindingRequest)
            .options(joinedload(MemberWhatsAppBindingRequest.member_profile).joinedload(MemberProfile.user))
            .options(joinedload(MemberWhatsAppBindingRequest.user))
            .options(joinedload(MemberWhatsAppBindingRequest.site))
            .order_by(
                MemberWhatsAppBindingRequest.last_started_at.desc(),
                MemberWhatsAppBindingRequest.created_at.desc(),
                MemberWhatsAppBindingRequest.id.desc(),
            )
        )
        if account_id is not None:
            query = query.where(MemberWhatsAppBindingRequest.account_id == account_id)
        if allowed_account_ids is not None:
            query = query.where(MemberWhatsAppBindingRequest.account_id.in_(sorted(allowed_account_ids)))
        if status is not None:
            query = query.where(MemberWhatsAppBindingRequest.status == status)
        requests = self._session.scalars(query).all()
        return [self._serialize_request(item) for item in requests]

    async def get_request(
        self,
        *,
        request_id: str,
    ) -> PlatformMemberWhatsAppBindingResponse:
        request = self._require_request(request_id=request_id)
        return self._serialize_request(request)

    async def update_status(
        self,
        *,
        request_id: str,
        status: PlatformMemberWhatsAppBindingStatus,
        note: str | None,
    ) -> PlatformMemberWhatsAppBindingResponse:
        request = self._require_request(request_id=request_id, for_update=True)
        normalized_note = (note or "").strip() or None

        if request.status == status:
            return self._serialize_request(request)
        if status not in MEMBER_WHATSAPP_BINDING_TRANSITIONS.get(request.status, set()):
            raise ValueError(
                f"Member WhatsApp binding request cannot transition from '{request.status}' to '{status}'."
            )
        if status == "failed" and normalized_note is None:
            raise ValueError("A failure note is required when failing a member WhatsApp binding request.")

        request.status = status
        request.last_error = normalized_note if status == "failed" else None
        if status == "bound":
            request.bound_at = request.bound_at or utc_now()
            self._mark_user_bound(request=request)
        else:
            request.bound_at = None
            if status == "pending":
                self._mark_user_unbound(request=request)

        self._create_member_notification(request=request, status=status, note=normalized_note)
        self._session.add(request)
        self._session.commit()
        reloaded = self._require_request(request_id=request_id)
        return self._serialize_request(reloaded)

    def _mark_user_bound(
        self,
        *,
        request: MemberWhatsAppBindingRequest,
    ) -> None:
        user = self._require_user(user_id=request.user_id)
        user.has_whatsapp = True
        self._session.add(user)

        phone_number = (request.requested_phone_number or "").strip()
        if not phone_number:
            return

        existing_whatsapp_identity = self._session.scalars(
            select(UserIdentity).where(
                UserIdentity.identity_type == "whatsapp",
                UserIdentity.identity_value == phone_number,
            )
        ).first()
        if existing_whatsapp_identity is not None:
            if existing_whatsapp_identity.user_id != request.user_id:
                raise ValueError(
                    f"WhatsApp identity '{phone_number}' is already linked to another member."
                )
            existing_whatsapp_identity.is_verified = True
            existing_whatsapp_identity.is_primary = True
            self._session.add(existing_whatsapp_identity)
            return

        self._session.add(
            UserIdentity(
                user_id=request.user_id,
                identity_type="whatsapp",
                identity_value=phone_number,
                is_verified=True,
                is_primary=True,
                metadata_json={
                    "source": "platform_member_whatsapp_binding",
                    "binding_request_id": request.id,
                },
            )
        )

    def _mark_user_unbound(
        self,
        *,
        request: MemberWhatsAppBindingRequest,
    ) -> None:
        user = self._require_user(user_id=request.user_id)
        user.has_whatsapp = False
        self._session.add(user)

    def _create_member_notification(
        self,
        *,
        request: MemberWhatsAppBindingRequest,
        status: str,
        note: str | None,
    ) -> None:
        title, default_body = self._build_notification_copy(status=status)
        body_text = note if note else default_body
        self._session.add(
            MemberNotification(
                account_id=request.account_id,
                user_id=request.user_id,
                member_profile_id=request.member_profile_id,
                site_id=request.site_id,
                category="system",
                title=title,
                body_text=body_text,
                is_read=False,
                reference_type="member_whatsapp_binding_request",
                reference_id=request.id,
                metadata_json={
                    "binding_status": status,
                    "requested_phone_number": request.requested_phone_number,
                    "start_count": int(request.start_count or 0),
                },
            )
        )

    def _require_request(
        self,
        *,
        request_id: str,
        for_update: bool = False,
    ) -> MemberWhatsAppBindingRequest:
        query = (
            select(MemberWhatsAppBindingRequest)
            .options(joinedload(MemberWhatsAppBindingRequest.member_profile).joinedload(MemberProfile.user))
            .options(joinedload(MemberWhatsAppBindingRequest.user))
            .options(joinedload(MemberWhatsAppBindingRequest.site))
            .where(MemberWhatsAppBindingRequest.id == request_id)
        )
        if for_update:
            query = query.with_for_update().execution_options(populate_existing=True)
        request = self._session.scalars(query).first()
        if request is None:
            raise LookupError(f"Member WhatsApp binding request '{request_id}' was not found.")
        return request

    def _require_user(
        self,
        *,
        user_id: str,
    ) -> AppUser:
        user = self._session.get(AppUser, user_id)
        if user is None:
            raise LookupError(f"User '{user_id}' was not found.")
        return user

    @staticmethod
    def _build_notification_copy(*, status: str) -> tuple[str, str]:
        if status == "bound":
            return (
                "WhatsApp binding completed",
                "Your WhatsApp binding request was completed successfully.",
            )
        if status == "failed":
            return (
                "WhatsApp binding failed",
                "Your WhatsApp binding request could not be completed.",
            )
        return (
            "WhatsApp binding restarted",
            "Your WhatsApp binding request was reopened for another attempt.",
        )

    @staticmethod
    def _serialize_request(
        request: MemberWhatsAppBindingRequest,
    ) -> PlatformMemberWhatsAppBindingResponse:
        user = request.user
        site = request.site
        member_profile = request.member_profile
        return PlatformMemberWhatsAppBindingResponse(
            id=request.id,
            account_id=request.account_id,
            user_id=request.user_id,
            member_profile_id=request.member_profile_id,
            site_id=request.site_id,
            site_key=site.site_key if site is not None else None,
            public_user_id=user.public_user_id,
            member_no=member_profile.member_no,
            display_name=user.display_name,
            status=request.status,
            requested_phone_number=request.requested_phone_number,
            start_count=int(request.start_count or 0),
            last_error=request.last_error,
            created_at=request.created_at,
            updated_at=request.updated_at,
            last_started_at=request.last_started_at,
            bound_at=request.bound_at,
        )
