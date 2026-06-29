from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.db.models import AppUser, WhatsAppAutoBindInvite, utc_now
from app.services.site_whatsapp_phone_pool_service import SiteWhatsAppPhonePoolService
from app.services.whatsapp_identity_service import (
    WhatsAppBindingConflictError,
    WhatsAppIdentityService,
)


class WhatsAppAutoBindError(Exception):
    def __init__(self, *, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class WhatsAppAutoBindInviteService:
    def __init__(self, *, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._pool_service = SiteWhatsAppPhonePoolService(session=session)
        self._identity_service = WhatsAppIdentityService(session=session)

    def create_invite(
        self,
        *,
        account_id: str,
        site_id: str,
        wa_id: str,
        inbound_phone_number_id: str,
        inbound_waba_id: str,
        inbound_message_id: str | None,
    ) -> WhatsAppAutoBindInvite:
        existing = self._session.scalars(
            select(WhatsAppAutoBindInvite).where(
                WhatsAppAutoBindInvite.site_id == site_id,
                WhatsAppAutoBindInvite.wa_id == wa_id,
                WhatsAppAutoBindInvite.inbound_phone_number_id == inbound_phone_number_id,
                WhatsAppAutoBindInvite.status == "pending",
                WhatsAppAutoBindInvite.expires_at > utc_now(),
            )
        ).first()
        if existing is not None:
            return existing

        site = self._pool_service.get_site_by_id(site_id=site_id)
        if site is None:
            raise LookupError(f"Site '{site_id}' was not found.")
        token = secrets.token_urlsafe(18)
        invite = WhatsAppAutoBindInvite(
            account_id=account_id,
            site_id=site_id,
            wa_id=wa_id,
            inbound_phone_number_id=inbound_phone_number_id,
            inbound_waba_id=inbound_waba_id,
            inbound_message_id=inbound_message_id,
            token_hash=self._hash_token(token),
            token_last4=token[-4:],
            invite_link=f"https://{site.domain}/whatsapp/auto-bind?token={quote(token)}",
            expires_at=utc_now() + timedelta(minutes=self._settings.whatsapp_auto_bind_invite_ttl_minutes),
            status="pending",
        )
        self._session.add(invite)
        self._session.flush()
        invite.metadata_json = {"plain_token": token}
        return invite

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def consume_invite(
        self,
        *,
        token: str,
        current_user_id: str,
        current_site_id: str,
    ) -> WhatsAppAutoBindInvite:
        invite = self._session.scalars(
            select(WhatsAppAutoBindInvite).where(
                WhatsAppAutoBindInvite.token_hash == self._hash_token(token)
            )
        ).first()
        if invite is None:
            raise WhatsAppAutoBindError(
                code="invite_not_found",
                message="WhatsApp auto-bind invite was not found.",
                status_code=404,
            )
        if invite.status != "pending":
            raise WhatsAppAutoBindError(
                code="invite_not_pending",
                message="WhatsApp auto-bind invite is no longer pending.",
                status_code=409,
            )
        if invite.expires_at <= utc_now():
            raise WhatsAppAutoBindError(
                code="invite_expired",
                message="WhatsApp auto-bind invite has expired.",
                status_code=410,
            )
        if invite.site_id != current_site_id:
            raise WhatsAppAutoBindError(
                code="site_scope_mismatch",
                message="Auto-bind invite does not belong to the current site.",
                status_code=409,
            )

        pool = self._pool_service.get_pool_by_phone_number_id(
            phone_number_id=invite.inbound_phone_number_id,
            active_only=True,
        )
        if pool is None:
            raise WhatsAppAutoBindError(
                code="phone_scope_inactive",
                message="Invite phone number is no longer active.",
                status_code=409,
            )
        user = self._session.get(AppUser, current_user_id)
        if user is None:
            raise WhatsAppAutoBindError(
                code="user_not_found",
                message="Current H5 member was not found.",
                status_code=404,
            )
        self._identity_service.bind_identity(
            account_id=invite.account_id,
            site_id=invite.site_id,
            user_id=current_user_id,
            wa_id=invite.wa_id,
            assigned_waba_id=invite.inbound_waba_id,
            assigned_phone_number_id=invite.inbound_phone_number_id,
            assigned_display_phone_number=pool.display_phone_number,
        )
        invite.status = "consumed"
        invite.consumed_at = utc_now()
        invite.user_id = current_user_id
        self._session.add(invite)
        self._session.flush()
        return invite
