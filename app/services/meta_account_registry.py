from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from uuid import uuid4

import structlog
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.settings import Settings
from app.db.models import (
    Account,
    EmbeddedSignupSession as EmbeddedSignupSessionModel,
    MetaBusinessPortfolio,
    WebhookSubscription,
    WhatsAppBusinessAccount,
    WhatsAppPhoneNumber,
    utc_now,
)
from app.providers.meta_management.base import (
    MetaEmbeddedSignupCompletionCommand,
    MetaManagementProvider,
    MetaPhoneNumberRecord,
    MetaPhoneNumberSyncCommand,
    MetaWebhookSubscriptionCommand,
)
from app.schemas.meta_accounts import (
    CompleteEmbeddedSignupSessionRequest,
    EmbeddedSignupCallbackRequest,
    EmbeddedSignupCurrentWabaState,
    EmbeddedSignupLaunchContext,
    EmbeddedSignupSessionSnapshot,
    EmbeddedSignupWebhookSubscriptionRequest,
    EmbeddedSignupSession,
    EmbeddedSignupSessionRequest,
    FailEmbeddedSignupSessionRequest,
    ManualMetaAccountRequest,
    MetaAccountUpdateRequest,
    MetaPhoneNumber,
    MetaPhoneNumberSyncResponse,
    MetaPhoneNumberScopeView,
    MetaWabaAccount,
    WebhookSubscriptionRequest,
    WebhookSubscriptionView,
)
from app.services.runtime_state import RuntimeStateStore

WHATSAPP_WEBHOOK_ROOT_PATH = "/webhooks/whatsapp"


@dataclass(slots=True)
class WebhookAuthContext:
    account_id: str
    waba_id: str
    verify_token: str | None
    app_secret: str | None


logger = structlog.get_logger()


@dataclass(slots=True)
class WebhookVerifyTokenConflict:
    verify_token_hint: str
    scopes: list[tuple[str, str]]
    hidden_scope_count: int = 0


class MetaAccountConflictError(ValueError):
    pass


class MetaAccountRegistry:
    def __init__(
        self,
        session: Session,
        runtime_state: RuntimeStateStore,
        settings: Settings,
        meta_management_provider: MetaManagementProvider,
    ) -> None:
        self._session = session
        self._runtime_state = runtime_state
        self._settings = settings
        self._meta_management_provider = meta_management_provider

    async def list_accounts(
        self,
        *,
        account_id: str | None = None,
        waba_id: str | None = None,
        allowed_account_ids: set[str] | None = None,
        is_active: bool | None = None,
        account_is_active: bool | None = None,
        ready_for_webhook_delivery: bool | None = None,
        ready_for_outbound_messages: bool | None = None,
        ready_for_meta_activation: bool | None = None,
        webhook_verification_status: str | None = None,
        webhook_runtime_status: str | None = None,
    ) -> list[MetaWabaAccount]:
        self._validate_account_waba_scope(
            account_id=account_id,
            waba_id=waba_id,
            allowed_account_ids=allowed_account_ids,
        )
        query = (
            select(WhatsAppBusinessAccount)
            .options(
                selectinload(WhatsAppBusinessAccount.account),
                selectinload(WhatsAppBusinessAccount.portfolio),
                selectinload(WhatsAppBusinessAccount.phone_numbers),
                selectinload(WhatsAppBusinessAccount.webhook_subscriptions),
            )
            .order_by(WhatsAppBusinessAccount.created_at, WhatsAppBusinessAccount.waba_id)
        )
        if account_id is not None:
            query = query.where(WhatsAppBusinessAccount.account_id == account_id)
        elif allowed_account_ids is not None:
            query = query.where(WhatsAppBusinessAccount.account_id.in_(allowed_account_ids))
        if waba_id is not None:
            query = query.where(WhatsAppBusinessAccount.waba_id == waba_id)
        waba_accounts = self._session.scalars(query).all()
        serialized_accounts = [self._serialize_waba_account(item) for item in waba_accounts]
        filtered_accounts = serialized_accounts
        if is_active is not None:
            filtered_accounts = [
                item
                for item in filtered_accounts
                if (item.account_is_active and item.is_active) == is_active
            ]
        if account_is_active is not None:
            filtered_accounts = [
                item for item in filtered_accounts if item.account_is_active == account_is_active
            ]
        if ready_for_webhook_delivery is not None:
            filtered_accounts = [
                item
                for item in filtered_accounts
                if item.ready_for_webhook_delivery == ready_for_webhook_delivery
            ]
        if ready_for_outbound_messages is not None:
            filtered_accounts = [
                item
                for item in filtered_accounts
                if item.ready_for_outbound_messages == ready_for_outbound_messages
            ]
        if ready_for_meta_activation is not None:
            filtered_accounts = [
                item
                for item in filtered_accounts
                if item.ready_for_meta_activation == ready_for_meta_activation
            ]
        if webhook_verification_status is not None:
            filtered_accounts = [
                item
                for item in filtered_accounts
                if item.webhook_verification_status == webhook_verification_status
            ]
        if webhook_runtime_status is not None:
            filtered_accounts = [
                item
                for item in filtered_accounts
                if item.webhook_runtime_status == webhook_runtime_status
            ]
        return filtered_accounts

    async def create_manual_account(
        self,
        payload: ManualMetaAccountRequest,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> MetaWabaAccount:
        account_id = payload.account_id or f"acc-{uuid4().hex[:8]}"
        account = await self._runtime_state.ensure_account(
            account_id=account_id,
            display_name=payload.display_name,
            provider_type="whatsapp",
            actor_type=actor_type,
            actor_id=actor_id,
            notes=payload.notes,
        )
        portfolio = self._get_or_create_portfolio(
            account_id=account.account_id,
            meta_business_portfolio_id=payload.meta_business_portfolio_id,
            display_name=payload.display_name,
        )
        waba_account = self._get_waba_by_waba_id(payload.waba_id)
        # 优先使用请求里显式传入的 verify_token；否则使用全局 token；最后允许空。
        request_verify_token = self._normalize_verify_token(payload.verify_token)
        global_verify_token = self._normalize_verify_token(
            self._settings.meta_global_webhook_verify_token or None
        )
        effective_verify_token = request_verify_token or global_verify_token
        effective_app_secret = payload.app_secret
        if effective_verify_token:
            self._ensure_verify_token_available(
                verify_token=effective_verify_token,
                current_account_id=account.account_id,
                current_waba_id=payload.waba_id,
                allow_reuse=True,
            )
        if waba_account is None:
            waba_account = WhatsAppBusinessAccount(
                account_id=account.account_id,
                portfolio_id=portfolio.id if portfolio else None,
                waba_id=payload.waba_id,
                onboarding_mode="manual",
                token_source=payload.token_source,
                access_token=payload.access_token,
                verify_token=effective_verify_token,
                app_secret=effective_app_secret,
                webhook_subscribed=False,
                is_active=True,
                ai_enabled=True,
            )
            self._session.add(waba_account)
            self._session.flush()
        else:
            self._ensure_waba_belongs_to_account(waba_account, account.account_id)
            self._ensure_current_root_webhook_receive_signature_routing(
                account_id=account.account_id,
                waba_id=payload.waba_id,
                app_secret=effective_app_secret,
            )
            waba_account.portfolio_id = portfolio.id if portfolio else waba_account.portfolio_id
            waba_account.onboarding_mode = "manual"
            waba_account.token_source = payload.token_source
            waba_account.access_token = payload.access_token
            waba_account.verify_token = effective_verify_token
            waba_account.app_secret = effective_app_secret

        self._sync_phone_numbers(waba_account=waba_account, phone_numbers=payload.phone_numbers)
        self._runtime_state.add_audit_log(
            account_id=account.account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="meta_manual_account_upserted",
            target_type="waba_account",
            target_id=payload.waba_id,
            payload={
                "meta_business_portfolio_id": payload.meta_business_portfolio_id,
                "token_source": payload.token_source,
                "phone_number_count": len(payload.phone_numbers),
            },
        )
        self._session.commit()
        self._session.refresh(waba_account)
        return self._serialize_waba_account(waba_account)

    async def update_account(
        self,
        account_id: str,
        waba_id: str,
        payload: MetaAccountUpdateRequest,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> MetaWabaAccount:
        await self._runtime_state.ensure_account(
            account_id=account_id,
            display_name=payload.display_name,
            provider_type="whatsapp",
            actor_type=actor_type,
            actor_id=actor_id,
            notes=payload.notes,
        )
        waba_account = self._require_waba_for_account(account_id=account_id, waba_id=waba_id)
        previous_phone_number_ids = sorted(
            item.phone_number_id for item in waba_account.phone_numbers if item.is_active
        )
        portfolio = self._get_or_create_portfolio(
            account_id=account_id,
            meta_business_portfolio_id=payload.meta_business_portfolio_id,
            display_name=payload.display_name,
        )
        waba_account.portfolio_id = portfolio.id if portfolio else waba_account.portfolio_id
        waba_account.token_source = payload.token_source or waba_account.token_source
        if payload.access_token is not None:
            waba_account.access_token = payload.access_token
        if payload.verify_token is not None:
            normalized_verify_token = self._normalize_verify_token(payload.verify_token)
            self._ensure_verify_token_available(
                verify_token=normalized_verify_token,
                current_account_id=account_id,
                current_waba_id=waba_id,
            )
            waba_account.verify_token = normalized_verify_token
        if payload.app_secret is not None:
            self._ensure_current_root_webhook_receive_signature_routing(
                account_id=account_id,
                waba_id=waba_id,
                app_secret=payload.app_secret,
            )
            waba_account.app_secret = payload.app_secret

        self._replace_phone_numbers(
            waba_account=waba_account,
            phone_numbers=payload.phone_numbers,
        )
        current_phone_number_ids = self._get_active_phone_number_ids(waba_account.id)
        self._runtime_state.add_audit_log(
            account_id=account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="meta_account_updated",
            target_type="waba_account",
            target_id=waba_id,
            payload={
                "display_name": payload.display_name,
                "meta_business_portfolio_id": payload.meta_business_portfolio_id,
                "token_source": waba_account.token_source,
                "phone_number_count": len(current_phone_number_ids),
                "phone_number_ids": current_phone_number_ids,
                "previous_phone_number_ids": previous_phone_number_ids,
                "access_token_updated": payload.access_token is not None,
                "verify_token_updated": payload.verify_token is not None,
                "app_secret_updated": payload.app_secret is not None,
            },
        )
        self._session.commit()
        self._session.refresh(waba_account)
        return self._serialize_waba_account(waba_account)

    async def create_embedded_signup_session(
        self,
        payload: EmbeddedSignupSessionRequest,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> EmbeddedSignupSession:
        account = await self._runtime_state.ensure_account(
            account_id=payload.account_id,
            display_name=payload.display_name,
            provider_type="whatsapp",
            actor_type=actor_type,
            actor_id=actor_id,
        )
        session_id = str(uuid4())
        launch_state = str(uuid4())
        callback_url = f"/webhooks/meta/embedded-signup/session/{session_id}"
        expires_at = (utc_now() + timedelta(minutes=30)).isoformat()
        launch_context = EmbeddedSignupLaunchContext(
            session_id=session_id,
            state=launch_state,
            callback_url=callback_url,
            redirect_uri=payload.redirect_uri,
            expires_at=expires_at,
            parameters={
                "state": launch_state,
                "redirect_uri": payload.redirect_uri,
                "callback_url": callback_url,
            },
        )
        session = EmbeddedSignupSessionModel(
            session_id=session_id,
            account_id=account.account_id,
            redirect_uri=payload.redirect_uri,
            provider_name=self._meta_management_provider.provider_name,
            status="created",
            completion_stage="pending_callback",
            last_event_source="operator",
            linked_phone_number_ids_json=[],
            completion_payload=self._build_embedded_signup_session_request_snapshot(
                webhook_subscription=payload.webhook_subscription,
                launch_context=launch_context,
            ),
        )
        self._session.add(session)
        self._runtime_state.add_audit_log(
            account_id=account.account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="embedded_signup_session_created",
            target_type="embedded_signup_session",
            target_id=session.session_id,
            payload={
                "redirect_uri": payload.redirect_uri,
                "provider_name": self._meta_management_provider.provider_name,
                "webhook_subscription_requested": payload.webhook_subscription is not None,
                "webhook_callback_url": (
                    payload.webhook_subscription.callback_url
                    if payload.webhook_subscription is not None
                    else None
                ),
                "launch_state_present": True,
                "launch_callback_url": callback_url,
                "launch_expires_at": expires_at,
            },
        )
        self._session.commit()
        self._session.refresh(session)
        session.account = account
        return self._serialize_embedded_signup_session(session)

    async def list_embedded_signup_sessions(
        self,
        account_id: str | None = None,
        status: str | None = None,
        completion_stage: str | None = None,
        remote_confirmed: bool | None = None,
        waba_id: str | None = None,
        allowed_account_ids: set[str] | None = None,
        webhook_subscription_status: str | None = None,
        webhook_verification_status: str | None = None,
        webhook_runtime_status: str | None = None,
        ready_for_webhook_delivery: bool | None = None,
        ready_for_outbound_messages: bool | None = None,
        ready_for_meta_activation: bool | None = None,
    ) -> list[EmbeddedSignupSession]:
        self._validate_account_waba_scope(
            account_id=account_id,
            waba_id=waba_id,
            allowed_account_ids=allowed_account_ids,
        )
        query = (
            select(EmbeddedSignupSessionModel)
            .options(
                selectinload(EmbeddedSignupSessionModel.account),
                selectinload(EmbeddedSignupSessionModel.waba_account).selectinload(
                    WhatsAppBusinessAccount.account
                ),
                selectinload(EmbeddedSignupSessionModel.created_webhook_subscription),
            )
            .order_by(EmbeddedSignupSessionModel.created_at.desc(), EmbeddedSignupSessionModel.session_id.desc())
        )
        if account_id is not None:
            query = query.where(EmbeddedSignupSessionModel.account_id == account_id)
        elif allowed_account_ids is not None:
            query = query.where(EmbeddedSignupSessionModel.account_id.in_(allowed_account_ids))

        sessions = self._session.scalars(query).all()
        serialized_sessions = [self._serialize_embedded_signup_session(item) for item in sessions]
        if status is not None:
            serialized_sessions = [item for item in serialized_sessions if item.status == status]
        if completion_stage is not None:
            serialized_sessions = [
                item for item in serialized_sessions if item.completion_stage == completion_stage
            ]
        if remote_confirmed is not None:
            serialized_sessions = [
                item for item in serialized_sessions if item.remote_confirmed == remote_confirmed
            ]
        if waba_id is not None:
            serialized_sessions = [item for item in serialized_sessions if item.waba_id == waba_id]
        if webhook_subscription_status is not None:
            serialized_sessions = [
                item
                for item in serialized_sessions
                if item.webhook_subscription_status == webhook_subscription_status
            ]
        if webhook_verification_status is not None:
            serialized_sessions = [
                item
                for item in serialized_sessions
                if item.webhook_verification_status == webhook_verification_status
            ]
        if webhook_runtime_status is not None:
            serialized_sessions = [
                item
                for item in serialized_sessions
                if item.webhook_runtime_status == webhook_runtime_status
            ]
        if ready_for_webhook_delivery is not None:
            serialized_sessions = [
                item
                for item in serialized_sessions
                if item.ready_for_webhook_delivery == ready_for_webhook_delivery
            ]
        if ready_for_outbound_messages is not None:
            serialized_sessions = [
                item
                for item in serialized_sessions
                if item.ready_for_outbound_messages == ready_for_outbound_messages
            ]
        if ready_for_meta_activation is not None:
            serialized_sessions = [
                item
                for item in serialized_sessions
                if item.ready_for_meta_activation == ready_for_meta_activation
            ]
        return serialized_sessions

    async def get_embedded_signup_session(
        self,
        session_id: str,
        allowed_account_ids: set[str] | None = None,
    ) -> EmbeddedSignupSession:
        """Get a single embedded signup session by session_id."""
        session_model = self._session.scalar(
            select(EmbeddedSignupSessionModel)
            .where(EmbeddedSignupSessionModel.session_id == session_id)
            .options(
                selectinload(EmbeddedSignupSessionModel.account),
                selectinload(EmbeddedSignupSessionModel.waba_account).selectinload(
                    WhatsAppBusinessAccount.account
                ),
                selectinload(EmbeddedSignupSessionModel.created_webhook_subscription),
            )
        )
        if session_model is None:
            raise LookupError(f"Embedded signup session '{session_id}' was not found.")
        serialized = self._serialize_embedded_signup_session(session_model)
        if allowed_account_ids is not None and serialized.account_id not in allowed_account_ids:
            raise PermissionError(f"Access denied to session '{session_id}'.")
        return serialized

    async def complete_embedded_signup_session(
        self,
        session_id: str,
        payload: CompleteEmbeddedSignupSessionRequest,
        allowed_account_ids: set[str] | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> EmbeddedSignupSession:
        session = self._require_embedded_signup_session(session_id)
        self._ensure_account_allowed(session.account_id, allowed_account_ids)
        self._ensure_embedded_signup_status(session, expected_status="created")
        resolved_waba_id = payload.waba_id or self._read_embedded_signup_string(
            payload.raw_payload,
            direct_keys=("waba_id",),
        )
        resolved_portfolio_id = payload.meta_business_portfolio_id or self._read_embedded_signup_string(
            payload.raw_payload,
            direct_keys=("meta_business_portfolio_id", "business_portfolio_id", "business_id"),
        )
        resolved_phone_number_ids = list(payload.phone_number_ids) or self._read_embedded_signup_phone_number_ids(
            payload.raw_payload
        )
        resolved_setup_session_id = payload.setup_session_id or self._read_embedded_signup_string(
            payload.raw_payload,
            direct_keys=("setup_session_id",),
        )
        resolved_authorization_code = payload.authorization_code or self._read_embedded_signup_string(
            payload.raw_payload,
            direct_keys=("authorization_code", "code"),
        )
        resolved_system_user_access_token = payload.system_user_access_token or self._read_embedded_signup_string(
            payload.raw_payload,
            direct_keys=("system_user_access_token", "access_token"),
        )
        webhook_subscription_context = (
            payload.webhook_subscription
            or self._extract_embedded_signup_webhook_subscription(session.completion_payload)
        )

        provider_result = await self._meta_management_provider.complete_embedded_signup_session(
            MetaEmbeddedSignupCompletionCommand(
                account_id=session.account_id,
                session_id=session.session_id,
                redirect_uri=session.redirect_uri,
                app_id=self._settings.meta_app_id,
                app_secret=self._settings.meta_app_secret,
                requested_waba_id=resolved_waba_id,
                meta_business_portfolio_id=resolved_portfolio_id,
                phone_number_ids=resolved_phone_number_ids,
                setup_session_id=resolved_setup_session_id,
                authorization_code=resolved_authorization_code,
                system_user_access_token=resolved_system_user_access_token,
                raw_payload=payload.raw_payload,
            )
        )

        linked_waba_id = provider_result.resolved_waba_id or resolved_waba_id
        portfolio_id = provider_result.resolved_portfolio_id or resolved_portfolio_id
        linked_phone_number_ids = provider_result.phone_number_ids or resolved_phone_number_ids
        access_token = provider_result.access_token or resolved_system_user_access_token
        waba_account = self._upsert_embedded_signup_waba(
            account_id=session.account_id,
            display_name=(
                session.account.display_name
                if session.account is not None
                else session.account_id
            ),
            waba_id=linked_waba_id,
            meta_business_portfolio_id=portfolio_id,
            phone_number_ids=linked_phone_number_ids,
            access_token=access_token,
            verify_token=(
                webhook_subscription_context.verify_token
                if webhook_subscription_context is not None
                else None
            ),
            app_secret=self._resolve_embedded_signup_app_secret(),
        )

        callback_received_at = utc_now()
        session.provider_name = provider_result.provider_name
        session.status = "completed"
        session.last_event_source = payload.event_source
        session.remote_confirmed = provider_result.remote_confirmed
        session.provider_waba_id = linked_waba_id
        session.provider_business_portfolio_id = portfolio_id
        session.setup_session_id = resolved_setup_session_id
        session.linked_phone_number_ids_json = list(linked_phone_number_ids)
        session.authorization_code_present = bool(resolved_authorization_code)
        session.system_user_access_token_present = bool(access_token)
        session.callback_received_at = callback_received_at
        session.completed_at = utc_now()
        session.waba_account_id = waba_account.id if waba_account is not None else None
        webhook_subscription_result: MetaWabaAccount | None = None
        if waba_account is not None and webhook_subscription_context is not None:
            webhook_subscription_result, created_subscription = await self._subscribe_webhook_for_waba_account(
                waba_account=waba_account,
                payload=self._coerce_webhook_subscription_request(webhook_subscription_context),
                actor_type=actor_type,
                actor_id=actor_id,
                audit_action="embedded_signup_webhook_subscription_upserted",
            )
            session.created_webhook_subscription_id = created_subscription.id

        session.completion_stage = self._resolve_embedded_signup_completion_stage(
            provider_completion_status=provider_result.completion_status,
            waba_linked=waba_account is not None,
            webhook_subscription_result=webhook_subscription_result,
        )
        session.completion_message = self._compose_embedded_signup_completion_message(
            provider_message=provider_result.message,
            webhook_subscription_result=webhook_subscription_result,
        )
        session.completion_payload = self._build_embedded_signup_payload_snapshot(
            session_request_payload=session.completion_payload,
            provider_name=provider_result.provider_name,
            provider_payload=provider_result.raw_response,
            request_payload=payload.raw_payload,
            phone_number_ids=linked_phone_number_ids,
            authorization_code_present=bool(resolved_authorization_code),
            system_user_access_token_present=bool(access_token),
            event_source=payload.event_source,
            webhook_subscription=webhook_subscription_context,
            webhook_subscription_result=(
                webhook_subscription_result.model_dump()
                if webhook_subscription_result is not None
                else None
            ),
        )
        session.error_message = None
        self._session.add(session)
        self._runtime_state.add_audit_log(
            account_id=session.account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="embedded_signup_session_completed",
            target_type="embedded_signup_session",
            target_id=session.session_id,
            payload={
                "waba_id": linked_waba_id,
                "meta_business_portfolio_id": portfolio_id,
                "phone_number_ids": linked_phone_number_ids,
                "provider_name": provider_result.provider_name,
                "completion_stage": session.completion_stage,
                "remote_confirmed": provider_result.remote_confirmed,
                "setup_session_id": resolved_setup_session_id,
                "authorization_code_present": bool(resolved_authorization_code),
                "system_user_access_token_present": bool(access_token),
                "event_source": payload.event_source,
                "message": session.completion_message,
                "webhook_subscription_requested": webhook_subscription_context is not None,
                "webhook_subscription_status": (
                    webhook_subscription_result.webhook_subscription_status
                    if webhook_subscription_result is not None
                    else None
                ),
                "webhook_verification_status": (
                    webhook_subscription_result.webhook_verification_status
                    if webhook_subscription_result is not None
                    else None
                ),
            },
        )
        self._session.commit()
        self._session.refresh(session)
        return self._serialize_embedded_signup_session(session)

    async def fail_embedded_signup_session(
        self,
        session_id: str,
        payload: FailEmbeddedSignupSessionRequest,
        allowed_account_ids: set[str] | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> EmbeddedSignupSession:
        session = self._require_embedded_signup_session(session_id)
        self._ensure_account_allowed(session.account_id, allowed_account_ids)
        self._ensure_embedded_signup_status(session, expected_status="created")
        session.status = "failed"
        session.completion_stage = "failed"
        session.last_event_source = payload.event_source
        session.remote_confirmed = False
        session.callback_received_at = utc_now()
        session.completion_payload = {
            "session_request": (
                session.completion_payload.get("session_request")
                if isinstance(session.completion_payload, dict)
                else None
            ),
            "request_payload": payload.raw_payload,
            "event_source": payload.event_source,
            "failed": True,
        }
        session.error_message = payload.error_message
        self._session.add(session)
        self._runtime_state.add_audit_log(
            account_id=session.account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="embedded_signup_session_failed",
            target_type="embedded_signup_session",
            target_id=session.session_id,
            payload={
                "error_message": payload.error_message,
                "event_source": payload.event_source,
                "raw_payload_present": payload.raw_payload is not None,
            },
        )
        self._session.commit()
        self._session.refresh(session)
        return self._serialize_embedded_signup_session(session)

    async def ingest_embedded_signup_callback(
        self,
        session_id: str,
        payload: EmbeddedSignupCallbackRequest,
        allowed_account_ids: set[str] | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
        require_launch_state: bool = False,
    ) -> EmbeddedSignupSession:
        session = self._require_embedded_signup_session(session_id)
        self._ensure_account_allowed(session.account_id, allowed_account_ids)
        self._validate_embedded_signup_launch_state(
            session=session,
            payload=payload,
            require_launch_state=require_launch_state,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        resolved_waba_id = payload.waba_id or self._read_embedded_signup_string(
            payload.raw_payload,
            direct_keys=("waba_id",),
        )
        resolved_portfolio_id = payload.meta_business_portfolio_id or self._read_embedded_signup_string(
            payload.raw_payload,
            direct_keys=("meta_business_portfolio_id", "business_portfolio_id", "business_id"),
        )
        resolved_phone_number_ids = list(payload.phone_number_ids) or self._read_embedded_signup_phone_number_ids(
            payload.raw_payload
        )
        resolved_setup_session_id = payload.setup_session_id or self._read_embedded_signup_string(
            payload.raw_payload,
            direct_keys=("setup_session_id",),
        )
        resolved_authorization_code = payload.authorization_code or self._read_embedded_signup_string(
            payload.raw_payload,
            direct_keys=("authorization_code", "code"),
        )
        resolved_system_user_access_token = payload.system_user_access_token or self._read_embedded_signup_string(
            payload.raw_payload,
            direct_keys=("system_user_access_token", "access_token"),
        )

        if session.status != "created":
            if session.status == payload.status:
                self._runtime_state.add_audit_log(
                    account_id=session.account_id,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    action="embedded_signup_callback_ignored",
                    target_type="embedded_signup_session",
                    target_id=session.session_id,
                    payload={
                        "reason": "duplicate_terminal_callback",
                        "incoming_status": payload.status,
                        "current_status": session.status,
                        "event_source": payload.event_source,
                    },
                )
                self._session.commit()
                return self._serialize_embedded_signup_session(session)
            raise MetaAccountConflictError(
                f"Embedded signup session '{session.session_id}' already finalized as '{session.status}'."
            )

        self._runtime_state.add_audit_log(
            account_id=session.account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="embedded_signup_callback_received",
            target_type="embedded_signup_session",
            target_id=session.session_id,
            payload={
                "status": payload.status,
                "event_source": payload.event_source,
                "waba_id": resolved_waba_id,
                "meta_business_portfolio_id": resolved_portfolio_id,
                "phone_number_count": len(resolved_phone_number_ids),
                "authorization_code_present": bool(resolved_authorization_code),
                "system_user_access_token_present": bool(resolved_system_user_access_token),
                "raw_payload_present": payload.raw_payload is not None,
            },
        )

        if payload.status == "completed":
            return await self.complete_embedded_signup_session(
                session_id=session_id,
                payload=CompleteEmbeddedSignupSessionRequest(
                    waba_id=resolved_waba_id,
                    meta_business_portfolio_id=resolved_portfolio_id,
                    phone_number_ids=resolved_phone_number_ids,
                    setup_session_id=resolved_setup_session_id,
                    authorization_code=resolved_authorization_code,
                    system_user_access_token=resolved_system_user_access_token,
                    raw_payload=payload.raw_payload,
                    event_source=payload.event_source,
                    webhook_subscription=payload.webhook_subscription,
                ),
                allowed_account_ids=allowed_account_ids,
                actor_type=actor_type,
                actor_id=actor_id,
            )

        return await self.fail_embedded_signup_session(
            session_id=session_id,
            payload=FailEmbeddedSignupSessionRequest(
                error_message=payload.error_message or "embedded_signup_callback_failed",
                raw_payload=payload.raw_payload,
                event_source=payload.event_source,
            ),
            allowed_account_ids=allowed_account_ids,
            actor_type=actor_type,
            actor_id=actor_id,
        )

    async def list_phone_numbers(
        self,
        account_id: str | None = None,
        waba_id: str | None = None,
        allowed_account_ids: set[str] | None = None,
        is_registered: bool | None = None,
        is_active: bool | None = None,
        quality_rating: str | None = None,
        ready_for_webhook_delivery: bool | None = None,
        ready_for_outbound_messages: bool | None = None,
        ready_for_meta_activation: bool | None = None,
        ) -> list[MetaPhoneNumberScopeView]:
        self._validate_account_waba_scope(
            account_id=account_id,
            waba_id=waba_id,
            allowed_account_ids=allowed_account_ids,
        )
        query = (
            select(WhatsAppPhoneNumber)
            .options(
                selectinload(WhatsAppPhoneNumber.waba_account).selectinload(
                    WhatsAppBusinessAccount.account
                )
            )
            .order_by(
                WhatsAppPhoneNumber.account_id.asc(),
                WhatsAppPhoneNumber.waba_id.asc(),
                WhatsAppPhoneNumber.is_active.desc(),
                WhatsAppPhoneNumber.display_phone_number.asc(),
            )
        )
        if account_id is not None:
            query = query.where(self._phone_number_matches_account_scope(account_id))
        elif allowed_account_ids is not None:
            query = query.where(WhatsAppPhoneNumber.account_id.in_(allowed_account_ids))
        if waba_id is not None:
            query = query.where(self._phone_number_matches_waba_scope(waba_id))
        if is_registered is not None:
            query = query.where(WhatsAppPhoneNumber.is_registered == is_registered)
        if is_active is not None:
            query = query.where(WhatsAppPhoneNumber.is_active == is_active)
        if quality_rating is not None:
            query = query.where(WhatsAppPhoneNumber.quality_rating == quality_rating)

        phone_numbers = self._session.scalars(query).all()
        serialized_phone_numbers = [self._serialize_phone_number_scope(item) for item in phone_numbers]
        if ready_for_webhook_delivery is not None:
            serialized_phone_numbers = [
                item
                for item in serialized_phone_numbers
                if item.ready_for_webhook_delivery == ready_for_webhook_delivery
            ]
        if ready_for_outbound_messages is not None:
            serialized_phone_numbers = [
                item
                for item in serialized_phone_numbers
                if item.ready_for_outbound_messages == ready_for_outbound_messages
            ]
        if ready_for_meta_activation is not None:
            serialized_phone_numbers = [
                item
                for item in serialized_phone_numbers
                if item.ready_for_meta_activation == ready_for_meta_activation
            ]
        return serialized_phone_numbers

    async def set_account_active(
        self,
        *,
        account_id: str,
        is_active: bool,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> None:
        await self._runtime_state.set_account_active(
            account_id=account_id,
            is_active=is_active,
            actor_type=actor_type,
            actor_id=actor_id,
        )

    async def set_waba_active(
        self,
        *,
        account_id: str,
        waba_id: str,
        is_active: bool,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> MetaWabaAccount:
        waba_account = self._require_waba_for_account(account_id=account_id, waba_id=waba_id)
        waba_account.is_active = is_active
        self._session.add(waba_account)
        self._runtime_state.add_audit_log(
            account_id=account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="meta_waba_status_updated",
            target_type="waba_account",
            target_id=waba_id,
            payload={"is_active": is_active},
        )
        self._session.commit()
        self._session.refresh(waba_account)
        return self._serialize_waba_account(waba_account)

    async def set_phone_number_active(
        self,
        *,
        account_id: str,
        waba_id: str,
        phone_number_id: str,
        is_active: bool,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> MetaPhoneNumberScopeView:
        phone_number = self._require_phone_number_for_scope(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
        )
        phone_number.is_active = is_active
        if not is_active:
            phone_number.is_registered = False
        self._session.add(phone_number)
        self._runtime_state.add_audit_log(
            account_id=account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="meta_phone_number_status_updated",
            target_type="phone_number",
            target_id=phone_number_id,
            payload={"waba_id": waba_id, "is_active": is_active},
        )
        self._session.commit()
        self._session.refresh(phone_number)
        return self._serialize_phone_number_scope(phone_number)

    async def apply_phone_number_webhook_update(
        self,
        *,
        account_id: str,
        waba_id: str,
        phone_number_id: str | None,
        display_phone_number: str | None,
        event_type: str,
        event: str | None,
        quality_rating: str | None,
        previous_quality_rating: str | None,
        messaging_limit_tier: str | None,
        max_daily_conversations_per_business: int | None,
        is_registered: bool | None,
        is_active: bool | None,
        raw_payload: dict[str, object],
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> MetaPhoneNumberScopeView | None:
        phone_number = self._find_phone_number_for_webhook(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            display_phone_number=display_phone_number,
        )
        if phone_number is None:
            return None

        previous_quality = phone_number.quality_rating
        normalized_quality = self._normalize_phone_quality_rating(quality_rating)
        if normalized_quality is not None:
            phone_number.quality_rating = normalized_quality
            phone_number.previous_quality_rating = previous_quality_rating or previous_quality
        elif previous_quality_rating is not None:
            phone_number.previous_quality_rating = previous_quality_rating
        phone_number.quality_event = event
        phone_number.messaging_limit_tier = messaging_limit_tier
        phone_number.max_daily_conversations_per_business = max_daily_conversations_per_business
        phone_number.last_quality_event_at = utc_now()
        phone_number.last_status_payload = raw_payload
        if is_registered is not None:
            phone_number.is_registered = is_registered
        if is_active is not None:
            phone_number.is_active = is_active
            if not is_active:
                phone_number.is_registered = False
        self._session.add(phone_number)
        self._runtime_state.add_audit_log(
            account_id=account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="whatsapp_phone_number_webhook_updated",
            target_type="phone_number",
            target_id=phone_number.phone_number_id,
            payload={
                "waba_id": waba_id,
                "phone_number_id": phone_number.phone_number_id,
                "event_type": event_type,
                "event": event,
                "previous_quality_rating": previous_quality,
                "quality_rating": phone_number.quality_rating,
                "incoming_previous_quality_rating": previous_quality_rating,
                "messaging_limit_tier": messaging_limit_tier,
                "max_daily_conversations_per_business": max_daily_conversations_per_business,
                "is_registered": phone_number.is_registered,
                "is_active": phone_number.is_active,
                "raw_payload": raw_payload,
            },
        )
        self._session.commit()
        self._session.refresh(phone_number)
        return self._serialize_phone_number_scope(phone_number)

    async def subscribe_webhook(
        self,
        account_id: str,
        waba_id: str,
        payload: WebhookSubscriptionRequest,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> MetaWabaAccount:
        waba_account = self._require_waba_for_account(account_id=account_id, waba_id=waba_id)
        subscribed_account, _ = await self._subscribe_webhook_for_waba_account(
            waba_account=waba_account,
            payload=payload,
            actor_type=actor_type,
            actor_id=actor_id,
            audit_action="meta_webhook_subscription_upserted",
        )
        self._session.commit()
        self._session.refresh(waba_account)
        return subscribed_account

    async def _subscribe_webhook_for_waba_account(
        self,
        *,
        waba_account: WhatsAppBusinessAccount,
        payload: WebhookSubscriptionRequest,
        actor_type: str,
        actor_id: str | None,
        audit_action: str,
    ) -> tuple[MetaWabaAccount, WebhookSubscription]:
        latest_subscription = self._get_latest_webhook_subscription_for_scope(
            account_id=waba_account.account_id,
            waba_id=waba_account.waba_id,
        )
        effective_app_secret = self._normalize_app_secret(waba_account.app_secret)
        effective_verify_token = self._normalize_verify_token(
            payload.verify_token
            or waba_account.verify_token
            or (latest_subscription.verify_token if latest_subscription is not None else None)
        )
        self._ensure_verify_token_available(
            verify_token=effective_verify_token,
            current_account_id=waba_account.account_id,
            current_waba_id=waba_account.waba_id,
        )
        self._ensure_root_webhook_receive_signature_routing_available(
            current_account_id=waba_account.account_id,
            current_waba_id=waba_account.waba_id,
            callback_url=payload.callback_url,
            app_secret=effective_app_secret,
        )
        app_id = payload.app_id or (latest_subscription.app_id if latest_subscription is not None else None)
        provider_result = await self._meta_management_provider.subscribe_webhook(
            MetaWebhookSubscriptionCommand(
                account_id=waba_account.account_id,
                waba_id=waba_account.waba_id,
                callback_url=payload.callback_url,
                verify_token=effective_verify_token,
                app_id=app_id,
                access_token=waba_account.access_token,
                app_secret=effective_app_secret,
            )
        )
        subscription = (
            self._session.execute(
                select(WebhookSubscription).where(
                    WebhookSubscription.account_id == waba_account.account_id,
                    WebhookSubscription.waba_id == waba_account.waba_id,
                    WebhookSubscription.callback_url == payload.callback_url,
                )
            )
            .scalars()
            .first()
        )
        if subscription is None:
            subscription = WebhookSubscription(
                account_id=waba_account.account_id,
                waba_account_id=waba_account.id,
                waba_id=waba_account.waba_id,
                callback_url=payload.callback_url,
                verify_token=effective_verify_token,
                app_secret=effective_app_secret,
                app_id=app_id,
                status=provider_result.subscription_status,
                subscribed_at=utc_now(),
            )
        else:
            subscription.account_id = waba_account.account_id
            subscription.waba_account_id = waba_account.id
            subscription.waba_id = waba_account.waba_id
            subscription.verify_token = effective_verify_token
            subscription.app_secret = effective_app_secret
            subscription.app_id = app_id
            subscription.status = provider_result.subscription_status
            subscription.subscribed_at = utc_now()
        self._session.add(subscription)

        if effective_verify_token:
            waba_account.verify_token = effective_verify_token
        waba_account.webhook_subscribed = True
        waba_account.webhook_verification_status = "pending"
        waba_account.webhook_last_verified_at = None
        waba_account.webhook_last_verification_error = None
        waba_account.webhook_runtime_status = "pending"
        waba_account.webhook_last_event_received_at = None
        waba_account.webhook_last_message_received_at = None
        waba_account.webhook_last_status_update_at = None
        waba_account.webhook_last_management_event_at = None
        waba_account.webhook_last_signature_failed_at = None
        waba_account.webhook_signature_failure_count = 0
        waba_account.webhook_runtime_error = None
        self._session.add(waba_account)
        self._runtime_state.add_audit_log(
            account_id=waba_account.account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=audit_action,
            target_type="waba_account",
            target_id=waba_account.waba_id,
            payload={
                "callback_url": payload.callback_url,
                "app_id": app_id,
                "provider_name": provider_result.provider_name,
                "subscription_status": provider_result.subscription_status,
                "remote_confirmed": provider_result.remote_confirmed,
                "message": provider_result.message,
            },
        )
        self._session.flush()
        return self._serialize_waba_account(waba_account), subscription

    async def sync_phone_numbers(
        self,
        account_id: str,
        waba_id: str,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> MetaPhoneNumberSyncResponse:
        waba_account = self._require_waba_for_account(account_id=account_id, waba_id=waba_id)
        existing_phone_numbers = [
            MetaPhoneNumberRecord(
                phone_number_id=item.phone_number_id,
                display_phone_number=item.display_phone_number,
                verified_name=item.verified_name,
                quality_rating=item.quality_rating,
                is_registered=item.is_registered,
                is_active=item.is_active,
            )
            for item in sorted(
                (phone_number for phone_number in waba_account.phone_numbers if phone_number.is_active),
                key=lambda item: item.display_phone_number,
            )
        ]
        provider_result = await self._meta_management_provider.sync_phone_numbers(
            MetaPhoneNumberSyncCommand(
                account_id=account_id,
                waba_id=waba_id,
                access_token=waba_account.access_token,
                existing_phone_numbers=existing_phone_numbers,
            )
        )
        sync_phone_numbers = [
            MetaPhoneNumber(
                phone_number_id=item.phone_number_id,
                display_phone_number=item.display_phone_number,
                verified_name=item.verified_name,
                quality_rating=item.quality_rating,
                is_registered=item.is_registered,
                is_active=item.is_active,
            )
            for item in provider_result.phone_numbers
        ]
        if provider_result.sync_mode == "remote_fetch":
            if not sync_phone_numbers and existing_phone_numbers:
                logger.warning(
                    "meta_phone_number_sync_empty_remote_fetch",
                    account_id=account_id,
                    waba_id=waba_id,
                    existing_active_count=len(existing_phone_numbers),
                    message=(
                        "Meta returned 0 phone numbers but DB has active numbers. "
                        "All existing numbers will be marked inactive. "
                        "Verify the stored access_token has whatsapp_business_management permission."
                    ),
                )
            self._replace_phone_numbers(
                waba_account=waba_account,
                phone_numbers=sync_phone_numbers,
            )
        elif sync_phone_numbers:
            self._sync_phone_numbers(
                waba_account=waba_account,
                phone_numbers=sync_phone_numbers,
            )
        if provider_result.sync_mode == "remote_fetch" or sync_phone_numbers:
            self._session.flush()

        self._runtime_state.add_audit_log(
            account_id=account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="meta_phone_numbers_synced",
            target_type="waba_account",
            target_id=waba_id,
            payload={
                "provider_name": provider_result.provider_name,
                "sync_mode": provider_result.sync_mode,
                "status": provider_result.status,
                "synced_count": len(provider_result.phone_numbers),
                "message": provider_result.message,
            },
        )
        self._session.commit()
        self._session.refresh(waba_account)
        refreshed_phone_numbers = sorted(
            (item for item in waba_account.phone_numbers if item.is_active),
            key=lambda item: item.display_phone_number,
        )
        return MetaPhoneNumberSyncResponse(
            account_id=account_id,
            waba_id=waba_id,
            provider_name=provider_result.provider_name,
            sync_mode=provider_result.sync_mode,
            status=provider_result.status,
            synced_count=len(refreshed_phone_numbers),
            phone_numbers=[
                MetaPhoneNumber(
                    phone_number_id=item.phone_number_id,
                    display_phone_number=item.display_phone_number,
                    verified_name=item.verified_name,
                    quality_rating=item.quality_rating,
                    is_registered=item.is_registered,
                    is_active=item.is_active,
                )
                for item in refreshed_phone_numbers
            ],
            message=provider_result.message,
        )

    async def list_webhook_subscriptions(
        self,
        account_id: str | None = None,
        waba_id: str | None = None,
        allowed_account_ids: set[str] | None = None,
        status: str | None = None,
        webhook_verification_status: str | None = None,
        webhook_runtime_status: str | None = None,
    ) -> list[WebhookSubscriptionView]:
        self._validate_account_waba_scope(
            account_id=account_id,
            waba_id=waba_id,
            allowed_account_ids=allowed_account_ids,
        )
        filter_current_scope_only = (
            webhook_verification_status is not None or webhook_runtime_status is not None
        )
        query = (
            select(WebhookSubscription)
            .options(
                selectinload(WebhookSubscription.waba_account).selectinload(
                    WhatsAppBusinessAccount.account
                )
            )
            .order_by(
                WebhookSubscription.subscribed_at.desc(),
                WebhookSubscription.created_at.desc(),
                WebhookSubscription.id.desc(),
            )
        )
        if account_id is not None:
            query = query.where(self._subscription_matches_account_scope(account_id))
        elif allowed_account_ids is not None:
            query = query.where(WebhookSubscription.account_id.in_(allowed_account_ids))
        if waba_id is not None:
            query = query.where(self._subscription_matches_waba_scope(waba_id))
        if status is not None and not filter_current_scope_only:
            query = query.where(WebhookSubscription.status == status)

        subscriptions = self._session.scalars(query).all()
        if filter_current_scope_only:
            current_subscription_ids = self._get_current_webhook_subscription_ids(subscriptions)
            subscriptions = [
                item for item in subscriptions if item.id in current_subscription_ids
            ]
        current_subscription_ids = self._get_current_webhook_subscription_ids(subscriptions)
        serialized_subscriptions = [
            self._serialize_webhook_subscription(
                item,
                apply_current_scope_state=item.id in current_subscription_ids,
            )
            for item in subscriptions
        ]
        if status is not None:
            serialized_subscriptions = [
                item for item in serialized_subscriptions if item.status == status
            ]
        if webhook_verification_status is not None:
            serialized_subscriptions = [
                item
                for item in serialized_subscriptions
                if item.webhook_verification_status == webhook_verification_status
            ]
        if webhook_runtime_status is not None:
            serialized_subscriptions = [
                item
                for item in serialized_subscriptions
                if item.webhook_runtime_status == webhook_runtime_status
            ]
        return serialized_subscriptions

    def record_webhook_verification_result(
        self,
        *,
        account_id: str,
        waba_id: str,
        status: str,
        error_message: str | None = None,
    ) -> None:
        waba_account = self._require_waba_for_account(account_id=account_id, waba_id=waba_id)
        if waba_account.webhook_verification_status == "verified" and status != "verified":
            self._session.add(waba_account)
            return
        waba_account.webhook_verification_status = status
        if status == "verified":
            waba_account.webhook_last_verified_at = utc_now()
            waba_account.webhook_last_verification_error = None
        else:
            waba_account.webhook_last_verification_error = error_message
        self._session.add(waba_account)

    def record_webhook_runtime_result(
        self,
        *,
        account_id: str,
        waba_id: str,
        status: str,
        error_message: str | None = None,
        message_count: int = 0,
        status_update_count: int = 0,
        management_event_count: int = 0,
        signature_failed: bool = False,
    ) -> None:
        waba_account = self._require_waba_for_account(account_id=account_id, waba_id=waba_id)
        now = utc_now()
        waba_account.webhook_runtime_status = status
        waba_account.webhook_runtime_error = error_message
        if signature_failed:
            waba_account.webhook_last_signature_failed_at = now
            waba_account.webhook_signature_failure_count += 1
        else:
            waba_account.webhook_last_event_received_at = now
            if message_count > 0:
                waba_account.webhook_last_message_received_at = now
            if status_update_count > 0:
                waba_account.webhook_last_status_update_at = now
            if management_event_count > 0:
                waba_account.webhook_last_management_event_at = now
        self._session.add(waba_account)

    async def get_webhook_auth_context(
        self,
        account_id: str,
        waba_id: str,
    ) -> WebhookAuthContext:
        waba_account = self._require_waba_for_account(account_id=account_id, waba_id=waba_id)
        return self._build_webhook_auth_context(waba_account)

    async def resolve_webhook_auth_context(
        self,
        waba_id: str,
    ) -> WebhookAuthContext:
        waba_account = self._get_waba_by_waba_id(waba_id)
        if waba_account is None:
            raise LookupError(f"WABA '{waba_id}' was not found.")
        return self._build_webhook_auth_context(waba_account)

    async def resolve_webhook_auth_context_by_verify_token(
        self,
        verify_token: str,
    ) -> WebhookAuthContext:
        matching_accounts = self._list_waba_accounts_by_verify_token(verify_token)

        if not matching_accounts:
            raise LookupError("No WABA matches the supplied webhook verify token.")
        if len(matching_accounts) > 1:
            raise MetaAccountConflictError(
                "Webhook verify token is shared by multiple WABAs. "
                "Use the scoped verify path or assign unique verify tokens before using the root webhook verify endpoint."
            )
        return self._build_webhook_auth_context(matching_accounts[0])

    async def list_webhook_auth_contexts_by_verify_token(
        self,
        verify_token: str,
    ) -> list[WebhookAuthContext]:
        return [
            self._build_webhook_auth_context(waba_account)
            for waba_account in self._list_waba_accounts_by_verify_token(verify_token)
        ]

    async def list_webhook_verify_token_conflicts(
        self,
        *,
        account_id: str | None = None,
        allowed_account_ids: set[str] | None = None,
    ) -> list[WebhookVerifyTokenConflict]:
        token_to_scopes: dict[str, list[tuple[str, str]]] = {}
        for waba_account in self._session.scalars(
            select(WhatsAppBusinessAccount)
            .options(selectinload(WhatsAppBusinessAccount.webhook_subscriptions))
            .order_by(WhatsAppBusinessAccount.account_id, WhatsAppBusinessAccount.waba_id)
        ).all():
            auth_context = self._build_webhook_auth_context(waba_account)
            if not auth_context.verify_token:
                continue
            token_to_scopes.setdefault(auth_context.verify_token, []).append(
                (waba_account.account_id, waba_account.waba_id)
            )

        conflicts: list[WebhookVerifyTokenConflict] = []
        for token, scopes in token_to_scopes.items():
            if len(scopes) <= 1:
                continue
            visible_scopes = scopes
            if account_id is not None:
                visible_scopes = [scope for scope in scopes if scope[0] == account_id]
            elif allowed_account_ids is not None:
                visible_scopes = [scope for scope in scopes if scope[0] in allowed_account_ids]
            if not visible_scopes:
                continue
            hidden_scope_count = len(scopes) - len(visible_scopes)
            conflicts.append(
                WebhookVerifyTokenConflict(
                    verify_token_hint=self._mask_verify_token(token),
                    scopes=sorted(visible_scopes if (account_id is not None or allowed_account_ids is not None) else scopes),
                    hidden_scope_count=hidden_scope_count,
                )
            )
        return conflicts

    async def delete_account(
        self,
        account_id: str,
        waba_id: str,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> dict[str, object]:
        """Delete a WABA and its associated phone numbers and webhook subscriptions."""
        waba_account = self._require_waba_for_account(account_id=account_id, waba_id=waba_id)
        deleted_waba_id = waba_account.waba_id
        deleted_account_id = waba_account.account_id

        # delete related entities first (cascade may not handle all)
        for sub in list(waba_account.webhook_subscriptions):
            self._session.delete(sub)
        for pn in list(waba_account.phone_numbers):
            self._session.delete(pn)
        self._session.delete(waba_account)

        self._runtime_state.add_audit_log(
            account_id=deleted_account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="meta_account_deleted",
            target_type="waba_account",
            target_id=deleted_waba_id,
            payload=None,
        )
        self._session.commit()
        return {"account_id": deleted_account_id, "waba_id": deleted_waba_id, "deleted": True}

    async def health_check_account(
        self,
        account_id: str,
        waba_id: str,
    ) -> dict[str, object]:
        """Test the account connection by verifying credentials with Meta."""
        waba_account = self._require_waba_for_account(account_id=account_id, waba_id=waba_id)
        if not waba_account.access_token:
            raise ValueError("该账户没有配置 Access Token，无法检测链路状态")
        try:
            result = await self._meta_management_provider.health_check(
                waba_id=waba_id,
                access_token=waba_account.access_token,
            )
            return {
                "account_id": account_id,
                "waba_id": waba_id,
                "status": "healthy" if result.get("ok", False) else "unhealthy",
                "detail": result,
            }
        except Exception as exc:
            return {
                "account_id": account_id,
                "waba_id": waba_id,
                "status": "error",
                "detail": {"error": str(exc)},
            }

    async def send_test_message(
        self,
        account_id: str,
        waba_id: str,
        phone_id: str,
        to: str,
        text: str,
    ) -> dict[str, object]:
        waba_account = self._require_waba_for_account(account_id=account_id, waba_id=waba_id)
        if not waba_account.access_token:
            raise ValueError("该账户没有配置 Access Token，无法发送消息")
        return await self._meta_management_provider.send_test_message(
            waba_id=waba_id,
            access_token=waba_account.access_token,
            phone_id=phone_id,
            to=to,
            text=text,
        )

    async def query_phone_detail(
        self,
        account_id: str,
        waba_id: str,
        phone_id: str,
    ) -> dict[str, object]:
        waba_account = self._require_waba_for_account(account_id=account_id, waba_id=waba_id)
        if not waba_account.access_token:
            raise ValueError("该账户没有配置 Access Token")
        return await self._meta_management_provider.query_phone_detail(
            waba_id=waba_id,
            access_token=waba_account.access_token,
            phone_id=phone_id,
        )

    async def query_business_profile(
        self,
        account_id: str,
        waba_id: str,
        phone_id: str,
    ) -> dict[str, object]:
        waba_account = self._require_waba_for_account(account_id=account_id, waba_id=waba_id)
        if not waba_account.access_token:
            raise ValueError("该账户没有配置 Access Token")
        return await self._meta_management_provider.query_business_profile(
            waba_id=waba_id,
            access_token=waba_account.access_token,
            phone_id=phone_id,
        )

    def _build_webhook_auth_context(
        self,
        waba_account: WhatsAppBusinessAccount,
    ) -> WebhookAuthContext:
        subscription = self._session.scalars(
            select(WebhookSubscription)
            .where(
                WebhookSubscription.account_id == waba_account.account_id,
                WebhookSubscription.waba_id == waba_account.waba_id,
            )
            .order_by(WebhookSubscription.subscribed_at.desc(), WebhookSubscription.created_at.desc())
        ).first()
        effective_verify_token = self._resolve_effective_webhook_verify_token(
            waba_account=waba_account,
            current_scope_subscription=subscription,
        )
        effective_app_secret = self._resolve_effective_webhook_app_secret(
            waba_account=waba_account,
            current_scope_subscription=subscription,
        )

        return WebhookAuthContext(
            account_id=waba_account.account_id,
            waba_id=waba_account.waba_id,
            verify_token=effective_verify_token,
            app_secret=effective_app_secret,
        )

    def _resolve_effective_webhook_verify_token(
        self,
        *,
        waba_account: WhatsAppBusinessAccount,
        current_scope_subscription: WebhookSubscription | None,
    ) -> str | None:
        direct_verify_token = self._normalize_verify_token(waba_account.verify_token)
        if direct_verify_token is None:
            return self._normalize_verify_token(
                current_scope_subscription.verify_token if current_scope_subscription else None
            )
        if current_scope_subscription is not None:
            return direct_verify_token
        historical_subscription_with_same_token = self._session.scalars(
            select(WebhookSubscription)
            .where(
                WebhookSubscription.account_id == waba_account.account_id,
                WebhookSubscription.waba_account_id == waba_account.id,
                WebhookSubscription.verify_token == direct_verify_token,
                WebhookSubscription.waba_id != waba_account.waba_id,
            )
            .order_by(WebhookSubscription.subscribed_at.desc(), WebhookSubscription.created_at.desc())
        ).first()
        if historical_subscription_with_same_token is not None:
            return None
        return direct_verify_token

    def _list_waba_accounts_by_verify_token(
        self,
        verify_token: str,
    ) -> list[WhatsAppBusinessAccount]:
        normalized_verify_token = verify_token.strip()
        if not normalized_verify_token:
            raise ValueError("Webhook verify token is required.")

        matching_accounts: list[WhatsAppBusinessAccount] = []
        for waba_account in self._session.scalars(
            select(WhatsAppBusinessAccount)
            .options(
                selectinload(WhatsAppBusinessAccount.account),
                selectinload(WhatsAppBusinessAccount.portfolio),
                selectinload(WhatsAppBusinessAccount.phone_numbers),
                selectinload(WhatsAppBusinessAccount.webhook_subscriptions),
            )
            .order_by(WhatsAppBusinessAccount.account_id, WhatsAppBusinessAccount.waba_id)
        ).all():
            auth_context = self._build_webhook_auth_context(waba_account)
            if auth_context.verify_token == normalized_verify_token:
                matching_accounts.append(waba_account)
        return matching_accounts

    def _resolve_effective_webhook_app_secret(
        self,
        *,
        waba_account: WhatsAppBusinessAccount,
        current_scope_subscription: WebhookSubscription | None,
    ) -> str | None:
        direct_app_secret = self._normalize_app_secret(waba_account.app_secret)
        if current_scope_subscription is None:
            return direct_app_secret

        subscription_snapshot_app_secret = self._normalize_app_secret(
            current_scope_subscription.app_secret
        )
        if subscription_snapshot_app_secret is not None:
            return subscription_snapshot_app_secret

        subscription_waba_account = self._resolve_waba_account_for_subscription(
            current_scope_subscription
        )
        legacy_subscription_waba_app_secret = self._normalize_app_secret(
            subscription_waba_account.app_secret if subscription_waba_account is not None else None
        )
        if legacy_subscription_waba_app_secret is not None:
            return legacy_subscription_waba_app_secret
        return direct_app_secret

    def _ensure_verify_token_available(
        self,
        *,
        verify_token: str | None,
        current_account_id: str,
        current_waba_id: str,
        allow_reuse: bool = False,
    ) -> None:
        if verify_token is None:
            return
        if allow_reuse:
            return
        for waba_account in self._session.scalars(
            select(WhatsAppBusinessAccount)
            .options(selectinload(WhatsAppBusinessAccount.webhook_subscriptions))
            .order_by(WhatsAppBusinessAccount.account_id, WhatsAppBusinessAccount.waba_id)
        ).all():
            if (
                waba_account.account_id == current_account_id
                and waba_account.waba_id == current_waba_id
            ):
                continue
            auth_context = self._build_webhook_auth_context(waba_account)
            if auth_context.verify_token == verify_token:
                raise MetaAccountConflictError(
                    "Webhook verify token "
                    f"'{self._mask_verify_token(verify_token)}' is already used by "
                    f"WABA '{waba_account.waba_id}' in account '{waba_account.account_id}'."
                )

    def _ensure_current_root_webhook_receive_signature_routing(
        self,
        *,
        account_id: str,
        waba_id: str,
        app_secret: str | None,
        callback_url: str | None = None,
    ) -> None:
        effective_callback_url = callback_url or self._get_latest_webhook_callback_url_for_scope(
            account_id=account_id,
            waba_id=waba_id,
        )
        if effective_callback_url is None:
            return
        self._ensure_root_webhook_receive_signature_routing_available(
            current_account_id=account_id,
            current_waba_id=waba_id,
            callback_url=effective_callback_url,
            app_secret=app_secret,
        )

    def _ensure_root_webhook_receive_signature_routing_available(
        self,
        *,
        current_account_id: str,
        current_waba_id: str,
        callback_url: str,
        app_secret: str | None,
    ) -> None:
        normalized_app_secret = self._normalize_app_secret(app_secret)
        if normalized_app_secret is None:
            return

        callback_target = self._normalize_root_webhook_callback_target(callback_url)
        if callback_target is None:
            return

        for waba_account in self._session.scalars(
            select(WhatsAppBusinessAccount)
            .options(selectinload(WhatsAppBusinessAccount.webhook_subscriptions))
            .order_by(WhatsAppBusinessAccount.account_id, WhatsAppBusinessAccount.waba_id)
        ).all():
            if (
                waba_account.account_id == current_account_id
                and waba_account.waba_id == current_waba_id
            ):
                continue
            other_callback_target = self._get_current_root_webhook_callback_target(waba_account)
            if other_callback_target != callback_target:
                continue
            other_app_secret = self._normalize_app_secret(
                self._build_webhook_auth_context(waba_account).app_secret
            )
            if other_app_secret is None or other_app_secret == normalized_app_secret:
                continue
            raise MetaAccountConflictError(
                "Root webhook callback target "
                f"'{callback_target}' is already bound to a different app secret by "
                f"WABA '{waba_account.waba_id}' in account '{waba_account.account_id}'. "
                "WABAs that share the root webhook receive endpoint must share one app secret, "
                "or move to scoped receive paths before formal launch."
            )

    def _get_current_root_webhook_callback_target(
        self,
        waba_account: WhatsAppBusinessAccount,
    ) -> str | None:
        latest_subscription = self._get_latest_webhook_subscription_for_scope(
            account_id=waba_account.account_id,
            waba_id=waba_account.waba_id,
        )
        if latest_subscription is None:
            return None
        return self._normalize_root_webhook_callback_target(latest_subscription.callback_url)

    def _get_latest_webhook_callback_url_for_scope(
        self,
        *,
        account_id: str,
        waba_id: str,
    ) -> str | None:
        latest_subscription = self._get_latest_webhook_subscription_for_scope(
            account_id=account_id,
            waba_id=waba_id,
        )
        if latest_subscription is None:
            return None
        return latest_subscription.callback_url

    def _has_root_webhook_routing_conflict(
        self,
        *,
        waba_account: WhatsAppBusinessAccount,
        auth_context: WebhookAuthContext,
        callback_url: str | None,
    ) -> bool:
        return (
            self._has_root_webhook_verify_token_conflict(
                waba_account=waba_account,
                verify_token=auth_context.verify_token,
            )
            or self._has_root_webhook_receive_signature_conflict(
                waba_account=waba_account,
                callback_url=callback_url,
                app_secret=auth_context.app_secret,
            )
        )

    def _has_root_webhook_verify_token_conflict(
        self,
        *,
        waba_account: WhatsAppBusinessAccount,
        verify_token: str | None,
    ) -> bool:
        normalized_verify_token = self._normalize_verify_token(verify_token)
        if normalized_verify_token is None:
            return False

        for other_waba_account in self._session.scalars(
            select(WhatsAppBusinessAccount)
            .options(selectinload(WhatsAppBusinessAccount.webhook_subscriptions))
            .order_by(WhatsAppBusinessAccount.account_id, WhatsAppBusinessAccount.waba_id)
        ).all():
            if (
                other_waba_account.account_id == waba_account.account_id
                and other_waba_account.waba_id == waba_account.waba_id
            ):
                continue
            other_auth_context = self._build_webhook_auth_context(other_waba_account)
            if other_auth_context.verify_token == normalized_verify_token:
                return True
        return False

    def _has_root_webhook_receive_signature_conflict(
        self,
        *,
        waba_account: WhatsAppBusinessAccount,
        callback_url: str | None,
        app_secret: str | None,
    ) -> bool:
        callback_target = self._normalize_root_webhook_callback_target(callback_url)
        normalized_app_secret = self._normalize_app_secret(app_secret)
        if callback_target is None or normalized_app_secret is None:
            return False

        for other_waba_account in self._session.scalars(
            select(WhatsAppBusinessAccount)
            .options(selectinload(WhatsAppBusinessAccount.webhook_subscriptions))
            .order_by(WhatsAppBusinessAccount.account_id, WhatsAppBusinessAccount.waba_id)
        ).all():
            if (
                other_waba_account.account_id == waba_account.account_id
                and other_waba_account.waba_id == waba_account.waba_id
            ):
                continue
            other_callback_target = self._get_current_root_webhook_callback_target(
                other_waba_account
            )
            if other_callback_target != callback_target:
                continue
            other_app_secret = self._normalize_app_secret(
                self._build_webhook_auth_context(other_waba_account).app_secret
            )
            if other_app_secret is not None and other_app_secret != normalized_app_secret:
                return True
        return False

    @staticmethod
    def _normalize_root_webhook_callback_target(callback_url: str | None) -> str | None:
        if callback_url is None:
            return None
        normalized_callback_url = callback_url.strip()
        if not normalized_callback_url:
            return None

        parsed_callback = urlsplit(normalized_callback_url)
        callback_path = MetaAccountRegistry._normalize_webhook_path(
            parsed_callback.path or normalized_callback_url
        )
        if callback_path != WHATSAPP_WEBHOOK_ROOT_PATH:
            return None

        if parsed_callback.scheme or parsed_callback.netloc:
            return f"{parsed_callback.scheme}://{parsed_callback.netloc}{callback_path}"
        return callback_path

    @staticmethod
    def _normalize_webhook_path(path: str) -> str:
        normalized_path = path.strip()
        if not normalized_path:
            return "/"
        if not normalized_path.startswith("/"):
            normalized_path = f"/{normalized_path}"
        if len(normalized_path) > 1:
            normalized_path = normalized_path.rstrip("/")
        return normalized_path

    @staticmethod
    def _normalize_app_secret(app_secret: str | None) -> str | None:
        if app_secret is None:
            return None
        normalized_app_secret = app_secret.strip()
        return normalized_app_secret or None

    @staticmethod
    def _normalize_verify_token(verify_token: str | None) -> str | None:
        if verify_token is None:
            return None
        normalized_verify_token = verify_token.strip()
        return normalized_verify_token or None

    def _get_or_create_portfolio(
        self,
        account_id: str,
        meta_business_portfolio_id: str | None,
        display_name: str,
    ) -> MetaBusinessPortfolio | None:
        if not meta_business_portfolio_id:
            return None
        portfolio = self._session.scalars(
            select(MetaBusinessPortfolio).where(
                MetaBusinessPortfolio.meta_business_portfolio_id == meta_business_portfolio_id
            )
        ).first()
        if portfolio is None:
            portfolio = MetaBusinessPortfolio(
                account_id=account_id,
                meta_business_portfolio_id=meta_business_portfolio_id,
                display_name=display_name,
                status="active",
            )
            self._session.add(portfolio)
            self._session.flush()
        else:
            if portfolio.account_id is None:
                portfolio.account_id = account_id
            elif portfolio.account_id != account_id:
                raise MetaAccountConflictError(
                    "Meta business portfolio "
                    f"'{meta_business_portfolio_id}' is already linked to account "
                    f"'{portfolio.account_id}'."
                )
            portfolio.display_name = display_name
            self._session.add(portfolio)
        return portfolio

    def _get_waba_by_waba_id(self, waba_id: str) -> WhatsAppBusinessAccount | None:
        return self._session.scalars(
            select(WhatsAppBusinessAccount)
            .options(
                selectinload(WhatsAppBusinessAccount.account),
                selectinload(WhatsAppBusinessAccount.portfolio),
                selectinload(WhatsAppBusinessAccount.phone_numbers),
                selectinload(WhatsAppBusinessAccount.webhook_subscriptions),
            )
            .where(WhatsAppBusinessAccount.waba_id == waba_id)
        ).first()

    def _require_waba_for_account(self, account_id: str, waba_id: str) -> WhatsAppBusinessAccount:
        waba_account = self._session.scalars(
            select(WhatsAppBusinessAccount)
            .options(
                selectinload(WhatsAppBusinessAccount.account),
                selectinload(WhatsAppBusinessAccount.portfolio),
                selectinload(WhatsAppBusinessAccount.phone_numbers),
                selectinload(WhatsAppBusinessAccount.webhook_subscriptions),
            )
            .where(
                WhatsAppBusinessAccount.account_id == account_id,
                WhatsAppBusinessAccount.waba_id == waba_id,
            )
        ).first()
        if waba_account is None:
            raise LookupError(f"WABA '{waba_id}' for account '{account_id}' was not found.")
        return waba_account

    def _validate_account_waba_scope(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        allowed_account_ids: set[str] | None = None,
    ) -> None:
        if account_id is None or waba_id is None:
            return
        waba_account = self._get_waba_by_waba_id(waba_id)
        if waba_account is None or waba_account.account_id == account_id:
            return
        if allowed_account_ids is not None and waba_account.account_id not in allowed_account_ids:
            raise ValueError(
                f"WABA '{waba_id}' is not available in account '{account_id}'."
            )
        raise ValueError(
            f"WABA '{waba_id}' belongs to account '{waba_account.account_id}', not '{account_id}'."
        )

    def _require_phone_number_for_scope(
        self,
        *,
        account_id: str,
        waba_id: str,
        phone_number_id: str,
    ) -> WhatsAppPhoneNumber:
        phone_number = self._session.scalars(
            select(WhatsAppPhoneNumber)
            .options(
                selectinload(WhatsAppPhoneNumber.waba_account).selectinload(
                    WhatsAppBusinessAccount.account
                )
            )
            .where(
                self._phone_number_matches_account_scope(account_id),
                self._phone_number_matches_waba_scope(waba_id),
                WhatsAppPhoneNumber.phone_number_id == phone_number_id,
            )
        ).first()
        if phone_number is None:
            raise LookupError(
                f"Phone number '{phone_number_id}' for WABA '{waba_id}' and account '{account_id}' was not found."
            )
        return phone_number

    def _find_phone_number_for_webhook(
        self,
        *,
        account_id: str,
        waba_id: str,
        phone_number_id: str | None,
        display_phone_number: str | None,
    ) -> WhatsAppPhoneNumber | None:
        query = (
            select(WhatsAppPhoneNumber)
            .options(
                selectinload(WhatsAppPhoneNumber.waba_account).selectinload(
                    WhatsAppBusinessAccount.account
                )
            )
            .where(
                self._phone_number_matches_account_scope(account_id),
                self._phone_number_matches_waba_scope(waba_id),
            )
        )
        if phone_number_id:
            return self._session.scalars(
                query.where(WhatsAppPhoneNumber.phone_number_id == phone_number_id)
            ).first()
        if display_phone_number:
            return self._session.scalars(
                query.where(WhatsAppPhoneNumber.display_phone_number == display_phone_number)
            ).first()
        return None

    @staticmethod
    def _normalize_phone_quality_rating(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if normalized in {"GREEN", "YELLOW", "RED", "UNKNOWN"}:
            return normalized
        return None

    def _get_latest_webhook_subscription(
        self,
        waba_account_id: str,
    ) -> WebhookSubscription | None:
        return self._session.scalars(
            select(WebhookSubscription)
            .where(WebhookSubscription.waba_account_id == waba_account_id)
            .order_by(
                WebhookSubscription.subscribed_at.desc(),
                WebhookSubscription.created_at.desc(),
                WebhookSubscription.id.desc(),
            )
        ).first()

    def _get_latest_webhook_subscription_for_scope(
        self,
        *,
        account_id: str,
        waba_id: str,
    ) -> WebhookSubscription | None:
        return self._session.scalars(
            select(WebhookSubscription)
            .where(
                WebhookSubscription.account_id == account_id,
                WebhookSubscription.waba_id == waba_id,
            )
            .order_by(
                WebhookSubscription.subscribed_at.desc(),
                WebhookSubscription.created_at.desc(),
                WebhookSubscription.id.desc(),
            )
        ).first()

    def _get_current_webhook_subscription_ids(
        self,
        subscriptions: list[WebhookSubscription],
    ) -> set[str]:
        latest_by_scope: dict[tuple[str, str], WebhookSubscription] = {}
        for subscription in subscriptions:
            scope_key = self._get_webhook_subscription_scope_key(subscription)
            if scope_key is None:
                continue
            current = latest_by_scope.get(scope_key)
            if current is None or self._webhook_subscription_sort_key(subscription) > self._webhook_subscription_sort_key(current):
                latest_by_scope[scope_key] = subscription
        return {item.id for item in latest_by_scope.values()}

    def _get_webhook_subscription_scope_key(
        self,
        subscription: WebhookSubscription,
    ) -> tuple[str, str] | None:
        waba_account = self._resolve_waba_account_for_subscription(subscription)
        resolved_account_id = subscription.account_id or (
            waba_account.account_id if waba_account is not None else None
        )
        resolved_waba_id = subscription.waba_id or (
            waba_account.waba_id if waba_account is not None else None
        )
        if resolved_account_id is None or resolved_waba_id is None:
            return None
        return (resolved_account_id, resolved_waba_id)

    @staticmethod
    def _webhook_subscription_sort_key(subscription: WebhookSubscription) -> tuple[object, object, str]:
        return (
            subscription.subscribed_at or subscription.created_at,
            subscription.created_at,
            subscription.id,
        )

    def _resolve_created_webhook_subscription_for_embedded_signup_session(
        self,
        session: EmbeddedSignupSessionModel,
    ) -> WebhookSubscription | None:
        if session.created_webhook_subscription is not None:
            return session.created_webhook_subscription
        if session.created_webhook_subscription_id is not None:
            return self._session.get(WebhookSubscription, session.created_webhook_subscription_id)
        return None

    def _require_embedded_signup_session(self, session_id: str) -> EmbeddedSignupSessionModel:
        session = self._session.scalars(
            select(EmbeddedSignupSessionModel)
            .options(
                selectinload(EmbeddedSignupSessionModel.account),
                selectinload(EmbeddedSignupSessionModel.waba_account).selectinload(
                    WhatsAppBusinessAccount.account
                ),
                selectinload(EmbeddedSignupSessionModel.created_webhook_subscription),
            )
            .where(EmbeddedSignupSessionModel.session_id == session_id)
        ).first()
        if session is None:
            raise LookupError(f"Embedded signup session '{session_id}' was not found.")
        return session

    @staticmethod
    def _phone_number_matches_account_scope(account_id: str) -> object:
        return or_(
            WhatsAppPhoneNumber.account_id == account_id,
            WhatsAppPhoneNumber.waba_account.has(WhatsAppBusinessAccount.account_id == account_id),
        )

    @staticmethod
    def _phone_number_matches_waba_scope(waba_id: str) -> object:
        return or_(
            WhatsAppPhoneNumber.waba_id == waba_id,
            WhatsAppPhoneNumber.waba_account.has(WhatsAppBusinessAccount.waba_id == waba_id),
        )

    @staticmethod
    def _subscription_matches_account_scope(account_id: str) -> object:
        return or_(
            WebhookSubscription.account_id == account_id,
            WebhookSubscription.waba_account.has(WhatsAppBusinessAccount.account_id == account_id),
        )

    @staticmethod
    def _subscription_matches_waba_scope(waba_id: str) -> object:
        return or_(
            WebhookSubscription.waba_id == waba_id,
            WebhookSubscription.waba_account.has(WhatsAppBusinessAccount.waba_id == waba_id),
        )

    def _sync_phone_numbers(
        self,
        waba_account: WhatsAppBusinessAccount,
        phone_numbers: list[MetaPhoneNumber],
    ) -> None:
        incoming_ids = sorted({item.phone_number_id for item in phone_numbers})
        if not incoming_ids:
            return

        existing_records = self._session.scalars(
            select(WhatsAppPhoneNumber).where(WhatsAppPhoneNumber.phone_number_id.in_(incoming_ids))
        ).all()
        for existing_record in existing_records:
            if existing_record.waba_account_id != waba_account.id:
                raise MetaAccountConflictError(
                    f"Phone number '{existing_record.phone_number_id}' is already bound to another WABA."
                )

        existing = {
            item.phone_number_id: item for item in existing_records
        }

        for phone_number in phone_numbers:
            record = existing.get(phone_number.phone_number_id)
            if record is None:
                record = WhatsAppPhoneNumber(
                    account_id=waba_account.account_id,
                    waba_account_id=waba_account.id,
                    waba_id=waba_account.waba_id,
                    phone_number_id=phone_number.phone_number_id,
                    display_phone_number=phone_number.display_phone_number,
                    verified_name=phone_number.verified_name,
                    quality_rating=phone_number.quality_rating,
                    is_registered=phone_number.is_registered,
                    is_active=True,
                )
                self._session.add(record)
                continue

            record.waba_account_id = waba_account.id
            record.account_id = waba_account.account_id
            record.waba_id = waba_account.waba_id
            record.display_phone_number = phone_number.display_phone_number
            record.verified_name = phone_number.verified_name
            record.quality_rating = phone_number.quality_rating
            record.is_registered = phone_number.is_registered
            record.is_active = True

    def _replace_phone_numbers(
        self,
        waba_account: WhatsAppBusinessAccount,
        phone_numbers: list[MetaPhoneNumber],
    ) -> None:
        incoming_ids = {item.phone_number_id for item in phone_numbers}
        for existing_record in list(waba_account.phone_numbers):
            if existing_record.phone_number_id in incoming_ids:
                continue
            if self._phone_number_has_dependencies(existing_record):
                existing_record.is_active = False
                existing_record.is_registered = False
                continue
            self._session.delete(existing_record)
        if phone_numbers:
            self._sync_phone_numbers(waba_account=waba_account, phone_numbers=phone_numbers)
        self._session.flush()

    def _get_active_phone_number_ids(self, waba_account_id: str) -> list[str]:
        return sorted(
            self._session.scalars(
                select(WhatsAppPhoneNumber.phone_number_id).where(
                    WhatsAppPhoneNumber.waba_account_id == waba_account_id,
                    WhatsAppPhoneNumber.is_active.is_(True),
                )
            ).all()
        )

    @staticmethod
    def _phone_number_has_dependencies(phone_number: WhatsAppPhoneNumber) -> bool:
        return any(
            (
                phone_number.conversations,
                phone_number.messages,
                phone_number.template_send_logs,
                phone_number.media_assets,
            )
        )

    @staticmethod
    def _ensure_account_allowed(
        account_id: str,
        allowed_account_ids: set[str] | None,
    ) -> None:
        if allowed_account_ids is None or account_id in allowed_account_ids:
            return
        raise PermissionError(
            f"Embedded signup session does not belong to an accessible account scope."
        )

    @staticmethod
    def _ensure_waba_belongs_to_account(
        waba_account: WhatsAppBusinessAccount,
        account_id: str,
    ) -> None:
        if waba_account.account_id == account_id:
            return
        raise MetaAccountConflictError(
            f"WABA '{waba_account.waba_id}' is already assigned to account '{waba_account.account_id}'."
        )

    @staticmethod
    def _ensure_embedded_signup_status(
        session: EmbeddedSignupSessionModel,
        *,
        expected_status: str,
    ) -> None:
        if session.status == expected_status:
            return
        raise MetaAccountConflictError(
            f"Embedded signup session '{session.session_id}' is already in terminal status '{session.status}'."
        )

    def _upsert_embedded_signup_waba(
        self,
        *,
        account_id: str,
        display_name: str,
        waba_id: str | None,
        meta_business_portfolio_id: str | None,
        phone_number_ids: list[str],
        access_token: str | None,
        verify_token: str | None,
        app_secret: str | None,
    ) -> WhatsAppBusinessAccount | None:
        if waba_id is None:
            return None
        normalized_verify_token = self._normalize_verify_token(verify_token)
        self._ensure_verify_token_available(
            verify_token=normalized_verify_token,
            current_account_id=account_id,
            current_waba_id=waba_id,
        )

        waba_account = self._get_waba_by_waba_id(waba_id)
        portfolio_id: str | None = None
        if meta_business_portfolio_id is not None:
            portfolio = self._get_or_create_portfolio(
                account_id=account_id,
                meta_business_portfolio_id=meta_business_portfolio_id,
                display_name=display_name,
            )
            portfolio_id = portfolio.id

        if waba_account is None:
            waba_account = WhatsAppBusinessAccount(
                account_id=account_id,
                portfolio_id=portfolio_id,
                waba_id=waba_id,
                onboarding_mode="embedded_signup",
                token_source="embedded_signup",
                access_token=access_token,
                verify_token=normalized_verify_token,
                app_secret=app_secret,
                webhook_subscribed=False,
                is_active=True,
                ai_enabled=True,
            )
            self._session.add(waba_account)
            self._session.flush()
        else:
            self._ensure_waba_belongs_to_account(waba_account, account_id)
            if portfolio_id is not None:
                waba_account.portfolio_id = portfolio_id
            waba_account.onboarding_mode = "embedded_signup"
            waba_account.token_source = "embedded_signup"
            if access_token:
                waba_account.access_token = access_token
            if normalized_verify_token:
                waba_account.verify_token = normalized_verify_token
            if app_secret:
                self._ensure_current_root_webhook_receive_signature_routing(
                    account_id=account_id,
                    waba_id=waba_id,
                    app_secret=app_secret,
                )
                waba_account.app_secret = app_secret

        if phone_number_ids:
            self._sync_phone_numbers(
                waba_account=waba_account,
                phone_numbers=[
                    MetaPhoneNumber(
                        phone_number_id=phone_number_id,
                        display_phone_number=phone_number_id,
                        verified_name=None,
                        quality_rating="UNKNOWN",
                        is_registered=False,
                        is_active=True,
                    )
                    for phone_number_id in phone_number_ids
                ],
            )
        return waba_account

    @staticmethod
    def _serialize_embedded_signup_webhook_subscription(
        webhook_subscription: EmbeddedSignupWebhookSubscriptionRequest | None,
    ) -> dict[str, object] | None:
        if webhook_subscription is None:
            return None
        return webhook_subscription.model_dump(exclude_none=True)

    @staticmethod
    def _extract_embedded_signup_webhook_subscription(
        payload: dict[str, object] | None,
    ) -> EmbeddedSignupWebhookSubscriptionRequest | None:
        if not isinstance(payload, dict):
            return None
        session_request = payload.get("session_request")
        if not isinstance(session_request, dict):
            return None
        webhook_subscription = session_request.get("webhook_subscription")
        return MetaAccountRegistry._parse_embedded_signup_webhook_subscription_snapshot(
            webhook_subscription
        )

    @staticmethod
    def _parse_embedded_signup_webhook_subscription_snapshot(
        snapshot: object,
    ) -> EmbeddedSignupWebhookSubscriptionRequest | None:
        if not isinstance(snapshot, dict):
            return None
        try:
            return EmbeddedSignupWebhookSubscriptionRequest.model_validate(snapshot)
        except ValidationError:
            callback_url = snapshot.get("callback_url")
            if not isinstance(callback_url, str) or not callback_url.strip():
                return None
            verify_token = snapshot.get("verify_token")
            app_id = snapshot.get("app_id")
            return EmbeddedSignupWebhookSubscriptionRequest(
                callback_url=callback_url.strip(),
                verify_token=verify_token.strip()
                if isinstance(verify_token, str) and verify_token.strip()
                else None,
                app_id=app_id.strip() if isinstance(app_id, str) and app_id.strip() else None,
            )

    @staticmethod
    def _read_snapshot_bool(value: object, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "y"}:
                return True
            if normalized in {"0", "false", "no", "n"}:
                return False
        return default

    @staticmethod
    def _read_snapshot_int(value: object, default: int = 0) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                return default
        return default

    @staticmethod
    def _read_snapshot_str(value: object) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None

    @classmethod
    def _read_snapshot_str_list(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]

    @classmethod
    def _parse_embedded_signup_completion_waba_snapshot(
        cls,
        snapshot: object,
        *,
        account_id: str,
        default_display_name: str,
        default_waba_id: str | None,
        default_portfolio_id: str | None,
    ) -> MetaWabaAccount | None:
        if not isinstance(snapshot, dict):
            return None
        try:
            return MetaWabaAccount.model_validate(snapshot)
        except ValidationError:
            subscription_status = cls._read_snapshot_str(snapshot.get("webhook_subscription_status"))
            verification_status = cls._read_snapshot_str(snapshot.get("webhook_verification_status"))
            runtime_status = cls._read_snapshot_str(snapshot.get("webhook_runtime_status"))
            onboarding_mode = cls._read_snapshot_str(snapshot.get("onboarding_mode"))
            token_source = cls._read_snapshot_str(snapshot.get("token_source"))
            return MetaWabaAccount(
                account_id=cls._read_snapshot_str(snapshot.get("account_id")) or account_id,
                display_name=cls._read_snapshot_str(snapshot.get("display_name")) or default_display_name,
                account_is_active=cls._read_snapshot_bool(snapshot.get("account_is_active"), True),
                notes=None,
                onboarding_mode=(
                    onboarding_mode
                    if onboarding_mode in {"manual", "embedded_signup"}
                    else "embedded_signup"
                ),
                meta_business_portfolio_id=(
                    cls._read_snapshot_str(snapshot.get("meta_business_portfolio_id"))
                    or default_portfolio_id
                    or ""
                ),
                waba_id=cls._read_snapshot_str(snapshot.get("waba_id")) or default_waba_id or "",
                token_source=(
                    token_source
                    if token_source in {"system_user", "user_access_token", "embedded_signup"}
                    else "embedded_signup"
                ),
                is_active=cls._read_snapshot_bool(snapshot.get("is_active"), True),
                webhook_subscribed=cls._read_snapshot_bool(snapshot.get("webhook_subscribed"), False),
                webhook_subscription_status=subscription_status,
                webhook_callback_url=cls._read_snapshot_str(snapshot.get("webhook_callback_url")),
                webhook_root_verify_path="",
                webhook_verify_path="",
                webhook_receive_path="",
                webhook_root_receive_path=WHATSAPP_WEBHOOK_ROOT_PATH,
                webhook_verification_status=(
                    verification_status
                    if verification_status in {"unknown", "pending", "verified", "failed", "unavailable"}
                    else "pending"
                ),
                webhook_last_verified_at=cls._read_snapshot_str(snapshot.get("webhook_last_verified_at")),
                webhook_last_verification_error=cls._read_snapshot_str(
                    snapshot.get("webhook_last_verification_error")
                ),
                webhook_runtime_status=(
                    runtime_status
                    if runtime_status
                    in {
                        "unknown",
                        "pending",
                        "verification_pending",
                        "healthy",
                        "signature_failed",
                        "payload_invalid",
                    }
                    else "pending"
                ),
                webhook_last_event_received_at=cls._read_snapshot_str(
                    snapshot.get("webhook_last_event_received_at")
                ),
                webhook_last_message_received_at=cls._read_snapshot_str(
                    snapshot.get("webhook_last_message_received_at")
                ),
                webhook_last_status_update_at=cls._read_snapshot_str(
                    snapshot.get("webhook_last_status_update_at")
                ),
                webhook_last_management_event_at=cls._read_snapshot_str(
                    snapshot.get("webhook_last_management_event_at")
                ),
                webhook_last_signature_failed_at=cls._read_snapshot_str(
                    snapshot.get("webhook_last_signature_failed_at")
                ),
                webhook_signature_failure_count=cls._read_snapshot_int(
                    snapshot.get("webhook_signature_failure_count"),
                    0,
                ),
                webhook_runtime_error=cls._read_snapshot_str(snapshot.get("webhook_runtime_error")),
                has_access_token=cls._read_snapshot_bool(snapshot.get("has_access_token"), False),
                has_verify_token=cls._read_snapshot_bool(snapshot.get("has_verify_token"), False),
                has_app_secret=cls._read_snapshot_bool(snapshot.get("has_app_secret"), False),
                phone_number_count=cls._read_snapshot_int(snapshot.get("phone_number_count"), 0),
                registered_phone_number_count=cls._read_snapshot_int(
                    snapshot.get("registered_phone_number_count"),
                    0,
                ),
                ready_for_webhook_verification=cls._read_snapshot_bool(
                    snapshot.get("ready_for_webhook_verification"),
                    False,
                ),
                ready_for_webhook_delivery=cls._read_snapshot_bool(
                    snapshot.get("ready_for_webhook_delivery"),
                    False,
                ),
                ready_for_outbound_messages=cls._read_snapshot_bool(
                    snapshot.get("ready_for_outbound_messages"),
                    False,
                ),
                ready_for_meta_activation=cls._read_snapshot_bool(
                    snapshot.get("ready_for_meta_activation"),
                    False,
                ),
                blocking_reasons=cls._read_snapshot_str_list(snapshot.get("blocking_reasons")),
                phone_numbers=[],
            )

    @staticmethod
    def _coerce_webhook_subscription_request(
        webhook_subscription: EmbeddedSignupWebhookSubscriptionRequest,
    ) -> WebhookSubscriptionRequest:
        return WebhookSubscriptionRequest(
            callback_url=webhook_subscription.callback_url,
            verify_token=webhook_subscription.verify_token,
            app_id=webhook_subscription.app_id,
        )

    def _resolve_embedded_signup_app_secret(self) -> str | None:
        for candidate in (self._settings.meta_app_secret, self._settings.wa_app_secret):
            if candidate:
                return candidate
        return None

    @staticmethod
    def _build_embedded_signup_session_request_snapshot(
        *,
        webhook_subscription: EmbeddedSignupWebhookSubscriptionRequest | None,
        launch_context: EmbeddedSignupLaunchContext | None,
    ) -> dict[str, object] | None:
        if webhook_subscription is None and launch_context is None:
            return None
        session_request: dict[str, object] = {}
        if webhook_subscription is not None:
            session_request["webhook_subscription"] = (
                MetaAccountRegistry._serialize_embedded_signup_webhook_subscription(
                    webhook_subscription
                )
            )
        if launch_context is not None:
            session_request["launch_context"] = launch_context.model_dump()
        return {"session_request": session_request}

    @staticmethod
    def _extract_embedded_signup_launch_context(
        payload: dict[str, object] | None,
    ) -> EmbeddedSignupLaunchContext | None:
        if not isinstance(payload, dict):
            return None
        session_request = payload.get("session_request")
        if not isinstance(session_request, dict):
            return None
        launch_context = session_request.get("launch_context")
        if not isinstance(launch_context, dict):
            return None
        try:
            return EmbeddedSignupLaunchContext.model_validate(launch_context)
        except ValidationError:
            return None

    def _validate_embedded_signup_launch_state(
        self,
        *,
        session: EmbeddedSignupSessionModel,
        payload: EmbeddedSignupCallbackRequest,
        require_launch_state: bool,
        actor_type: str,
        actor_id: str | None,
    ) -> None:
        if not require_launch_state:
            return
        launch_context = self._extract_embedded_signup_launch_context(session.completion_payload)
        if launch_context is None:
            self._record_embedded_signup_callback_rejected(
                session=session,
                payload=payload,
                actor_type=actor_type,
                actor_id=actor_id,
                reason="missing_launch_context",
            )
            raise MetaAccountConflictError(
                f"Embedded signup callback launch context is missing for session '{session.session_id}'."
            )
        if launch_context.session_id != session.session_id:
            self._record_embedded_signup_callback_rejected(
                session=session,
                payload=payload,
                actor_type=actor_type,
                actor_id=actor_id,
                reason="launch_context_mismatch",
            )
            raise MetaAccountConflictError(
                f"Embedded signup callback launch context does not match session '{session.session_id}'."
            )
        supplied_state = payload.state or self._read_embedded_signup_string(
            payload.raw_payload,
            direct_keys=("state",),
        )
        if supplied_state is not None and supplied_state != launch_context.state:
            self._record_embedded_signup_callback_rejected(
                session=session,
                payload=payload,
                actor_type=actor_type,
                actor_id=actor_id,
                reason="state_mismatch",
            )
            raise MetaAccountConflictError(
                f"Embedded signup callback state does not match session '{session.session_id}'."
            )
        expires_at = self._parse_embedded_signup_launch_expires_at(launch_context.expires_at)
        if expires_at is None or expires_at <= utc_now():
            self._record_embedded_signup_callback_rejected(
                session=session,
                payload=payload,
                actor_type=actor_type,
                actor_id=actor_id,
                reason="state_expired",
            )
            raise MetaAccountConflictError(
                f"Embedded signup callback state expired for session '{session.session_id}'."
            )

    def _record_embedded_signup_callback_rejected(
        self,
        *,
        session: EmbeddedSignupSessionModel,
        payload: EmbeddedSignupCallbackRequest,
        actor_type: str,
        actor_id: str | None,
        reason: str,
    ) -> None:
        supplied_state = payload.state or self._read_embedded_signup_string(
            payload.raw_payload,
            direct_keys=("state",),
        )
        self._runtime_state.add_audit_log(
            account_id=session.account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="embedded_signup_callback_rejected",
            target_type="embedded_signup_session",
            target_id=session.session_id,
            payload={
                "reason": reason,
                "incoming_status": payload.status,
                "event_source": payload.event_source,
                "state_present": supplied_state is not None,
                "raw_payload_present": payload.raw_payload is not None,
            },
        )
        self._session.commit()

    @staticmethod
    def _parse_embedded_signup_launch_expires_at(value: str) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(UTC).replace(tzinfo=None)
        return parsed

    @staticmethod
    def _build_embedded_signup_payload_snapshot(
        *,
        session_request_payload: dict[str, object] | None,
        provider_name: str,
        provider_payload: dict[str, object] | None,
        request_payload: dict[str, object] | None,
        phone_number_ids: list[str],
        authorization_code_present: bool,
        system_user_access_token_present: bool,
        event_source: str,
        webhook_subscription: EmbeddedSignupWebhookSubscriptionRequest | None,
        webhook_subscription_result: dict[str, object] | None,
    ) -> dict[str, object]:
        return {
            "session_request": (
                session_request_payload.get("session_request")
                if isinstance(session_request_payload, dict)
                else None
            ),
            "provider_name": provider_name,
            "provider_payload": provider_payload,
            "request_payload": request_payload,
            "phone_number_ids": phone_number_ids,
            "authorization_code_present": authorization_code_present,
            "system_user_access_token_present": system_user_access_token_present,
            "event_source": event_source,
            "webhook_subscription": MetaAccountRegistry._serialize_embedded_signup_webhook_subscription(
                webhook_subscription
            ),
            "webhook_subscription_result": webhook_subscription_result,
        }

    @classmethod
    def _read_embedded_signup_string(
        cls,
        payload: dict[str, object] | None,
        *,
        direct_keys: tuple[str, ...],
    ) -> str | None:
        if not isinstance(payload, dict):
            return None
        for key in direct_keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for candidate in cls._iter_embedded_signup_candidate_mappings(payload):
            for key in direct_keys:
                value = candidate.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    @classmethod
    def _read_embedded_signup_phone_number_ids(
        cls,
        payload: dict[str, object] | None,
    ) -> list[str]:
        if not isinstance(payload, dict):
            return []
        for candidate in (payload, *cls._iter_embedded_signup_candidate_mappings(payload)):
            phone_number_ids = cls._coerce_embedded_signup_phone_number_ids(
                candidate.get("phone_number_ids")
            )
            if phone_number_ids:
                return phone_number_ids
            phone_numbers = cls._coerce_embedded_signup_phone_number_ids(
                candidate.get("phone_numbers")
            )
            if phone_numbers:
                return phone_numbers
            phone_number_id = candidate.get("phone_number_id")
            if isinstance(phone_number_id, str) and phone_number_id.strip():
                return [phone_number_id.strip()]
        return []

    @classmethod
    def _iter_embedded_signup_candidate_mappings(
        cls,
        payload: dict[str, object],
    ) -> list[dict[str, object]]:
        candidates: list[dict[str, object]] = []
        for key, value in payload.items():
            if isinstance(value, dict):
                if key in {"data", "payload", "result", "session", "embedded_signup", "authorization"}:
                    candidates.append(value)
                candidates.extend(cls._iter_embedded_signup_candidate_mappings(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        candidates.extend(cls._iter_embedded_signup_candidate_mappings(item))
        return candidates

    @staticmethod
    def _coerce_embedded_signup_phone_number_ids(value: object) -> list[str]:
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        if not isinstance(value, list):
            return []
        phone_number_ids: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                phone_number_ids.append(item.strip())
            elif isinstance(item, dict):
                item_id = item.get("id") or item.get("phone_number_id")
                if isinstance(item_id, str) and item_id.strip():
                    phone_number_ids.append(item_id.strip())
        return phone_number_ids

    @staticmethod
    def _resolve_embedded_signup_completion_stage(
        *,
        provider_completion_status: str,
        waba_linked: bool,
        webhook_subscription_result: MetaWabaAccount | None,
    ) -> str:
        if not waba_linked:
            return provider_completion_status
        if (
            webhook_subscription_result is not None
            and not webhook_subscription_result.ready_for_webhook_delivery
        ):
            return "webhook_verification_pending"
        return "local_waba_linked"

    @staticmethod
    def _compose_embedded_signup_completion_message(
        *,
        provider_message: str | None,
        webhook_subscription_result: MetaWabaAccount | None,
    ) -> str | None:
        if webhook_subscription_result is None:
            return provider_message
        subscription_status = webhook_subscription_result.webhook_subscription_status or "unknown"
        verification_status = webhook_subscription_result.webhook_verification_status or "pending"
        suffix = (
            "Webhook subscription was created and the WABA is waiting for verify challenge completion."
            if not webhook_subscription_result.ready_for_webhook_delivery
            else "Webhook subscription is active and delivery readiness is available."
        )
        base = provider_message.strip() if provider_message else ""
        if base:
            return f"{base} {suffix} (subscription_status={subscription_status}, verification_status={verification_status})"
        return f"{suffix} (subscription_status={subscription_status}, verification_status={verification_status})"

    def _serialize_waba_account(self, waba_account: WhatsAppBusinessAccount) -> MetaWabaAccount:
        account = waba_account.account
        portfolio = waba_account.portfolio
        phone_numbers = sorted(
            (item for item in waba_account.phone_numbers if item.is_active),
            key=lambda item: item.display_phone_number,
        )
        auth_context = self._build_webhook_auth_context(waba_account)
        latest_subscription = self._get_latest_webhook_subscription_for_scope(
            account_id=waba_account.account_id,
            waba_id=waba_account.waba_id,
        )
        registered_phone_number_count = sum(
            1
            for item in phone_numbers
            if item.is_registered and item.is_active
        )
        has_access_token = bool(waba_account.access_token)
        has_verify_token = bool(auth_context.verify_token)
        has_app_secret = bool(auth_context.app_secret)
        ready_for_webhook_verification = has_verify_token
        account_is_active = bool(account.is_active) if account is not None else True
        webhook_subscription_status = latest_subscription.status if latest_subscription is not None else None
        webhook_subscribed = self._is_effectively_webhook_subscribed(
            webhook_subscribed=bool(waba_account.webhook_subscribed),
            subscription_status=webhook_subscription_status,
        )
        ready_for_webhook_delivery = (
            account_is_active
            and waba_account.is_active
            and
            self._is_webhook_delivery_ready(
                webhook_subscribed=webhook_subscribed,
                subscription_status=webhook_subscription_status,
                has_verify_token=has_verify_token,
                has_app_secret=has_app_secret,
                webhook_verification_status=waba_account.webhook_verification_status,
            )
        )
        ready_for_outbound_messages = (
            account_is_active
            and waba_account.is_active
            and has_access_token
            and registered_phone_number_count > 0
        )
        blocking_reasons = self._build_waba_blocking_reasons(
            account_is_active=account_is_active,
            is_active=waba_account.is_active,
            has_access_token=has_access_token,
            has_verify_token=has_verify_token,
            has_app_secret=has_app_secret,
            webhook_subscribed=webhook_subscribed,
            ready_for_webhook_delivery=ready_for_webhook_delivery,
            phone_number_count=len(phone_numbers),
            registered_phone_number_count=registered_phone_number_count,
        )
        scoped_webhook_path = self._build_scoped_webhook_path(
            account_id=waba_account.account_id,
            waba_id=waba_account.waba_id,
        )
        webhook_callback_url = (
            latest_subscription.callback_url if latest_subscription is not None else None
        )
        ready_for_meta_activation = ready_for_webhook_delivery and ready_for_outbound_messages
        has_root_webhook_routing_conflict = self._has_root_webhook_routing_conflict(
            waba_account=waba_account,
            auth_context=auth_context,
            callback_url=webhook_callback_url,
        )
        return MetaWabaAccount(
            account_id=waba_account.account_id,
            display_name=account.display_name if account is not None else waba_account.account_id,
            account_is_active=account_is_active,
            notes=account.notes if account is not None else None,
            onboarding_mode=waba_account.onboarding_mode,
            meta_business_portfolio_id=(
                portfolio.meta_business_portfolio_id if portfolio is not None else ""
            ),
            waba_id=waba_account.waba_id,
            token_source=waba_account.token_source,
            is_active=waba_account.is_active,
            webhook_subscribed=webhook_subscribed,
            webhook_subscription_status=webhook_subscription_status,
            webhook_callback_url=webhook_callback_url,
            webhook_root_verify_path=WHATSAPP_WEBHOOK_ROOT_PATH,
            webhook_verify_path=scoped_webhook_path,
            webhook_receive_path=scoped_webhook_path,
            webhook_root_receive_path=WHATSAPP_WEBHOOK_ROOT_PATH,
            webhook_verification_status=waba_account.webhook_verification_status,
            webhook_last_verified_at=(
                waba_account.webhook_last_verified_at.isoformat()
                if waba_account.webhook_last_verified_at is not None
                else None
            ),
            webhook_last_verification_error=waba_account.webhook_last_verification_error,
            webhook_runtime_status=waba_account.webhook_runtime_status,
            webhook_last_event_received_at=(
                waba_account.webhook_last_event_received_at.isoformat()
                if waba_account.webhook_last_event_received_at is not None
                else None
            ),
            webhook_last_message_received_at=(
                waba_account.webhook_last_message_received_at.isoformat()
                if waba_account.webhook_last_message_received_at is not None
                else None
            ),
            webhook_last_status_update_at=(
                waba_account.webhook_last_status_update_at.isoformat()
                if waba_account.webhook_last_status_update_at is not None
                else None
            ),
            webhook_last_management_event_at=(
                waba_account.webhook_last_management_event_at.isoformat()
                if waba_account.webhook_last_management_event_at is not None
                else None
            ),
            webhook_last_signature_failed_at=(
                waba_account.webhook_last_signature_failed_at.isoformat()
                if waba_account.webhook_last_signature_failed_at is not None
                else None
            ),
            webhook_signature_failure_count=waba_account.webhook_signature_failure_count,
            webhook_runtime_error=waba_account.webhook_runtime_error,
            has_access_token=has_access_token,
            has_verify_token=has_verify_token,
            has_app_secret=has_app_secret,
            phone_number_count=len(phone_numbers),
            registered_phone_number_count=registered_phone_number_count,
            ready_for_webhook_verification=ready_for_webhook_verification,
            ready_for_webhook_delivery=ready_for_webhook_delivery,
            ready_for_outbound_messages=ready_for_outbound_messages,
            ready_for_meta_activation=ready_for_meta_activation,
            ready_for_formal_activation=(
                ready_for_meta_activation and not has_root_webhook_routing_conflict
            ),
            has_root_webhook_routing_conflict=has_root_webhook_routing_conflict,
            blocking_reasons=blocking_reasons,
            phone_numbers=[
                MetaPhoneNumber(
                    phone_number_id=item.phone_number_id,
                    display_phone_number=item.display_phone_number,
                    verified_name=item.verified_name,
                    quality_rating=item.quality_rating,
                    is_registered=item.is_registered,
                    is_active=item.is_active,
                )
                for item in phone_numbers
            ],
        )

    def _serialize_webhook_subscription(
        self,
        subscription: WebhookSubscription,
        *,
        apply_current_scope_state: bool,
    ) -> WebhookSubscriptionView:
        waba_account = self._resolve_waba_account_for_subscription(subscription)
        account = self._resolve_account_for_waba_account(waba_account)
        portfolio = self._resolve_portfolio_for_waba_account(waba_account)
        resolved_account_id = subscription.account_id or (
            waba_account.account_id if waba_account is not None else ""
        )
        resolved_waba_id = subscription.waba_id or (
            waba_account.waba_id if waba_account is not None else ""
        )
        scoped_webhook_path = self._build_scoped_webhook_path(
            account_id=resolved_account_id,
            waba_id=resolved_waba_id,
        )
        return WebhookSubscriptionView(
            id=subscription.id,
            account_id=resolved_account_id,
            account_display_name=(
                account.display_name
                if account is not None
                else resolved_account_id
            ),
            meta_business_portfolio_id=(
                portfolio.meta_business_portfolio_id if portfolio is not None else None
            ),
            waba_id=resolved_waba_id,
            callback_url=subscription.callback_url,
            webhook_root_verify_path=WHATSAPP_WEBHOOK_ROOT_PATH,
            webhook_verify_path=scoped_webhook_path,
            webhook_receive_path=scoped_webhook_path,
            webhook_root_receive_path=WHATSAPP_WEBHOOK_ROOT_PATH,
            verify_token_present=bool(subscription.verify_token),
            app_secret_present=bool(self._normalize_app_secret(subscription.app_secret)),
            app_id=subscription.app_id,
            status=subscription.status,
            current_scope_state_applied=apply_current_scope_state,
            subscribed_at=(
                subscription.subscribed_at.isoformat() if subscription.subscribed_at is not None else None
            ),
            webhook_verification_status=(
                waba_account.webhook_verification_status
                if apply_current_scope_state and waba_account is not None
                else "pending"
            ),
            webhook_last_verified_at=(
                waba_account.webhook_last_verified_at.isoformat()
                if (
                    apply_current_scope_state
                    and waba_account is not None
                    and waba_account.webhook_last_verified_at is not None
                )
                else None
            ),
            webhook_last_verification_error=(
                waba_account.webhook_last_verification_error
                if apply_current_scope_state and waba_account is not None
                else None
            ),
            webhook_runtime_status=(
                waba_account.webhook_runtime_status
                if apply_current_scope_state and waba_account is not None
                else "pending"
            ),
            webhook_last_event_received_at=(
                waba_account.webhook_last_event_received_at.isoformat()
                if (
                    apply_current_scope_state
                    and waba_account is not None
                    and waba_account.webhook_last_event_received_at is not None
                )
                else None
            ),
            webhook_last_message_received_at=(
                waba_account.webhook_last_message_received_at.isoformat()
                if (
                    apply_current_scope_state
                    and waba_account is not None
                    and waba_account.webhook_last_message_received_at is not None
                )
                else None
            ),
            webhook_last_status_update_at=(
                waba_account.webhook_last_status_update_at.isoformat()
                if (
                    apply_current_scope_state
                    and waba_account is not None
                    and waba_account.webhook_last_status_update_at is not None
                )
                else None
            ),
            webhook_last_management_event_at=(
                waba_account.webhook_last_management_event_at.isoformat()
                if (
                    apply_current_scope_state
                    and waba_account is not None
                    and waba_account.webhook_last_management_event_at is not None
                )
                else None
            ),
            webhook_last_signature_failed_at=(
                waba_account.webhook_last_signature_failed_at.isoformat()
                if (
                    apply_current_scope_state
                    and waba_account is not None
                    and waba_account.webhook_last_signature_failed_at is not None
                )
                else None
            ),
            webhook_signature_failure_count=(
                waba_account.webhook_signature_failure_count
                if apply_current_scope_state and waba_account is not None
                else 0
            ),
            webhook_runtime_error=(
                waba_account.webhook_runtime_error
                if apply_current_scope_state and waba_account is not None
                else None
            ),
            created_at=subscription.created_at.isoformat(),
            updated_at=subscription.updated_at.isoformat(),
        )

    def _serialize_embedded_signup_session(
        self,
        session: EmbeddedSignupSessionModel,
    ) -> EmbeddedSignupSession:
        waba_account = self._resolve_waba_account_for_embedded_signup_session(session)
        created_subscription = self._resolve_created_webhook_subscription_for_embedded_signup_session(session)
        waba_snapshot = self._serialize_waba_account(waba_account) if waba_account is not None else None
        account = session.account
        portfolio = self._resolve_portfolio_for_waba_account(waba_account)
        fallback_display_name = (
            account.display_name
            if account is not None
            else (
                waba_account.account.display_name
                if waba_account is not None and waba_account.account is not None
                else session.account_id
            )
        )
        payload_snapshot = session.completion_payload if isinstance(session.completion_payload, dict) else {}
        launch_context = self._extract_embedded_signup_launch_context(payload_snapshot)
        webhook_snapshot = payload_snapshot.get("webhook_subscription")
        webhook_result_snapshot = payload_snapshot.get("webhook_subscription_result")
        configured_webhook = (
            self._parse_embedded_signup_webhook_subscription_snapshot(webhook_snapshot)
            or self._extract_embedded_signup_webhook_subscription(session.completion_payload)
        )
        completion_waba_snapshot = self._parse_embedded_signup_completion_waba_snapshot(
            webhook_result_snapshot,
            account_id=session.account_id,
            default_display_name=fallback_display_name,
            default_waba_id=session.provider_waba_id or (waba_account.waba_id if waba_account is not None else None),
            default_portfolio_id=(
                session.provider_business_portfolio_id
                or (portfolio.meta_business_portfolio_id if portfolio is not None else None)
            ),
        )
        linked_waba_id = waba_account.waba_id if waba_account is not None else None
        current_waba_auth_context = (
            self._build_webhook_auth_context(waba_account)
            if waba_account is not None
            else WebhookAuthContext(
                account_id=session.account_id,
                waba_id=linked_waba_id or session.provider_waba_id or "",
                verify_token=None,
                app_secret=None,
            )
        )
        current_subscription = (
            self._get_latest_webhook_subscription_for_scope(
                account_id=session.account_id,
                waba_id=linked_waba_id,
            )
            if linked_waba_id
            else None
        )
        session_snapshot = EmbeddedSignupSessionSnapshot(
            waba_id=session.provider_waba_id,
            meta_business_portfolio_id=session.provider_business_portfolio_id,
            linked_phone_number_ids=list(session.linked_phone_number_ids_json or []),
            webhook_callback_url=(
                configured_webhook.callback_url if configured_webhook is not None else None
            ),
            webhook_verify_token_present=(
                configured_webhook is not None and bool(configured_webhook.verify_token)
            ),
            webhook_app_secret_present=(
                completion_waba_snapshot.has_app_secret
                if completion_waba_snapshot is not None
                else False
            ),
            webhook_app_id=(
                configured_webhook.app_id if configured_webhook is not None else None
            ),
            webhook_subscription_status=(
                completion_waba_snapshot.webhook_subscription_status
                if completion_waba_snapshot is not None
                else None
            ),
            webhook_verification_status=(
                completion_waba_snapshot.webhook_verification_status
                if completion_waba_snapshot is not None
                else None
            ),
            webhook_runtime_status=(
                completion_waba_snapshot.webhook_runtime_status
                if completion_waba_snapshot is not None
                else None
            ),
            ready_for_webhook_delivery=(
                completion_waba_snapshot.ready_for_webhook_delivery
                if completion_waba_snapshot is not None
                else None
            ),
            ready_for_outbound_messages=(
                completion_waba_snapshot.ready_for_outbound_messages
                if completion_waba_snapshot is not None
                else None
            ),
            ready_for_meta_activation=(
                completion_waba_snapshot.ready_for_meta_activation
                if completion_waba_snapshot is not None
                else None
            ),
            webhook_blocking_reasons=(
                self._build_embedded_signup_webhook_blocking_reasons(
                    completion_waba_snapshot.blocking_reasons
                )
                if completion_waba_snapshot is not None
                else []
            ),
        )
        current_waba_state = (
            EmbeddedSignupCurrentWabaState(
                waba_id=linked_waba_id,
                meta_business_portfolio_id=(
                    portfolio.meta_business_portfolio_id if portfolio is not None else None
                ),
                webhook_callback_url=(
                    (
                        current_subscription.callback_url
                        if current_subscription is not None
                        else (waba_snapshot.webhook_callback_url if waba_snapshot is not None else None)
                    )
                ),
                webhook_verify_token_present=bool(current_waba_auth_context.verify_token),
                webhook_app_secret_present=bool(current_waba_auth_context.app_secret),
                webhook_app_id=(
                    current_subscription.app_id if current_subscription is not None else None
                ),
                webhook_subscription_status=(
                    waba_snapshot.webhook_subscription_status if waba_snapshot is not None else None
                ),
                webhook_verification_status=(
                    waba_snapshot.webhook_verification_status if waba_snapshot is not None else None
                ),
                webhook_runtime_status=(
                    waba_snapshot.webhook_runtime_status if waba_snapshot is not None else None
                ),
                ready_for_webhook_delivery=(
                    waba_snapshot.ready_for_webhook_delivery if waba_snapshot is not None else False
                ),
                ready_for_outbound_messages=(
                    waba_snapshot.ready_for_outbound_messages if waba_snapshot is not None else False
                ),
                ready_for_meta_activation=(
                    waba_snapshot.ready_for_meta_activation if waba_snapshot is not None else False
                ),
                webhook_blocking_reasons=(
                    self._build_embedded_signup_webhook_blocking_reasons(
                        waba_snapshot.blocking_reasons
                    )
                    if waba_snapshot is not None
                    else []
                ),
            )
            if waba_snapshot is not None
            else None
        )
        return EmbeddedSignupSession(
            session_id=session.session_id,
            account_id=session.account_id,
            display_name=fallback_display_name,
            redirect_uri=session.redirect_uri,
            provider_name=session.provider_name,
            status=session.status,
            completion_stage=session.completion_stage,
            event_source=session.last_event_source,
            remote_confirmed=session.remote_confirmed,
            waba_id=session.provider_waba_id or linked_waba_id,
            linked_waba_id=linked_waba_id,
            provider_waba_id=session.provider_waba_id,
            meta_business_portfolio_id=(
                session.provider_business_portfolio_id
                or (portfolio.meta_business_portfolio_id if portfolio is not None else None)
            ),
            setup_session_id=session.setup_session_id,
            linked_phone_number_ids=list(session.linked_phone_number_ids_json or []),
            authorization_code_present=session.authorization_code_present,
            system_user_access_token_present=session.system_user_access_token_present,
            launch_context=launch_context,
            callback_received_at=(
                session.callback_received_at.isoformat()
                if session.callback_received_at is not None
                else None
            ),
            completed_at=(
                session.completed_at.isoformat() if session.completed_at is not None else None
            ),
            completion_message=session.completion_message,
            error_message=session.error_message,
            webhook_callback_url=(
                created_subscription.callback_url
                if created_subscription is not None
                else (
                    configured_webhook.callback_url if configured_webhook is not None else None
                )
            ),
            webhook_verify_token_present=(
                bool(created_subscription.verify_token)
                if created_subscription is not None
                else (
                    configured_webhook is not None and bool(configured_webhook.verify_token)
                )
            ),
            webhook_app_secret_present=(
                bool(self._normalize_app_secret(created_subscription.app_secret))
                if created_subscription is not None
                else (
                    completion_waba_snapshot.has_app_secret
                    if completion_waba_snapshot is not None
                    else False
                )
            ),
            webhook_app_id=(
                created_subscription.app_id
                if created_subscription is not None
                else (configured_webhook.app_id if configured_webhook is not None else None)
            ),
            webhook_subscription_status=(
                created_subscription.status
                if created_subscription is not None
                else (waba_snapshot.webhook_subscription_status if waba_snapshot is not None else None)
            ),
            webhook_verification_status=(
                waba_snapshot.webhook_verification_status if waba_snapshot is not None else None
            ),
            webhook_runtime_status=(
                waba_snapshot.webhook_runtime_status if waba_snapshot is not None else None
            ),
            ready_for_webhook_delivery=(
                waba_snapshot.ready_for_webhook_delivery if waba_snapshot is not None else False
            ),
            ready_for_outbound_messages=(
                waba_snapshot.ready_for_outbound_messages if waba_snapshot is not None else False
            ),
            ready_for_meta_activation=(
                waba_snapshot.ready_for_meta_activation if waba_snapshot is not None else False
            ),
            webhook_blocking_reasons=(
                self._build_embedded_signup_webhook_blocking_reasons(
                    waba_snapshot.blocking_reasons
                )
                if waba_snapshot is not None
                else []
            ),
            completion_webhook_subscription_status=(
                completion_waba_snapshot.webhook_subscription_status
                if completion_waba_snapshot is not None
                else None
            ),
            completion_webhook_verification_status=(
                completion_waba_snapshot.webhook_verification_status
                if completion_waba_snapshot is not None
                else None
            ),
            completion_webhook_runtime_status=(
                completion_waba_snapshot.webhook_runtime_status
                if completion_waba_snapshot is not None
                else None
            ),
            completion_ready_for_webhook_delivery=(
                completion_waba_snapshot.ready_for_webhook_delivery
                if completion_waba_snapshot is not None
                else None
            ),
            completion_ready_for_outbound_messages=(
                completion_waba_snapshot.ready_for_outbound_messages
                if completion_waba_snapshot is not None
                else None
            ),
            completion_ready_for_meta_activation=(
                completion_waba_snapshot.ready_for_meta_activation
                if completion_waba_snapshot is not None
                else None
            ),
            completion_webhook_blocking_reasons=(
                self._build_embedded_signup_webhook_blocking_reasons(
                    completion_waba_snapshot.blocking_reasons
                )
                if completion_waba_snapshot is not None
                else []
            ),
            session_snapshot=session_snapshot,
            current_waba_state=current_waba_state,
        )

    def _serialize_phone_number_scope(
        self,
        phone_number: WhatsAppPhoneNumber,
    ) -> MetaPhoneNumberScopeView:
        waba_account = self._resolve_waba_account_for_phone_number(phone_number)
        account = self._resolve_account_for_waba_account(waba_account)
        portfolio = self._resolve_portfolio_for_waba_account(waba_account)
        resolved_account_id = phone_number.account_id or (
            waba_account.account_id if waba_account is not None else ""
        )
        resolved_waba_id = phone_number.waba_id or (
            waba_account.waba_id if waba_account is not None else ""
        )
        auth_context = (
            self._build_webhook_auth_context(waba_account)
            if waba_account is not None
            else WebhookAuthContext(
                account_id=resolved_account_id,
                waba_id=resolved_waba_id,
                verify_token=None,
                app_secret=None,
            )
        )
        has_access_token = bool(waba_account.access_token) if waba_account is not None else False
        has_verify_token = bool(auth_context.verify_token)
        has_app_secret = bool(auth_context.app_secret)
        account_is_active = bool(account.is_active) if account is not None else True
        waba_is_active = bool(waba_account.is_active) if waba_account is not None else False
        latest_subscription = (
            self._get_latest_webhook_subscription_for_scope(
                account_id=waba_account.account_id,
                waba_id=waba_account.waba_id,
            )
            if waba_account is not None
            else None
        )
        webhook_subscription_status = latest_subscription.status if latest_subscription is not None else None
        webhook_subscribed = self._is_effectively_webhook_subscribed(
            webhook_subscribed=bool(waba_account.webhook_subscribed) if waba_account is not None else False,
            subscription_status=webhook_subscription_status,
        )
        ready_for_webhook_delivery = (
            account_is_active
            and waba_is_active
            and
            self._is_webhook_delivery_ready(
                webhook_subscribed=webhook_subscribed,
                subscription_status=webhook_subscription_status,
                has_verify_token=has_verify_token,
                has_app_secret=has_app_secret,
                webhook_verification_status=(
                    waba_account.webhook_verification_status if waba_account is not None else "pending"
                ),
            )
        )
        ready_for_outbound_messages = (
            account_is_active
            and waba_is_active
            and has_access_token
            and phone_number.is_registered
            and phone_number.is_active
        )
        blocking_reasons = self._build_phone_blocking_reasons(
            account_is_active=account_is_active,
            waba_is_active=waba_is_active,
            has_access_token=has_access_token,
            has_verify_token=has_verify_token,
            has_app_secret=has_app_secret,
            webhook_subscribed=webhook_subscribed,
            ready_for_webhook_delivery=ready_for_webhook_delivery,
            is_registered=phone_number.is_registered,
            is_active=phone_number.is_active,
        )
        return MetaPhoneNumberScopeView(
            account_id=resolved_account_id,
            account_display_name=(
                account.display_name
                if account is not None
                else resolved_account_id
            ),
            account_is_active=account_is_active,
            meta_business_portfolio_id=(
                portfolio.meta_business_portfolio_id if portfolio is not None else None
            ),
            waba_id=resolved_waba_id,
            phone_number_id=phone_number.phone_number_id,
            display_phone_number=phone_number.display_phone_number,
            verified_name=phone_number.verified_name,
            quality_rating=phone_number.quality_rating,
            quality_event=phone_number.quality_event,
            previous_quality_rating=phone_number.previous_quality_rating,
            messaging_limit_tier=phone_number.messaging_limit_tier,
            max_daily_conversations_per_business=phone_number.max_daily_conversations_per_business,
            last_quality_event_at=(
                phone_number.last_quality_event_at.isoformat()
                if phone_number.last_quality_event_at is not None
                else None
            ),
            is_registered=phone_number.is_registered,
            is_active=phone_number.is_active,
            webhook_subscribed=webhook_subscribed,
            webhook_subscription_status=webhook_subscription_status,
            ready_for_webhook_delivery=ready_for_webhook_delivery,
            ready_for_outbound_messages=ready_for_outbound_messages,
            ready_for_meta_activation=ready_for_webhook_delivery and ready_for_outbound_messages,
            blocking_reasons=blocking_reasons,
        )

    def _resolve_waba_account_for_phone_number(
        self,
        phone_number: WhatsAppPhoneNumber,
    ) -> WhatsAppBusinessAccount | None:
        if phone_number.waba_account is not None:
            return phone_number.waba_account
        return self._session.get(WhatsAppBusinessAccount, phone_number.waba_account_id)

    def _resolve_waba_account_for_subscription(
        self,
        subscription: WebhookSubscription,
    ) -> WhatsAppBusinessAccount | None:
        if subscription.waba_account is not None:
            return subscription.waba_account
        if subscription.account_id and subscription.waba_id:
            waba_account = self._session.scalars(
                select(WhatsAppBusinessAccount).where(
                    WhatsAppBusinessAccount.account_id == subscription.account_id,
                    WhatsAppBusinessAccount.waba_id == subscription.waba_id,
                )
            ).first()
            if waba_account is not None:
                return waba_account
        return self._session.get(WhatsAppBusinessAccount, subscription.waba_account_id)

    def _resolve_waba_account_for_embedded_signup_session(
        self,
        session: EmbeddedSignupSessionModel,
    ) -> WhatsAppBusinessAccount | None:
        if session.waba_account is not None:
            return session.waba_account
        if session.provider_waba_id:
            waba_account = self._session.scalars(
                select(WhatsAppBusinessAccount).where(
                    WhatsAppBusinessAccount.account_id == session.account_id,
                    WhatsAppBusinessAccount.waba_id == session.provider_waba_id,
                )
            ).first()
            if waba_account is not None:
                return waba_account
        if session.waba_account_id is None:
            return None
        return self._session.get(WhatsAppBusinessAccount, session.waba_account_id)

    def _resolve_account_for_waba_account(
        self,
        waba_account: WhatsAppBusinessAccount | None,
    ) -> Account | None:
        if waba_account is None:
            return None
        if waba_account.account is not None:
            return waba_account.account
        return self._session.get(Account, waba_account.account_id)

    def _resolve_portfolio_for_waba_account(
        self,
        waba_account: WhatsAppBusinessAccount | None,
    ) -> MetaBusinessPortfolio | None:
        if waba_account is None:
            return None
        if waba_account.portfolio is not None:
            return waba_account.portfolio
        if waba_account.portfolio_id is None:
            return None
        return self._session.get(MetaBusinessPortfolio, waba_account.portfolio_id)

    @staticmethod
    def _build_scoped_webhook_path(*, account_id: str, waba_id: str) -> str:
        return f"{WHATSAPP_WEBHOOK_ROOT_PATH}/{account_id}/wabas/{waba_id}"

    @staticmethod
    def _mask_verify_token(verify_token: str) -> str:
        if len(verify_token) <= 4:
            return "*" * len(verify_token)
        return f"{verify_token[:2]}***{verify_token[-2:]}"

    @staticmethod
    def _is_effectively_webhook_subscribed(
        *,
        webhook_subscribed: bool,
        subscription_status: str | None,
    ) -> bool:
        return webhook_subscribed or subscription_status in {
            "mock_subscribed",
            "remote_subscribed",
            "subscribed",
        }

    def _is_webhook_delivery_ready(
        self,
        *,
        webhook_subscribed: bool,
        subscription_status: str | None,
        has_verify_token: bool,
        has_app_secret: bool,
        webhook_verification_status: str | None,
    ) -> bool:
        if not webhook_subscribed or not has_verify_token or not has_app_secret:
            return False
        provider_name = (self._settings.messaging_provider or "").strip().lower()
        if provider_name == "whatsapp":
            return (
                subscription_status == "remote_subscribed"
                and (webhook_verification_status or "pending") == "verified"
            )
        return subscription_status in {"mock_subscribed", "remote_subscribed", "subscribed"}

    @staticmethod
    def _build_waba_blocking_reasons(
        *,
        account_is_active: bool,
        is_active: bool,
        has_access_token: bool,
        has_verify_token: bool,
        has_app_secret: bool,
        webhook_subscribed: bool,
        ready_for_webhook_delivery: bool,
        phone_number_count: int,
        registered_phone_number_count: int,
    ) -> list[str]:
        reasons: list[str] = []
        if not account_is_active:
            reasons.append("account_inactive")
        if not is_active:
            reasons.append("waba_inactive")
        if not has_access_token:
            reasons.append("missing_access_token")
        if phone_number_count == 0:
            reasons.append("missing_phone_numbers")
        elif registered_phone_number_count == 0:
            reasons.append("missing_registered_phone_numbers")
        if not has_verify_token:
            reasons.append("missing_verify_token")
        if not has_app_secret:
            reasons.append("missing_app_secret")
        if not webhook_subscribed:
            reasons.append("missing_webhook_subscription")
        elif not ready_for_webhook_delivery:
            reasons.append("webhook_not_ready")
        return reasons

    @staticmethod
    def _build_embedded_signup_webhook_blocking_reasons(
        blocking_reasons: list[str],
    ) -> list[str]:
        webhook_only_reasons = {
            "account_inactive",
            "waba_inactive",
            "missing_verify_token",
            "missing_app_secret",
            "missing_webhook_subscription",
            "webhook_not_ready",
        }
        return [reason for reason in blocking_reasons if reason in webhook_only_reasons]

    @staticmethod
    def _build_phone_blocking_reasons(
        *,
        account_is_active: bool,
        waba_is_active: bool,
        has_access_token: bool,
        has_verify_token: bool,
        has_app_secret: bool,
        webhook_subscribed: bool,
        ready_for_webhook_delivery: bool,
        is_registered: bool,
        is_active: bool,
    ) -> list[str]:
        reasons: list[str] = []
        if not account_is_active:
            reasons.append("account_inactive")
        if not waba_is_active:
            reasons.append("waba_inactive")
        if not is_active:
            reasons.append("phone_inactive")
        if not has_access_token:
            reasons.append("missing_access_token")
        if not is_registered:
            reasons.append("phone_not_registered")
        if not has_verify_token:
            reasons.append("missing_verify_token")
        if not has_app_secret:
            reasons.append("missing_app_secret")
        if not webhook_subscribed:
            reasons.append("missing_webhook_subscription")
        elif not ready_for_webhook_delivery:
            reasons.append("webhook_not_ready")
        return reasons
