from sqlalchemy.orm import Session

from app.db.models import MemberWhatsAppBindingRequest, utc_now
from app.schemas.h5_member_whatsapp_binding import H5MemberWhatsAppBindingResponse
from app.services.h5_member_auth_service import H5MemberContext


class H5MemberWhatsAppBindingService:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    async def get_binding(self, *, context: H5MemberContext) -> H5MemberWhatsAppBindingResponse:
        binding_request = self._get_binding_request(context=context)
        if binding_request is not None and context.user.has_whatsapp and binding_request.status != "bound":
            binding_request.status = "bound"
            binding_request.bound_at = binding_request.bound_at or utc_now()
            binding_request.last_error = None
            self._session.add(binding_request)
            self._session.commit()
            self._session.refresh(binding_request)
        return self._build_response(context=context, binding_request=binding_request)

    async def start_binding(self, *, context: H5MemberContext) -> H5MemberWhatsAppBindingResponse:
        now = utc_now()
        binding_request = self._get_binding_request(context=context)

        if context.user.has_whatsapp:
            if binding_request is not None and binding_request.status != "bound":
                binding_request.status = "bound"
                binding_request.bound_at = binding_request.bound_at or now
                binding_request.last_error = None
                self._session.add(binding_request)
                self._session.commit()
                self._session.refresh(binding_request)
            return self._build_response(context=context, binding_request=binding_request)

        if binding_request is None:
            binding_request = MemberWhatsAppBindingRequest(
                account_id=context.account_id,
                user_id=context.user.id,
                member_profile_id=context.member_profile.id,
                site_id=context.site.id,
                status="pending",
                requested_phone_number=context.phone,
                start_count=1,
                last_started_at=now,
                metadata_json={
                    "source": "h5_member_portal",
                    "placeholder": "awaiting_meta_configuration",
                },
            )
        else:
            binding_request.status = "pending"
            binding_request.site_id = context.site.id
            binding_request.requested_phone_number = context.phone
            binding_request.start_count = int(binding_request.start_count or 0) + 1
            binding_request.last_started_at = now
            binding_request.last_error = None

        self._session.add(binding_request)
        self._session.commit()
        self._session.refresh(binding_request)
        return self._build_response(context=context, binding_request=binding_request)

    def _build_response(
        self,
        *,
        context: H5MemberContext,
        binding_request: MemberWhatsAppBindingRequest | None,
    ) -> H5MemberWhatsAppBindingResponse:
        is_bound = bool(context.user.has_whatsapp)
        binding_status = "bound" if is_bound else "not_started"
        request_id = None
        requested_at = None
        start_count = 0
        resolved_last_updated_at = None

        if binding_request is not None:
            request_id = binding_request.id
            requested_at = binding_request.last_started_at or binding_request.created_at
            start_count = int(binding_request.start_count or 0)
            resolved_last_updated_at = (
                binding_request.last_started_at
                or binding_request.bound_at
                or binding_request.updated_at
            )
            if not is_bound:
                binding_status = binding_request.status

        if is_bound:
            resolved_last_updated_at = (
                binding_request.bound_at
                if binding_request is not None and binding_request.bound_at is not None
                else (
                    context.user.last_active_at
                    or context.auth_session.last_seen_at
                    or context.auth_session.created_at
                )
            )
        return H5MemberWhatsAppBindingResponse(
            is_bound=is_bound,
            binding_status=binding_status,
            request_id=request_id,
            phone_number=context.phone if is_bound else None,
            requested_at=requested_at,
            start_count=start_count,
            last_updated_at=resolved_last_updated_at,
        )

    def _get_binding_request(
        self,
        *,
        context: H5MemberContext,
    ) -> MemberWhatsAppBindingRequest | None:
        return self._session.query(MemberWhatsAppBindingRequest).filter(
            MemberWhatsAppBindingRequest.account_id == context.account_id,
            MemberWhatsAppBindingRequest.member_profile_id == context.member_profile.id,
        ).one_or_none()
