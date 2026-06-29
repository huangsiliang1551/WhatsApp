from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.db.models import H5Site, WhatsAppAuthSession, utc_now
from app.services.site_whatsapp_phone_pool_service import SiteWhatsAppPhonePoolService
from app.services.whatsapp_identity_service import (
    WhatsAppBindingConflictError,
    WhatsAppIdentityService,
)
from app.services.whatsapp_phone_selection_service import (
    WhatsAppPhoneSelectionError,
    WhatsAppPhoneSelectionService,
)


class WhatsAppAuthSessionError(Exception):
    def __init__(self, *, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class WhatsAppAuthSessionService:
    def __init__(self, *, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._pool_service = SiteWhatsAppPhonePoolService(session=session)
        self._selection_service = WhatsAppPhoneSelectionService(session=session)
        self._identity_service = WhatsAppIdentityService(session=session)

    def start_bind_session(self, *, site_id: str, user_id: str) -> WhatsAppAuthSession:
        return self._start_session(
            session_type="bind",
            site_id=site_id,
            user_id=user_id,
        )

    def start_login_session(self, *, site_key: str, browser_session_id: str | None = None) -> WhatsAppAuthSession:
        site = self._pool_service.get_site_by_key(site_key=site_key)
        if site is None:
            raise WhatsAppAuthSessionError(
                code="site_not_found",
                message=f"Site '{site_key}' was not found.",
                status_code=404,
            )
        return self._start_session(
            session_type="login",
            site_id=site.id,
            user_id=None,
            browser_session_id=browser_session_id,
        )

    def get_session(self, *, session_id: str) -> WhatsAppAuthSession:
        auth_session = self._session.get(WhatsAppAuthSession, session_id)
        if auth_session is None:
            raise WhatsAppAuthSessionError(
                code="session_not_found",
                message="WhatsApp auth session was not found.",
                status_code=404,
            )
        return auth_session

    def consume_auth_command(
        self,
        *,
        command_text: str,
        wa_id: str,
        inbound_phone_number_id: str,
        inbound_waba_id: str,
        inbound_message_id: str | None,
    ) -> WhatsAppAuthSession:
        prefix, token = self._parse_command(command_text)
        auth_session = self._session.scalars(
            select(WhatsAppAuthSession).where(
                WhatsAppAuthSession.token_hash == self._hash_token(token),
            )
        ).first()
        if auth_session is None:
            raise WhatsAppAuthSessionError(code="session_not_found", message="Auth token is invalid.", status_code=404)
        if auth_session.command_prefix != prefix:
            raise WhatsAppAuthSessionError(code="command_prefix_mismatch", message="Auth command prefix does not match.")
        if auth_session.status != "pending":
            return auth_session
        if auth_session.expires_at <= utc_now():
            auth_session.status = "failed"
            auth_session.failure_code = "session_expired"
            auth_session.failure_reason = "WhatsApp auth session expired."
            self._session.add(auth_session)
            self._session.flush()
            raise WhatsAppAuthSessionError(code="session_expired", message="WhatsApp auth session expired.", status_code=410)
        if auth_session.selected_phone_number_id != inbound_phone_number_id:
            raise WhatsAppAuthSessionError(
                code="wrong_phone_number",
                message="Auth command was sent to the wrong phone number.",
                status_code=409,
            )
        if auth_session.selected_waba_id != inbound_waba_id:
            raise WhatsAppAuthSessionError(
                code="wrong_waba",
                message="Auth command WABA scope does not match.",
                status_code=409,
            )

        if auth_session.session_type == "bind":
            if auth_session.user_id is None:
                raise WhatsAppAuthSessionError(code="missing_user_scope", message="Bind session has no user scope.")
            self._identity_service.bind_identity(
                account_id=auth_session.account_id,
                site_id=auth_session.site_id,
                user_id=auth_session.user_id,
                wa_id=wa_id,
                assigned_waba_id=auth_session.selected_waba_id,
                assigned_phone_number_id=auth_session.selected_phone_number_id,
                assigned_display_phone_number=auth_session.selected_display_phone_number,
            )
        else:
            identity = self._identity_service.get_by_wa_id(wa_id=wa_id)
            if identity is None:
                raise WhatsAppAuthSessionError(
                    code="login_requires_existing_binding",
                    message="Login requires an existing WhatsApp binding in the current implementation.",
                    status_code=409,
                )
            if identity.site_id != auth_session.site_id:
                raise WhatsAppBindingConflictError(
                    code="wa_id_already_bound",
                    message="This WhatsApp account is already bound to another site.",
                )
            auth_session.user_id = identity.user_id
            auth_session.identity_id = identity.id

        auth_session.status = "confirmed"
        auth_session.wa_id = wa_id
        auth_session.inbound_message_id = inbound_message_id
        auth_session.confirmed_at = utc_now()
        auth_session.consumed_at = auth_session.confirmed_at
        self._session.add(auth_session)
        self._session.flush()
        return auth_session

    def _start_session(
        self,
        *,
        session_type: str,
        site_id: str,
        user_id: str | None,
        browser_session_id: str | None = None,
    ) -> WhatsAppAuthSession:
        site = self._pool_service.get_site_by_id(site_id=site_id)
        if site is None:
            raise WhatsAppAuthSessionError(code="site_not_found", message=f"Site '{site_id}' was not found.", status_code=404)

        existing = self._find_pending_session(
            site_id=site_id,
            user_id=user_id,
            session_type=session_type,
            browser_session_id=browser_session_id,
        )
        if existing is not None:
            return existing

        try:
            selected = self._selection_service.select_phone(
                account_id=site.account_id,
                site_id=site.id,
                user_id=user_id,
                wa_id=None,
                prefer_existing_assignment=session_type == "bind",
            )
        except WhatsAppPhoneSelectionError as exc:
            raise WhatsAppAuthSessionError(code=exc.code, message=exc.message, status_code=409) from exc

        prefix = "BIND" if session_type == "bind" else "LOGIN"
        token = secrets.token_urlsafe(10)
        command_text = f"{prefix} {token}"
        auth_session = WhatsAppAuthSession(
            account_id=site.account_id,
            site_id=site.id,
            user_id=user_id,
            session_type=session_type,
            token_hash=self._hash_token(token),
            token_last4=token[-4:],
            command_prefix=prefix,
            selected_waba_id=selected.waba_id,
            selected_phone_number_id=selected.phone_number_id,
            selected_display_phone_number=selected.display_phone_number,
            wa_link=f"https://wa.me/{selected.display_phone_number}?text={quote(command_text)}",
            command_text=command_text,
            status="pending",
            browser_session_id=browser_session_id,
            expires_at=utc_now() + timedelta(minutes=self._settings.whatsapp_auth_session_ttl_minutes),
        )
        self._session.add(auth_session)
        self._session.flush()
        return auth_session

    def _find_pending_session(
        self,
        *,
        site_id: str,
        user_id: str | None,
        session_type: str,
        browser_session_id: str | None,
    ) -> WhatsAppAuthSession | None:
        stmt = select(WhatsAppAuthSession).where(
            WhatsAppAuthSession.site_id == site_id,
            WhatsAppAuthSession.session_type == session_type,
            WhatsAppAuthSession.status == "pending",
            WhatsAppAuthSession.expires_at > utc_now(),
        )
        if user_id is not None:
            stmt = stmt.where(WhatsAppAuthSession.user_id == user_id)
        elif browser_session_id:
            stmt = stmt.where(WhatsAppAuthSession.browser_session_id == browser_session_id)
        else:
            return None
        return self._session.scalars(
            stmt.order_by(WhatsAppAuthSession.created_at.desc())
        ).first()

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_command(command_text: str) -> tuple[str, str]:
        normalized = " ".join((command_text or "").strip().split())
        prefix, _, token = normalized.partition(" ")
        if not prefix or not token:
            raise WhatsAppAuthSessionError(code="invalid_command", message="WhatsApp auth command is invalid.")
        return prefix.upper(), token
