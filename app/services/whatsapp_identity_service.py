from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AppUser, UserWhatsAppServiceAssignment, WhatsAppIdentity, utc_now


class WhatsAppBindingConflictError(Exception):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class WhatsAppIdentityService:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    def get_by_wa_id(self, *, wa_id: str) -> WhatsAppIdentity | None:
        return self._session.scalars(
            select(WhatsAppIdentity).where(WhatsAppIdentity.wa_id == wa_id)
        ).first()

    def bind_identity(
        self,
        *,
        account_id: str,
        site_id: str,
        user_id: str,
        wa_id: str,
        assigned_waba_id: str,
        assigned_phone_number_id: str,
        assigned_display_phone_number: str,
        member_profile_id: str | None = None,
    ) -> WhatsAppIdentity:
        now = utc_now()
        existing_wa = self.get_by_wa_id(wa_id=wa_id)
        if existing_wa is not None and existing_wa.user_id != user_id:
            raise WhatsAppBindingConflictError(
                code="wa_id_already_bound",
                message="This WhatsApp account is already bound to another user.",
            )

        identity = self._session.scalars(
            select(WhatsAppIdentity).where(WhatsAppIdentity.user_id == user_id)
        ).first()
        if identity is not None and identity.wa_id != wa_id:
            raise WhatsAppBindingConflictError(
                code="user_already_bound",
                message="This user is already bound to another WhatsApp account.",
            )
        if identity is None:
            identity = WhatsAppIdentity(
                wa_id=wa_id,
                account_id=account_id,
                site_id=site_id,
                user_id=user_id,
                member_profile_id=member_profile_id,
                binding_status="bound",
                first_bound_phone_number_id=assigned_phone_number_id,
                current_assigned_phone_number_id=assigned_phone_number_id,
                bound_at=now,
                first_seen_at=now,
                last_seen_at=now,
            )
        else:
            identity.site_id = site_id
            identity.account_id = account_id
            identity.member_profile_id = member_profile_id
            identity.binding_status = "bound"
            identity.current_assigned_phone_number_id = assigned_phone_number_id
            identity.bound_at = identity.bound_at or now
            identity.last_seen_at = now
        self._session.add(identity)
        self._session.flush()

        assignment = self._session.scalars(
            select(UserWhatsAppServiceAssignment).where(
                UserWhatsAppServiceAssignment.user_id == user_id,
                UserWhatsAppServiceAssignment.status == "active",
            )
        ).first()
        if assignment is None:
            assignment = UserWhatsAppServiceAssignment(
                account_id=account_id,
                site_id=site_id,
                user_id=user_id,
                wa_id=wa_id,
                assigned_waba_id=assigned_waba_id,
                assigned_phone_number_id=assigned_phone_number_id,
                assigned_display_phone_number=assigned_display_phone_number,
                assignment_source="bind",
                status="active",
            )
        else:
            assignment.site_id = site_id
            assignment.wa_id = wa_id
            assignment.assigned_waba_id = assigned_waba_id
            assignment.assigned_phone_number_id = assigned_phone_number_id
            assignment.assigned_display_phone_number = assigned_display_phone_number
        self._session.add(assignment)

        user = self._session.get(AppUser, user_id)
        if user is not None:
            user.has_whatsapp = True
            self._session.add(user)
        self._session.flush()
        return identity
