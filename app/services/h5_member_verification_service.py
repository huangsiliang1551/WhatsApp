from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import MemberVerificationDocument, MemberVerificationRequest
from app.schemas.h5_member_verification import (
    H5MemberVerificationCreateRequest,
    H5MemberVerificationDocumentResponse,
    H5MemberVerificationRequestResponse,
    H5MemberVerificationSummaryResponse,
)
from app.services.h5_member_auth_service import H5MemberContext

ACTIVE_MEMBER_VERIFICATION_STATUSES = {"pending", "under_review"}


class H5MemberVerificationService:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    async def get_summary(
        self,
        *,
        context: H5MemberContext,
    ) -> H5MemberVerificationSummaryResponse:
        requests = self._list_request_rows(context=context)
        active_request = next(
            (item for item in requests if item.status in ACTIVE_MEMBER_VERIFICATION_STATUSES),
            None,
        )
        current_status = requests[0].status if requests else "not_submitted"
        history = [self._serialize_request(item) for item in requests]
        return H5MemberVerificationSummaryResponse(
            current_status=current_status,
            has_active_request=active_request is not None,
            active_request=self._serialize_request(active_request) if active_request is not None else None,
            history=history,
        )

    async def list_requests(
        self,
        *,
        context: H5MemberContext,
    ) -> list[H5MemberVerificationRequestResponse]:
        return [self._serialize_request(item) for item in self._list_request_rows(context=context)]

    async def get_request(
        self,
        *,
        context: H5MemberContext,
        request_id: str,
    ) -> H5MemberVerificationRequestResponse:
        request = self._require_request(context=context, request_id=request_id)
        return self._serialize_request(request)

    async def create_request(
        self,
        *,
        context: H5MemberContext,
        payload: H5MemberVerificationCreateRequest,
    ) -> H5MemberVerificationRequestResponse:
        existing_active = next(
            (
                item
                for item in self._list_request_rows(context=context)
                if item.status in ACTIVE_MEMBER_VERIFICATION_STATUSES
            ),
            None,
        )
        if existing_active is not None:
            raise ValueError("An active verification request already exists.")

        request = MemberVerificationRequest(
            account_id=context.account_id,
            member_profile_id=context.member_profile.id,
            request_type=payload.request_type,
            status="pending",
            notes=payload.notes,
        )
        self._session.add(request)
        self._session.flush()

        for document in payload.documents:
            self._session.add(
                MemberVerificationDocument(
                    account_id=context.account_id,
                    verification_request_id=request.id,
                    file_name=document.file_name,
                    mime_type=document.mime_type,
                    storage_key=document.storage_key,
                    metadata_json=document.metadata_json,
                )
            )

        self._session.commit()
        reloaded = self._require_request(context=context, request_id=request.id)
        return self._serialize_request(reloaded)

    def _list_request_rows(
        self,
        *,
        context: H5MemberContext,
    ) -> list[MemberVerificationRequest]:
        return self._session.scalars(
            select(MemberVerificationRequest)
            .options(selectinload(MemberVerificationRequest.documents))
            .where(
                MemberVerificationRequest.account_id == context.account_id,
                MemberVerificationRequest.member_profile_id == context.member_profile.id,
            )
            .order_by(MemberVerificationRequest.created_at.desc(), MemberVerificationRequest.id.desc())
        ).all()

    def _require_request(
        self,
        *,
        context: H5MemberContext,
        request_id: str,
    ) -> MemberVerificationRequest:
        request = self._session.scalars(
            select(MemberVerificationRequest)
            .options(selectinload(MemberVerificationRequest.documents))
            .where(
                MemberVerificationRequest.id == request_id,
                MemberVerificationRequest.account_id == context.account_id,
                MemberVerificationRequest.member_profile_id == context.member_profile.id,
            )
        ).first()
        if request is None:
            raise LookupError(f"Verification request '{request_id}' was not found.")
        return request

    @staticmethod
    def _serialize_request(
        request: MemberVerificationRequest,
    ) -> H5MemberVerificationRequestResponse:
        documents = sorted(request.documents, key=lambda item: (item.created_at, item.id))
        return H5MemberVerificationRequestResponse(
            id=request.id,
            request_type=request.request_type,
            status=request.status,
            notes=request.notes,
            review_note=request.review_note,
            reviewer_actor_id=request.reviewer_actor_id,
            reviewed_at=request.reviewed_at,
            created_at=request.created_at,
            updated_at=request.updated_at,
            documents=[
                H5MemberVerificationDocumentResponse(
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
