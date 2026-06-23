from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db.models import AppUser, MemberNotification, MemberProfile, MemberVerificationRequest, utc_now
from app.schemas.platform_member_verifications import (
    PlatformMemberVerificationDocumentResponse,
    PlatformMemberVerificationResponse,
    PlatformMemberVerificationStatus,
)

TERMINAL_MEMBER_VERIFICATION_STATUSES = {"approved", "rejected"}


class PlatformMemberVerificationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def list_requests(
        self,
        *,
        account_id: str | None = None,
        allowed_account_ids: set[str] | None = None,
        status: PlatformMemberVerificationStatus | None = None,
    ) -> list[PlatformMemberVerificationResponse]:
        query = (
            select(MemberVerificationRequest)
            .options(selectinload(MemberVerificationRequest.documents))
            .options(joinedload(MemberVerificationRequest.member_profile).joinedload(MemberProfile.user))
            .order_by(MemberVerificationRequest.created_at.desc(), MemberVerificationRequest.id.desc())
        )
        if account_id is not None:
            query = query.where(MemberVerificationRequest.account_id == account_id)
        if allowed_account_ids is not None:
            query = query.where(MemberVerificationRequest.account_id.in_(sorted(allowed_account_ids)))
        if status is not None:
            query = query.where(MemberVerificationRequest.status == status)

        requests = self._session.scalars(query).all()
        return [self._serialize_request(item) for item in requests]

    async def get_request(self, *, request_id: str) -> PlatformMemberVerificationResponse:
        request = self._require_request(request_id=request_id)
        return self._serialize_request(request)

    async def update_status(
        self,
        *,
        request_id: str,
        status: PlatformMemberVerificationStatus,
        note: str | None,
        reviewer_actor_id: str,
    ) -> PlatformMemberVerificationResponse:
        request = self._require_request(request_id=request_id, for_update=True)
        normalized_note = (note or "").strip() or None
        self._validate_transition(current_status=request.status, next_status=status, note=normalized_note)

        request.status = status
        request.review_note = normalized_note
        request.reviewer_actor_id = reviewer_actor_id
        request.reviewed_at = utc_now() if status in TERMINAL_MEMBER_VERIFICATION_STATUSES else None
        self._session.add(request)
        self._session.flush()

        self._session.add(
            MemberNotification(
                account_id=request.account_id,
                user_id=request.member_profile.user_id,
                member_profile_id=request.member_profile_id,
                site_id=request.member_profile.user.registration_site_id,
                category="system",
                title=self._build_notification_title(status),
                body_text=self._build_notification_body(status=status, note=normalized_note),
            )
        )
        self._session.commit()

        reloaded = self._require_request(request_id=request_id)
        return self._serialize_request(reloaded)

    def _validate_transition(
        self,
        *,
        current_status: str,
        next_status: str,
        note: str | None,
    ) -> None:
        if current_status == next_status:
            raise ValueError(f"Member verification request is already '{next_status}'.")
        if current_status in TERMINAL_MEMBER_VERIFICATION_STATUSES:
            raise ValueError(f"Member verification request cannot transition from '{current_status}' to '{next_status}'.")
        allowed_transitions: dict[str, set[str]] = {
            "pending": {"under_review", "approved", "rejected"},
            "under_review": {"approved", "rejected"},
        }
        if next_status not in allowed_transitions.get(current_status, set()):
            raise ValueError(f"Member verification request cannot transition from '{current_status}' to '{next_status}'.")
        if next_status == "rejected" and note is None:
            raise ValueError("A review note is required when rejecting a member verification request.")

    def _require_request(
        self,
        *,
        request_id: str,
        for_update: bool = False,
    ) -> MemberVerificationRequest:
        query = (
            select(MemberVerificationRequest)
            .options(selectinload(MemberVerificationRequest.documents))
            .options(joinedload(MemberVerificationRequest.member_profile).joinedload(MemberProfile.user))
            .where(MemberVerificationRequest.id == request_id)
        )
        if for_update:
            query = query.with_for_update()
        request = self._session.scalars(query).first()
        if request is None:
            raise LookupError(f"Member verification request '{request_id}' was not found.")
        return request

    @staticmethod
    def _build_notification_title(status: str) -> str:
        if status == "under_review":
            return "会员认证审核中"
        if status == "approved":
            return "会员认证已通过"
        return "会员认证已驳回"

    @classmethod
    def _build_notification_body(cls, *, status: str, note: str | None) -> str:
        if status == "under_review":
            base = "您的会员认证资料已进入人工审核。"
        elif status == "approved":
            base = "您的会员认证资料已审核通过。"
        else:
            base = "您的会员认证资料已被驳回。"
        if note:
            return f"{base} {note}"
        return base

    @staticmethod
    def _serialize_request(request: MemberVerificationRequest) -> PlatformMemberVerificationResponse:
        user: AppUser = request.member_profile.user
        documents = sorted(request.documents, key=lambda item: (item.created_at, item.id))
        return PlatformMemberVerificationResponse(
            id=request.id,
            account_id=request.account_id,
            member_profile_id=request.member_profile_id,
            user_id=user.id,
            public_user_id=user.public_user_id,
            member_no=request.member_profile.member_no,
            display_name=user.display_name,
            request_type=request.request_type,
            status=request.status,
            notes=request.notes,
            review_note=request.review_note,
            reviewer_actor_id=request.reviewer_actor_id,
            created_at=request.created_at,
            updated_at=request.updated_at,
            reviewed_at=request.reviewed_at,
            documents=[
                PlatformMemberVerificationDocumentResponse(
                    id=document.id,
                    file_name=document.file_name,
                    mime_type=document.mime_type,
                    storage_key=document.storage_key,
                    metadata_json=document.metadata_json,
                    created_at=document.created_at,
                )
                for document in documents
            ],
        )
