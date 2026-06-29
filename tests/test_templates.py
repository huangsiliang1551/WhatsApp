import asyncio
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_messaging_service, get_template_registry_service
from app.core.settings import Settings
from app.db.models import (
    Account,
    Conversation,
    MediaAsset,
    MediaAssetEvent,
    MediaAssetProviderSync,
    Message,
    MessageEvent,
    TemplateDailyStat,
    TemplateFailureStat,
    TemplateHourlyStat,
    ProviderStatusEventBuffer,
    TemplateSendLog,
    MessageTemplate,
    WhatsAppBusinessAccount,
    WhatsAppPhoneNumber,
    utc_now,
)
from app.providers.messaging.base import MessagingProvider
from app.providers.messaging.mock_provider import MockMessagingProvider
from app.providers.messaging.whatsapp_provider import WhatsAppProvider
from app.providers.template_registry.base import TemplateRegistryProvider
from app.providers.template_registry.mock_provider import MockTemplateRegistryProvider
from app.providers.template_registry.whatsapp_provider import WhatsAppTemplateRegistryProvider
from app.providers.translation.fallback_provider import FallbackTranslationProvider
from app.schemas.messaging import (
    MediaAssetSyncRequest,
    MediaAssetSyncResult,
    OutboundDispatchRequest,
    OutboundDispatchResult,
    ProviderStatusUpdate,
)
from app.schemas.template_registry import (
    TemplateRegistryRemoteTemplate,
    TemplateRegistrySubmitRequest,
    TemplateRegistrySubmitResult,
    TemplateRegistrySyncResult,
)
from app.schemas.templates import (
    TemplateDraftRequest,
    TemplateDraftUpdateRequest,
    TemplateSendRequest,
    TemplateStatusUpdateRequest,
    TemplateSyncRequest,
)
from app.services.runtime_state import RuntimeStateStore
from app.services.template_service import TemplateService
from app.services.template_stats_aggregator import TemplateStatsAggregator
from app.services.translation_service import TranslationService


def build_template_service(
    db_session_factory: sessionmaker[Session],
    messaging_provider: MessagingProvider | None = None,
    template_registry_provider: TemplateRegistryProvider | None = None,
) -> tuple[Session, RuntimeStateStore, TemplateService]:
    session = db_session_factory()
    settings = Settings.model_validate(
        {
            "TEST_MODE": True,
            "LIVE_TRANSLATION_ENABLED": False,
            "TRANSLATION_PROVIDER": "fallback",
        }
    )
    runtime_state = RuntimeStateStore(session)
    translation_service = TranslationService(
        settings=settings,
        provider=FallbackTranslationProvider(),
    )
    template_service = TemplateService(
        session=session,
        runtime_state=runtime_state,
        translation_service=translation_service,
        messaging_provider=messaging_provider or MockMessagingProvider(),
        template_registry_provider=template_registry_provider or MockTemplateRegistryProvider(),
    )
    return session, runtime_state, template_service


def get_provider_sync_reference(provider_sync: MediaAssetProviderSync) -> str | None:
    provider_media_id = getattr(provider_sync, "provider_media_id", None)
    if provider_media_id:
        return provider_media_id
    return provider_sync.meta_media_id


def create_waba(session: Session, account_id: str, waba_id: str) -> None:
    session.add(
        WhatsAppBusinessAccount(
            account_id=account_id,
            waba_id=waba_id,
            onboarding_mode="manual",
            token_source="system_user",
            access_token="token-placeholder",
            webhook_subscribed=False,
            is_active=True,
            ai_enabled=True,
        )
    )
    session.commit()


def create_phone_number(
    session: Session,
    *,
    account_id: str,
    waba_id: str,
    phone_number_id: str,
) -> None:
    waba_account = session.query(WhatsAppBusinessAccount).filter_by(
        account_id=account_id,
        waba_id=waba_id,
    ).one()
    session.add(
        WhatsAppPhoneNumber(
            account_id=account_id,
            waba_account_id=waba_account.id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            display_phone_number="+10000000000",
            verified_name="Template Test",
            quality_rating="GREEN",
            is_registered=True,
            is_active=True,
        )
    )
    session.commit()


def recreate_template_waba_row(
    session: Session,
    *,
    account_id: str,
    official_waba_id: str,
    phone_number_id: str,
    legacy_waba_id: str,
) -> WhatsAppBusinessAccount:
    legacy_waba = session.query(WhatsAppBusinessAccount).filter_by(
        account_id=account_id,
        waba_id=official_waba_id,
    ).one()
    legacy_waba.waba_id = legacy_waba_id
    session.flush()

    recreated_waba = WhatsAppBusinessAccount(
        account_id=account_id,
        portfolio_id=legacy_waba.portfolio_id,
        waba_id=official_waba_id,
        onboarding_mode=legacy_waba.onboarding_mode,
        token_source=legacy_waba.token_source,
        access_token=legacy_waba.access_token,
        verify_token=legacy_waba.verify_token,
        app_secret=legacy_waba.app_secret,
        webhook_subscribed=legacy_waba.webhook_subscribed,
        is_active=legacy_waba.is_active,
        ai_enabled=legacy_waba.ai_enabled,
    )
    session.add(recreated_waba)
    session.flush()

    phone_number = session.query(WhatsAppPhoneNumber).filter_by(
        account_id=account_id,
        phone_number_id=phone_number_id,
    ).one()
    phone_number.waba_account_id = recreated_waba.id
    phone_number.waba_id = official_waba_id
    return recreated_waba


def create_media_asset(
    session: Session,
    *,
    account_id: str,
    waba_id: str,
    phone_number_id: str | None,
    asset_id: str,
    name: str,
    asset_type: str,
    storage_url: str | None = None,
    storage_key: str | None = None,
    meta_media_id: str | None = None,
) -> None:
    phone_number = None
    if phone_number_id is not None:
        phone_number = (
            session.query(WhatsAppPhoneNumber)
            .join(WhatsAppPhoneNumber.waba_account)
            .filter(
                WhatsAppBusinessAccount.account_id == account_id,
                WhatsAppBusinessAccount.waba_id == waba_id,
                WhatsAppPhoneNumber.phone_number_id == phone_number_id,
            )
            .one()
        )
    session.add(
        MediaAsset(
            id=asset_id,
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number.id if phone_number is not None else None,
            name=name,
            asset_type=asset_type,
            mime_type="image/jpeg" if asset_type == "image" else "application/pdf",
            storage_url=storage_url,
            storage_key=storage_key,
            meta_media_id=meta_media_id,
            is_active=True,
        )
    )
    session.commit()


def delete_template_detail_aggregate_rows(
    session: Session,
    *,
    account_id: str,
    template_id: str,
) -> list[str]:
    deleted_tables: list[str] = []
    deleted_hourly = (
        session.query(TemplateHourlyStat)
        .filter(
            TemplateHourlyStat.account_id == account_id,
            TemplateHourlyStat.template_id == template_id,
        )
        .delete(synchronize_session=False)
    )
    if deleted_hourly:
        deleted_tables.append(TemplateHourlyStat.__tablename__)
    deleted_failures = (
        session.query(TemplateFailureStat)
        .filter(
            TemplateFailureStat.account_id == account_id,
            TemplateFailureStat.template_id == template_id,
        )
        .delete(synchronize_session=False)
    )
    if deleted_failures:
        deleted_tables.append(TemplateFailureStat.__tablename__)
    session.commit()
    return deleted_tables


class AcceptedWhatsAppLikeProvider(MessagingProvider):
    provider_name = "whatsapp"

    def __init__(self) -> None:
        self._message_counter = 0

    async def normalize_inbound(self, payload: object) -> list[object]:
        del payload
        return []

    async def normalize_status_updates(self, payload: object) -> list[ProviderStatusUpdate]:
        del payload
        return []

    async def send_outbound(self, payload: OutboundDispatchRequest) -> OutboundDispatchResult:
        self._message_counter += 1
        return OutboundDispatchResult(
            provider_name=self.provider_name,
            provider_message_id=f"wamid.test.approved.{self._message_counter}",
            accepted=True,
            external_status="accepted",
            raw_response={"recipient_id": payload.recipient_id},
        )

    async def sync_media_asset(self, payload: MediaAssetSyncRequest) -> MediaAssetSyncResult:
        existing_provider_media_id = payload.resolved_existing_provider_media_id
        return MediaAssetSyncResult(
            provider_name=self.provider_name,
            phone_number_id=payload.phone_number_id,
            waba_id=payload.waba_id,
            provider_media_id=existing_provider_media_id,
            sync_status="reused" if existing_provider_media_id else "failed",
            error_code=None if existing_provider_media_id else "missing_media_id",
            error_message=(
                None
                if existing_provider_media_id
                else "Accepted test provider expects an existing provider media id."
            ),
            raw_response={"asset_id": payload.asset_id},
        )

    async def download_media(
        self,
        *,
        media_id: str,
        access_token: str,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
    ) -> tuple[str, bytes, str]:
        return f"{media_id}.bin", b"mock-media-content", "application/octet-stream"


class RecordingAcceptedWhatsAppLikeProvider(AcceptedWhatsAppLikeProvider):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[OutboundDispatchRequest] = []

    async def send_outbound(self, payload: OutboundDispatchRequest) -> OutboundDispatchResult:
        self.requests.append(payload)
        return await super().send_outbound(payload)


class FailingTemplateProvider(MessagingProvider):
    provider_name = "mock"

    async def normalize_inbound(self, payload: object) -> list[object]:
        del payload
        return []

    async def normalize_status_updates(self, payload: object) -> list[ProviderStatusUpdate]:
        del payload
        return []

    async def send_outbound(self, payload: OutboundDispatchRequest) -> OutboundDispatchResult:
        del payload
        raise RuntimeError("provider_unavailable")

    async def sync_media_asset(self, payload: MediaAssetSyncRequest) -> MediaAssetSyncResult:
        del payload
        raise RuntimeError("provider_sync_unavailable")

    async def download_media(
        self,
        *,
        media_id: str,
        access_token: str,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
    ) -> tuple[str, bytes, str]:
        return f"{media_id}.bin", b"mock-media-content", "application/octet-stream"


class RecordingTemplateRegistryProvider(TemplateRegistryProvider):
    provider_name = "template_registry_mock"

    def __init__(
        self,
        *,
        submit_result: TemplateRegistrySubmitResult | None = None,
        sync_result: TemplateRegistrySyncResult | None = None,
    ) -> None:
        self._submit_result = submit_result
        self._sync_result = sync_result or TemplateRegistrySyncResult(
            provider_name=self.provider_name,
            templates=[],
        )
        self.submit_requests: list[TemplateRegistrySubmitRequest] = []
        self.sync_requests: list[dict[str, str | None]] = []

    async def submit_template(
        self,
        payload: TemplateRegistrySubmitRequest,
    ) -> TemplateRegistrySubmitResult:
        self.submit_requests.append(payload)
        if self._submit_result is not None:
            return self._submit_result

        remote_template = TemplateRegistryRemoteTemplate(
            provider_template_id="provider-template-default",
            name=payload.name,
            language=payload.language,
            category=payload.category,
            status="PENDING",
            components=payload.components,
            raw_payload={"name": payload.name},
        )
        return TemplateRegistrySubmitResult(
            provider_name=self.provider_name,
            action="submitted",
            remote_status="PENDING",
            provider_template_id=remote_template.provider_template_id,
            remote_template=remote_template,
            raw_response=remote_template.raw_payload,
        )

    async def sync_templates(
        self,
        *,
        account_id: str,
        waba_id: str,
        access_token: str | None,
    ) -> TemplateRegistrySyncResult:
        self.sync_requests.append(
            {
                "account_id": account_id,
                "waba_id": waba_id,
                "access_token": access_token,
            }
        )
        return self._sync_result


class FailingTemplateRegistryProvider(TemplateRegistryProvider):
    provider_name = "template_registry_failing"

    async def submit_template(
        self,
        payload: TemplateRegistrySubmitRequest,
    ) -> TemplateRegistrySubmitResult:
        del payload
        raise RuntimeError("template_registry_unavailable")

    async def sync_templates(
        self,
        *,
        account_id: str,
        waba_id: str,
        access_token: str | None,
    ) -> TemplateRegistrySyncResult:
        del account_id, waba_id, access_token
        raise RuntimeError("template_registry_sync_unavailable")


def register_template_route_account(
    client: TestClient,
    *,
    phone_numbers: list[dict[str, object]] | None = None,
) -> None:
    response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "template-route-account-1",
            "display_name": "Template Route Account",
            "meta_business_portfolio_id": "portfolio-template-route-1",
            "waba_id": "waba-template-route-1",
            "access_token": "token-template-route-1",
            "verify_token": "verify-template-route-1",
            "app_secret": "secret-template-route-1",
            "token_source": "system_user",
            "phone_numbers": phone_numbers
            or [
                {
                    "phone_number_id": "phone-template-route-1",
                    "display_phone_number": "+1 555 300 0001",
                    "verified_name": "Template Route",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert response.status_code == 200


def test_template_send_logs_expose_and_filter_external_conversation_id(
    client: TestClient,
) -> None:
    register_template_route_account(client)

    for conversation_id, user_id in (
        ("template-route-conv-external-a", "template-route-user-external-a"),
        ("template-route-conv-external-b", "template-route-user-external-b"),
    ):
        inbound_response = client.post(
            "/dev/mock/inbound-message",
            json={
                "account_id": "template-route-account-1",
                "conversation_id": conversation_id,
                "user_id": user_id,
                "text": "template send log clarity",
                "mode": "echo",
                "language_hint": "en",
                "phone_number_id": "phone-template-route-1",
            },
        )
        assert inbound_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_conversation_clarity",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, your update is ready.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    first_send_response = client.post(
        f"/api/templates/{template_id}/send",
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-conv-external-a",
            "variables": {"first_name": "Ana"},
        },
    )
    assert first_send_response.status_code == 200
    first_send = first_send_response.json()
    assert first_send["conversation_id"] == "template-route-conv-external-a"
    assert first_send["conversation_id"] == first_send["external_conversation_id"]
    assert first_send["external_conversation_id"] == "template-route-conv-external-a"
    assert first_send["internal_conversation_id"] != "template-route-conv-external-a"

    second_send_response = client.post(
        f"/api/templates/{template_id}/send",
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-conv-external-b",
            "variables": {"first_name": "Ben"},
        },
    )
    assert second_send_response.status_code == 200
    second_send = second_send_response.json()
    assert second_send["conversation_id"] == "template-route-conv-external-b"
    assert second_send["conversation_id"] == second_send["external_conversation_id"]
    assert second_send["internal_conversation_id"] != "template-route-conv-external-b"

    send_logs_response = client.get(
        "/api/templates/send-logs",
        params={"account_id": "template-route-account-1", "template_id": template_id},
    )
    assert send_logs_response.status_code == 200
    send_logs = send_logs_response.json()
    first_log = next(item for item in send_logs if item["message_id"] == first_send["message_id"])
    assert first_log["conversation_id"] == "template-route-conv-external-a"
    assert first_log["external_conversation_id"] == "template-route-conv-external-a"
    assert first_log["internal_conversation_id"] == first_send["internal_conversation_id"]
    for item in send_logs:
        assert item["conversation_id"] == item["external_conversation_id"]
        assert item["internal_conversation_id"]
        assert item["internal_conversation_id"] != item["external_conversation_id"]

    filtered_response = client.get(
        "/api/templates/send-logs",
        params={
            "account_id": "template-route-account-1",
            "template_id": template_id,
            "external_conversation_id": "template-route-conv-external-a",
        },
    )
    assert filtered_response.status_code == 200
    filtered_logs = filtered_response.json()
    assert [item["message_id"] for item in filtered_logs] == [first_send["message_id"]]
    assert filtered_logs[0]["conversation_id"] == filtered_logs[0]["external_conversation_id"]
    assert filtered_logs[0]["internal_conversation_id"] == first_send["internal_conversation_id"]

    compatibility_alias_response = client.get(
        "/api/templates/send-logs",
        params={
            "account_id": "template-route-account-1",
            "template_id": template_id,
            "conversation_id": "template-route-conv-external-a",
        },
    )
    assert compatibility_alias_response.status_code == 200
    compatibility_alias_logs = compatibility_alias_response.json()
    assert [item["message_id"] for item in compatibility_alias_logs] == [first_send["message_id"]]

    internal_filtered_response = client.get(
        "/api/templates/send-logs",
        params={
            "account_id": "template-route-account-1",
            "template_id": template_id,
            "internal_conversation_id": first_send["internal_conversation_id"],
        },
    )
    assert internal_filtered_response.status_code == 200
    internal_filtered_logs = internal_filtered_response.json()
    assert [item["message_id"] for item in internal_filtered_logs] == [first_send["message_id"]]

    combined_match_response = client.get(
        "/api/templates/send-logs",
        params={
            "account_id": "template-route-account-1",
            "template_id": template_id,
            "conversation_id": "template-route-conv-external-a",
            "internal_conversation_id": first_send["internal_conversation_id"],
        },
    )
    assert combined_match_response.status_code == 200
    combined_match_logs = combined_match_response.json()
    assert [item["message_id"] for item in combined_match_logs] == [first_send["message_id"]]

    compatible_duplicate_alias_response = client.get(
        "/api/templates/send-logs",
        params={
            "account_id": "template-route-account-1",
            "template_id": template_id,
            "conversation_id": "template-route-conv-external-a",
            "external_conversation_id": "template-route-conv-external-a",
        },
    )
    assert compatible_duplicate_alias_response.status_code == 200
    compatible_duplicate_alias_logs = compatible_duplicate_alias_response.json()
    assert [item["message_id"] for item in compatible_duplicate_alias_logs] == [first_send["message_id"]]

    combined_mismatch_response = client.get(
        "/api/templates/send-logs",
        params={
            "account_id": "template-route-account-1",
            "template_id": template_id,
            "conversation_id": "template-route-conv-external-a",
            "internal_conversation_id": second_send_response.json()["internal_conversation_id"],
        },
    )
    assert combined_mismatch_response.status_code == 200
    assert combined_mismatch_response.json() == []

    conflict_response = client.get(
        "/api/templates/send-logs",
        params={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-conv-external-b",
            "external_conversation_id": "template-route-conv-external-a",
        },
    )
    assert conflict_response.status_code == 400


def test_template_send_logs_keep_official_waba_scope_after_local_waba_row_recreation(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_template_route_account(client)

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-conv-recreated-waba",
            "user_id": "template-route-user-recreated-waba",
            "text": "template send log recreated waba",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "phone-template-route-1",
        },
    )
    assert inbound_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_recreated_waba_send_log",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, recreated WABA logs stay scoped.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    send_response = client.post(
        f"/api/templates/{template_id}/send",
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-conv-recreated-waba",
            "variables": {"first_name": "Ana"},
        },
    )
    assert send_response.status_code == 200
    send_payload = send_response.json()

    session = db_session_factory()
    try:
        recreated_waba = recreate_template_waba_row(
            session,
            account_id="template-route-account-1",
            official_waba_id="waba-template-route-1",
            phone_number_id="phone-template-route-1",
            legacy_waba_id="waba-template-route-1-legacy",
        )
        stored_template = session.query(MessageTemplate).filter_by(id=template_id).one()
        stored_template.waba_account_id = recreated_waba.id
        session.commit()
    finally:
        session.close()

    send_logs_response = client.get(
        "/api/templates/send-logs",
        params={
            "account_id": "template-route-account-1",
            "template_id": template_id,
            "waba_id": "waba-template-route-1",
        },
    )
    assert send_logs_response.status_code == 200
    send_logs = send_logs_response.json()
    assert [item["message_id"] for item in send_logs] == [send_payload["message_id"]]
    assert send_logs[0]["waba_id"] == "waba-template-route-1"
    assert send_logs[0]["external_conversation_id"] == "template-route-conv-recreated-waba"

    legacy_logs_response = client.get(
        "/api/templates/send-logs",
        params={
            "account_id": "template-route-account-1",
            "template_id": template_id,
            "waba_id": "waba-template-route-1-legacy",
        },
    )
    assert legacy_logs_response.status_code == 400
    assert "bound to WABA 'waba-template-route-1'" in str(
        legacy_logs_response.json()["detail"]
    )


def test_template_send_route_rejects_non_assigned_agent(client: TestClient) -> None:
    register_template_route_account(client)

    for agent_id in ("agent-template-route-owner", "agent-template-route-other"):
        agent_response = client.post(
            "/api/runtime/agents",
            json={
                "account_id": "template-route-account-1",
                "agent_id": agent_id,
                "display_name": agent_id,
                "status": "online",
                "is_active": True,
            },
        )
        assert agent_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-assigned-conv-1",
            "user_id": "template-route-assigned-user-1",
            "text": "send template",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "phone-template-route-1",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/template-route-account-1/template-route-assigned-conv-1/assignment",
        json={
            "agent_id": "agent-template-route-owner",
            "assigned_by_agent_id": "agent-template-route-owner",
            "reason": "template_reply",
        },
    )
    assert assignment_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "assigned_agent_notice",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, your update is ready.",
            "sample_variables": {"first_name": "Ana"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    send_response = client.post(
        f"/api/templates/{template_id}/send",
        headers={
            "X-Actor-Id": "agent-template-route-other",
            "X-Actor-Role": "support_agent",
            "X-Actor-Account-Ids": "template-route-account-1",
        },
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-assigned-conv-1",
            "variables": {"first_name": "Ana"},
            "agent_id": "agent-template-route-other",
        },
    )
    assert send_response.status_code == 403
    assert "assigned to 'agent-template-route-owner'" in send_response.json()["detail"]


def test_template_send_route_rejects_non_assigned_agent_when_agent_id_is_omitted(
    client: TestClient,
) -> None:
    register_template_route_account(client)

    for agent_id in ("agent-template-route-owner-implicit", "agent-template-route-other-implicit"):
        agent_response = client.post(
            "/api/runtime/agents",
            json={
                "account_id": "template-route-account-1",
                "agent_id": agent_id,
                "display_name": agent_id,
                "status": "online",
                "is_active": True,
            },
        )
        assert agent_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-assigned-conv-implicit-1",
            "user_id": "template-route-assigned-user-implicit-1",
            "text": "send template without explicit agent id",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "phone-template-route-1",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/template-route-account-1/template-route-assigned-conv-implicit-1/assignment",
        json={
            "agent_id": "agent-template-route-owner-implicit",
            "assigned_by_agent_id": "agent-template-route-owner-implicit",
            "reason": "template_reply",
        },
    )
    assert assignment_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "assigned_agent_notice_implicit",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, your update is ready.",
            "sample_variables": {"first_name": "Ana"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    send_response = client.post(
        f"/api/templates/{template_id}/send",
        headers={
            "X-Actor-Id": "agent-template-route-other-implicit",
            "X-Actor-Role": "support_agent",
            "X-Actor-Account-Ids": "template-route-account-1",
        },
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-assigned-conv-implicit-1",
            "variables": {"first_name": "Ana"},
        },
    )
    assert send_response.status_code == 403
    assert "assigned to 'agent-template-route-owner-implicit'" in send_response.json()["detail"]


def test_template_send_route_allows_assigned_agent_when_agent_id_is_omitted(
    client: TestClient,
) -> None:
    register_template_route_account(client)

    agent_response = client.post(
        "/api/runtime/agents",
        json={
            "account_id": "template-route-account-1",
            "agent_id": "agent-template-route-owner-implicit-ok",
            "display_name": "agent-template-route-owner-implicit-ok",
            "status": "online",
            "is_active": True,
        },
    )
    assert agent_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-assigned-conv-implicit-ok-1",
            "user_id": "template-route-assigned-user-implicit-ok-1",
            "text": "send template as assigned agent without explicit agent id",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "phone-template-route-1",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/template-route-account-1/template-route-assigned-conv-implicit-ok-1/assignment",
        json={
            "agent_id": "agent-template-route-owner-implicit-ok",
            "assigned_by_agent_id": "agent-template-route-owner-implicit-ok",
            "reason": "template_reply",
        },
    )
    assert assignment_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "assigned_agent_notice_implicit_ok",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, your update is ready.",
            "sample_variables": {"first_name": "Ana"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    send_response = client.post(
        f"/api/templates/{template_id}/send",
        headers={
            "X-Actor-Id": "agent-template-route-owner-implicit-ok",
            "X-Actor-Role": "support_agent",
            "X-Actor-Account-Ids": "template-route-account-1",
        },
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-assigned-conv-implicit-ok-1",
            "variables": {"first_name": "Ana"},
        },
    )
    assert send_response.status_code == 200
    assert send_response.json()["account_id"] == "template-route-account-1"


def test_template_send_route_returns_503_for_missing_whatsapp_access_token(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    client.app.dependency_overrides[get_messaging_service] = lambda: WhatsAppProvider()
    register_template_route_account(client)

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-missing-token-conv",
            "user_id": "template-route-missing-token-user",
            "text": "send template",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "phone-template-route-1",
        },
    )
    assert inbound_response.status_code == 200

    create_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_send_missing_token",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, this send requires a token.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert create_response.status_code == 200
    template_id = create_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    with db_session_factory() as session:
        waba_account = session.query(WhatsAppBusinessAccount).filter_by(
            account_id="template-route-account-1",
            waba_id="waba-template-route-1",
        ).one()
        waba_account.access_token = None
        session.commit()

    send_response = client.post(
        f"/api/templates/{template_id}/send",
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-missing-token-conv",
            "variables": {"first_name": "Ana"},
        },
    )

    assert send_response.status_code == 503
    assert "access token" in send_response.json()["detail"].lower()


def test_template_send_route_returns_502_for_provider_runtime_failure(
    client: TestClient,
) -> None:
    client.app.dependency_overrides[get_messaging_service] = lambda: FailingTemplateProvider()
    register_template_route_account(client)

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-provider-failure-conv",
            "user_id": "template-route-provider-failure-user",
            "text": "send template",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "phone-template-route-1",
        },
    )
    assert inbound_response.status_code == 200

    create_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_send_provider_failure",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, this send should surface provider failure.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert create_response.status_code == 200
    template_id = create_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    send_response = client.post(
        f"/api/templates/{template_id}/send",
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-provider-failure-conv",
            "variables": {"first_name": "Ana"},
        },
    )

    assert send_response.status_code == 502
    assert send_response.json()["detail"] == "Template send failed: provider_unavailable"


def test_template_service_creates_drafts_and_lists_with_filters(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(db_session_factory)

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-1",
                display_name="Template Account 1",
                provider_type="whatsapp",
            )
        )
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-2",
                display_name="Template Account 2",
                provider_type="whatsapp",
            )
        )
        create_waba(session, account_id="template-account-1", waba_id="waba-template-1")

        first_template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-1",
                    waba_id="waba-template-1",
                    name="order_ready",
                    language="en",
                    category="UTILITY",
                    body_text="Hello {{first_name}}, your order {{order_id}} is ready.",
                    header_text="Order update",
                    footer_text="Reply STOP to opt out.",
                    sample_variables={"first_name": "Customer", "order_id": "A-100"},
                )
            )
        )
        second_template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-2",
                    name="bonjour_offer",
                    language="fr",
                    category="MARKETING",
                    body_text="Bonjour {{first_name}}, nouvelle offre disponible.",
                    sample_variables={"first_name": "Client"},
                )
            )
        )

        updated_template = asyncio.run(
            template_service.update_template_status(
                first_template.template_id,
                TemplateStatusUpdateRequest(
                    status="APPROVED",
                    meta_template_id="meta-template-1",
                ),
            )
        )

        account_templates = asyncio.run(
            template_service.list_templates(account_id="template-account-1")
        )
        approved_templates = asyncio.run(template_service.list_templates(status="APPROVED"))
        french_templates = asyncio.run(template_service.list_templates(language="fr"))
        create_logs = asyncio.run(
            runtime_state.list_audit_logs(
                account_id="template-account-1",
                action="template_draft_created",
            )
        )
        status_logs = asyncio.run(
            runtime_state.list_audit_logs(
                account_id="template-account-1",
                action="template_status_updated",
            )
        )
        stored_first_template = session.query(MessageTemplate).filter_by(id=first_template.template_id).one()

        assert first_template.status == "DRAFT"
        assert first_template.waba_id == "waba-template-1"
        assert stored_first_template.waba_id == "waba-template-1"
        assert first_template.body_text == "Hello {{first_name}}, your order {{order_id}} is ready."
        assert first_template.header_text == "Order update"
        assert first_template.footer_text == "Reply STOP to opt out."
        assert first_template.sample_variables == {"first_name": "Customer", "order_id": "A-100"}
        assert updated_template.status == "APPROVED"
        assert updated_template.meta_template_id == "meta-template-1"
        assert {item.template_id for item in account_templates} == {first_template.template_id}
        assert {item.template_id for item in approved_templates} == {first_template.template_id}
        assert {item.template_id for item in french_templates} == {second_template.template_id}
        assert len(create_logs) == 1
        assert create_logs[0].target_id == "order_ready"
        assert len(status_logs) == 1
        assert status_logs[0].target_id == first_template.template_id
    finally:
        session.close()


def test_template_service_creates_draft_with_header_media_binding(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(db_session_factory)

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-media-draft",
                display_name="Template Media Draft Account",
                provider_type="whatsapp",
            )
        )
        create_waba(session, account_id="template-account-media-draft", waba_id="waba-template-media")
        create_media_asset(
            session,
            account_id="template-account-media-draft",
            waba_id="waba-template-media",
            phone_number_id=None,
            asset_id="asset-template-header-1",
            name="shipping-banner",
            asset_type="image",
            storage_url="https://cdn.example.com/shipping-banner.jpg",
            meta_media_id="meta-shipping-banner-1",
        )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-media-draft",
                    waba_id="waba-template-media",
                    name="shipping_media_template",
                    language="en",
                    category="UTILITY",
                    body_text="Hello {{first_name}}, your order is ready.",
                    header_media_asset_id="asset-template-header-1",
                    sample_variables={"first_name": "Customer"},
                )
            )
        )

        assert template.header_text is None
        assert template.header_media_asset_id == "asset-template-header-1"
        assert template.header_media_asset_name == "shipping-banner"
        assert template.header_media_asset_type == "image"
    finally:
        session.close()


def test_template_service_updates_draft_and_tracks_audit(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(db_session_factory)

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-draft-update",
                display_name="Template Draft Update Account",
                provider_type="whatsapp",
            )
        )
        create_waba(
            session,
            account_id="template-account-draft-update",
            waba_id="waba-template-update-1",
        )
        create_waba(
            session,
            account_id="template-account-draft-update",
            waba_id="waba-template-update-2",
        )
        create_media_asset(
            session,
            account_id="template-account-draft-update",
            waba_id="waba-template-update-2",
            phone_number_id=None,
            asset_id="asset-template-update-header-1",
            name="updated-header",
            asset_type="image",
            storage_url="https://cdn.example.com/updated-header.jpg",
            meta_media_id="meta-updated-header-1",
        )

        draft = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-draft-update",
                    waba_id="waba-template-update-1",
                    name="shipping_draft",
                    language="en",
                    category="UTILITY",
                    body_text="Hello {{first_name}}, shipping starts soon.",
                    header_text="Original header",
                    footer_text="Original footer",
                    sample_variables={"first_name": "Customer"},
                )
            )
        )

        updated = asyncio.run(
            template_service.update_template_draft(
                draft.template_id,
                TemplateDraftUpdateRequest(
                    waba_id="waba-template-update-2",
                    name="shipping_draft_v2",
                    language="pt_BR",
                    category="MARKETING",
                    body_text="Ola {{first_name}}, seu pedido {{order_id}} saiu para entrega.",
                    header_text=None,
                    header_media_asset_id="asset-template-update-header-1",
                    header_media_handle="header-handle-1",
                    footer_text=None,
                    sample_variables={
                        "first_name": "Cliente",
                        "order_id": "SO-20001",
                    },
                ),
            )
        )
        update_logs = asyncio.run(
            runtime_state.list_audit_logs(
                account_id="template-account-draft-update",
                action="template_draft_updated",
            )
        )
        updated_template = session.query(MessageTemplate).filter_by(id=draft.template_id).one()

        assert updated.waba_id == "waba-template-update-2"
        assert updated_template.waba_id == "waba-template-update-2"
        assert updated.name == "shipping_draft_v2"
        assert updated.language == "pt_BR"
        assert updated.category == "MARKETING"
        assert updated.body_text == "Ola {{first_name}}, seu pedido {{order_id}} saiu para entrega."
        assert updated.header_text is None
        assert updated.header_media_asset_id == "asset-template-update-header-1"
        assert updated.header_media_asset_name == "updated-header"
        assert updated.header_media_asset_type == "image"
        assert updated.header_media_handle == "header-handle-1"
        assert updated.footer_text is None
        assert updated.sample_variables == {
            "first_name": "Cliente",
            "order_id": "SO-20001",
        }
        assert len(update_logs) == 1
        assert update_logs[0].target_id == draft.template_id
        assert update_logs[0].payload["waba_id"] == "waba-template-update-2"
        assert update_logs[0].payload["header_media_asset_id"] == "asset-template-update-header-1"
        assert update_logs[0].payload["updated_fields"] == [
            "body_text",
            "category",
            "footer_text",
            "header_media_asset_id",
            "header_media_handle",
            "header_text",
            "language",
            "name",
            "sample_variables",
            "waba_id",
        ]
    finally:
        session.close()


def test_template_service_rejects_draft_update_for_non_draft_status(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(db_session_factory)

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-draft-lock",
                display_name="Template Draft Lock Account",
                provider_type="whatsapp",
            )
        )
        draft = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-draft-lock",
                    name="lock_me",
                    language="en",
                    category="UTILITY",
                    body_text="Hello {{first_name}}.",
                    sample_variables={"first_name": "Customer"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                draft.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )

        with pytest.raises(ValueError, match="can no longer be edited as a draft"):
            asyncio.run(
                template_service.update_template_draft(
                    draft.template_id,
                    TemplateDraftUpdateRequest(body_text="Updated body."),
                )
            )
    finally:
        session.close()


def test_template_service_validates_waba_scope_when_updating_draft_header_media(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(db_session_factory)

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-draft-scope",
                display_name="Template Draft Scope Account",
                provider_type="whatsapp",
            )
        )
        create_waba(
            session,
            account_id="template-account-draft-scope",
            waba_id="waba-template-scope-1",
        )
        create_waba(
            session,
            account_id="template-account-draft-scope",
            waba_id="waba-template-scope-2",
        )
        create_media_asset(
            session,
            account_id="template-account-draft-scope",
            waba_id="waba-template-scope-2",
            phone_number_id=None,
            asset_id="asset-template-scope-header-1",
            name="scope-header",
            asset_type="image",
            storage_url="https://cdn.example.com/scope-header.jpg",
            meta_media_id="meta-scope-header-1",
        )
        draft = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-draft-scope",
                    waba_id="waba-template-scope-1",
                    name="scope_template",
                    language="en",
                    category="UTILITY",
                    body_text="Body",
                )
            )
        )

        with pytest.raises(ValueError, match="is bound to WABA 'waba-template-scope-2'"):
            asyncio.run(
                template_service.update_template_draft(
                    draft.template_id,
                    TemplateDraftUpdateRequest(
                        header_media_asset_id="asset-template-scope-header-1",
                    ),
                )
            )
    finally:
        session.close()


def test_template_service_rejects_cross_account_header_media_asset(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(db_session_factory)

    try:
        for account_id in ("template-header-scope-a", "template-header-scope-b"):
            asyncio.run(
                runtime_state.ensure_account(
                    account_id=account_id,
                    display_name=account_id,
                    provider_type="whatsapp",
                )
            )
        create_waba(
            session,
            account_id="template-header-scope-a",
            waba_id="waba-template-header-scope-a",
        )
        create_waba(
            session,
            account_id="template-header-scope-b",
            waba_id="waba-template-header-scope-b",
        )
        create_media_asset(
            session,
            account_id="template-header-scope-b",
            waba_id="waba-template-header-scope-b",
            phone_number_id=None,
            asset_id="asset-template-header-scope-b",
            name="cross-account-header",
            asset_type="image",
            storage_url="https://cdn.example.com/cross-account-header.jpg",
            meta_media_id="meta-cross-account-header",
        )

        with pytest.raises(ValueError, match="does not belong to account 'template-header-scope-a'"):
            asyncio.run(
                template_service.create_template_draft(
                    TemplateDraftRequest(
                        account_id="template-header-scope-a",
                        waba_id="waba-template-header-scope-a",
                        name="cross_account_header_create",
                        language="en",
                        category="UTILITY",
                        body_text="Body",
                        header_media_asset_id="asset-template-header-scope-b",
                    )
                )
            )

        draft = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-header-scope-a",
                    waba_id="waba-template-header-scope-a",
                    name="cross_account_header_update",
                    language="en",
                    category="UTILITY",
                    body_text="Body",
                )
            )
        )

        with pytest.raises(ValueError, match="does not belong to account 'template-header-scope-a'"):
            asyncio.run(
                template_service.update_template_draft(
                    draft.template_id,
                    TemplateDraftUpdateRequest(
                        header_media_asset_id="asset-template-header-scope-b",
                    ),
                )
            )
    finally:
        session.close()


def test_template_service_submit_updates_lifecycle_fields(
    db_session_factory: sessionmaker[Session],
) -> None:
    registry_provider = RecordingTemplateRegistryProvider(
        submit_result=TemplateRegistrySubmitResult(
            provider_name="template_registry_mock",
            action="submitted",
            remote_status="PENDING",
            provider_template_id="meta-template-submit-1",
            remote_template=TemplateRegistryRemoteTemplate(
                provider_template_id="meta-template-submit-1",
                name="delivery_notice",
                language="en",
                category="UTILITY",
                status="PENDING",
                components={
                    "body_text": "Delivery update for {{order_id}}",
                    "header_text": "Shipment notice",
                    "footer_text": "Reply HELP for support.",
                    "sample_variables": {"order_id": "A-100"},
                },
                raw_payload={"id": "meta-template-submit-1", "status": "PENDING"},
            ),
            raw_response={"id": "meta-template-submit-1", "status": "PENDING"},
        )
    )
    session, runtime_state, template_service = build_template_service(
        db_session_factory,
        template_registry_provider=registry_provider,
    )

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-submit",
                display_name="Template Submit Account",
                provider_type="whatsapp",
            )
        )
        create_waba(
            session,
            account_id="template-account-submit",
            waba_id="waba-template-submit",
        )
        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-submit",
                    waba_id="waba-template-submit",
                    name="delivery_notice",
                    language="en",
                    category="UTILITY",
                    body_text="Delivery update for {{order_id}}",
                    header_text="Shipment notice",
                    footer_text="Reply HELP for support.",
                    sample_variables={"order_id": "A-100"},
                )
            )
        )

        response = asyncio.run(template_service.submit_template(template.template_id))
        stored_template = session.query(MessageTemplate).filter_by(id=template.template_id).one()
        audit_logs = asyncio.run(
            runtime_state.list_audit_logs(
                account_id="template-account-submit",
                action="template_submitted",
            )
        )

        assert response.provider == "template_registry_mock"
        assert response.action == "submitted"
        assert response.remote_status == "PENDING"
        assert response.template.template_id == template.template_id
        assert response.template.status == "PENDING"
        assert response.template.meta_template_id == "meta-template-submit-1"
        assert response.template.submitted_at is not None
        assert response.template.last_synced_at is not None
        assert registry_provider.submit_requests[0].account_id == "template-account-submit"
        assert registry_provider.submit_requests[0].waba_id == "waba-template-submit"
        assert registry_provider.submit_requests[0].access_token == "token-placeholder"
        assert registry_provider.submit_requests[0].components["body_text"] == "Delivery update for {{order_id}}"
        assert stored_template.meta_template_id == "meta-template-submit-1"
        assert stored_template.status == "PENDING"
        assert stored_template.submitted_at is not None
        assert stored_template.last_synced_at is not None
        assert stored_template.provider_template_payload == {
            "id": "meta-template-submit-1",
            "status": "PENDING",
        }
        assert len(audit_logs) == 1
        assert audit_logs[0].target_id == template.template_id
        assert audit_logs[0].payload["provider"] == "template_registry_mock"
        assert audit_logs[0].payload["meta_template_id"] == "meta-template-submit-1"
        assert audit_logs[0].payload["remote_status"] == "PENDING"
    finally:
        session.close()


def test_template_service_submit_rejects_non_draft_template(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(
        db_session_factory,
    )

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-submit-once",
                display_name="Template Submit Once Account",
                provider_type="whatsapp",
            )
        )
        create_waba(
            session,
            account_id="template-account-submit-once",
            waba_id="waba-template-submit-once",
        )
        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-submit-once",
                    waba_id="waba-template-submit-once",
                    name="delivery_notice_submit_once",
                    language="en",
                    category="UTILITY",
                    body_text="Delivery update for {{order_id}}",
                    sample_variables={"order_id": "A-100"},
                )
            )
        )

        first_submit = asyncio.run(template_service.submit_template(template.template_id))
        assert first_submit.template.status == "PENDING"

        with pytest.raises(ValueError, match="cannot be submitted again"):
            asyncio.run(template_service.submit_template(template.template_id))
    finally:
        session.close()


def test_template_service_submit_includes_header_media_component_metadata(
    db_session_factory: sessionmaker[Session],
) -> None:
    registry_provider = RecordingTemplateRegistryProvider()
    session, runtime_state, template_service = build_template_service(
        db_session_factory,
        template_registry_provider=registry_provider,
    )

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-submit-media",
                display_name="Template Submit Media Account",
                provider_type="whatsapp",
            )
        )
        create_waba(
            session,
            account_id="template-account-submit-media",
            waba_id="waba-template-submit-media",
        )
        create_media_asset(
            session,
            account_id="template-account-submit-media",
            waba_id="waba-template-submit-media",
            phone_number_id=None,
            asset_id="asset-template-submit-media",
            name="header-banner",
            asset_type="image",
            storage_url="https://cdn.example.com/header-banner.jpg",
        )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-submit-media",
                    waba_id="waba-template-submit-media",
                    name="delivery_notice_media",
                    language="en",
                    category="UTILITY",
                    body_text="Delivery update for {{order_id}}",
                    header_media_asset_id="asset-template-submit-media",
                    header_media_handle="4::example-media-handle",
                    sample_variables={"order_id": "A-100"},
                )
            )
        )

        asyncio.run(template_service.submit_template(template.template_id))

        assert len(registry_provider.submit_requests) == 1
        assert registry_provider.submit_requests[0].components["header_media_asset_type"] == "image"
        assert registry_provider.submit_requests[0].components["header_media_handle"] == (
            "4::example-media-handle"
        )
    finally:
        session.close()


def test_template_service_sync_imports_missing_templates(
    db_session_factory: sessionmaker[Session],
) -> None:
    registry_provider = RecordingTemplateRegistryProvider(
        sync_result=TemplateRegistrySyncResult(
            provider_name="template_registry_mock",
            templates=[
                TemplateRegistryRemoteTemplate(
                    provider_template_id="meta-sync-import-1",
                    name="order_ready",
                    language="en",
                    category="UTILITY",
                    status="APPROVED",
                    components={
                        "body_text": "Order {{order_id}} is ready.",
                        "header_text": "Order update",
                        "footer_text": "Reply STOP to opt out.",
                        "sample_variables": {"order_id": "A-100"},
                    },
                    raw_payload={"id": "meta-sync-import-1", "name": "order_ready"},
                ),
                TemplateRegistryRemoteTemplate(
                    provider_template_id="meta-sync-import-2",
                    name="expedition_status",
                    language="fr",
                    category="MARKETING",
                    status="PENDING",
                    components={
                        "body_text": "Commande {{order_id}} en preparation.",
                        "header_media_type": "image",
                        "header_media_handle": "4::remote-media-handle",
                        "sample_variables": {"order_id": "FR-100"},
                    },
                    raw_payload={"id": "meta-sync-import-2", "name": "expedition_status"},
                ),
            ],
        )
    )
    session, runtime_state, template_service = build_template_service(
        db_session_factory,
        template_registry_provider=registry_provider,
    )

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-sync-import",
                display_name="Template Sync Import Account",
                provider_type="whatsapp",
            )
        )
        create_waba(
            session,
            account_id="template-account-sync-import",
            waba_id="waba-template-sync-import",
        )

        response = asyncio.run(
            template_service.sync_templates(
                TemplateSyncRequest(
                    account_id="template-account-sync-import",
                    waba_id="waba-template-sync-import",
                    import_missing=True,
                )
            )
        )
        stored_templates = asyncio.run(
            template_service.list_templates(account_id="template-account-sync-import")
        )
        audit_logs = asyncio.run(
            runtime_state.list_audit_logs(
                account_id="template-account-sync-import",
                action="template_sync_completed",
            )
        )

        assert response.provider == "template_registry_mock"
        assert response.account_id == "template-account-sync-import"
        assert response.waba_id == "waba-template-sync-import"
        assert response.created_count == 2
        assert response.updated_count == 0
        assert response.skipped_count == 0
        assert len(response.templates) == 2
        assert registry_provider.sync_requests == [
            {
                "account_id": "template-account-sync-import",
                "waba_id": "waba-template-sync-import",
                "access_token": "token-placeholder",
            }
        ]
        by_name = {item.name: item for item in stored_templates}
        assert set(by_name) == {"order_ready", "expedition_status"}
        assert by_name["order_ready"].meta_template_id == "meta-sync-import-1"
        assert by_name["order_ready"].status == "APPROVED"
        assert by_name["order_ready"].header_text == "Order update"
        assert by_name["order_ready"].footer_text == "Reply STOP to opt out."
        assert by_name["order_ready"].last_synced_at is not None
        assert by_name["expedition_status"].meta_template_id == "meta-sync-import-2"
        assert by_name["expedition_status"].status == "PENDING"
        assert by_name["expedition_status"].body_text == "Commande {{order_id}} en preparation."
        assert by_name["expedition_status"].header_media_asset_type == "image"
        assert by_name["expedition_status"].header_media_handle == "4::remote-media-handle"
        assert len(audit_logs) == 1
        assert audit_logs[0].payload["created_count"] == 2
        assert audit_logs[0].payload["updated_count"] == 0
        assert audit_logs[0].payload["skipped_count"] == 0
        assert audit_logs[0].payload["import_missing"] is True
        assert {item.waba_id for item in stored_templates} == {"waba-template-sync-import"}
    finally:
        session.close()


def test_template_service_sync_updates_existing_template(
    db_session_factory: sessionmaker[Session],
) -> None:
    registry_provider = RecordingTemplateRegistryProvider(
        sync_result=TemplateRegistrySyncResult(
            provider_name="template_registry_mock",
            templates=[
                TemplateRegistryRemoteTemplate(
                    provider_template_id="meta-template-existing",
                    name="shipping_update",
                    language="en",
                    category="MARKETING",
                    status="REJECTED",
                    rejected_reason="policy_violation",
                    components={
                        "body_text": "Updated remote body for {{order_id}}",
                        "header_text": "Remote header",
                        "footer_text": "Remote footer",
                        "sample_variables": {"order_id": "A-999"},
                    },
                    raw_payload={"id": "meta-template-existing", "status": "REJECTED"},
                )
            ],
        )
    )
    session, runtime_state, template_service = build_template_service(
        db_session_factory,
        template_registry_provider=registry_provider,
    )

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-sync-update",
                display_name="Template Sync Update Account",
                provider_type="whatsapp",
            )
        )
        create_waba(
            session,
            account_id="template-account-sync-update",
            waba_id="waba-template-sync-update",
        )
        local_template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-sync-update",
                    waba_id="waba-template-sync-update",
                    name="shipping_update",
                    language="en",
                    category="UTILITY",
                    body_text="Local body {{order_id}}",
                    header_text="Local header",
                    footer_text="Local footer",
                    sample_variables={"order_id": "A-100"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                local_template.template_id,
                TemplateStatusUpdateRequest(
                    status="PENDING",
                    meta_template_id="meta-template-existing",
                ),
            )
        )

        response = asyncio.run(
            template_service.sync_templates(
                TemplateSyncRequest(
                    account_id="template-account-sync-update",
                    waba_id="waba-template-sync-update",
                    import_missing=True,
                )
            )
        )
        updated_template = session.query(MessageTemplate).filter_by(id=local_template.template_id).one()
        audit_logs = asyncio.run(
            runtime_state.list_audit_logs(
                account_id="template-account-sync-update",
                action="template_sync_completed",
            )
        )

        assert response.created_count == 0
        assert response.updated_count == 1
        assert response.skipped_count == 0
        assert len(response.templates) == 1
        assert response.templates[0].template_id == local_template.template_id
        assert response.templates[0].status == "REJECTED"
        assert response.templates[0].meta_template_id == "meta-template-existing"
        assert response.templates[0].body_text == "Updated remote body for {{order_id}}"
        assert response.templates[0].header_text == "Remote header"
        assert response.templates[0].footer_text == "Remote footer"
        assert response.templates[0].rejected_reason == "policy_violation"
        assert response.templates[0].last_synced_at is not None
        assert updated_template.category == "MARKETING"
        assert updated_template.status == "REJECTED"
        assert updated_template.waba_id == "waba-template-sync-update"
        assert updated_template.rejected_reason == "policy_violation"
        assert updated_template.components == {
            "body_text": "Updated remote body for {{order_id}}",
            "header_text": "Remote header",
            "footer_text": "Remote footer",
            "sample_variables": {"order_id": "A-999"},
        }
        assert updated_template.last_synced_at is not None
        assert updated_template.provider_template_payload == {
            "id": "meta-template-existing",
            "status": "REJECTED",
        }
        assert len(audit_logs) == 1
        assert audit_logs[0].payload["created_count"] == 0
        assert audit_logs[0].payload["updated_count"] == 1
        assert audit_logs[0].payload["skipped_count"] == 0
    finally:
        session.close()


def test_template_service_uses_template_waba_snapshot_after_relationship_drift(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(db_session_factory)

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-snapshot",
                display_name="Template Snapshot Account",
                provider_type="whatsapp",
            )
        )
        create_waba(
            session,
            account_id="template-account-snapshot",
            waba_id="waba-template-snapshot",
        )

        draft = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-snapshot",
                    waba_id="waba-template-snapshot",
                    name="snapshot_template",
                    language="en",
                    category="UTILITY",
                    body_text="Hello {{first_name}}, snapshot stays stable.",
                    sample_variables={"first_name": "Customer"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                draft.template_id,
                TemplateStatusUpdateRequest(
                    status="PENDING",
                    meta_template_id="meta-template-snapshot",
                ),
            )
        )

        waba_account = session.query(WhatsAppBusinessAccount).filter_by(
            account_id="template-account-snapshot",
            waba_id="waba-template-snapshot",
        ).one()
        waba_account.waba_id = "waba-template-snapshot-drifted"
        session.commit()

        snapshot_templates = asyncio.run(
            template_service.list_templates(
                account_id="template-account-snapshot",
                waba_id="waba-template-snapshot",
            )
        )
        drifted_templates = asyncio.run(
            template_service.list_templates(
                account_id="template-account-snapshot",
                waba_id="waba-template-snapshot-drifted",
            )
        )
        webhook_update = asyncio.run(
            template_service.apply_template_webhook_update(
                account_id="template-account-snapshot",
                waba_id="waba-template-snapshot",
                meta_template_id="meta-template-snapshot",
                name="snapshot_template",
                language="en",
                status="APPROVED",
                rejected_reason=None,
                quality_score="GREEN",
                event_type="message_template_status_update",
                raw_payload={"event": "snapshot_template_webhook"},
            )
        )
        stored_template = session.query(MessageTemplate).filter_by(id=draft.template_id).one()

        assert [item.template_id for item in snapshot_templates] == [draft.template_id]
        assert snapshot_templates[0].waba_id == "waba-template-snapshot"
        assert drifted_templates == []
        assert webhook_update is not None
        assert webhook_update.waba_id == "waba-template-snapshot"
        assert webhook_update.status == "APPROVED"
        assert stored_template.waba_id == "waba-template-snapshot"
    finally:
        session.close()


def test_template_service_sync_rebinds_recreated_local_waba_rows_by_official_waba_id(
    db_session_factory: sessionmaker[Session],
) -> None:
    registry_provider = RecordingTemplateRegistryProvider(
        sync_result=TemplateRegistrySyncResult(
            provider_name="template_registry_mock",
            templates=[
                TemplateRegistryRemoteTemplate(
                    provider_template_id="meta-template-recreated-waba",
                    name="shipping_update",
                    language="en",
                    category="UTILITY",
                    status="APPROVED",
                    components={
                        "body_text": "Remote body for rebound WABA {{order_id}}",
                        "sample_variables": {"order_id": "B-200"},
                    },
                    raw_payload={"id": "meta-template-recreated-waba"},
                )
            ],
        )
    )
    session, runtime_state, template_service = build_template_service(
        db_session_factory,
        template_registry_provider=registry_provider,
    )

    try:
        account_id = "template-account-sync-recreated-waba"
        official_waba_id = "waba-template-recreated"
        legacy_waba_id = "waba-template-recreated-legacy"
        asyncio.run(
            runtime_state.ensure_account(
                account_id=account_id,
                display_name="Template Sync Recreated WABA Account",
                provider_type="whatsapp",
            )
        )
        create_waba(session, account_id=account_id, waba_id=official_waba_id)

        draft = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id=account_id,
                    waba_id=official_waba_id,
                    name="shipping_update",
                    language="en",
                    category="UTILITY",
                    body_text="Local body before WABA row rebuild {{order_id}}",
                    sample_variables={"order_id": "A-100"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                draft.template_id,
                TemplateStatusUpdateRequest(
                    status="PENDING",
                    meta_template_id="meta-template-recreated-waba",
                ),
            )
        )

        legacy_waba = session.query(WhatsAppBusinessAccount).filter_by(
            account_id=account_id,
            waba_id=official_waba_id,
        ).one()
        legacy_waba.waba_id = legacy_waba_id
        session.commit()

        create_waba(session, account_id=account_id, waba_id=official_waba_id)
        recreated_waba = session.query(WhatsAppBusinessAccount).filter_by(
            account_id=account_id,
            waba_id=official_waba_id,
        ).one()

        response = asyncio.run(
            template_service.sync_templates(
                TemplateSyncRequest(
                    account_id=account_id,
                    waba_id=official_waba_id,
                    import_missing=True,
                )
            )
        )

        stored_templates = session.query(MessageTemplate).filter_by(
            account_id=account_id,
            waba_id=official_waba_id,
            meta_template_id="meta-template-recreated-waba",
        ).all()
        rebound_template = session.query(MessageTemplate).filter_by(id=draft.template_id).one()

        assert response.created_count == 0
        assert response.updated_count == 1
        assert response.skipped_count == 0
        assert [item.template_id for item in response.templates] == [draft.template_id]
        assert len(stored_templates) == 1
        assert rebound_template.waba_account_id == recreated_waba.id
        assert rebound_template.waba_id == official_waba_id
        assert rebound_template.meta_template_id == "meta-template-recreated-waba"
        assert rebound_template.components["body_text"] == "Remote body for rebound WABA {{order_id}}"
    finally:
        session.close()


def test_template_service_sync_does_not_rebind_same_name_template_from_another_waba(
    db_session_factory: sessionmaker[Session],
) -> None:
    registry_provider = RecordingTemplateRegistryProvider(
        sync_result=TemplateRegistrySyncResult(
            provider_name="template_registry_mock",
            templates=[
                TemplateRegistryRemoteTemplate(
                    provider_template_id="meta-template-secondary-waba",
                    name="shipping_update",
                    language="en",
                    category="UTILITY",
                    status="APPROVED",
                    components={
                        "body_text": "Secondary WABA body for {{order_id}}",
                        "sample_variables": {"order_id": "B-100"},
                    },
                    raw_payload={"id": "meta-template-secondary-waba"},
                )
            ],
        )
    )
    session, runtime_state, template_service = build_template_service(
        db_session_factory,
        template_registry_provider=registry_provider,
    )

    try:
        account_id = "template-account-sync-multi-waba"
        asyncio.run(
            runtime_state.ensure_account(
                account_id=account_id,
                display_name="Template Sync Multi WABA Account",
                provider_type="whatsapp",
            )
        )
        create_waba(session, account_id=account_id, waba_id="waba-template-sync-primary")
        create_waba(session, account_id=account_id, waba_id="waba-template-sync-secondary")
        primary_waba = session.query(WhatsAppBusinessAccount).filter_by(
            account_id=account_id,
            waba_id="waba-template-sync-primary",
        ).one()
        secondary_waba = session.query(WhatsAppBusinessAccount).filter_by(
            account_id=account_id,
            waba_id="waba-template-sync-secondary",
        ).one()

        primary_template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id=account_id,
                    waba_id="waba-template-sync-primary",
                    name="shipping_update",
                    language="en",
                    category="UTILITY",
                    body_text="Primary WABA body {{order_id}}",
                    sample_variables={"order_id": "A-100"},
                )
            )
        )

        response = asyncio.run(
            template_service.sync_templates(
                TemplateSyncRequest(
                    account_id=account_id,
                    waba_id="waba-template-sync-secondary",
                    import_missing=True,
                )
            )
        )

        primary_after_sync = session.query(MessageTemplate).filter_by(id=primary_template.template_id).one()
        all_templates = session.query(MessageTemplate).filter_by(
            account_id=account_id,
            name="shipping_update",
            language="en",
        ).all()
        by_waba_id = {template.waba_account_id: template for template in all_templates}

        assert response.created_count == 1
        assert response.updated_count == 0
        assert primary_after_sync.waba_account_id == primary_waba.id
        assert primary_after_sync.meta_template_id is None
        assert set(by_waba_id) == {primary_waba.id, secondary_waba.id}
        assert by_waba_id[secondary_waba.id].meta_template_id == "meta-template-secondary-waba"
        assert by_waba_id[secondary_waba.id].components["body_text"] == "Secondary WABA body for {{order_id}}"
    finally:
        session.close()


def test_template_service_mock_send_records_message_and_scoped_send_logs(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(db_session_factory)

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-send",
                display_name="Template Send Account",
                provider_type="whatsapp",
            )
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-send",
                conversation_id="conv-template-1",
                customer_id="wa-user-1",
                customer_language="es",
                customer_language_source="detected",
            )
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-send",
                conversation_id="conv-template-2",
                customer_id="wa-user-2",
                customer_language="es",
                customer_language_source="detected",
            )
        )
        asyncio.run(
            runtime_state.upsert_agent(
                agent_id="agent-template-1",
                display_name="Template Agent 1",
                email=None,
                status="online",
                is_active=True,
            )
        )
        asyncio.run(
            runtime_state.assign_conversation(
                account_id="template-account-send",
                conversation_id="conv-template-1",
                agent_id="agent-template-1",
                assigned_by_agent_id="agent-template-1",
                reason="template_manual_send",
            )
        )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-send",
                    name="shipping_update",
                    language="en",
                    category="UTILITY",
                    body_text="Hello {{first_name}}, your order {{order_id}} is ready.",
                    sample_variables={"first_name": "Guest", "order_id": "A-000"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )

        first_send = asyncio.run(
            template_service.send_template(
                template.template_id,
                TemplateSendRequest(
                    account_id="template-account-send",
                    conversation_id="conv-template-1",
                    variables={"first_name": "Ana", "order_id": "A-100"},
                    agent_id="agent-template-1",
                ),
            )
        )
        second_send = asyncio.run(
            template_service.send_template(
                template.template_id,
                TemplateSendRequest(
                    account_id="template-account-send",
                    conversation_id="conv-template-2",
                    variables={"first_name": "Luis"},
                ),
            )
        )

        conv_one_messages = asyncio.run(
            runtime_state.list_message_models(
                account_id="template-account-send",
                conversation_id="conv-template-1",
            )
        )
        all_logs = asyncio.run(template_service.list_send_logs(account_id="template-account-send"))
        conv_one_logs = asyncio.run(
            template_service.list_send_logs(
                account_id="template-account-send",
                conversation_id="conv-template-1",
            )
        )
        conv_one_external_logs = asyncio.run(
            template_service.list_send_logs(
                account_id="template-account-send",
                external_conversation_id="conv-template-1",
            )
        )
        conv_one_internal_logs = asyncio.run(
            template_service.list_send_logs(
                account_id="template-account-send",
                internal_conversation_id=first_send.internal_conversation_id,
            )
        )
        conv_one_combined_logs = asyncio.run(
            template_service.list_send_logs(
                account_id="template-account-send",
                conversation_id="conv-template-1",
                internal_conversation_id=first_send.internal_conversation_id,
            )
        )
        conv_one_combined_empty_logs = asyncio.run(
            template_service.list_send_logs(
                account_id="template-account-send",
                conversation_id="conv-template-1",
                internal_conversation_id=second_send.internal_conversation_id,
            )
        )
        conv_one_duplicate_alias_logs = asyncio.run(
            template_service.list_send_logs(
                account_id="template-account-send",
                conversation_id="conv-template-1",
                external_conversation_id="conv-template-1",
            )
        )
        send_logs = asyncio.run(
            runtime_state.list_audit_logs(
                account_id="template-account-send",
                action="template_sent",
            )
        )

        assert first_send.status == "SENT"
        assert first_send.conversation_id == "conv-template-1"
        assert first_send.conversation_id == first_send.external_conversation_id
        assert first_send.internal_conversation_id != first_send.conversation_id
        assert first_send.delivered_text == "Hello Ana, your order A-100 is ready."
        assert first_send.template_language == "en"
        assert second_send.conversation_id == "conv-template-2"
        assert second_send.conversation_id == second_send.external_conversation_id
        assert second_send.internal_conversation_id != second_send.conversation_id
        assert second_send.delivered_text == "Hello Luis, your order A-000 is ready."
        assert len(conv_one_messages) == 1
        assert conv_one_messages[0].message_type == "template"
        assert conv_one_messages[0].content_text == first_send.delivered_text
        assert conv_one_messages[0].translated_text is None
        assert conv_one_messages[0].payload == {
            "template_id": template.template_id,
            "template_name": "shipping_update",
            "template_language": "en",
            "variables": {"first_name": "Ana", "order_id": "A-100"},
            "header_media_asset_id": None,
            "header_media_asset_name": None,
            "header_media_asset_type": None,
            "header_media_storage_url": None,
            "header_media_provider_media_id": None,
            "header_media_meta_media_id": None,
            "agent_id": "agent-template-1",
            "provider": "mock",
            "provider_message_id": first_send.message_id,
            "provider_accepted": True,
            "mock_send": True,
        }
        assert conv_one_messages[0].sent_by_agent_id is not None
        assert len(all_logs) == 2
        assert {item.message_id for item in all_logs} == {first_send.message_id, second_send.message_id}
        assert len(conv_one_logs) == 1
        assert len(conv_one_external_logs) == 1
        assert len(conv_one_internal_logs) == 1
        assert len(conv_one_combined_logs) == 1
        assert conv_one_combined_empty_logs == []
        assert len(conv_one_duplicate_alias_logs) == 1
        assert conv_one_logs[0].id == first_send.send_log_id
        assert conv_one_external_logs[0].id == first_send.send_log_id
        assert conv_one_internal_logs[0].id == first_send.send_log_id
        assert conv_one_combined_logs[0].id == first_send.send_log_id
        assert conv_one_duplicate_alias_logs[0].id == first_send.send_log_id
        assert conv_one_logs[0].template_id == template.template_id
        assert conv_one_logs[0].template_name == "shipping_update"
        assert conv_one_logs[0].conversation_id == "conv-template-1"
        assert conv_one_logs[0].external_conversation_id == "conv-template-1"
        assert conv_one_logs[0].internal_conversation_id == first_send.internal_conversation_id
        assert conv_one_logs[0].header_media_provider_media_id is None
        assert conv_one_logs[0].header_media_sync_status is None
        assert conv_one_logs[0].wa_id == "wa-user-1"
        assert conv_one_logs[0].status == "SENT"
        assert len(send_logs) == 2
        assert send_logs[0].payload["provider"] == "mock"
        assert send_logs[0].payload["idempotency_key"] is None
        assert send_logs[0].payload["wa_id"] in {"wa-user-1", "wa-user-2"}
        assert send_logs[0].payload["send_log_id"] in {first_send.send_log_id, second_send.send_log_id}
    finally:
        session.close()


def test_template_service_send_template_includes_bound_header_media(
    db_session_factory: sessionmaker[Session],
) -> None:
    provider = RecordingAcceptedWhatsAppLikeProvider()
    session, runtime_state, template_service = build_template_service(
        db_session_factory,
        messaging_provider=provider,
    )

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-header-send",
                display_name="Template Header Send Account",
                provider_type="whatsapp",
            )
        )
        create_waba(session, account_id="template-account-header-send", waba_id="waba-template-header")
        create_phone_number(
            session,
            account_id="template-account-header-send",
            waba_id="waba-template-header",
            phone_number_id="phone-template-header",
        )
        create_media_asset(
            session,
            account_id="template-account-header-send",
            waba_id="waba-template-header",
            phone_number_id="phone-template-header",
            asset_id="asset-template-header-send",
            name="header-doc.pdf",
            asset_type="document",
            storage_url="https://cdn.example.com/header-doc.pdf",
            meta_media_id="meta-header-doc-1",
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-header-send",
                conversation_id="conv-template-header",
                customer_id="wa-user-template-header",
                customer_language="en",
                customer_language_source="hint",
                provider_phone_number_id="phone-template-header",
            )
        )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-header-send",
                    waba_id="waba-template-header",
                    name="header_bound_template",
                    language="en",
                    category="UTILITY",
                    body_text="Order {{order_id}} is ready.",
                    header_media_asset_id="asset-template-header-send",
                    sample_variables={"order_id": "A-100"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )

        response = asyncio.run(
            template_service.send_template(
                template.template_id,
                TemplateSendRequest(
                    account_id="template-account-header-send",
                    conversation_id="conv-template-header",
                    variables={"order_id": "A-200"},
                ),
            )
        )
        messages = asyncio.run(
            runtime_state.list_message_models(
                account_id="template-account-header-send",
                conversation_id="conv-template-header",
            )
        )
        send_logs = asyncio.run(
            template_service.list_send_logs(account_id="template-account-header-send")
        )
        asset_events = session.query(MediaAssetEvent).filter_by(
            asset_id="asset-template-header-send"
        ).all()

        assert len(provider.requests) == 1
        assert provider.requests[0].message_type == "template"
        assert provider.requests[0].template_header_media_type == "document"
        assert provider.requests[0].media_asset_id == "meta-header-doc-1"
        assert provider.requests[0].file_name == "header-doc.pdf"
        assert response.header_media_asset_id == "asset-template-header-send"
        assert response.header_media_asset_name == "header-doc.pdf"
        assert response.header_media_asset_type == "document"
        assert response.header_media_provider_media_id == "meta-header-doc-1"
        assert response.header_media_sync_status == "reused"
        assert messages[0].payload["header_media_asset_id"] == "asset-template-header-send"
        assert messages[0].payload["header_media_asset_type"] == "document"
        assert send_logs[0].header_media_asset_id == "asset-template-header-send"
        assert send_logs[0].header_media_asset_name == "header-doc.pdf"
        assert send_logs[0].header_media_asset_type == "document"
        assert send_logs[0].header_media_provider_media_id == "meta-header-doc-1"
        assert send_logs[0].header_media_sync_status == "reused"
        asyncio.run(
            runtime_state.record_provider_status_event(
                account_id="template-account-header-send",
                update=ProviderStatusUpdate(
                    provider_name=provider.provider_name,
                    account_id="template-account-header-send",
                    waba_id="waba-template-header",
                    phone_number_id="phone-template-header",
                    provider_message_id=response.message_id or "",
                    external_status="DELIVERED",
                    recipient_id="wa-user-template-header",
                    occurred_at="2026-06-07T10:00:00",
                    payload={
                        "conversation_origin_type": "business_initiated",
                        "conversation_category": "utility",
                        "pricing_model": "CBP",
                        "billable": True,
                    },
                ),
            )
        )
        session.expire_all()
        asset_events = (
            session.query(MediaAssetEvent)
            .filter_by(asset_id="asset-template-header-send")
            .order_by(MediaAssetEvent.created_at.asc(), MediaAssetEvent.id.asc())
            .all()
        )
        assert [event.event_type for event in asset_events] == [
            "media_asset_sync_reused",
            "media_asset_template_sent",
            "media_asset_template_status_delivered",
        ]
        assert asset_events[1].waba_id == "waba-template-header"
        assert asset_events[2].payload["conversation_id"] == "conv-template-header"
        assert asset_events[2].payload["external_conversation_id"] == "conv-template-header"
        assert asset_events[2].payload["internal_conversation_id"] == send_logs[0].internal_conversation_id
        assert (
            asset_events[2].payload["internal_conversation_id"]
            != asset_events[2].payload["external_conversation_id"]
        )
    finally:
        session.close()


def test_template_service_send_template_rejects_missing_meta_access_token(
    db_session_factory: sessionmaker[Session],
) -> None:
    provider = RecordingAcceptedWhatsAppLikeProvider()
    session, runtime_state, template_service = build_template_service(
        db_session_factory,
        messaging_provider=provider,
    )

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-missing-token",
                display_name="Template Missing Token Account",
                provider_type="whatsapp",
            )
        )
        create_waba(
            session,
            account_id="template-account-missing-token",
            waba_id="waba-template-missing-token",
        )
        create_phone_number(
            session,
            account_id="template-account-missing-token",
            waba_id="waba-template-missing-token",
            phone_number_id="phone-template-missing-token",
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-missing-token",
                conversation_id="conv-template-missing-token",
                customer_id="wa-user-template-missing-token",
                customer_language="en",
                customer_language_source="hint",
                provider_phone_number_id="phone-template-missing-token",
            )
        )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-missing-token",
                    waba_id="waba-template-missing-token",
                    name="missing_token_template",
                    language="en",
                    category="UTILITY",
                    body_text="Order {{order_id}} is ready.",
                    sample_variables={"order_id": "A-100"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )

        waba_account = session.query(WhatsAppBusinessAccount).filter_by(
            account_id="template-account-missing-token",
            waba_id="waba-template-missing-token",
        ).one()
        waba_account.access_token = None
        session.commit()

        with pytest.raises(ValueError, match="access token"):
            asyncio.run(
                template_service.send_template(
                    template.template_id,
                    TemplateSendRequest(
                        account_id="template-account-missing-token",
                        conversation_id="conv-template-missing-token",
                        variables={"order_id": "A-200"},
                    ),
                )
            )

        assert provider.requests == []
    finally:
        session.close()


def test_template_service_updates_daily_stats_incrementally(
    db_session_factory: sessionmaker[Session],
) -> None:
    provider = RecordingAcceptedWhatsAppLikeProvider()
    session, runtime_state, template_service = build_template_service(
        db_session_factory,
        messaging_provider=provider,
    )

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-daily-stats",
                display_name="Template Daily Stats Account",
                provider_type="whatsapp",
            )
        )
        create_waba(
            session,
            account_id="template-account-daily-stats",
            waba_id="waba-template-daily-stats",
        )
        create_phone_number(
            session,
            account_id="template-account-daily-stats",
            waba_id="waba-template-daily-stats",
            phone_number_id="phone-template-daily-stats",
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-daily-stats",
                conversation_id="conv-template-daily-stats",
                customer_id="wa-user-template-daily-stats",
                customer_language="en",
                customer_language_source="hint",
                provider_phone_number_id="phone-template-daily-stats",
            )
        )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-daily-stats",
                    waba_id="waba-template-daily-stats",
                    name="daily_stats_template",
                    language="en",
                    category="UTILITY",
                    body_text="Order {{order_id}} is ready.",
                    sample_variables={"order_id": "A-100"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )

        response = asyncio.run(
            template_service.send_template(
                template.template_id,
                TemplateSendRequest(
                    account_id="template-account-daily-stats",
                    conversation_id="conv-template-daily-stats",
                    variables={"order_id": "A-200"},
                ),
            )
        )

        daily_stat = session.query(TemplateDailyStat).filter_by(
            account_id="template-account-daily-stats",
            template_id=template.template_id,
        ).one()
        assert daily_stat.send_count == 1
        assert daily_stat.delivered_count == 0
        assert daily_stat.read_count == 0
        assert daily_stat.failed_count == 0
        assert daily_stat.billable_count == 0

        asyncio.run(
            runtime_state.record_provider_status_event(
                account_id="template-account-daily-stats",
                update=ProviderStatusUpdate(
                    provider_name=provider.provider_name,
                    account_id="template-account-daily-stats",
                    waba_id="waba-template-daily-stats",
                    phone_number_id="phone-template-daily-stats",
                    provider_message_id=response.message_id or "",
                    external_status="DELIVERED",
                    recipient_id="wa-user-template-daily-stats",
                    occurred_at="2026-06-07T10:00:00",
                    payload={
                        "conversation_origin_type": "business_initiated",
                        "conversation_category": "utility",
                        "pricing_model": "CBP",
                        "billable": True,
                    },
                ),
            )
        )
        session.expire_all()
        delivered_stat = session.query(TemplateDailyStat).filter_by(
            account_id="template-account-daily-stats",
            template_id=template.template_id,
        ).one()
        assert delivered_stat.send_count == 1
        assert delivered_stat.delivered_count == 1
        assert delivered_stat.read_count == 0
        assert delivered_stat.failed_count == 0
        assert delivered_stat.billable_count == 1

        asyncio.run(
            runtime_state.record_provider_status_event(
                account_id="template-account-daily-stats",
                update=ProviderStatusUpdate(
                    provider_name=provider.provider_name,
                    account_id="template-account-daily-stats",
                    waba_id="waba-template-daily-stats",
                    phone_number_id="phone-template-daily-stats",
                    provider_message_id=response.message_id or "",
                    external_status="DELIVERED",
                    recipient_id="wa-user-template-daily-stats",
                    occurred_at="2026-06-07T10:01:00",
                    payload={
                        "conversation_origin_type": "business_initiated",
                        "conversation_category": "utility",
                        "pricing_model": "CBP",
                        "billable": True,
                    },
                ),
            )
        )
        session.expire_all()
        duplicate_delivered_stat = session.query(TemplateDailyStat).filter_by(
            account_id="template-account-daily-stats",
            template_id=template.template_id,
        ).one()
        delivered_events = session.query(MessageEvent).filter_by(
            event_type=f"{provider.provider_name}_status_DELIVERED"
        ).all()
        assert duplicate_delivered_stat.delivered_count == 1
        assert len(delivered_events) == 1

        asyncio.run(
            runtime_state.record_provider_status_event(
                account_id="template-account-daily-stats",
                update=ProviderStatusUpdate(
                    provider_name=provider.provider_name,
                    account_id="template-account-daily-stats",
                    waba_id="waba-template-daily-stats",
                    phone_number_id="phone-template-daily-stats",
                    provider_message_id=response.message_id or "",
                    external_status="READ",
                    recipient_id="wa-user-template-daily-stats",
                    occurred_at="2026-06-07T10:05:00",
                    payload={
                        "conversation_origin_type": "business_initiated",
                        "conversation_category": "utility",
                        "pricing_model": "CBP",
                        "billable": True,
                    },
                ),
            )
        )
        session.expire_all()
        read_stat = session.query(TemplateDailyStat).filter_by(
            account_id="template-account-daily-stats",
            template_id=template.template_id,
        ).one()
        assert read_stat.send_count == 1
        assert read_stat.delivered_count == 1
        assert read_stat.read_count == 1
        assert read_stat.failed_count == 0
        assert read_stat.billable_count == 1
    finally:
        session.close()


def test_template_service_replays_unmatched_provider_status_after_send_log_creation(
    db_session_factory: sessionmaker[Session],
) -> None:
    provider = AcceptedWhatsAppLikeProvider()
    session, runtime_state, template_service = build_template_service(
        db_session_factory,
        messaging_provider=provider,
    )

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-status-replay",
                display_name="Template Status Replay Account",
                provider_type="whatsapp",
            )
        )
        create_waba(
            session,
            account_id="template-account-status-replay",
            waba_id="waba-template-status-replay",
        )
        create_phone_number(
            session,
            account_id="template-account-status-replay",
            waba_id="waba-template-status-replay",
            phone_number_id="phone-template-status-replay",
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-status-replay",
                conversation_id="conv-template-status-replay",
                customer_id="wa-user-template-status-replay",
                customer_language="en",
                customer_language_source="hint",
                provider_phone_number_id="phone-template-status-replay",
            )
        )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-status-replay",
                    waba_id="waba-template-status-replay",
                    name="status_replay_template",
                    language="en",
                    category="UTILITY",
                    body_text="Replay {{order_id}} is ready.",
                    sample_variables={"order_id": "A-100"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )

        expected_provider_message_id = "wamid.test.approved.1"
        status_update = ProviderStatusUpdate(
            provider_name=provider.provider_name,
            account_id="template-account-status-replay",
            waba_id="waba-template-status-replay",
            phone_number_id="phone-template-status-replay",
            provider_message_id=expected_provider_message_id,
            external_status="read",
            recipient_id="wa-user-template-status-replay",
            occurred_at="2026-06-07T10:00:00",
            payload={
                "conversation_origin_type": "business_initiated",
                "conversation_category": "utility",
                "pricing_model": "CBP",
                "billable": True,
            },
        )
        assert asyncio.run(
            runtime_state.record_provider_status_event(
                account_id="template-account-status-replay",
                update=status_update,
            )
        ) is False
        assert asyncio.run(
            runtime_state.record_provider_status_event(
                account_id="template-account-status-replay",
                update=status_update,
            )
        ) is False

        buffered_event = session.query(ProviderStatusEventBuffer).filter_by(
            account_id="template-account-status-replay",
            provider_name=provider.provider_name,
            provider_message_id=expected_provider_message_id,
            external_status="read",
        ).one()
        assert buffered_event.replay_state == "pending"
        assert buffered_event.seen_count == 2

        response = asyncio.run(
            template_service.send_template(
                template.template_id,
                TemplateSendRequest(
                    account_id="template-account-status-replay",
                    conversation_id="conv-template-status-replay",
                    variables={"order_id": "A-200"},
                ),
            )
        )
        assert response.message_id == expected_provider_message_id

        send_log = session.query(TemplateSendLog).filter_by(
            account_id="template-account-status-replay",
            message_id=expected_provider_message_id,
        ).one()
        assert send_log.status == "READ"
        assert send_log.delivered_at is not None
        assert send_log.read_at is not None
        assert send_log.conversation_origin_type == "business_initiated"
        assert send_log.conversation_category == "utility"
        assert send_log.pricing_model == "CBP"
        assert send_log.billable is True

        session.refresh(buffered_event)
        assert buffered_event.replay_state == "replayed"
        assert buffered_event.replayed_at is not None
        assert buffered_event.replayed_message_event_id is not None

        status_events = session.query(MessageEvent).filter_by(
            account_id="template-account-status-replay",
            event_type="whatsapp_status_read",
        ).all()
        assert len(status_events) == 1
        assert status_events[0].payload["provider_message_id"] == expected_provider_message_id

        replayed_again = asyncio.run(
            runtime_state.replay_unmatched_provider_status_events(
                account_id="template-account-status-replay",
                provider_message_id=expected_provider_message_id,
            )
        )
        assert replayed_again == 0
        assert session.query(MessageEvent).filter_by(
            account_id="template-account-status-replay",
            event_type="whatsapp_status_read",
        ).count() == 1
    finally:
        session.close()


def test_template_send_status_matches_nested_message_scope_snapshot(
    db_session_factory: sessionmaker[Session],
) -> None:
    provider = AcceptedWhatsAppLikeProvider()
    session, runtime_state, template_service = build_template_service(
        db_session_factory,
        messaging_provider=provider,
    )

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-status-nested-scope",
                display_name="Template Status Nested Scope Account",
                provider_type="whatsapp",
            )
        )
        create_waba(
            session,
            account_id="template-account-status-nested-scope",
            waba_id="waba-template-status-nested-scope",
        )
        create_phone_number(
            session,
            account_id="template-account-status-nested-scope",
            waba_id="waba-template-status-nested-scope",
            phone_number_id="phone-template-status-nested-scope",
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-status-nested-scope",
                conversation_id="conv-template-status-nested-scope",
                customer_id="wa-user-template-status-nested-scope",
                customer_language="en",
                customer_language_source="hint",
                provider_phone_number_id="phone-template-status-nested-scope",
            )
        )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-status-nested-scope",
                    waba_id="waba-template-status-nested-scope",
                    name="status_nested_scope_template",
                    language="en",
                    category="UTILITY",
                    body_text="Nested scope {{order_id}} is ready.",
                    sample_variables={"order_id": "A-300"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )

        response = asyncio.run(
            template_service.send_template(
                template.template_id,
                TemplateSendRequest(
                    account_id="template-account-status-nested-scope",
                    conversation_id="conv-template-status-nested-scope",
                    variables={"order_id": "A-301"},
                ),
            )
        )
        assert response.message_id == "wamid.test.approved.1"

        message = session.query(Message).filter_by(
            account_id="template-account-status-nested-scope",
            provider_message_id=response.message_id,
        ).one()
        message.phone_number_id = None
        message.phone_number = None
        message.payload = {
            "provider": provider.provider_name,
            "provider_message_id": response.message_id,
            "provider_payload": {
                "waba_id": "waba-template-status-nested-scope",
                "metadata": {
                    "phone_number_id": "phone-template-status-nested-scope",
                },
            },
        }
        session.commit()

        update = ProviderStatusUpdate(
            provider_name=provider.provider_name,
            account_id="template-account-status-nested-scope",
            waba_id=None,
            phone_number_id=None,
            provider_message_id=response.message_id or "",
            external_status="DELIVERED",
            recipient_id="wa-user-template-status-nested-scope",
            occurred_at="2026-06-10T09:00:00Z",
            payload={"conversation_origin_type": "business_initiated"},
        )
        assert asyncio.run(
            runtime_state.record_provider_status_event(
                account_id="template-account-status-nested-scope",
                update=update,
            )
        ) is True

        status_event = session.query(MessageEvent).filter_by(
            account_id="template-account-status-nested-scope",
            event_type="whatsapp_status_DELIVERED",
        ).one()
        send_log = session.query(TemplateSendLog).filter_by(
            account_id="template-account-status-nested-scope",
            message_id=response.message_id,
        ).one()

        assert status_event.waba_id == "waba-template-status-nested-scope"
        assert status_event.phone_number_id == "phone-template-status-nested-scope"
        assert status_event.payload["waba_id"] == "waba-template-status-nested-scope"
        assert status_event.payload["phone_number_id"] == "phone-template-status-nested-scope"
        assert send_log.status == "DELIVERED"
        assert send_log.delivered_at is not None
    finally:
        session.close()


def test_template_stats_aggregator_records_nested_message_waba_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    session = db_session_factory()
    try:
        session.add(
            Account(
                account_id="template-stats-nested-waba-account",
                display_name="Template Stats Nested WABA Account",
                provider_type="whatsapp",
                is_active=True,
                ai_enabled=True,
            )
        )
        create_waba(
            session,
            account_id="template-stats-nested-waba-account",
            waba_id="waba-template-stats-nested-scope",
        )
        create_phone_number(
            session,
            account_id="template-stats-nested-waba-account",
            waba_id="waba-template-stats-nested-scope",
            phone_number_id="phone-template-stats-nested-scope",
        )
        conversation = Conversation(
            account_id="template-stats-nested-waba-account",
            external_conversation_id="conv-template-stats-nested-scope",
            customer_id="wa-template-stats-nested-user",
            status="open",
        )
        session.add(conversation)
        session.flush()

        message = Message(
            account_id="template-stats-nested-waba-account",
            conversation_id=conversation.id,
            sender_id="system",
            recipient_id="wa-template-stats-nested-user",
            direction="outbound",
            message_type="template",
            content_text="template stats nested scope",
            payload={
                "provider_payload": {
                    "metadata": {
                        "waba_id": "waba-template-stats-nested-scope",
                        "phone_number_id": "phone-template-stats-nested-scope",
                    }
                }
            },
            provider_message_id="provider-msg-template-stats-nested-scope",
        )
        session.add(message)
        session.flush()

        send_log = TemplateSendLog(
            account_id="template-stats-nested-waba-account",
            template_id=None,
            conversation_id=conversation.id,
            phone_number_id="phone-template-stats-nested-scope-local-row",
            waba_id="waba-template-stats-legacy-row",
            template_name="template_stats_nested_scope",
            template_language="en",
            template_category="UTILITY",
            template_code="template-stats-nested-scope",
            wa_id="wa-template-stats-nested-user",
            message_id=message.id,
            status="SENT",
            sent_at=utc_now(),
            last_status_at=utc_now(),
        )
        session.add(send_log)
        session.flush()

        aggregator = TemplateStatsAggregator(session)
        aggregator.record_send_log_created(send_log)
        session.commit()

        nested_scope_rows = (
            session.query(TemplateDailyStat)
            .filter(
                TemplateDailyStat.account_id == "template-stats-nested-waba-account",
                TemplateDailyStat.waba_id == "waba-template-stats-nested-scope",
                TemplateDailyStat.phone_number_id == "phone-template-stats-nested-scope",
                TemplateDailyStat.template_name == "template_stats_nested_scope",
            )
            .all()
        )
        legacy_scope_rows = (
            session.query(TemplateDailyStat)
            .filter(
                TemplateDailyStat.account_id == "template-stats-nested-waba-account",
                TemplateDailyStat.waba_id == "waba-template-stats-legacy-row",
                TemplateDailyStat.template_name == "template_stats_nested_scope",
            )
            .all()
        )

        assert len(nested_scope_rows) == 1
        assert nested_scope_rows[0].send_count == 1
        assert legacy_scope_rows == []
    finally:
        session.close()


def test_template_send_status_does_not_downgrade_after_read(
    db_session_factory: sessionmaker[Session],
) -> None:
    provider = AcceptedWhatsAppLikeProvider()
    session, runtime_state, template_service = build_template_service(
        db_session_factory,
        messaging_provider=provider,
    )

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-status-ordering",
                display_name="Template Status Ordering Account",
                provider_type="whatsapp",
            )
        )
        create_waba(
            session,
            account_id="template-account-status-ordering",
            waba_id="waba-template-status-ordering",
        )
        create_phone_number(
            session,
            account_id="template-account-status-ordering",
            waba_id="waba-template-status-ordering",
            phone_number_id="phone-template-status-ordering",
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-status-ordering",
                conversation_id="conv-template-status-ordering",
                customer_id="wa-user-template-status-ordering",
                customer_language="en",
                customer_language_source="hint",
                provider_phone_number_id="phone-template-status-ordering",
            )
        )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-status-ordering",
                    waba_id="waba-template-status-ordering",
                    name="status_ordering_template",
                    language="en",
                    category="UTILITY",
                    body_text="Ordering {{order_id}} is ready.",
                    sample_variables={"order_id": "A-100"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )

        response = asyncio.run(
            template_service.send_template(
                template.template_id,
                TemplateSendRequest(
                    account_id="template-account-status-ordering",
                    conversation_id="conv-template-status-ordering",
                    variables={"order_id": "A-200"},
                ),
            )
        )
        assert response.message_id == "wamid.test.approved.1"

        read_update = ProviderStatusUpdate(
            provider_name=provider.provider_name,
            account_id="template-account-status-ordering",
            waba_id="waba-template-status-ordering",
            phone_number_id="phone-template-status-ordering",
            provider_message_id=response.message_id or "",
            external_status="READ",
            recipient_id="wa-user-template-status-ordering",
            occurred_at="2026-06-07T10:00:00",
            payload={
                "conversation_origin_type": "business_initiated",
                "conversation_category": "utility",
                "pricing_model": "CBP",
                "billable": True,
            },
        )
        delivered_update = ProviderStatusUpdate(
            provider_name=provider.provider_name,
            account_id="template-account-status-ordering",
            waba_id="waba-template-status-ordering",
            phone_number_id="phone-template-status-ordering",
            provider_message_id=response.message_id or "",
            external_status="DELIVERED",
            recipient_id="wa-user-template-status-ordering",
            occurred_at="2026-06-07T10:01:00",
            payload={
                "conversation_origin_type": "business_initiated",
                "conversation_category": "utility",
                "pricing_model": "CBP",
                "billable": True,
            },
        )

        assert asyncio.run(
            runtime_state.record_provider_status_event(
                account_id="template-account-status-ordering",
                update=read_update,
            )
        ) is True
        assert asyncio.run(
            runtime_state.record_provider_status_event(
                account_id="template-account-status-ordering",
                update=delivered_update,
            )
        ) is True

        send_log = session.query(TemplateSendLog).filter_by(id=response.send_log_id).one()
        assert send_log.status == "READ"
        assert send_log.delivered_at is not None
        assert send_log.read_at is not None
        assert send_log.failed_at is None

        daily_stat = session.query(TemplateDailyStat).filter_by(
            account_id="template-account-status-ordering",
            template_id=template.template_id,
            waba_id="waba-template-status-ordering",
            phone_number_id="phone-template-status-ordering",
        ).one()
        assert daily_stat.send_count == 1
        assert daily_stat.delivered_count == 1
        assert daily_stat.read_count == 1
        assert daily_stat.failed_count == 0
    finally:
        session.close()


def test_template_service_send_template_syncs_bound_header_media_in_mock_mode(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(db_session_factory)

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-header-sync",
                display_name="Template Header Sync Account",
                provider_type="mock",
            )
        )
        create_waba(session, account_id="template-account-header-sync", waba_id="waba-template-header-sync")
        create_phone_number(
            session,
            account_id="template-account-header-sync",
            waba_id="waba-template-header-sync",
            phone_number_id="phone-template-header-sync",
        )
        create_media_asset(
            session,
            account_id="template-account-header-sync",
            waba_id="waba-template-header-sync",
            phone_number_id="phone-template-header-sync",
            asset_id="asset-template-header-sync",
            name="header-banner.jpg",
            asset_type="image",
            storage_url="https://cdn.example.com/header-banner.jpg",
            meta_media_id=None,
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-header-sync",
                conversation_id="conv-template-header-sync",
                customer_id="wa-user-template-header-sync",
                customer_language="en",
                customer_language_source="hint",
                provider_phone_number_id="phone-template-header-sync",
            )
        )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-header-sync",
                    waba_id="waba-template-header-sync",
                    name="header_sync_template",
                    language="en",
                    category="UTILITY",
                    body_text="Order {{order_id}} is ready.",
                    header_media_asset_id="asset-template-header-sync",
                    sample_variables={"order_id": "A-100"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )

        response = asyncio.run(
            template_service.send_template(
                template.template_id,
                TemplateSendRequest(
                    account_id="template-account-header-sync",
                    conversation_id="conv-template-header-sync",
                    variables={"order_id": "A-200"},
                ),
            )
        )
        messages = asyncio.run(
            runtime_state.list_message_models(
                account_id="template-account-header-sync",
                conversation_id="conv-template-header-sync",
            )
        )
        asset_events = session.query(MediaAssetEvent).filter_by(
            asset_id="asset-template-header-sync"
        ).order_by(MediaAssetEvent.created_at.asc()).all()
        synced_asset = session.query(MediaAsset).filter_by(id="asset-template-header-sync").one()
        provider_sync = session.query(MediaAssetProviderSync).filter_by(
            asset_id="asset-template-header-sync",
            phone_number_id="phone-template-header-sync",
        ).one()
        provider_reference = get_provider_sync_reference(provider_sync)

        assert response.status == "SENT"
        assert provider_reference is not None
        assert response.header_media_provider_media_id == provider_reference
        assert response.header_media_sync_status == "synced"
        assert synced_asset.meta_media_id is None
        assert synced_asset.meta_media_status is None
        assert provider_sync.provider_media_id == provider_reference
        assert provider_sync.meta_media_id is not None
        assert provider_sync.meta_media_id.startswith("mock-media-")
        assert provider_sync.sync_status == "synced"
        assert messages[0].payload["header_media_provider_media_id"] == provider_reference
        assert [event.event_type for event in asset_events] == [
            "media_asset_sync_succeeded",
            "media_asset_template_sent",
        ]
        assert asset_events[1].waba_id == "waba-template-header-sync"
    finally:
        session.close()


def test_template_header_media_send_accepts_storage_key_only_asset(
    db_session_factory: sessionmaker[Session],
    tmp_path,
) -> None:
    session, runtime_state, template_service = build_template_service(db_session_factory)

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-header-storage-key",
                display_name="Template Header Storage Key",
                provider_type="whatsapp",
            )
        )
        create_waba(
            session,
            account_id="template-account-header-storage-key",
            waba_id="waba-template-header-storage-key",
        )
        create_phone_number(
            session,
            account_id="template-account-header-storage-key",
            waba_id="waba-template-header-storage-key",
            phone_number_id="phone-template-header-storage-key",
        )

        asset_path = tmp_path / "template-header-banner.jpg"
        asset_path.write_bytes(b"header-media")
        create_media_asset(
            session,
            account_id="template-account-header-storage-key",
            waba_id="waba-template-header-storage-key",
            phone_number_id="phone-template-header-storage-key",
            asset_id="asset-template-header-storage-key",
            name="header-banner-local.jpg",
            asset_type="image",
            storage_key=str(asset_path),
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-header-storage-key",
                conversation_id="conv-template-header-storage-key",
                customer_id="wa-user-template-header-storage-key",
                customer_language="en",
                customer_language_source="hint",
                provider_phone_number_id="phone-template-header-storage-key",
            )
        )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-header-storage-key",
                    waba_id="waba-template-header-storage-key",
                    name="header_storage_key_template",
                    language="en",
                    category="UTILITY",
                    body_text="Order {{order_id}} is ready.",
                    header_media_asset_id="asset-template-header-storage-key",
                    sample_variables={"order_id": "A-100"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )

        response = asyncio.run(
            template_service.send_template(
                template.template_id,
                TemplateSendRequest(
                    account_id="template-account-header-storage-key",
                    conversation_id="conv-template-header-storage-key",
                    variables={"order_id": "A-200"},
                ),
            )
        )
        messages = asyncio.run(
            runtime_state.list_message_models(
                account_id="template-account-header-storage-key",
                conversation_id="conv-template-header-storage-key",
            )
        )
        provider_sync = session.query(MediaAssetProviderSync).filter_by(
            asset_id="asset-template-header-storage-key",
            phone_number_id="phone-template-header-storage-key",
        ).one()
        provider_reference = get_provider_sync_reference(provider_sync)

        assert response.status == "SENT"
        assert provider_reference is not None
        assert response.header_media_provider_media_id == provider_reference
        assert response.header_media_sync_status == "synced"
        assert provider_sync.provider_media_id == provider_reference
        assert provider_sync.meta_media_id is not None
        assert provider_sync.meta_media_id.startswith("mock-media-")
        assert messages[0].payload["header_media_provider_media_id"] == provider_reference
    finally:
        session.close()


def test_template_service_idempotency_key_reuses_existing_send_log(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(db_session_factory)

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-idempotent",
                display_name="Template Idempotent Account",
                provider_type="whatsapp",
            )
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-idempotent",
                conversation_id="conv-template-idempotent",
                customer_id="wa-user-idempotent",
                customer_language="en",
                customer_language_source="hint",
            )
        )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-idempotent",
                    name="idempotent_template",
                    language="en",
                    category="UTILITY",
                    body_text="Hello {{first_name}}",
                    sample_variables={"first_name": "Customer"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )

        first_send = asyncio.run(
            template_service.send_template(
                template.template_id,
                TemplateSendRequest(
                    account_id="template-account-idempotent",
                    conversation_id="conv-template-idempotent",
                    variables={"first_name": "Ana"},
                    idempotency_key="idem-template-1",
                ),
            )
        )
        second_send = asyncio.run(
            template_service.send_template(
                template.template_id,
                TemplateSendRequest(
                    account_id="template-account-idempotent",
                    conversation_id="conv-template-idempotent",
                    variables={"first_name": "Ana"},
                    idempotency_key="idem-template-1",
                ),
            )
        )

        messages = asyncio.run(
            runtime_state.list_message_models(
                account_id="template-account-idempotent",
                conversation_id="conv-template-idempotent",
            )
        )
        logs = asyncio.run(
            template_service.list_send_logs(account_id="template-account-idempotent")
        )

        assert first_send.send_log_id == second_send.send_log_id
        assert first_send.message_id == second_send.message_id
        assert len(messages) == 1
        assert len(logs) == 1
        assert logs[0].idempotency_key == "idem-template-1"
        send_audit_logs = asyncio.run(
            runtime_state.list_audit_logs(
                account_id="template-account-idempotent",
                action="template_sent",
            )
        )
        assert len(send_audit_logs) == 1
        assert send_audit_logs[0].payload["idempotency_key"] == "idem-template-1"
    finally:
        session.close()


def test_template_service_idempotency_key_is_account_scoped(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(db_session_factory)

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-idempotent-scope",
                display_name="Template Idempotent Scope Account",
                provider_type="whatsapp",
            )
        )
        for conversation_id, customer_id in (
            ("conv-template-idempotent-scope-1", "wa-user-idempotent-scope-1"),
            ("conv-template-idempotent-scope-2", "wa-user-idempotent-scope-2"),
        ):
            asyncio.run(
                runtime_state.ensure_conversation(
                    account_id="template-account-idempotent-scope",
                    conversation_id=conversation_id,
                    customer_id=customer_id,
                    customer_language="en",
                    customer_language_source="hint",
                )
            )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-idempotent-scope",
                    name="idempotent_scope_template",
                    language="en",
                    category="UTILITY",
                    body_text="Hello {{first_name}}",
                    sample_variables={"first_name": "Customer"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )

        first_send = asyncio.run(
            template_service.send_template(
                template.template_id,
                TemplateSendRequest(
                    account_id="template-account-idempotent-scope",
                    conversation_id="conv-template-idempotent-scope-1",
                    variables={"first_name": "Ana"},
                    idempotency_key="idem-template-account-scope",
                ),
            )
        )

        with pytest.raises(ValueError, match="idempotency key"):
            asyncio.run(
                template_service.send_template(
                    template.template_id,
                    TemplateSendRequest(
                        account_id="template-account-idempotent-scope",
                        conversation_id="conv-template-idempotent-scope-2",
                        variables={"first_name": "Luis"},
                        idempotency_key="idem-template-account-scope",
                    ),
                )
            )

        logs = asyncio.run(
            template_service.list_send_logs(account_id="template-account-idempotent-scope")
        )
        assert len(logs) == 1
        assert logs[0].id == first_send.send_log_id
        assert logs[0].idempotency_key == "idem-template-account-scope"
    finally:
        session.close()


def test_template_service_whatsapp_provider_requires_approved_status(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(
        db_session_factory,
        messaging_provider=AcceptedWhatsAppLikeProvider(),
    )

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-whatsapp",
                display_name="Template WhatsApp Account",
                provider_type="whatsapp",
            )
        )
        create_waba(session, account_id="template-account-whatsapp", waba_id="waba-template-wa")
        create_phone_number(
            session,
            account_id="template-account-whatsapp",
            waba_id="waba-template-wa",
            phone_number_id="phone-template-wa",
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-whatsapp",
                conversation_id="conv-template-wa",
                customer_id="wa-user-template-wa",
                customer_language="en",
                customer_language_source="hint",
                provider_phone_number_id="phone-template-wa",
            )
        )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-whatsapp",
                    waba_id="waba-template-wa",
                    name="wa_template_pending",
                    language="en",
                    category="UTILITY",
                    body_text="Hello {{first_name}}",
                    sample_variables={"first_name": "Customer"},
                )
            )
        )

        with pytest.raises(ValueError, match="cannot be sent"):
            asyncio.run(
                template_service.send_template(
                    template.template_id,
                    TemplateSendRequest(
                        account_id="template-account-whatsapp",
                        conversation_id="conv-template-wa",
                        variables={"first_name": "Ana"},
                    ),
                )
            )

        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )
        with pytest.raises(ValueError, match="does not match conversation Phone-Number-ID"):
            asyncio.run(
                template_service.send_template(
                    template.template_id,
                    TemplateSendRequest(
                        account_id="template-account-whatsapp",
                        conversation_id="conv-template-wa",
                        phone_number_id="phone-template-other",
                        variables={"first_name": "Ana"},
                    ),
                )
            )
        response = asyncio.run(
            template_service.send_template(
                template.template_id,
                TemplateSendRequest(
                    account_id="template-account-whatsapp",
                    conversation_id="conv-template-wa",
                    phone_number_id="phone-template-wa",
                    variables={"first_name": "Ana"},
                ),
            )
        )
        send_logs = asyncio.run(
            template_service.list_send_logs(account_id="template-account-whatsapp")
        )
        assert response.status == "SENT"
        assert response.provider == "whatsapp"
        assert response.phone_number_id == "phone-template-wa"
        assert len(send_logs) == 1
        assert send_logs[0].waba_id == "waba-template-wa"
        assert send_logs[0].phone_number_id == "phone-template-wa"
        assert send_logs[0].template_language == "en"
        assert send_logs[0].template_category == "UTILITY"
    finally:
        session.close()


def test_template_service_records_failed_send_attempt_when_provider_raises(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(
        db_session_factory,
        messaging_provider=FailingTemplateProvider(),
    )

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-failure",
                display_name="Template Failure Account",
                provider_type="mock",
            )
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-failure",
                conversation_id="conv-template-failure",
                customer_id="wa-user-template-failure",
                customer_language="en",
                customer_language_source="hint",
            )
        )
        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-failure",
                    name="failing_template",
                    language="en",
                    category="UTILITY",
                    body_text="Hello {{first_name}}",
                    sample_variables={"first_name": "Customer"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )

        with pytest.raises(ValueError, match="Template send failed"):
            asyncio.run(
                template_service.send_template(
                    template.template_id,
                    TemplateSendRequest(
                        account_id="template-account-failure",
                        conversation_id="conv-template-failure",
                        variables={"first_name": "Ana"},
                        idempotency_key="idem-template-failure",
                    ),
                )
            )

        logs = asyncio.run(
            template_service.list_send_logs(account_id="template-account-failure")
        )
        audit_logs = asyncio.run(
            runtime_state.list_audit_logs(
                account_id="template-account-failure",
                action="template_send_failed",
            )
        )

        assert len(logs) == 1
        assert logs[0].status == "FAILED"
        assert logs[0].error_code == "dispatch_exception"
        assert logs[0].idempotency_key == "idem-template-failure"
        assert len(audit_logs) == 1
        assert audit_logs[0].payload["failure_reason"] == "provider_unavailable"
        assert audit_logs[0].payload["status"] == "FAILED"
    finally:
        session.close()


def test_template_service_failed_header_media_sync_does_not_backfill_legacy_asset_reference(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(
        db_session_factory,
        messaging_provider=FailingTemplateProvider(),
    )

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-header-failure",
                display_name="Template Header Failure Account",
                provider_type="mock",
            )
        )
        create_waba(
            session,
            account_id="template-account-header-failure",
            waba_id="waba-template-header-failure",
        )
        create_phone_number(
            session,
            account_id="template-account-header-failure",
            waba_id="waba-template-header-failure",
            phone_number_id="phone-template-header-failure",
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-header-failure",
                conversation_id="conv-template-header-failure",
                customer_id="wa-user-template-header-failure",
                customer_language="en",
                customer_language_source="hint",
                provider_phone_number_id="phone-template-header-failure",
            )
        )
        create_media_asset(
            session,
            account_id="template-account-header-failure",
            waba_id="waba-template-header-failure",
            phone_number_id=None,
            asset_id="asset-template-header-failure",
            name="header-failure.jpg",
            asset_type="image",
            storage_url="https://cdn.example.com/header-failure.jpg",
            meta_media_id="legacy-header-media-1",
        )
        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-header-failure",
                    waba_id="waba-template-header-failure",
                    name="header_failure_template",
                    language="en",
                    category="UTILITY",
                    body_text="Hello {{first_name}}",
                    header_media_asset_id="asset-template-header-failure",
                    sample_variables={"first_name": "Customer"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )

        with pytest.raises(ValueError, match="Template send failed"):
            asyncio.run(
                template_service.send_template(
                    template.template_id,
                    TemplateSendRequest(
                        account_id="template-account-header-failure",
                        conversation_id="conv-template-header-failure",
                        variables={"first_name": "Ana"},
                    ),
                )
            )

        logs = asyncio.run(
            template_service.list_send_logs(account_id="template-account-header-failure")
        )
        asset_events = (
            session.query(MediaAssetEvent)
            .filter_by(asset_id="asset-template-header-failure")
            .order_by(MediaAssetEvent.created_at.asc(), MediaAssetEvent.id.asc())
            .all()
        )

        assert len(logs) == 1
        assert logs[0].status == "FAILED"
        assert logs[0].error_code == "header_media_sync_failed"
        assert logs[0].header_media_asset_id == "asset-template-header-failure"
        assert logs[0].header_media_provider_media_id is None

        failed_template_event = next(
            event for event in asset_events if event.event_type == "media_asset_template_send_failed"
        )
        assert failed_template_event.provider_media_id is None
        assert failed_template_event.meta_media_id is None
        assert failed_template_event.payload["provider_media_id"] is None
        assert failed_template_event.payload["meta_media_id"] is None
    finally:
        session.close()


def test_template_service_list_send_logs_supports_error_code_filter(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(db_session_factory)

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-log-filter",
                display_name="Template Log Filter Account",
                provider_type="mock",
            )
        )
        session.add_all(
            [
                TemplateSendLog(
                    account_id="template-account-log-filter",
                    wa_id="wa-user-filter-1",
                    status="FAILED",
                    error_code="dispatch_exception",
                    failed_at=utc_now(),
                    last_status_at=utc_now(),
                ),
                TemplateSendLog(
                    account_id="template-account-log-filter",
                    wa_id="wa-user-filter-2",
                    status="FAILED",
                    error_code="header_media_sync_failed",
                    failed_at=utc_now(),
                    last_status_at=utc_now(),
                ),
                TemplateSendLog(
                    account_id="template-account-log-filter",
                    wa_id="wa-user-filter-3",
                    status="SENT",
                    error_code=None,
                    sent_at=utc_now(),
                    last_status_at=utc_now(),
                ),
            ]
        )
        session.commit()

        filtered_logs = asyncio.run(
            template_service.list_send_logs(
                account_id="template-account-log-filter",
                status="FAILED",
                error_code="dispatch_exception",
            )
        )
        assert len(filtered_logs) == 1
        assert filtered_logs[0].error_code == "dispatch_exception"
        assert filtered_logs[0].status == "FAILED"
    finally:
        session.close()


def test_template_send_rejects_conversation_routed_through_different_waba(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(db_session_factory)

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-waba-mismatch",
                display_name="Template WABA Mismatch Account",
                provider_type="mock",
            )
        )
        create_waba(
            session,
            account_id="template-account-waba-mismatch",
            waba_id="waba-template-mismatch-a",
        )
        create_waba(
            session,
            account_id="template-account-waba-mismatch",
            waba_id="waba-template-mismatch-b",
        )
        create_phone_number(
            session,
            account_id="template-account-waba-mismatch",
            waba_id="waba-template-mismatch-b",
            phone_number_id="phone-template-mismatch-b",
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-waba-mismatch",
                conversation_id="conv-template-mismatch",
                customer_id="wa-user-template-mismatch",
                customer_language="en",
                customer_language_source="hint",
                provider_phone_number_id="phone-template-mismatch-b",
            )
        )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-waba-mismatch",
                    waba_id="waba-template-mismatch-a",
                    name="template_waba_mismatch",
                    language="en",
                    category="UTILITY",
                    body_text="Hello {{first_name}}",
                    sample_variables={"first_name": "Customer"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )

        with pytest.raises(ValueError, match="bound to WABA 'waba-template-mismatch-a'"):
            asyncio.run(
                template_service.send_template(
                    template.template_id,
                    TemplateSendRequest(
                        account_id="template-account-waba-mismatch",
                        conversation_id="conv-template-mismatch",
                        variables={"first_name": "Ana"},
                    ),
                )
            )

        logs = asyncio.run(
            template_service.list_send_logs(account_id="template-account-waba-mismatch")
        )
        assert len(logs) == 1
        assert logs[0].status == "FAILED"
        assert logs[0].error_code == "template_route_mismatch"
        assert logs[0].phone_number_id == "phone-template-mismatch-b"
    finally:
        session.close()


def test_template_send_accepts_recreated_local_waba_row_with_same_official_waba_id(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(db_session_factory)

    try:
        account_id = "template-account-waba-recreated-send"
        official_waba_id = "waba-template-send-recreated"
        asyncio.run(
            runtime_state.ensure_account(
                account_id=account_id,
                display_name="Template WABA Recreated Send Account",
                provider_type="mock",
            )
        )
        create_waba(session, account_id=account_id, waba_id=official_waba_id)
        create_phone_number(
            session,
            account_id=account_id,
            waba_id=official_waba_id,
            phone_number_id="phone-template-send-recreated",
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id=account_id,
                conversation_id="conv-template-send-recreated",
                customer_id="wa-user-template-send-recreated",
                customer_language="en",
                customer_language_source="hint",
                provider_phone_number_id="phone-template-send-recreated",
            )
        )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id=account_id,
                    waba_id=official_waba_id,
                    name="template_send_recreated",
                    language="en",
                    category="UTILITY",
                    body_text="Hello {{first_name}}",
                    sample_variables={"first_name": "Customer"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )

        legacy_waba = session.query(WhatsAppBusinessAccount).filter_by(
            account_id=account_id,
            waba_id=official_waba_id,
        ).one()
        legacy_waba.waba_id = f"{official_waba_id}-legacy"
        session.commit()

        create_waba(session, account_id=account_id, waba_id=official_waba_id)
        recreated_waba = session.query(WhatsAppBusinessAccount).filter_by(
            account_id=account_id,
            waba_id=official_waba_id,
        ).one()

        response = asyncio.run(
            template_service.send_template(
                template.template_id,
                TemplateSendRequest(
                    account_id=account_id,
                    conversation_id="conv-template-send-recreated",
                    variables={"first_name": "Ana"},
                ),
            )
        )
        rebound_template = session.query(MessageTemplate).filter_by(id=template.template_id).one()

        assert response.status == "SENT"
        assert response.delivered_text == "Hello Ana"
        assert rebound_template.waba_account_id == recreated_waba.id
        assert rebound_template.waba_id == official_waba_id
    finally:
        session.close()


def test_template_stats_cost_status_is_not_applicable_without_billable_counts(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(db_session_factory)

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-cost-na",
                display_name="Template Cost NA Account",
                provider_type="mock",
            )
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-cost-na",
                conversation_id="conv-template-cost-na",
                customer_id="wa-user-template-cost-na",
                customer_language="en",
                customer_language_source="hint",
            )
        )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-cost-na",
                    name="cost_not_applicable_template",
                    language="en",
                    category="UTILITY",
                    body_text="Hello {{first_name}}",
                    sample_variables={"first_name": "Customer"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )
        asyncio.run(
            template_service.send_template(
                template.template_id,
                TemplateSendRequest(
                    account_id="template-account-cost-na",
                    conversation_id="conv-template-cost-na",
                    variables={"first_name": "Ana"},
                ),
            )
        )

        summary = asyncio.run(
            template_service.get_stats_summary(
                account_id="template-account-cost-na",
                phone_number_id=None,
                category=None,
                language=None,
                date_from=None,
                date_to=None,
                allowed_account_ids=None,
            )
        )
        daily_rows = asyncio.run(
            template_service.list_daily_stats(
                account_id="template-account-cost-na",
                phone_number_id=None,
                category=None,
                language=None,
                date_from=None,
                date_to=None,
                allowed_account_ids=None,
            )
        )
        analytics = asyncio.run(
            template_service.get_template_analytics(
                template_id=template.template_id,
                phone_number_id=None,
                date_from=None,
                date_to=None,
                allowed_account_ids=None,
            )
        )

        assert summary.billable_count == 0
        assert summary.estimated_cost == 0
        assert summary.estimated_cost_status == "not_applicable"
        assert len(daily_rows) == 1
        assert daily_rows[0].billable_count == 0
        assert daily_rows[0].estimated_cost == 0
        assert daily_rows[0].estimated_cost_status == "not_applicable"
        assert analytics.summary.billable_count == 0
        assert analytics.summary.estimated_cost == 0
        assert analytics.summary.estimated_cost_status == "not_applicable"
        assert len(analytics.daily_rows) == 1
        assert analytics.daily_rows[0].estimated_cost_status == "not_applicable"
    finally:
        session.close()


def test_template_stats_cost_status_is_missing_provider_cost_when_billable_without_cost(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(db_session_factory)

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-cost-missing",
                display_name="Template Cost Missing Account",
                provider_type="whatsapp",
            )
        )
        create_waba(
            session,
            account_id="template-account-cost-missing",
            waba_id="waba-template-cost-missing",
        )
        create_phone_number(
            session,
            account_id="template-account-cost-missing",
            waba_id="waba-template-cost-missing",
            phone_number_id="phone-template-cost-missing",
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-cost-missing",
                conversation_id="conv-template-cost-missing",
                customer_id="wa-user-template-cost-missing",
                customer_language="en",
                customer_language_source="hint",
                provider_phone_number_id="phone-template-cost-missing",
            )
        )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-cost-missing",
                    waba_id="waba-template-cost-missing",
                    name="cost_missing_provider_template",
                    language="en",
                    category="UTILITY",
                    body_text="Hello {{first_name}}",
                    sample_variables={"first_name": "Customer"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )
        send_result = asyncio.run(
            template_service.send_template(
                template.template_id,
                TemplateSendRequest(
                    account_id="template-account-cost-missing",
                    conversation_id="conv-template-cost-missing",
                    variables={"first_name": "Ana"},
                ),
            )
        )

        send_log = session.query(TemplateSendLog).filter_by(id=send_result.send_log_id).one()
        send_log.billable = True
        session.add(send_log)
        session.commit()
        asyncio.run(
            template_service.rebuild_daily_stats(
                account_id="template-account-cost-missing",
                waba_id=None,
                phone_number_id=None,
                date_from=None,
                date_to=None,
                allowed_account_ids=None,
            )
        )

        summary = asyncio.run(
            template_service.get_stats_summary(
                account_id="template-account-cost-missing",
                phone_number_id=None,
                category=None,
                language=None,
                date_from=None,
                date_to=None,
                allowed_account_ids=None,
            )
        )
        daily_rows = asyncio.run(
            template_service.list_daily_stats(
                account_id="template-account-cost-missing",
                phone_number_id=None,
                category=None,
                language=None,
                date_from=None,
                date_to=None,
                allowed_account_ids=None,
            )
        )
        analytics = asyncio.run(
            template_service.get_template_analytics(
                template_id=template.template_id,
                phone_number_id=None,
                date_from=None,
                date_to=None,
                allowed_account_ids=None,
            )
        )

        assert summary.billable_count == 1
        assert summary.estimated_cost == 0
        assert summary.estimated_cost_status == "missing_provider_cost"
        assert len(daily_rows) == 1
        assert daily_rows[0].billable_count == 1
        assert daily_rows[0].estimated_cost == 0
        assert daily_rows[0].estimated_cost_status == "missing_provider_cost"
        assert analytics.summary.billable_count == 1
        assert analytics.summary.estimated_cost == 0
        assert analytics.summary.estimated_cost_status == "missing_provider_cost"
        assert len(analytics.daily_rows) == 1
        assert analytics.daily_rows[0].estimated_cost_status == "missing_provider_cost"
    finally:
        session.close()


def test_template_analytics_detail_comes_from_rebuildable_aggregates(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(
        db_session_factory,
        messaging_provider=AcceptedWhatsAppLikeProvider(),
    )

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-analytics-detail",
                display_name="Template Analytics Detail Account",
                provider_type="whatsapp",
            )
        )
        create_waba(
            session,
            account_id="template-account-analytics-detail",
            waba_id="waba-template-analytics-detail",
        )
        create_phone_number(
            session,
            account_id="template-account-analytics-detail",
            waba_id="waba-template-analytics-detail",
            phone_number_id="phone-template-analytics-detail",
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-analytics-detail",
                conversation_id="conv-template-analytics-detail",
                customer_id="wa-user-template-analytics-detail",
                customer_language="en",
                customer_language_source="hint",
                provider_phone_number_id="phone-template-analytics-detail",
            )
        )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-analytics-detail",
                    waba_id="waba-template-analytics-detail",
                    name="analytics_detail_template",
                    language="en",
                    category="UTILITY",
                    body_text="Order {{order_id}} is ready.",
                    sample_variables={"order_id": "A-100"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )

        send_results = [
            asyncio.run(
                template_service.send_template(
                    template.template_id,
                    TemplateSendRequest(
                        account_id="template-account-analytics-detail",
                        conversation_id="conv-template-analytics-detail",
                        variables={"order_id": order_id},
                    ),
                )
            )
            for order_id in ("A-201", "A-202", "A-203", "A-204")
        ]

        logs = {
            item.id: item
            for item in session.query(TemplateSendLog)
            .filter(
                TemplateSendLog.id.in_([result.send_log_id for result in send_results]),
            )
            .all()
        }
        logs[send_results[0].send_log_id].sent_at = datetime.fromisoformat("2026-06-07T09:05:00")
        logs[send_results[0].send_log_id].status = "FAILED"
        logs[send_results[0].send_log_id].failed_at = datetime.fromisoformat("2026-06-07T09:06:00")
        logs[send_results[0].send_log_id].last_status_at = datetime.fromisoformat("2026-06-07T09:06:00")
        logs[send_results[0].send_log_id].error_code = "recipient_blocked"

        logs[send_results[1].send_log_id].sent_at = datetime.fromisoformat("2026-06-07T09:25:00")
        logs[send_results[1].send_log_id].status = "FAILED"
        logs[send_results[1].send_log_id].failed_at = datetime.fromisoformat("2026-06-07T09:26:00")
        logs[send_results[1].send_log_id].last_status_at = datetime.fromisoformat("2026-06-07T09:26:00")
        logs[send_results[1].send_log_id].error_code = "recipient_blocked"

        logs[send_results[2].send_log_id].sent_at = datetime.fromisoformat("2026-06-07T10:05:00")
        logs[send_results[2].send_log_id].status = "READ"
        logs[send_results[2].send_log_id].delivered_at = datetime.fromisoformat("2026-06-07T10:06:00")
        logs[send_results[2].send_log_id].read_at = datetime.fromisoformat("2026-06-07T10:07:00")
        logs[send_results[2].send_log_id].last_status_at = datetime.fromisoformat("2026-06-07T10:07:00")
        logs[send_results[2].send_log_id].error_code = None

        logs[send_results[3].send_log_id].sent_at = datetime.fromisoformat("2026-06-07T10:45:00")
        logs[send_results[3].send_log_id].status = "FAILED"
        logs[send_results[3].send_log_id].failed_at = datetime.fromisoformat("2026-06-07T10:46:00")
        logs[send_results[3].send_log_id].last_status_at = datetime.fromisoformat("2026-06-07T10:46:00")
        logs[send_results[3].send_log_id].error_code = "rate_limited"
        session.commit()

        asyncio.run(
            template_service.rebuild_daily_stats(
                account_id="template-account-analytics-detail",
                waba_id=None,
                phone_number_id=None,
                date_from=None,
                date_to=None,
                allowed_account_ids=None,
            )
        )

        analytics = asyncio.run(
            template_service.get_template_analytics(
                template_id=template.template_id,
                phone_number_id=None,
                date_from=None,
                date_to=None,
                allowed_account_ids=None,
            )
        )

        assert analytics.summary.send_count == 4
        assert analytics.summary.delivered_count == 1
        assert analytics.summary.read_count == 1
        assert analytics.summary.failed_count == 3
        assert [item.model_dump() for item in analytics.hourly_rows] == [
            {
                "hour_bucket": 9,
                "send_count": 2,
                "delivered_count": 0,
                "read_count": 0,
                "failed_count": 2,
            },
            {
                "hour_bucket": 10,
                "send_count": 2,
                "delivered_count": 1,
                "read_count": 1,
                "failed_count": 1,
            },
        ]
        assert [item.model_dump() for item in analytics.failure_reasons] == [
            {"error_code": "recipient_blocked", "failed_count": 2},
            {"error_code": "rate_limited", "failed_count": 1},
        ]

        deleted_tables = delete_template_detail_aggregate_rows(
            session,
            account_id="template-account-analytics-detail",
            template_id=template.template_id,
        )
        assert deleted_tables, "Expected template analytics detail aggregate tables to exist."

        analytics_without_detail_aggregates = asyncio.run(
            template_service.get_template_analytics(
                template_id=template.template_id,
                phone_number_id=None,
                date_from=None,
                date_to=None,
                allowed_account_ids=None,
            )
        )

        assert analytics_without_detail_aggregates.summary.send_count == 4
        assert analytics_without_detail_aggregates.summary.delivered_count == 1
        assert analytics_without_detail_aggregates.summary.read_count == 1
        assert analytics_without_detail_aggregates.summary.failed_count == 3
        assert analytics_without_detail_aggregates.hourly_rows == []
        assert analytics_without_detail_aggregates.failure_reasons == []

        asyncio.run(
            template_service.rebuild_daily_stats(
                account_id="template-account-analytics-detail",
                waba_id=None,
                phone_number_id=None,
                date_from=None,
                date_to=None,
                allowed_account_ids=None,
            )
        )
        rebuilt_analytics = asyncio.run(
            template_service.get_template_analytics(
                template_id=template.template_id,
                phone_number_id=None,
                date_from=None,
                date_to=None,
                allowed_account_ids=None,
            )
        )

        assert [item.model_dump() for item in rebuilt_analytics.hourly_rows] == [
            {
                "hour_bucket": 9,
                "send_count": 2,
                "delivered_count": 0,
                "read_count": 0,
                "failed_count": 2,
            },
            {
                "hour_bucket": 10,
                "send_count": 2,
                "delivered_count": 1,
                "read_count": 1,
                "failed_count": 1,
            },
        ]
        assert [item.model_dump() for item in rebuilt_analytics.failure_reasons] == [
            {"error_code": "recipient_blocked", "failed_count": 2},
            {"error_code": "rate_limited", "failed_count": 1},
        ]
    finally:
        session.close()


def test_template_waba_filters_scope_template_lists_logs_and_stats(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(
        db_session_factory,
        messaging_provider=AcceptedWhatsAppLikeProvider(),
    )

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-waba-filters",
                display_name="Template WABA Filters Account",
                provider_type="whatsapp",
            )
        )
        create_waba(
            session,
            account_id="template-account-waba-filters",
            waba_id="waba-template-filter-a",
        )
        create_waba(
            session,
            account_id="template-account-waba-filters",
            waba_id="waba-template-filter-b",
        )
        create_phone_number(
            session,
            account_id="template-account-waba-filters",
            waba_id="waba-template-filter-a",
            phone_number_id="phone-template-filter-a",
        )
        create_phone_number(
            session,
            account_id="template-account-waba-filters",
            waba_id="waba-template-filter-b",
            phone_number_id="phone-template-filter-b",
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-waba-filters",
                conversation_id="conv-template-filter-a",
                customer_id="wa-user-template-filter-a",
                customer_language="en",
                customer_language_source="hint",
                provider_phone_number_id="phone-template-filter-a",
            )
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-waba-filters",
                conversation_id="conv-template-filter-b",
                customer_id="wa-user-template-filter-b",
                customer_language="en",
                customer_language_source="hint",
                provider_phone_number_id="phone-template-filter-b",
            )
        )

        template_a = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-waba-filters",
                    waba_id="waba-template-filter-a",
                    name="waba_filter_template_a",
                    language="en",
                    category="UTILITY",
                    body_text="Hello {{first_name}} from A",
                    sample_variables={"first_name": "Customer"},
                )
            )
        )
        template_b = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-waba-filters",
                    waba_id="waba-template-filter-b",
                    name="waba_filter_template_b",
                    language="en",
                    category="UTILITY",
                    body_text="Hello {{first_name}} from B",
                    sample_variables={"first_name": "Customer"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template_a.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template_b.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )
        asyncio.run(
            template_service.send_template(
                template_a.template_id,
                TemplateSendRequest(
                    account_id="template-account-waba-filters",
                    conversation_id="conv-template-filter-a",
                    variables={"first_name": "Ana"},
                ),
            )
        )
        asyncio.run(
            template_service.send_template(
                template_b.template_id,
                TemplateSendRequest(
                    account_id="template-account-waba-filters",
                    conversation_id="conv-template-filter-b",
                    variables={"first_name": "Ben"},
                ),
            )
        )

        filtered_templates = asyncio.run(
            template_service.list_templates(
                account_id="template-account-waba-filters",
                waba_id="waba-template-filter-a",
            )
        )
        filtered_logs = asyncio.run(
            template_service.list_send_logs(
                account_id="template-account-waba-filters",
                waba_id="waba-template-filter-a",
            )
        )
        filtered_summary = asyncio.run(
            template_service.get_stats_summary(
                account_id="template-account-waba-filters",
                waba_id="waba-template-filter-a",
                phone_number_id=None,
                category=None,
                language=None,
                date_from=None,
                date_to=None,
                allowed_account_ids=None,
            )
        )
        filtered_daily_rows = asyncio.run(
            template_service.list_daily_stats(
                account_id="template-account-waba-filters",
                waba_id="waba-template-filter-a",
                phone_number_id=None,
                category=None,
                language=None,
                date_from=None,
                date_to=None,
                allowed_account_ids=None,
            )
        )
        filtered_analytics = asyncio.run(
            template_service.get_template_analytics(
                template_id=template_a.template_id,
                waba_id="waba-template-filter-a",
                phone_number_id=None,
                date_from=None,
                date_to=None,
                allowed_account_ids=None,
            )
        )

        assert [item.template_id for item in filtered_templates] == [template_a.template_id]
        assert len(filtered_logs) == 1
        assert filtered_logs[0].waba_id == "waba-template-filter-a"
        assert filtered_logs[0].template_id == template_a.template_id
        assert filtered_summary.send_count == 1
        assert filtered_summary.delivered_count == 0
        assert len(filtered_daily_rows) == 1
        assert filtered_daily_rows[0].waba_id == "waba-template-filter-a"
        assert filtered_daily_rows[0].template_id == template_a.template_id
        assert filtered_analytics.template_id == template_a.template_id
        assert len(filtered_analytics.daily_rows) == 1
        assert filtered_analytics.daily_rows[0].waba_id == "waba-template-filter-a"
    finally:
        session.close()


def test_template_phone_number_filters_scope_logs_and_stats_within_same_waba(
    db_session_factory: sessionmaker[Session],
) -> None:
    session, runtime_state, template_service = build_template_service(
        db_session_factory,
        messaging_provider=AcceptedWhatsAppLikeProvider(),
    )

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="template-account-phone-filters",
                display_name="Template Phone Filters Account",
                provider_type="whatsapp",
            )
        )
        create_waba(
            session,
            account_id="template-account-phone-filters",
            waba_id="waba-template-phone-filters",
        )
        create_phone_number(
            session,
            account_id="template-account-phone-filters",
            waba_id="waba-template-phone-filters",
            phone_number_id="phone-template-filter-1",
        )
        create_phone_number(
            session,
            account_id="template-account-phone-filters",
            waba_id="waba-template-phone-filters",
            phone_number_id="phone-template-filter-2",
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-phone-filters",
                conversation_id="conv-template-filter-1",
                customer_id="wa-user-template-filter-1",
                customer_language="en",
                customer_language_source="hint",
                provider_phone_number_id="phone-template-filter-1",
            )
        )
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="template-account-phone-filters",
                conversation_id="conv-template-filter-2",
                customer_id="wa-user-template-filter-2",
                customer_language="en",
                customer_language_source="hint",
                provider_phone_number_id="phone-template-filter-2",
            )
        )

        template = asyncio.run(
            template_service.create_template_draft(
                TemplateDraftRequest(
                    account_id="template-account-phone-filters",
                    waba_id="waba-template-phone-filters",
                    name="phone_filter_template",
                    language="en",
                    category="UTILITY",
                    body_text="Hello {{first_name}} from shared WABA",
                    sample_variables={"first_name": "Customer"},
                )
            )
        )
        asyncio.run(
            template_service.update_template_status(
                template.template_id,
                TemplateStatusUpdateRequest(status="APPROVED"),
            )
        )

        first_send = asyncio.run(
            template_service.send_template(
                template.template_id,
                TemplateSendRequest(
                    account_id="template-account-phone-filters",
                    conversation_id="conv-template-filter-1",
                    variables={"first_name": "Ana"},
                ),
            )
        )
        second_send = asyncio.run(
            template_service.send_template(
                template.template_id,
                TemplateSendRequest(
                    account_id="template-account-phone-filters",
                    conversation_id="conv-template-filter-2",
                    variables={"first_name": "Ben"},
                ),
            )
        )

        logs = {
            item.id: item
            for item in session.query(TemplateSendLog)
            .filter(
                TemplateSendLog.id.in_([first_send.send_log_id, second_send.send_log_id]),
            )
            .all()
        }
        logs[first_send.send_log_id].sent_at = datetime.fromisoformat("2026-06-07T09:05:00")
        logs[first_send.send_log_id].status = "READ"
        logs[first_send.send_log_id].delivered_at = datetime.fromisoformat("2026-06-07T09:06:00")
        logs[first_send.send_log_id].read_at = datetime.fromisoformat("2026-06-07T09:07:00")
        logs[first_send.send_log_id].last_status_at = datetime.fromisoformat("2026-06-07T09:07:00")
        logs[first_send.send_log_id].error_code = None

        logs[second_send.send_log_id].sent_at = datetime.fromisoformat("2026-06-07T10:25:00")
        logs[second_send.send_log_id].status = "FAILED"
        logs[second_send.send_log_id].failed_at = datetime.fromisoformat("2026-06-07T10:26:00")
        logs[second_send.send_log_id].last_status_at = datetime.fromisoformat("2026-06-07T10:26:00")
        logs[second_send.send_log_id].error_code = "recipient_blocked"
        session.commit()

        asyncio.run(
            template_service.rebuild_daily_stats(
                account_id="template-account-phone-filters",
                waba_id="waba-template-phone-filters",
                phone_number_id=None,
                date_from=None,
                date_to=None,
                allowed_account_ids=None,
            )
        )

        filtered_logs = asyncio.run(
            template_service.list_send_logs(
                account_id="template-account-phone-filters",
                waba_id="waba-template-phone-filters",
                template_id=template.template_id,
                phone_number_id="phone-template-filter-1",
            )
        )
        filtered_summary = asyncio.run(
            template_service.get_stats_summary(
                account_id="template-account-phone-filters",
                waba_id="waba-template-phone-filters",
                phone_number_id="phone-template-filter-1",
                category=None,
                language=None,
                date_from=None,
                date_to=None,
                allowed_account_ids=None,
            )
        )
        filtered_daily_rows = asyncio.run(
            template_service.list_daily_stats(
                account_id="template-account-phone-filters",
                waba_id="waba-template-phone-filters",
                phone_number_id="phone-template-filter-1",
                category=None,
                language=None,
                date_from=None,
                date_to=None,
                allowed_account_ids=None,
            )
        )
        filtered_analytics = asyncio.run(
            template_service.get_template_analytics(
                template_id=template.template_id,
                waba_id="waba-template-phone-filters",
                phone_number_id="phone-template-filter-1",
                date_from=None,
                date_to=None,
                allowed_account_ids=None,
            )
        )

        assert len(filtered_logs) == 1
        assert filtered_logs[0].id == first_send.send_log_id
        assert filtered_logs[0].phone_number_id == "phone-template-filter-1"
        assert filtered_logs[0].status == "READ"

        assert filtered_summary.send_count == 1
        assert filtered_summary.delivered_count == 1
        assert filtered_summary.read_count == 1
        assert filtered_summary.failed_count == 0

        assert len(filtered_daily_rows) == 1
        assert filtered_daily_rows[0].template_id == template.template_id
        assert filtered_daily_rows[0].waba_id == "waba-template-phone-filters"
        assert filtered_daily_rows[0].phone_number_id == "phone-template-filter-1"
        assert filtered_daily_rows[0].send_count == 1
        assert filtered_daily_rows[0].delivered_count == 1
        assert filtered_daily_rows[0].read_count == 1
        assert filtered_daily_rows[0].failed_count == 0

        assert filtered_analytics.template_id == template.template_id
        assert filtered_analytics.summary.send_count == 1
        assert filtered_analytics.summary.delivered_count == 1
        assert filtered_analytics.summary.read_count == 1
        assert filtered_analytics.summary.failed_count == 0
        assert len(filtered_analytics.daily_rows) == 1
        assert filtered_analytics.daily_rows[0].phone_number_id == "phone-template-filter-1"
        assert [item.model_dump() for item in filtered_analytics.hourly_rows] == [
            {
                "hour_bucket": 9,
                "send_count": 1,
                "delivered_count": 1,
                "read_count": 1,
                "failed_count": 0,
            }
        ]
        assert filtered_analytics.failure_reasons == []
    finally:
        session.close()


def test_rebuild_template_stats_route_recreates_deleted_daily_rows(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_template_route_account(client)

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-conv-1",
            "user_id": "template-route-user-1",
            "text": "template rebuild",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "phone-template-route-1",
        },
    )
    assert inbound_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_rebuild",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, rebuild is ready.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    send_response = client.post(
        f"/api/templates/{template_id}/send",
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-conv-1",
            "variables": {"first_name": "Ana"},
        },
    )
    assert send_response.status_code == 200

    session = db_session_factory()
    try:
        assert (
            session.query(TemplateDailyStat)
            .filter(TemplateDailyStat.account_id == "template-route-account-1")
            .count()
            == 1
        )
        session.query(TemplateDailyStat).filter(
            TemplateDailyStat.account_id == "template-route-account-1"
        ).delete(synchronize_session=False)
        session.commit()
        assert (
            session.query(TemplateDailyStat)
            .filter(TemplateDailyStat.account_id == "template-route-account-1")
            .count()
            == 0
        )
    finally:
        session.close()

    rebuild_response = client.post(
        "/api/templates/stats/rebuild",
        params={"account_id": "template-route-account-1"},
    )
    assert rebuild_response.status_code == 200
    rebuild_payload = rebuild_response.json()
    assert rebuild_payload["account_id"] == "template-route-account-1"
    assert rebuild_payload["date_from"] is None
    assert rebuild_payload["date_to"] is None
    assert datetime.fromisoformat(rebuild_payload["rebuilt_at"])

    session = db_session_factory()
    try:
        rebuilt_rows = (
            session.query(TemplateDailyStat)
            .filter(TemplateDailyStat.account_id == "template-route-account-1")
            .all()
        )
        assert len(rebuilt_rows) == 1
        assert rebuilt_rows[0].template_id == template_id
        assert rebuilt_rows[0].template_name == "template_route_rebuild"
        assert rebuilt_rows[0].send_count == 1
        assert rebuilt_rows[0].delivered_count == 0
        assert rebuilt_rows[0].failed_count == 0
    finally:
        session.close()

    summary_response = client.get(
        "/api/templates/stats/summary",
        params={"account_id": "template-route-account-1"},
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["send_count"] == 1
    assert summary["delivered_count"] == 0
    assert summary["read_count"] == 0
    assert summary["failed_count"] == 0
    assert summary["billable_count"] == 0
    assert summary["estimated_cost_status"] == "not_applicable"

    audit_logs_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "template-route-account-1",
            "action": "template_stats_rebuilt",
            "limit": 10,
        },
    )
    assert audit_logs_response.status_code == 200
    audit_logs = audit_logs_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["target_type"] == "template_daily_stats"


def test_rebuild_template_stats_route_tracks_phone_scope_in_audit_log(
    client: TestClient,
) -> None:
    register_template_route_account(client)

    rebuild_response = client.post(
        "/api/templates/stats/rebuild",
        params={
            "account_id": "template-route-account-1",
            "phone_number_id": "phone-template-route-1",
        },
    )
    assert rebuild_response.status_code == 200
    payload = rebuild_response.json()
    assert payload["account_id"] == "template-route-account-1"
    assert payload["phone_number_id"] == "phone-template-route-1"

    audit_logs_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "template-route-account-1",
            "action": "template_stats_rebuilt",
            "limit": 10,
        },
    )
    assert audit_logs_response.status_code == 200
    audit_logs = audit_logs_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["target_id"] == "phone-template-route-1"
    assert audit_logs[0]["payload"]["scope_type"] == "phone_number"


def test_rebuild_template_stats_route_respects_sent_or_created_date_window(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_template_route_account(
        client,
        phone_numbers=[
            {
                "phone_number_id": "phone-template-route-window-1",
                "display_phone_number": "+1 555 300 0201",
                "verified_name": "Template Route Window 1",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
            {
                "phone_number_id": "phone-template-route-window-2",
                "display_phone_number": "+1 555 300 0202",
                "verified_name": "Template Route Window 2",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
        ],
    )

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_window_rebuild",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, window rebuild is ready.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    send_log_ids: dict[str, str] = {}
    for conversation_id, user_id, phone_number_id in (
        (
            "conv-template-route-window-sent-at",
            "user-template-route-window-sent-at",
            "phone-template-route-window-1",
        ),
        (
            "conv-template-route-window-created-at",
            "user-template-route-window-created-at",
            "phone-template-route-window-1",
        ),
        (
            "conv-template-route-window-outside-sent-at",
            "user-template-route-window-outside-sent-at",
            "phone-template-route-window-2",
        ),
    ):
        inbound_response = client.post(
            "/dev/mock/inbound-message",
            json={
                "account_id": "template-route-account-1",
                "conversation_id": conversation_id,
                "user_id": user_id,
                "text": "template window rebuild",
                "mode": "echo",
                "language_hint": "en",
                "phone_number_id": phone_number_id,
            },
        )
        assert inbound_response.status_code == 200

        send_response = client.post(
            f"/api/templates/{template_id}/send",
            json={
                "account_id": "template-route-account-1",
                "conversation_id": conversation_id,
                "variables": {"first_name": "Ana"},
            },
        )
        assert send_response.status_code == 200
        send_log_ids[conversation_id] = send_response.json()["send_log_id"]

    session = db_session_factory()
    try:
        sent_at_log = session.query(TemplateSendLog).filter_by(
            id=send_log_ids["conv-template-route-window-sent-at"]
        ).one()
        sent_at_log.sent_at = datetime.fromisoformat("2026-06-07T09:15:00")
        sent_at_log.created_at = datetime.fromisoformat("2026-06-06T09:15:00")
        sent_at_log.last_status_at = datetime.fromisoformat("2026-06-07T09:15:00")

        created_at_log = session.query(TemplateSendLog).filter_by(
            id=send_log_ids["conv-template-route-window-created-at"]
        ).one()
        created_at_log.sent_at = None
        created_at_log.created_at = datetime.fromisoformat("2026-06-07T10:15:00")
        created_at_log.last_status_at = datetime.fromisoformat("2026-06-07T10:15:00")

        outside_sent_at_log = session.query(TemplateSendLog).filter_by(
            id=send_log_ids["conv-template-route-window-outside-sent-at"]
        ).one()
        outside_sent_at_log.sent_at = datetime.fromisoformat("2026-06-06T11:15:00")
        outside_sent_at_log.created_at = datetime.fromisoformat("2026-06-07T11:15:00")
        outside_sent_at_log.last_status_at = datetime.fromisoformat("2026-06-06T11:15:00")

        session.query(TemplateDailyStat).filter(
            TemplateDailyStat.account_id == "template-route-account-1"
        ).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()

    rebuild_response = client.post(
        "/api/templates/stats/rebuild",
        params={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "date_from": "2026-06-07",
            "date_to": "2026-06-07",
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text
    rebuild_payload = rebuild_response.json()
    assert rebuild_payload["account_id"] == "template-route-account-1"
    assert rebuild_payload["waba_id"] == "waba-template-route-1"
    assert rebuild_payload["date_from"] == "2026-06-07"
    assert rebuild_payload["date_to"] == "2026-06-07"

    session = db_session_factory()
    try:
        rebuilt_rows = (
            session.query(TemplateDailyStat)
            .filter(TemplateDailyStat.account_id == "template-route-account-1")
            .all()
        )
        assert len(rebuilt_rows) == 1
        assert rebuilt_rows[0].date.isoformat() == "2026-06-07"
        assert rebuilt_rows[0].template_id == template_id
        assert rebuilt_rows[0].waba_id == "waba-template-route-1"
        assert rebuilt_rows[0].phone_number_id == "phone-template-route-window-1"
        assert rebuilt_rows[0].send_count == 2
    finally:
        session.close()

    summary_response = client.get(
        "/api/templates/stats/summary",
        params={
            "account_id": "template-route-account-1",
            "date_from": "2026-06-07",
            "date_to": "2026-06-07",
        },
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["send_count"] == 2
    assert summary["delivered_count"] == 0
    assert summary["failed_count"] == 0


def test_rebuild_template_stats_route_rejects_cross_account_operator_scope(
    client: TestClient,
) -> None:
    register_template_route_account(client)

    response = client.post(
        "/api/templates/stats/rebuild",
        params={"account_id": "template-route-account-1"},
        headers={
            "X-Actor-Id": "operator-template-route-other",
            "X-Actor-Role": "operator",
            "X-Actor-Account-Ids": "template-route-account-other",
        },
    )

    assert response.status_code == 403
    assert "cannot access account 'template-route-account-1'" in response.json()["detail"]


def test_template_stats_routes_return_404_for_missing_account_scope(
    client: TestClient,
) -> None:
    missing_account_id = "template-route-missing-account"
    expected_detail = f"Account '{missing_account_id}' was not found."

    for method, path in (
        ("get", "/api/templates/stats/summary"),
        ("get", "/api/templates/stats/daily"),
        ("post", "/api/templates/stats/rebuild"),
    ):
        response = getattr(client, method)(
            path,
            params={"account_id": missing_account_id},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == expected_detail


def test_template_list_and_send_logs_routes_return_404_for_missing_account_scope(
    client: TestClient,
) -> None:
    missing_account_id = "template-route-missing-account-list"
    expected_detail = f"Account '{missing_account_id}' was not found."

    for path in (
        "/api/templates",
        "/api/templates/send-logs",
    ):
        response = client.get(
            path,
            params={"account_id": missing_account_id},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == expected_detail


def test_template_draft_route_returns_404_without_creating_missing_account(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    missing_account_id = "template-route-missing-account-draft"

    response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": missing_account_id,
            "waba_id": "waba-unused-for-missing-account",
            "name": "missing_account_template",
            "language": "zh_CN",
            "category": "UTILITY",
            "body_text": "missing account should fail",
            "sample_variables": {},
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == f"Account '{missing_account_id}' was not found."

    with db_session_factory() as session:
        assert session.get(Account, missing_account_id) is None


def test_template_submit_route_returns_409_for_non_draft_template(
    client: TestClient,
) -> None:
    register_template_route_account(client)

    create_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_submit_once",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, submit once only.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert create_response.status_code == 200
    template_id = create_response.json()["template_id"]

    first_submit_response = client.post(f"/api/templates/{template_id}/submit")
    assert first_submit_response.status_code == 200
    assert first_submit_response.json()["template"]["status"] == "PENDING"

    second_submit_response = client.post(f"/api/templates/{template_id}/submit")
    assert second_submit_response.status_code == 409
    assert "cannot be submitted again" in second_submit_response.json()["detail"]


def test_template_draft_patch_route_updates_draft_fields(
    client: TestClient,
) -> None:
    register_template_route_account(client)

    create_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_patch_update",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, original draft copy.",
            "header_text": "Original header",
            "footer_text": "Original footer",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert create_response.status_code == 200
    template_id = create_response.json()["template_id"]

    patch_response = client.patch(
        f"/api/templates/{template_id}/draft",
        json={
            "language": "pt_BR",
            "body_text": "Ola {{first_name}}, seu pedido {{order_id}} esta pronto.",
            "header_text": None,
            "footer_text": None,
            "sample_variables": {
                "first_name": "Cliente",
                "order_id": "A-200",
            },
        },
    )
    assert patch_response.status_code == 200, patch_response.text
    payload = patch_response.json()
    assert payload["template_id"] == template_id
    assert payload["status"] == "DRAFT"
    assert payload["language"] == "pt_BR"
    assert payload["body_text"] == "Ola {{first_name}}, seu pedido {{order_id}} esta pronto."
    assert payload["header_text"] is None
    assert payload["footer_text"] is None
    assert payload["sample_variables"] == {
        "first_name": "Cliente",
        "order_id": "A-200",
    }


def test_template_submit_route_returns_503_when_whatsapp_access_token_is_missing(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_template_route_account(client)

    create_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_missing_submit_token",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, submit should require a token.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert create_response.status_code == 200
    template_id = create_response.json()["template_id"]

    with db_session_factory() as session:
        waba_account = session.query(WhatsAppBusinessAccount).filter_by(
            account_id="template-route-account-1",
            waba_id="waba-template-route-1",
        ).one()
        waba_account.access_token = None
        session.commit()

    client.app.dependency_overrides[get_template_registry_service] = (
        lambda: WhatsAppTemplateRegistryProvider()
    )
    try:
        submit_response = client.post(f"/api/templates/{template_id}/submit")
    finally:
        client.app.dependency_overrides.pop(get_template_registry_service, None)

    assert submit_response.status_code == 503
    assert "access_token" in submit_response.json()["detail"]


def test_template_sync_route_returns_503_when_whatsapp_access_token_is_missing(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_template_route_account(client)

    with db_session_factory() as session:
        waba_account = session.query(WhatsAppBusinessAccount).filter_by(
            account_id="template-route-account-1",
            waba_id="waba-template-route-1",
        ).one()
        waba_account.access_token = None
        session.commit()

    client.app.dependency_overrides[get_template_registry_service] = (
        lambda: WhatsAppTemplateRegistryProvider()
    )
    try:
        sync_response = client.post(
            "/api/templates/sync",
            json={
                "account_id": "template-route-account-1",
                "waba_id": "waba-template-route-1",
                "import_missing": True,
            },
        )
    finally:
        client.app.dependency_overrides.pop(get_template_registry_service, None)

    assert sync_response.status_code == 503
    assert "access_token" in sync_response.json()["detail"]


def test_template_draft_patch_route_returns_404_for_missing_waba(
    client: TestClient,
) -> None:
    register_template_route_account(client)

    create_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_patch_missing_waba",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, patch should fail for unknown WABA.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert create_response.status_code == 200
    template_id = create_response.json()["template_id"]

    patch_response = client.patch(
        f"/api/templates/{template_id}/draft",
        json={"waba_id": "waba-template-route-missing"},
    )

    assert patch_response.status_code == 404
    assert (
        patch_response.json()["detail"]
        == "WABA 'waba-template-route-missing' for account 'template-route-account-1' was not found."
    )


def test_template_submit_route_returns_502_when_registry_provider_fails(
    client: TestClient,
) -> None:
    register_template_route_account(client)

    create_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_submit_registry_failure",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, upstream submit should surface as provider failure.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert create_response.status_code == 200
    template_id = create_response.json()["template_id"]

    client.app.dependency_overrides[get_template_registry_service] = (
        lambda: FailingTemplateRegistryProvider()
    )
    try:
        submit_response = client.post(f"/api/templates/{template_id}/submit")
    finally:
        client.app.dependency_overrides.pop(get_template_registry_service, None)

    assert submit_response.status_code == 502
    assert submit_response.json()["detail"] == "template_registry_unavailable"


def test_template_sync_route_returns_502_when_registry_provider_fails(
    client: TestClient,
) -> None:
    register_template_route_account(client)

    client.app.dependency_overrides[get_template_registry_service] = (
        lambda: FailingTemplateRegistryProvider()
    )
    try:
        sync_response = client.post(
            "/api/templates/sync",
            json={
                "account_id": "template-route-account-1",
                "waba_id": "waba-template-route-1",
                "import_missing": True,
            },
        )
    finally:
        client.app.dependency_overrides.pop(get_template_registry_service, None)

    assert sync_response.status_code == 502
    assert sync_response.json()["detail"] == "template_registry_sync_unavailable"


def test_template_draft_route_returns_409_for_cross_account_header_media_asset(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_template_route_account(client)

    second_account_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "template-route-account-2",
            "display_name": "Template Route Account 2",
            "meta_business_portfolio_id": "portfolio-template-route-2",
            "waba_id": "waba-template-route-2",
            "access_token": "token-template-route-2",
            "verify_token": "verify-template-route-2",
            "app_secret": "secret-template-route-2",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "phone-template-route-2",
                    "display_phone_number": "+1 555 300 0002",
                    "verified_name": "Template Route 2",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert second_account_response.status_code == 200

    with db_session_factory() as session:
        create_media_asset(
            session,
            account_id="template-route-account-2",
            waba_id="waba-template-route-2",
            phone_number_id=None,
            asset_id="asset-template-route-cross-account",
            name="cross-account-header",
            asset_type="image",
            storage_url="https://cdn.example.com/template-route-cross-account.jpg",
            meta_media_id="meta-template-route-cross-account",
        )

    response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_cross_account_header",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, cross-account header should be rejected.",
            "header_media_asset_id": "asset-template-route-cross-account",
            "sample_variables": {"first_name": "Customer"},
        },
    )

    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "Media asset 'asset-template-route-cross-account' does not belong to account 'template-route-account-1'."
    )


def test_template_analytics_route_enforces_account_scope_and_missing_template_contract(
    client: TestClient,
) -> None:
    register_template_route_account(client)

    create_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_scope_analytics",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, your scoped template is ready.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert create_response.status_code == 200
    template_id = create_response.json()["template_id"]

    cross_account_response = client.get(
        f"/api/templates/{template_id}/analytics",
        headers={
            "X-Actor-Id": "operator-template-route-analytics-other",
            "X-Actor-Role": "operator",
            "X-Actor-Account-Ids": "template-route-account-other",
        },
    )
    assert cross_account_response.status_code == 403
    assert "accessible account scope" in cross_account_response.json()["detail"]

    missing_response = client.get("/api/templates/template-route-missing-analytics/analytics")
    assert missing_response.status_code == 404
    assert "template-route-missing-analytics" in missing_response.json()["detail"]


def test_template_routes_reject_invalid_date_window_filters(
    client: TestClient,
) -> None:
    register_template_route_account(client)

    for method, path in (
        ("get", "/api/templates/send-logs"),
        ("get", "/api/templates/stats/summary"),
        ("get", "/api/templates/stats/daily"),
        ("post", "/api/templates/stats/rebuild"),
    ):
        response = getattr(client, method)(
            path,
            params={
                "account_id": "template-route-account-1",
                "date_from": "2026-06-08",
                "date_to": "2026-06-07",
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "date_from must be less than or equal to date_to."


def test_template_send_logs_and_stats_routes_filter_by_waba_and_phone_number(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_template_route_account(
        client,
        phone_numbers=[
            {
                "phone_number_id": "phone-template-route-filter-1",
                "display_phone_number": "+1 555 300 0301",
                "verified_name": "Template Route Filter 1",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
            {
                "phone_number_id": "phone-template-route-filter-2",
                "display_phone_number": "+1 555 300 0302",
                "verified_name": "Template Route Filter 2",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
        ],
    )

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_waba_phone_filter",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, your scoped update is ready.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    for conversation_id, user_id, phone_number_id, first_name in (
        (
            "template-route-filter-conv-1",
            "template-route-filter-user-1",
            "phone-template-route-filter-1",
            "Ana",
        ),
        (
            "template-route-filter-conv-2",
            "template-route-filter-user-2",
            "phone-template-route-filter-2",
            "Ben",
        ),
    ):
        inbound_response = client.post(
            "/dev/mock/inbound-message",
            json={
                "account_id": "template-route-account-1",
                "conversation_id": conversation_id,
                "user_id": user_id,
                "text": "template route filter scope",
                "mode": "echo",
                "language_hint": "en",
                "phone_number_id": phone_number_id,
            },
        )
        assert inbound_response.status_code == 200

        send_response = client.post(
            f"/api/templates/{template_id}/send",
            json={
                "account_id": "template-route-account-1",
                "conversation_id": conversation_id,
                "variables": {"first_name": first_name},
            },
        )
        assert send_response.status_code == 200

    filtered_logs_response = client.get(
        "/api/templates/send-logs",
        params={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "phone_number_id": "phone-template-route-filter-1",
            "template_id": template_id,
        },
    )
    assert filtered_logs_response.status_code == 200
    filtered_logs = filtered_logs_response.json()
    assert len(filtered_logs) == 1
    assert filtered_logs[0]["waba_id"] == "waba-template-route-1"
    assert filtered_logs[0]["phone_number_id"] == "phone-template-route-filter-1"
    assert filtered_logs[0]["conversation_id"] == "template-route-filter-conv-1"
    assert filtered_logs[0]["conversation_id"] == filtered_logs[0]["external_conversation_id"]
    assert filtered_logs[0]["internal_conversation_id"] != "template-route-filter-conv-1"

    summary_response = client.get(
        "/api/templates/stats/summary",
        params={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "phone_number_id": "phone-template-route-filter-1",
        },
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["send_count"] == 1
    assert summary["delivered_count"] == 0
    assert summary["failed_count"] == 0

    daily_response = client.get(
        "/api/templates/stats/daily",
        params={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "phone_number_id": "phone-template-route-filter-1",
        },
    )
    assert daily_response.status_code == 200
    daily_rows = daily_response.json()
    assert len(daily_rows) == 1
    assert daily_rows[0]["waba_id"] == "waba-template-route-1"
    assert daily_rows[0]["phone_number_id"] == "phone-template-route-filter-1"
    assert daily_rows[0]["send_count"] == 1

    session = db_session_factory()
    try:
        persisted_logs = (
            session.query(TemplateSendLog)
            .filter(
                TemplateSendLog.account_id == "template-route-account-1",
                TemplateSendLog.template_id == template_id,
            )
            .order_by(TemplateSendLog.created_at.asc())
            .all()
        )
        assert len(persisted_logs) == 2
        assert {log.phone_number_id for log in persisted_logs} == {
            "phone-template-route-filter-1",
            "phone-template-route-filter-2",
        }
    finally:
        session.close()


def test_template_send_log_routes_preserve_legacy_provider_phone_number_scope(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    provider_phone_number_id = "phone-template-route-legacy-provider"
    register_template_route_account(
        client,
        phone_numbers=[
            {
                "phone_number_id": provider_phone_number_id,
                "display_phone_number": "+1 555 300 0351",
                "verified_name": "Template Route Legacy Provider",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_legacy_provider_phone",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, legacy provider phone scope is ready.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    session = db_session_factory()
    try:
        template = session.get(MessageTemplate, template_id)
        assert template is not None
        session.add(
            TemplateSendLog(
                account_id="template-route-account-1",
                template_id=template_id,
                waba_id="waba-template-route-1",
                template_name=template.name,
                template_language=template.language,
                template_category=template.category,
                template_code=template.meta_template_id,
                phone_number_id=provider_phone_number_id,
                wa_id="wa-template-route-legacy-provider",
                message_id="msg-template-route-legacy-provider",
                status="SENT",
                sent_at=utc_now(),
                last_status_at=utc_now(),
            )
        )
        session.commit()
    finally:
        session.close()

    logs_response = client.get(
        "/api/templates/send-logs",
        params={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "phone_number_id": provider_phone_number_id,
            "template_id": template_id,
        },
    )
    assert logs_response.status_code == 200, logs_response.text
    logs = logs_response.json()
    assert len(logs) == 1
    assert logs[0]["phone_number_id"] == provider_phone_number_id
    assert logs[0]["message_id"] == "msg-template-route-legacy-provider"

    rebuild_response = client.post(
        "/api/templates/stats/rebuild",
        params={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "phone_number_id": provider_phone_number_id,
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text

    daily_response = client.get(
        "/api/templates/stats/daily",
        params={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "phone_number_id": provider_phone_number_id,
        },
    )
    assert daily_response.status_code == 200
    daily_rows = daily_response.json()
    assert len(daily_rows) == 1
    assert daily_rows[0]["phone_number_id"] == provider_phone_number_id
    assert daily_rows[0]["send_count"] == 1


def test_template_send_log_routes_extract_provider_scope_from_nested_message_payload(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    provider_phone_number_id = "phone-template-route-nested-payload"
    register_template_route_account(
        client,
        phone_numbers=[
            {
                "phone_number_id": provider_phone_number_id,
                "display_phone_number": "+1 555 300 0353",
                "verified_name": "Template Route Nested Payload",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_nested_scope_payload",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, nested scope payload is ready.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    session = db_session_factory()
    try:
        template = session.get(MessageTemplate, template_id)
        assert template is not None
        conversation = (
            session.query(Conversation)
            .filter(
                Conversation.account_id == "template-route-account-1",
                Conversation.external_conversation_id == "template-route-nested-conversation",
            )
            .first()
        )
        if conversation is None:
            conversation = Conversation(
                account_id="template-route-account-1",
                external_conversation_id="template-route-nested-conversation",
                customer_id="wa-template-route-nested-payload",
                status="open",
            )
            session.add(conversation)
            session.flush()
        message = Message(
            account_id="template-route-account-1",
            conversation_id=conversation.id,
            sender_id="system",
            recipient_id="wa-template-route-nested-payload",
            direction="outbound",
            message_type="template",
            content_text="nested payload scope",
            payload={
                "provider_payload": {
                    "metadata": {
                        "phone_number_id": provider_phone_number_id,
                    },
                    "waba_id": "waba-template-route-1",
                }
            },
            provider_message_id="provider-msg-template-route-nested-payload",
        )
        session.add(message)
        session.flush()
        session.add(
            TemplateSendLog(
                account_id="template-route-account-1",
                template_id=template_id,
                waba_id="waba-template-route-stale",
                template_name=template.name,
                template_language=template.language,
                template_category=template.category,
                template_code=template.meta_template_id,
                phone_number_id="phone-template-route-nested-payload-local-row",
                wa_id="wa-template-route-nested-payload",
                message_id=message.id,
                status="SENT",
                sent_at=utc_now(),
                last_status_at=utc_now(),
            )
        )
        session.commit()
    finally:
        session.close()

    logs_response = client.get(
        "/api/templates/send-logs",
        params={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "phone_number_id": provider_phone_number_id,
            "template_id": template_id,
        },
    )
    assert logs_response.status_code == 200, logs_response.text
    logs = logs_response.json()
    assert len(logs) == 1
    assert logs[0]["waba_id"] == "waba-template-route-1"
    assert logs[0]["phone_number_id"] == provider_phone_number_id

    rebuild_response = client.post(
        "/api/templates/stats/rebuild",
        params={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "phone_number_id": provider_phone_number_id,
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text

    daily_response = client.get(
        "/api/templates/stats/daily",
        params={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "phone_number_id": provider_phone_number_id,
        },
    )
    assert daily_response.status_code == 200
    daily_rows = daily_response.json()
    assert len(daily_rows) == 1
    assert daily_rows[0]["waba_id"] == "waba-template-route-1"
    assert daily_rows[0]["phone_number_id"] == provider_phone_number_id
    assert daily_rows[0]["send_count"] == 1


def test_template_send_log_routes_ignore_legacy_local_phone_row_ids_when_filtering_provider_scope(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    provider_phone_number_id = "phone-template-route-mixed-scope"
    register_template_route_account(
        client,
        phone_numbers=[
            {
                "phone_number_id": provider_phone_number_id,
                "display_phone_number": "+1 555 300 0352",
                "verified_name": "Template Route Mixed Scope",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_mixed_phone_scope",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, mixed phone scope stays isolated.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    session = db_session_factory()
    try:
        template = session.get(MessageTemplate, template_id)
        assert template is not None
        phone_number = session.query(WhatsAppPhoneNumber).filter_by(
            account_id="template-route-account-1",
            phone_number_id=provider_phone_number_id,
        ).one()
        session.add_all(
            [
                TemplateSendLog(
                    account_id="template-route-account-1",
                    template_id=template_id,
                    waba_id="waba-template-route-1",
                    template_name=template.name,
                    template_language=template.language,
                    template_category=template.category,
                    template_code=template.meta_template_id,
                    phone_number_id=phone_number.id,
                    wa_id="wa-template-route-mixed-legacy",
                    message_id="msg-template-route-mixed-legacy",
                    status="SENT",
                    sent_at=utc_now(),
                    last_status_at=utc_now(),
                ),
                TemplateSendLog(
                    account_id="template-route-account-1",
                    template_id=template_id,
                    waba_id="waba-template-route-1",
                    template_name=template.name,
                    template_language=template.language,
                    template_category=template.category,
                    template_code=template.meta_template_id,
                    phone_number_id=provider_phone_number_id,
                    wa_id="wa-template-route-mixed-provider",
                    message_id="msg-template-route-mixed-provider",
                    status="SENT",
                    sent_at=utc_now(),
                    last_status_at=utc_now(),
                ),
            ]
        )
        session.commit()
    finally:
        session.close()

    logs_response = client.get(
        "/api/templates/send-logs",
        params={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "phone_number_id": provider_phone_number_id,
            "template_id": template_id,
        },
    )
    assert logs_response.status_code == 200, logs_response.text
    logs = logs_response.json()
    assert [item["message_id"] for item in logs] == ["msg-template-route-mixed-provider"]

    rebuild_response = client.post(
        "/api/templates/stats/rebuild",
        params={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "phone_number_id": provider_phone_number_id,
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text

    daily_response = client.get(
        "/api/templates/stats/daily",
        params={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "phone_number_id": provider_phone_number_id,
        },
    )
    assert daily_response.status_code == 200
    daily_rows = daily_response.json()
    assert len(daily_rows) == 1
    assert daily_rows[0]["phone_number_id"] == provider_phone_number_id
    assert daily_rows[0]["send_count"] == 1


def test_template_stats_rebuild_preserves_snapshot_phone_scope_after_relationship_drift(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_template_route_account(
        client,
        phone_numbers=[
            {
                "phone_number_id": "phone-template-route-drift-1",
                "display_phone_number": "+1 555 300 0361",
                "verified_name": "Template Route Drift 1",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-conv-drift-snapshot",
            "user_id": "template-route-user-drift-snapshot",
            "text": "template stats drift snapshot",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "phone-template-route-drift-1",
        },
    )
    assert inbound_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_stats_drift_snapshot",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, stats rebuild keeps snapshot scope.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    send_response = client.post(
        f"/api/templates/{template_id}/send",
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-conv-drift-snapshot",
            "variables": {"first_name": "Ana"},
        },
    )
    assert send_response.status_code == 200

    with db_session_factory() as session:
        phone_number = session.query(WhatsAppPhoneNumber).filter_by(
            account_id="template-route-account-1",
            phone_number_id="phone-template-route-drift-1",
        ).one()
        phone_number.phone_number_id = "phone-template-route-drift-1-current"
        phone_number.waba_id = "waba-template-route-1-current"
        assert phone_number.waba_account is not None
        phone_number.waba_account.waba_id = "waba-template-route-1-current"
        session.commit()

    with db_session_factory() as session:
        send_logs = (
            session.query(TemplateSendLog)
            .filter(
                TemplateSendLog.account_id == "template-route-account-1",
                TemplateSendLog.template_id == template_id,
            )
            .all()
        )
        assert len(send_logs) == 1
        assert send_logs[0].waba_id == "waba-template-route-1"
        assert send_logs[0].phone_number_id == "phone-template-route-drift-1"

    rebuild_response = client.post(
        "/api/templates/stats/rebuild",
        params={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "phone_number_id": "phone-template-route-drift-1",
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text

    summary_response = client.get(
        "/api/templates/stats/summary",
        params={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "phone_number_id": "phone-template-route-drift-1",
        },
    )
    assert summary_response.status_code == 200, summary_response.text
    summary = summary_response.json()
    assert summary["send_count"] == 1
    assert summary["failed_count"] == 0

    daily_response = client.get(
        "/api/templates/stats/daily",
        params={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "phone_number_id": "phone-template-route-drift-1",
        },
    )
    assert daily_response.status_code == 200, daily_response.text
    daily_rows = daily_response.json()
    assert len(daily_rows) == 1
    assert daily_rows[0]["waba_id"] == "waba-template-route-1"
    assert daily_rows[0]["phone_number_id"] == "phone-template-route-drift-1"
    assert daily_rows[0]["send_count"] == 1


def test_template_analytics_route_preserves_snapshot_phone_scope_after_relationship_drift(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_template_route_account(
        client,
        phone_numbers=[
            {
                "phone_number_id": "phone-template-route-analytics-drift-1",
                "display_phone_number": "+1 555 300 0362",
                "verified_name": "Template Route Analytics Drift 1",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-conv-analytics-drift-snapshot",
            "user_id": "template-route-user-analytics-drift-snapshot",
            "text": "template analytics drift snapshot",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "phone-template-route-analytics-drift-1",
        },
    )
    assert inbound_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_analytics_drift_snapshot",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, analytics route keeps snapshot scope.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    send_response = client.post(
        f"/api/templates/{template_id}/send",
        json={
            "account_id": "template-route-account-1",
            "conversation_id": "template-route-conv-analytics-drift-snapshot",
            "variables": {"first_name": "Ana"},
        },
    )
    assert send_response.status_code == 200

    with db_session_factory() as session:
        phone_number = session.query(WhatsAppPhoneNumber).filter_by(
            account_id="template-route-account-1",
            phone_number_id="phone-template-route-analytics-drift-1",
        ).one()
        phone_number.phone_number_id = "phone-template-route-analytics-drift-1-current"
        phone_number.waba_id = "waba-template-route-1-current"
        assert phone_number.waba_account is not None
        phone_number.waba_account.waba_id = "waba-template-route-1-current"
        session.commit()

    analytics_response = client.get(
        f"/api/templates/{template_id}/analytics",
        params={
            "waba_id": "waba-template-route-1",
            "phone_number_id": "phone-template-route-analytics-drift-1",
        },
    )
    assert analytics_response.status_code == 200, analytics_response.text
    analytics = analytics_response.json()
    assert analytics["template_id"] == template_id
    assert analytics["summary"]["send_count"] == 1
    assert analytics["summary"]["failed_count"] == 0
    assert len(analytics["daily_rows"]) == 1
    assert analytics["daily_rows"][0]["waba_id"] == "waba-template-route-1"
    assert analytics["daily_rows"][0]["phone_number_id"] == "phone-template-route-analytics-drift-1"
    assert analytics["daily_rows"][0]["send_count"] == 1

    drifted_response = client.get(
        f"/api/templates/{template_id}/analytics",
        params={
            "waba_id": "waba-template-route-1-current",
            "phone_number_id": "phone-template-route-analytics-drift-1-current",
        },
    )
    assert drifted_response.status_code == 400, drifted_response.text
    assert (
        drifted_response.json()["detail"]
        == f"Template '{template_id}' is bound to WABA 'waba-template-route-1', "
        "not 'waba-template-route-1-current'."
    )


def test_template_send_logs_and_stats_routes_reject_mismatched_waba_and_phone_scope(
    client: TestClient,
) -> None:
    register_template_route_account(
        client,
        phone_numbers=[
            {
                "phone_number_id": "phone-template-route-mismatch-1",
                "display_phone_number": "+1 555 300 0401",
                "verified_name": "Template Route Mismatch 1",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )

    for method, path in (
        ("get", "/api/templates/send-logs"),
        ("get", "/api/templates/stats/summary"),
        ("get", "/api/templates/stats/daily"),
        ("post", "/api/templates/stats/rebuild"),
    ):
        response = getattr(client, method)(
            path,
            params={
                "account_id": "template-route-account-1",
                "waba_id": "waba-template-route-other",
                "phone_number_id": "phone-template-route-mismatch-1",
            },
        )
        assert response.status_code == 400
        assert "belongs to WABA 'waba-template-route-1'" in response.json()["detail"]


def test_template_routes_reject_cross_account_waba_scope_without_phone_filter(
    client: TestClient,
) -> None:
    register_template_route_account(client)
    response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "template-route-account-2",
            "display_name": "Template Route Account 2",
            "meta_business_portfolio_id": "portfolio-template-route-2",
            "waba_id": "waba-template-route-2",
            "access_token": "token-template-route-2",
            "verify_token": "verify-template-route-2",
            "app_secret": "secret-template-route-2",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "phone-template-route-2",
                    "display_phone_number": "+1 555 300 0002",
                    "verified_name": "Template Route Two",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert response.status_code == 200

    expected_detail = (
        "WABA 'waba-template-route-2' belongs to account "
        "'template-route-account-2', not 'template-route-account-1'."
    )
    for method, path in (
        ("get", "/api/templates/send-logs"),
        ("get", "/api/templates/stats/summary"),
        ("get", "/api/templates/stats/daily"),
        ("post", "/api/templates/stats/rebuild"),
    ):
        scoped_response = getattr(client, method)(
            path,
            params={
                "account_id": "template-route-account-1",
                "waba_id": "waba-template-route-2",
            },
        )
        assert scoped_response.status_code == 400
        assert scoped_response.json()["detail"] == expected_detail


def test_template_analytics_route_rejects_mismatched_waba_and_phone_scope(
    client: TestClient,
) -> None:
    register_template_route_account(
        client,
        phone_numbers=[
            {
                "phone_number_id": "phone-template-route-analytics-mismatch-1",
                "display_phone_number": "+1 555 300 0451",
                "verified_name": "Template Route Analytics Mismatch 1",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_analytics_mismatch",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, analytics mismatch check.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    mismatch_response = client.get(
        f"/api/templates/{template_id}/analytics",
        params={
            "waba_id": "waba-template-route-other",
            "phone_number_id": "phone-template-route-analytics-mismatch-1",
        },
    )
    assert mismatch_response.status_code == 400
    assert "belongs to WABA 'waba-template-route-1'" in mismatch_response.json()["detail"]


def test_template_routes_reject_phone_scope_from_other_waba_without_explicit_waba_filter(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_template_route_account(client)

    session = db_session_factory()
    try:
        create_waba(
            session,
            account_id="template-route-account-1",
            waba_id="waba-template-route-phone-only-other",
        )
        create_phone_number(
            session,
            account_id="template-route-account-1",
            waba_id="waba-template-route-phone-only-other",
            phone_number_id="phone-template-route-phone-only-other",
        )
    finally:
        session.close()

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_phone_only_scope_mismatch",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, phone-only scope mismatch check.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    for path in (
        "/api/templates/send-logs",
        f"/api/templates/{template_id}/analytics",
    ):
        response = client.get(
            path,
            params={
                "account_id": "template-route-account-1",
                "template_id": template_id,
                "phone_number_id": "phone-template-route-phone-only-other",
            }
            if path == "/api/templates/send-logs"
            else {
                "phone_number_id": "phone-template-route-phone-only-other",
            },
        )
        assert response.status_code == 400
        assert (
            "Phone-Number-ID 'phone-template-route-phone-only-other' belongs to WABA "
            "'waba-template-route-phone-only-other', not 'waba-template-route-1'."
            == response.json()["detail"]
        )


def test_rebuild_template_stats_route_can_scope_to_phone_number(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_template_route_account(
        client,
        phone_numbers=[
            {
                "phone_number_id": "phone-template-route-scope-1",
                "display_phone_number": "+1 555 300 0101",
                "verified_name": "Template Route Scope 1",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
            {
                "phone_number_id": "phone-template-route-scope-2",
                "display_phone_number": "+1 555 300 0102",
                "verified_name": "Template Route Scope 2",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
        ],
    )

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_scope_rebuild",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, scoped rebuild is ready.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    for phone_number_id in (
        "phone-template-route-scope-1",
        "phone-template-route-scope-2",
    ):
        inbound_response = client.post(
            "/dev/mock/inbound-message",
            json={
                "account_id": "template-route-account-1",
                "conversation_id": f"conv-{phone_number_id}",
                "user_id": f"user-{phone_number_id}",
                "text": "template scoped rebuild",
                "mode": "echo",
                "language_hint": "en",
                "phone_number_id": phone_number_id,
            },
        )
        assert inbound_response.status_code == 200

        send_response = client.post(
            f"/api/templates/{template_id}/send",
            json={
                "account_id": "template-route-account-1",
                "conversation_id": f"conv-{phone_number_id}",
                "variables": {"first_name": "Ana"},
            },
        )
        assert send_response.status_code == 200

    session = db_session_factory()
    try:
        phone_2_rows_before = (
            session.query(TemplateDailyStat)
            .filter(
                TemplateDailyStat.account_id == "template-route-account-1",
                TemplateDailyStat.phone_number_id == "phone-template-route-scope-2",
            )
            .count()
        )
        assert phone_2_rows_before == 1
        session.query(TemplateDailyStat).filter(
            TemplateDailyStat.account_id == "template-route-account-1",
            TemplateDailyStat.phone_number_id == "phone-template-route-scope-1",
        ).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()

    rebuild_response = client.post(
        "/api/templates/stats/rebuild",
        params={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "phone_number_id": "phone-template-route-scope-1",
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text
    rebuild_payload = rebuild_response.json()
    assert rebuild_payload["waba_id"] == "waba-template-route-1"
    assert rebuild_payload["phone_number_id"] == "phone-template-route-scope-1"

    session = db_session_factory()
    try:
        assert (
            session.query(TemplateDailyStat)
            .filter(
                TemplateDailyStat.account_id == "template-route-account-1",
                TemplateDailyStat.phone_number_id == "phone-template-route-scope-1",
            )
            .count()
            == 1
        )
        assert (
            session.query(TemplateDailyStat)
            .filter(
                TemplateDailyStat.account_id == "template-route-account-1",
                TemplateDailyStat.phone_number_id == "phone-template-route-scope-2",
            )
            .count()
            == phone_2_rows_before
        )
    finally:
        session.close()


def test_phone_scoped_template_stats_rebuild_preserves_other_phone_detail_aggregates(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_template_route_account(
        client,
        phone_numbers=[
            {
                "phone_number_id": "phone-template-route-detail-scope-1",
                "display_phone_number": "+1 555 300 0111",
                "verified_name": "Template Route Detail Scope 1",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
            {
                "phone_number_id": "phone-template-route-detail-scope-2",
                "display_phone_number": "+1 555 300 0112",
                "verified_name": "Template Route Detail Scope 2",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
        ],
    )

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_detail_scope_rebuild",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, detail scoped rebuild is ready.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    send_log_ids: dict[str, str] = {}
    for conversation_id, user_id, phone_number_id in (
        (
            "conv-template-route-detail-scope-1",
            "user-template-route-detail-scope-1",
            "phone-template-route-detail-scope-1",
        ),
        (
            "conv-template-route-detail-scope-2",
            "user-template-route-detail-scope-2",
            "phone-template-route-detail-scope-2",
        ),
    ):
        inbound_response = client.post(
            "/dev/mock/inbound-message",
            json={
                "account_id": "template-route-account-1",
                "conversation_id": conversation_id,
                "user_id": user_id,
                "text": "template detail scoped rebuild",
                "mode": "echo",
                "language_hint": "en",
                "phone_number_id": phone_number_id,
            },
        )
        assert inbound_response.status_code == 200

        send_response = client.post(
            f"/api/templates/{template_id}/send",
            json={
                "account_id": "template-route-account-1",
                "conversation_id": conversation_id,
                "variables": {"first_name": "Ana"},
            },
        )
        assert send_response.status_code == 200
        send_log_ids[phone_number_id] = send_response.json()["send_log_id"]

    session = db_session_factory()
    try:
        phone_1_log = session.query(TemplateSendLog).filter_by(
            id=send_log_ids["phone-template-route-detail-scope-1"]
        ).one()
        phone_1_log.sent_at = datetime.fromisoformat("2026-06-07T09:05:00")
        phone_1_log.status = "READ"
        phone_1_log.delivered_at = datetime.fromisoformat("2026-06-07T09:06:00")
        phone_1_log.read_at = datetime.fromisoformat("2026-06-07T09:07:00")
        phone_1_log.failed_at = None
        phone_1_log.error_code = None
        phone_1_log.last_status_at = datetime.fromisoformat("2026-06-07T09:07:00")

        phone_2_log = session.query(TemplateSendLog).filter_by(
            id=send_log_ids["phone-template-route-detail-scope-2"]
        ).one()
        phone_2_log.sent_at = datetime.fromisoformat("2026-06-07T10:05:00")
        phone_2_log.status = "FAILED"
        phone_2_log.delivered_at = None
        phone_2_log.read_at = None
        phone_2_log.failed_at = datetime.fromisoformat("2026-06-07T10:06:00")
        phone_2_log.error_code = "rate_limited"
        phone_2_log.last_status_at = datetime.fromisoformat("2026-06-07T10:06:00")

        session.query(TemplateDailyStat).filter(
            TemplateDailyStat.account_id == "template-route-account-1"
        ).delete(synchronize_session=False)
        session.query(TemplateHourlyStat).filter(
            TemplateHourlyStat.account_id == "template-route-account-1"
        ).delete(synchronize_session=False)
        session.query(TemplateFailureStat).filter(
            TemplateFailureStat.account_id == "template-route-account-1"
        ).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()


def test_phone_scoped_template_stats_rebuild_cleans_legacy_scope_rows(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_template_route_account(
        client,
        phone_numbers=[
            {
                "phone_number_id": "phone-template-route-cleanup-1",
                "display_phone_number": "+1 555 300 0121",
                "verified_name": "Template Route Cleanup 1",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
            {
                "phone_number_id": "phone-template-route-cleanup-2",
                "display_phone_number": "+1 555 300 0122",
                "verified_name": "Template Route Cleanup 2",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
        ],
    )

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "name": "template_route_scope_cleanup",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, scoped cleanup is ready.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    send_log_ids: dict[str, str] = {}
    for conversation_id, user_id, phone_number_id in (
        (
            "conv-template-route-cleanup-1",
            "user-template-route-cleanup-1",
            "phone-template-route-cleanup-1",
        ),
        (
            "conv-template-route-cleanup-2",
            "user-template-route-cleanup-2",
            "phone-template-route-cleanup-2",
        ),
    ):
        inbound_response = client.post(
            "/dev/mock/inbound-message",
            json={
                "account_id": "template-route-account-1",
                "conversation_id": conversation_id,
                "user_id": user_id,
                "text": "template scoped cleanup",
                "mode": "echo",
                "language_hint": "en",
                "phone_number_id": phone_number_id,
            },
        )
        assert inbound_response.status_code == 200

        send_response = client.post(
            f"/api/templates/{template_id}/send",
            json={
                "account_id": "template-route-account-1",
                "conversation_id": conversation_id,
                "variables": {"first_name": "Ana"},
            },
        )
        assert send_response.status_code == 200
        send_log_ids[phone_number_id] = send_response.json()["send_log_id"]

    session = db_session_factory()
    try:
        phone_1_log = session.query(TemplateSendLog).filter_by(
            id=send_log_ids["phone-template-route-cleanup-1"]
        ).one()
        phone_1_log.sent_at = datetime.fromisoformat("2026-06-07T09:05:00")
        phone_1_log.status = "FAILED"
        phone_1_log.failed_at = datetime.fromisoformat("2026-06-07T09:06:00")
        phone_1_log.last_status_at = datetime.fromisoformat("2026-06-07T09:06:00")
        phone_1_log.error_code = "recipient_blocked"

        phone_2_log = session.query(TemplateSendLog).filter_by(
            id=send_log_ids["phone-template-route-cleanup-2"]
        ).one()
        phone_2_log.sent_at = datetime.fromisoformat("2026-06-07T10:05:00")
        phone_2_log.status = "READ"
        phone_2_log.delivered_at = datetime.fromisoformat("2026-06-07T10:06:00")
        phone_2_log.read_at = datetime.fromisoformat("2026-06-07T10:07:00")
        phone_2_log.failed_at = None
        phone_2_log.error_code = None
        phone_2_log.last_status_at = datetime.fromisoformat("2026-06-07T10:07:00")
        session.commit()
    finally:
        session.close()

    full_rebuild_response = client.post(
        "/api/templates/stats/rebuild",
        params={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
        },
    )
    assert full_rebuild_response.status_code == 200, full_rebuild_response.text

    session = db_session_factory()
    try:
        legacy_phone_row = session.query(WhatsAppPhoneNumber).filter_by(
            account_id="template-route-account-1",
            phone_number_id="phone-template-route-cleanup-1",
        ).one()
        legacy_scope_phone_id = legacy_phone_row.id
        session.add(
            TemplateDailyStat(
                date=date.fromisoformat("2026-06-07"),
                account_id="template-route-account-1",
                template_id=template_id,
                waba_id="waba-template-route-1",
                phone_number_id=legacy_scope_phone_id,
                template_name="template_route_scope_cleanup",
                template_code=None,
                template_category="UTILITY",
                template_language="en",
                send_count=1,
                delivered_count=0,
                read_count=0,
                failed_count=1,
                billable_count=0,
                estimated_cost=0,
            )
        )
        session.add(
            TemplateHourlyStat(
                date=date.fromisoformat("2026-06-07"),
                hour_bucket=9,
                account_id="template-route-account-1",
                template_id=template_id,
                waba_id="waba-template-route-1",
                phone_number_id=legacy_scope_phone_id,
                template_name="template_route_scope_cleanup",
                template_code=None,
                template_category="UTILITY",
                template_language="en",
                send_count=1,
                delivered_count=0,
                read_count=0,
                failed_count=1,
                billable_count=0,
                estimated_cost=0,
            )
        )
        session.add(
            TemplateFailureStat(
                date=date.fromisoformat("2026-06-07"),
                account_id="template-route-account-1",
                template_id=template_id,
                waba_id="waba-template-route-1",
                phone_number_id=legacy_scope_phone_id,
                template_name="template_route_scope_cleanup",
                template_code=None,
                template_category="UTILITY",
                template_language="en",
                error_code="recipient_blocked",
                failed_count=1,
            )
        )
        session.commit()
    finally:
        session.close()

    scoped_rebuild_response = client.post(
        "/api/templates/stats/rebuild",
        params={
            "account_id": "template-route-account-1",
            "waba_id": "waba-template-route-1",
            "phone_number_id": "phone-template-route-cleanup-1",
        },
    )
    assert scoped_rebuild_response.status_code == 200, scoped_rebuild_response.text

    session = db_session_factory()
    try:
        assert (
            session.query(TemplateDailyStat)
            .filter(
                TemplateDailyStat.account_id == "template-route-account-1",
                TemplateDailyStat.template_id == template_id,
                TemplateDailyStat.phone_number_id == legacy_scope_phone_id,
            )
            .count()
            == 0
        )
        assert (
            session.query(TemplateHourlyStat)
            .filter(
                TemplateHourlyStat.account_id == "template-route-account-1",
                TemplateHourlyStat.template_id == template_id,
                TemplateHourlyStat.phone_number_id == legacy_scope_phone_id,
            )
            .count()
            == 0
        )
        assert (
            session.query(TemplateFailureStat)
            .filter(
                TemplateFailureStat.account_id == "template-route-account-1",
                TemplateFailureStat.template_id == template_id,
                TemplateFailureStat.phone_number_id == legacy_scope_phone_id,
            )
            .count()
            == 0
        )
        assert (
            session.query(TemplateDailyStat)
            .filter(
                TemplateDailyStat.account_id == "template-route-account-1",
                TemplateDailyStat.template_id == template_id,
                TemplateDailyStat.phone_number_id == "phone-template-route-cleanup-2",
            )
            .count()
            == 1
        )
    finally:
        session.close()
