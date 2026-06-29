from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.services.site_whatsapp_phone_pool_service import SiteWhatsAppPhonePoolService
from app.services.whatsapp_auth_session_service import (
    WhatsAppAuthSessionError,
    WhatsAppAuthSessionService,
)
from app.services.whatsapp_auto_bind_invite_service import WhatsAppAutoBindInviteService
from app.services.whatsapp_identity_service import WhatsAppIdentityService


@dataclass(slots=True)
class WhatsAppInboundRouteResult:
    action: str
    handled: bool
    should_enter_ai: bool
    reply_text: str | None = None
    invite_link: str | None = None
    site_id: str | None = None
    account_id: str | None = None
    user_id: str | None = None
    reply_phone_number_id: str | None = None
    reply_waba_id: str | None = None
    conversation_scope_key: str | None = None
    message_routing_metadata: dict[str, str] | None = None


class WhatsAppInboundCommandRouter:
    def __init__(self, *, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._pool_service = SiteWhatsAppPhonePoolService(session=session)
        self._auth_service = WhatsAppAuthSessionService(session=session, settings=settings)
        self._invite_service = WhatsAppAutoBindInviteService(session=session, settings=settings)
        self._identity_service = WhatsAppIdentityService(session=session)

    def try_handle_inbound(
        self,
        *,
        text: str,
        wa_id: str,
        inbound_phone_number_id: str,
        inbound_waba_id: str,
        inbound_message_id: str | None,
    ) -> WhatsAppInboundRouteResult:
        stripped = (text or "").strip()
        if stripped.upper().startswith(("LOGIN ", "BIND ")):
            self._auth_service.consume_auth_command(
                command_text=stripped,
                wa_id=wa_id,
                inbound_phone_number_id=inbound_phone_number_id,
                inbound_waba_id=inbound_waba_id,
                inbound_message_id=inbound_message_id,
            )
            return WhatsAppInboundRouteResult(
                action="auth_command",
                handled=True,
                should_enter_ai=False,
            )

        pool = self._pool_service.get_pool_by_phone_number_id(
            phone_number_id=inbound_phone_number_id,
            active_only=True,
        )
        if pool is None:
            return WhatsAppInboundRouteResult(
                action="unknown_phone_number",
                handled=True,
                should_enter_ai=False,
            )

        identity = self._identity_service.get_by_wa_id(wa_id=wa_id)
        if identity is None:
            invite = self._invite_service.create_invite(
                account_id=pool.account_id,
                site_id=pool.site_id,
                wa_id=wa_id,
                inbound_phone_number_id=inbound_phone_number_id,
                inbound_waba_id=inbound_waba_id,
                inbound_message_id=inbound_message_id,
            )
            return WhatsAppInboundRouteResult(
                action="binding_prompt",
                handled=True,
                should_enter_ai=False,
                reply_text=f"{self._settings.whatsapp_unbound_message_reply_text} {invite.invite_link}",
                invite_link=invite.invite_link,
                site_id=pool.site_id,
                account_id=pool.account_id,
            )

        if identity.site_id != pool.site_id:
            return WhatsAppInboundRouteResult(
                action="reject_cross_site",
                handled=True,
                should_enter_ai=False,
                reply_text="This WhatsApp account is already bound to another site.",
                site_id=pool.site_id,
                account_id=pool.account_id,
                user_id=identity.user_id,
            )

        return WhatsAppInboundRouteResult(
            action="bound_message",
            handled=False,
            should_enter_ai=True,
            site_id=identity.site_id,
            account_id=identity.account_id,
            user_id=identity.user_id,
            reply_phone_number_id=inbound_phone_number_id,
            reply_waba_id=inbound_waba_id,
            conversation_scope_key=f"{identity.account_id}:{identity.user_id}:whatsapp",
            message_routing_metadata={
                "site_id": identity.site_id,
                "user_id": identity.user_id,
                "wa_id": wa_id,
                "inbound_phone_number_id": inbound_phone_number_id,
                "inbound_waba_id": inbound_waba_id,
                "reply_phone_number_id": inbound_phone_number_id,
                "reply_waba_id": inbound_waba_id,
            },
        )
