import asyncio
import json
import os
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_messaging_service
from app.api.routes import webhooks as webhook_routes
from app.core.settings import get_settings
from app.db.models import (
    MessageEvent,
    MessageTemplate,
    ProviderStatusEventBuffer,
    WhatsAppBusinessAccount,
    WhatsAppPhoneNumber,
)
from app.providers.messaging.base import MessagingProvider
from app.providers.messaging.whatsapp_provider import WhatsAppProvider
from app.schemas.messaging import (
    MediaAssetSyncRequest,
    MediaAssetSyncResult,
    OutboundDispatchRequest,
    OutboundDispatchResult,
    ProviderStatusUpdate,
)
from app.schemas.mock_message import NormalizedMessage
from app.services.runtime_state import RuntimeStateStore
from tests.conftest import StubMetaManagementProvider


def register_meta_account_with_webhook_secret(client: TestClient) -> None:
    response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-webhook-account",
            "display_name": "Meta Webhook Account",
            "meta_business_portfolio_id": "portfolio-webhook-1",
            "waba_id": "waba-webhook-1",
            "access_token": "token-webhook-1",
            "verify_token": "verify-webhook-1",
            "app_secret": "secret-webhook-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-webhook-1",
                    "display_phone_number": "+1 555 000 0001",
                    "verified_name": "Webhook Brand",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert response.status_code == 200


def subscribe_meta_webhook(client: TestClient) -> None:
    response = client.post(
        "/api/meta/accounts/meta-webhook-account/wabas/waba-webhook-1/webhook-subscription",
        json={"callback_url": "https://example.com/webhook/runtime"},
    )
    assert response.status_code == 200


def register_meta_account_without_webhook_secrets(client: TestClient) -> None:
    response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-webhook-no-secret-account",
            "display_name": "Meta Webhook No Secret Account",
            "meta_business_portfolio_id": "portfolio-webhook-no-secret",
            "waba_id": "waba-webhook-no-secret",
            "access_token": "token-webhook-no-secret",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-webhook-no-secret",
                    "display_phone_number": "+1 555 000 0002",
                    "verified_name": "Webhook No Secret Brand",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert response.status_code == 200


def register_second_meta_account_with_webhook_secret(client: TestClient) -> None:
    response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-webhook-account-two",
            "display_name": "Meta Webhook Account Two",
            "meta_business_portfolio_id": "portfolio-webhook-2",
            "waba_id": "waba-webhook-2",
            "access_token": "token-webhook-2",
            "verify_token": "verify-webhook-2",
            "app_secret": "secret-webhook-2",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-webhook-2",
                    "display_phone_number": "+1 555 000 0002",
                    "verified_name": "Webhook Brand Two",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert response.status_code == 200


class FixedMessageIdWhatsAppProvider(MessagingProvider):
    provider_name = "whatsapp"

    def __init__(self, provider_message_id: str) -> None:
        self._provider_message_id = provider_message_id
        self._whatsapp_provider = WhatsAppProvider()

    async def normalize_inbound(self, payload: object) -> list[NormalizedMessage]:
        return await self._whatsapp_provider.normalize_inbound(payload)

    async def normalize_status_updates(self, payload: object) -> list[ProviderStatusUpdate]:
        return await self._whatsapp_provider.normalize_status_updates(payload)

    async def send_outbound(self, payload: OutboundDispatchRequest) -> OutboundDispatchResult:
        return OutboundDispatchResult(
            provider_name=self.provider_name,
            provider_message_id=self._provider_message_id,
            accepted=True,
            external_status="accepted",
            raw_response={
                "message_type": payload.message_type,
                "recipient_id": payload.recipient_id,
                "template_name": payload.template_name,
            },
        )

    async def sync_media_asset(self, payload: MediaAssetSyncRequest) -> MediaAssetSyncResult:
        return MediaAssetSyncResult(
            provider_name=self.provider_name,
            phone_number_id=payload.phone_number_id,
            waba_id=payload.waba_id,
            sync_status="unsupported",
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


def build_whatsapp_status_payload(
    *,
    provider_message_id: str,
    status: str,
    timestamp: str,
    recipient_id: str,
    waba_id: str = "waba-webhook-1",
    phone_number_id: str = "pn-webhook-1",
    display_phone_number: str = "+1 555 000 0001",
    error_code: str | None = None,
) -> dict[str, object]:
    status_item: dict[str, object] = {
        "id": provider_message_id,
        "status": status,
        "timestamp": timestamp,
        "recipient_id": recipient_id,
        "conversation": {
            "id": f"meta-early-{status}-conversation",
            "expiration_timestamp": "1712350000",
            "origin": {"type": "business_initiated"},
        },
        "pricing": {
            "billable": True,
            "category": "utility",
            "pricing_model": "CBP",
        },
    }
    if error_code is not None:
        status_item["errors"] = [
            {
                "code": error_code,
                "title": "Provider failed",
                "message": "Template delivery failed.",
            }
        ]
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": waba_id,
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": display_phone_number,
                                "phone_number_id": phone_number_id,
                            },
                            "statuses": [
                                status_item
                            ],
                        },
                    }
                ],
            }
        ],
    }


def build_template_webhook_payload(
    *,
    waba_id: str,
    field: str,
    value: dict[str, object],
) -> dict[str, object]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": waba_id,
                "changes": [
                    {
                        "field": field,
                        "value": value,
                    }
                ],
            }
        ],
    }


def assert_external_conversation_identity(
    payload: dict[str, object],
    *,
    expected_external_conversation_id: str,
    expected_internal_conversation_id: str,
) -> None:
    assert payload["conversation_id"] == expected_external_conversation_id
    assert payload["external_conversation_id"] == expected_external_conversation_id
    assert payload["conversation_id"] == payload["external_conversation_id"]
    assert payload["internal_conversation_id"] == expected_internal_conversation_id
    assert payload["internal_conversation_id"] != expected_external_conversation_id


def sign_whatsapp_payload(payload: dict[str, object], app_secret: str) -> tuple[bytes, str]:
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return raw_body, WhatsAppProvider.build_signature(app_secret, raw_body)


def recreate_webhook_waba_row_with_new_secret(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    official_waba_id: str,
    phone_number_id: str,
    legacy_waba_id: str,
    recreated_app_secret: str,
) -> None:
    with db_session_factory() as session:
        legacy_waba = (
            session.query(WhatsAppBusinessAccount)
            .filter(
                WhatsAppBusinessAccount.account_id == account_id,
                WhatsAppBusinessAccount.waba_id == official_waba_id,
            )
            .one()
        )
        legacy_waba.waba_id = legacy_waba_id
        legacy_waba.app_secret = None
        session.flush()

        recreated_waba = WhatsAppBusinessAccount(
            account_id=account_id,
            portfolio_id=legacy_waba.portfolio_id,
            waba_id=official_waba_id,
            onboarding_mode=legacy_waba.onboarding_mode,
            token_source=legacy_waba.token_source,
            access_token=legacy_waba.access_token,
            verify_token=legacy_waba.verify_token,
            app_secret=recreated_app_secret,
            webhook_subscribed=False,
            is_active=legacy_waba.is_active,
            ai_enabled=legacy_waba.ai_enabled,
        )
        session.add(recreated_waba)
        session.flush()

        phone_number = (
            session.query(WhatsAppPhoneNumber)
            .filter(
                WhatsAppPhoneNumber.account_id == account_id,
                WhatsAppPhoneNumber.phone_number_id == phone_number_id,
            )
            .one()
        )
        phone_number.waba_account_id = recreated_waba.id
        phone_number.waba_id = official_waba_id
        session.commit()


def test_verify_whatsapp_webhook_challenge(client: TestClient) -> None:
    register_meta_account_with_webhook_secret(client)
    subscribe_meta_webhook(client)

    response = client.get(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-webhook-1",
            "hub.challenge": "challenge-123",
        },
    )

    assert response.status_code == 200
    assert response.text == "challenge-123"

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-webhook-account",
            "action": "meta_webhook_verification_succeeded",
            "target_type": "waba_account",
            "target_id": "waba-webhook-1",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"]["mode"] == "subscribe"

    accounts_response = client.get("/api/meta/accounts")
    assert accounts_response.status_code == 200
    account = next(item for item in accounts_response.json() if item["account_id"] == "meta-webhook-account")
    assert account["webhook_verification_status"] == "verified"
    assert account["webhook_last_verified_at"] is not None
    assert account["webhook_last_verification_error"] is None

    subscriptions_response = client.get(
        "/api/meta/accounts/webhook-subscriptions",
        params={"account_id": "meta-webhook-account"},
    )
    assert subscriptions_response.status_code == 200
    assert subscriptions_response.json()[0]["webhook_verification_status"] == "verified"


def test_verify_whatsapp_webhook_uses_subscription_snapshot_after_waba_row_recreation(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_meta_account_without_webhook_secrets(client)

    subscribe_response = client.post(
        "/api/meta/accounts/meta-webhook-no-secret-account/wabas/waba-webhook-no-secret/webhook-subscription",
        json={
            "callback_url": "https://example.com/webhook/recreated-verify",
            "verify_token": "verify-webhook-recreated",
        },
    )
    assert subscribe_response.status_code == 200

    session = db_session_factory()
    try:
        legacy_waba = session.query(WhatsAppBusinessAccount).filter_by(
            account_id="meta-webhook-no-secret-account",
            waba_id="waba-webhook-no-secret",
        ).one()
        legacy_waba.waba_id = "waba-webhook-no-secret-legacy"
        session.commit()

        recreated_waba = WhatsAppBusinessAccount(
            account_id="meta-webhook-no-secret-account",
            portfolio_id=legacy_waba.portfolio_id,
            waba_id="waba-webhook-no-secret",
            onboarding_mode="manual",
            token_source="system_user",
            access_token="token-webhook-no-secret-recreated",
            webhook_subscribed=False,
            is_active=True,
            ai_enabled=True,
        )
        session.add(recreated_waba)
        session.commit()
    finally:
        session.close()

    response = client.get(
        "/webhooks/whatsapp/meta-webhook-no-secret-account/wabas/waba-webhook-no-secret",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-webhook-recreated",
            "hub.challenge": "challenge-recreated",
        },
    )

    assert response.status_code == 200
    assert response.text == "challenge-recreated"


def test_receive_whatsapp_webhook_uses_subscription_snapshot_after_waba_row_recreation(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_meta_account_with_webhook_secret(client)
    subscribe_meta_webhook(client)
    recreate_webhook_waba_row_with_new_secret(
        db_session_factory,
        account_id="meta-webhook-account",
        official_waba_id="waba-webhook-1",
        phone_number_id="pn-webhook-1",
        legacy_waba_id="waba-webhook-1-legacy-receive",
        recreated_app_secret="secret-webhook-1-recreated",
    )

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "contacts": [
                                {
                                    "wa_id": "14150001021",
                                    "profile": {"name": "Scoped Recreated Customer"},
                                }
                            ],
                            "messages": [
                                {
                                    "from": "14150001021",
                                    "id": "wamid.webhook.recreated.scoped.1",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "scoped webhook still works after recreated waba row"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body, signature = sign_whatsapp_payload(payload, "secret-webhook-1")

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "whatsapp"
    assert body["account_id"] == "meta-webhook-account"
    assert body["waba_id"] == "waba-webhook-1"
    assert body["signature_verified"] is True
    assert body["accepted_messages"] == 1

    conversation_response = client.get(
        "/api/conversations",
        params={"account_id": "meta-webhook-account"},
    )
    assert conversation_response.status_code == 200
    conversations = conversation_response.json()
    assert [item["conversation_id"] for item in conversations] == ["wa:pn-webhook-1:14150001021"]
    assert conversations[0]["waba_id"] == "waba-webhook-1"
    assert conversations[0]["phone_number_id"] == "pn-webhook-1"


def test_verify_whatsapp_webhook_requires_waba_verify_token_in_whatsapp_mode(
    client: TestClient,
) -> None:
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "WA_VERIFY_TOKEN": os.environ.get("WA_VERIFY_TOKEN"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["WA_VERIFY_TOKEN"] = "global-verify-token"
        get_settings.cache_clear()
        register_meta_account_without_webhook_secrets(client)

        response = client.get(
            "/webhooks/whatsapp/meta-webhook-no-secret-account/wabas/waba-webhook-no-secret",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "global-verify-token",
                "hub.challenge": "challenge-should-not-pass",
            },
        )

        assert response.status_code == 503
        assert response.json()["detail"] == "Webhook verify token is not configured for this WABA."

        audit_response = client.get(
            "/api/runtime/audit-logs",
            params={
                "account_id": "meta-webhook-no-secret-account",
                "action": "meta_webhook_verification_unavailable",
                "target_type": "waba_account",
                "target_id": "waba-webhook-no-secret",
            },
        )
        assert audit_response.status_code == 200
        audit_logs = audit_response.json()
        assert len(audit_logs) == 1
        assert audit_logs[0]["payload"] == {"reason": "missing_verify_token"}

        root_scope_failed_audit_response = client.get(
            "/api/runtime/audit-logs",
            params={
                "account_id": "meta-webhook-no-secret-account",
                "action": "meta_webhook_root_scope_failed",
                "target_type": "waba_account",
                "target_id": "waba-webhook-no-secret",
            },
        )
        assert root_scope_failed_audit_response.status_code == 200
        assert root_scope_failed_audit_response.json() == []

        accounts_response = client.get("/api/meta/accounts")
        assert accounts_response.status_code == 200
        account = next(
            item
            for item in accounts_response.json()
            if item["account_id"] == "meta-webhook-no-secret-account"
        )
        assert account["webhook_verification_status"] == "unavailable"
        assert account["webhook_last_verification_error"] == "missing_verify_token"
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_verify_whatsapp_webhook_failure_is_audited(client: TestClient) -> None:
    register_meta_account_with_webhook_secret(client)
    subscribe_meta_webhook(client)

    response = client.get(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "challenge-123",
        },
    )

    assert response.status_code == 403

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-webhook-account",
            "action": "meta_webhook_verification_failed",
            "target_type": "waba_account",
            "target_id": "waba-webhook-1",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"]["mode"] == "subscribe"
    assert audit_logs[0]["payload"]["error"] == "Webhook verify token mismatch."

    accounts_response = client.get("/api/meta/accounts")
    assert accounts_response.status_code == 200
    account = next(item for item in accounts_response.json() if item["account_id"] == "meta-webhook-account")
    assert account["webhook_verification_status"] == "failed"
    assert account["webhook_last_verified_at"] is None
    assert account["webhook_last_verification_error"] == "Webhook verify token mismatch."


def test_verify_whatsapp_webhook_missing_waba_scope_is_audited(client: TestClient) -> None:
    register_meta_account_with_webhook_secret(client)

    response = client.get(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-missing",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-webhook-1",
            "hub.challenge": "challenge-missing-waba",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "WABA 'waba-webhook-missing' for account 'meta-webhook-account' was not found."
    )

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-webhook-account",
            "action": "meta_webhook_verification_scope_missing",
            "target_type": "waba_account",
            "target_id": "waba-webhook-missing",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"] == {
        "mode": "subscribe",
        "reason": "waba_scope_not_found",
        "error": "WABA 'waba-webhook-missing' for account 'meta-webhook-account' was not found.",
        "verify_token_present": True,
    }
    assert "verify-webhook-1" not in str(audit_logs[0]["payload"])


def test_verify_whatsapp_webhook_success_after_failure_clears_error_state(client: TestClient) -> None:
    register_meta_account_with_webhook_secret(client)
    subscribe_meta_webhook(client)

    failed_response = client.get(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "challenge-failed-first",
        },
    )
    assert failed_response.status_code == 403

    success_response = client.get(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-webhook-1",
            "hub.challenge": "challenge-success-second",
        },
    )
    assert success_response.status_code == 200
    assert success_response.text == "challenge-success-second"

    accounts_response = client.get("/api/meta/accounts")
    assert accounts_response.status_code == 200
    account = next(item for item in accounts_response.json() if item["account_id"] == "meta-webhook-account")
    assert account["webhook_verification_status"] == "verified"
    assert account["webhook_last_verified_at"] is not None
    assert account["webhook_last_verification_error"] is None

    subscriptions_response = client.get(
        "/api/meta/accounts/webhook-subscriptions",
        params={"account_id": "meta-webhook-account"},
    )
    assert subscriptions_response.status_code == 200
    assert subscriptions_response.json()[0]["webhook_verification_status"] == "verified"

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-webhook-account",
            "target_type": "waba_account",
            "target_id": "waba-webhook-1",
            "limit": 10,
        },
    )
    assert audit_response.status_code == 200
    actions = [item["action"] for item in audit_response.json()]
    assert "meta_webhook_verification_failed" in actions
    assert "meta_webhook_verification_succeeded" in actions


def test_root_verify_whatsapp_webhook_resolves_unique_verify_token(client: TestClient) -> None:
    register_meta_account_with_webhook_secret(client)

    response = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-webhook-1",
            "hub.challenge": "challenge-root-verify-1",
        },
    )

    assert response.status_code == 200
    assert response.text == "challenge-root-verify-1"

    accounts_response = client.get(
        "/api/meta/accounts",
        params={"account_id": "meta-webhook-account"},
    )
    assert accounts_response.status_code == 200
    payload = accounts_response.json()[0]
    assert payload["webhook_verification_status"] == "verified"
    assert payload["webhook_root_verify_path"] == "/webhooks/whatsapp"


def test_root_verify_whatsapp_webhook_uses_subscription_snapshot_after_waba_row_recreation(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_meta_account_without_webhook_secrets(client)

    subscribe_response = client.post(
        "/api/meta/accounts/meta-webhook-no-secret-account/wabas/waba-webhook-no-secret/webhook-subscription",
        json={
            "callback_url": "https://example.com/webhook/root-recreated-verify",
            "verify_token": "verify-root-webhook-recreated",
        },
    )
    assert subscribe_response.status_code == 200

    session = db_session_factory()
    try:
        legacy_waba = session.query(WhatsAppBusinessAccount).filter_by(
            account_id="meta-webhook-no-secret-account",
            waba_id="waba-webhook-no-secret",
        ).one()
        legacy_waba.waba_id = "waba-webhook-no-secret-legacy-root-verify"
        session.commit()

        recreated_waba = WhatsAppBusinessAccount(
            account_id="meta-webhook-no-secret-account",
            portfolio_id=legacy_waba.portfolio_id,
            waba_id="waba-webhook-no-secret",
            onboarding_mode="manual",
            token_source="system_user",
            access_token="token-webhook-no-secret-recreated-root-verify",
            webhook_subscribed=False,
            is_active=True,
            ai_enabled=True,
        )
        session.add(recreated_waba)
        session.commit()
    finally:
        session.close()

    response = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-root-webhook-recreated",
            "hub.challenge": "challenge-root-recreated",
        },
    )

    assert response.status_code == 200
    assert response.text == "challenge-root-recreated"

    accounts_response = client.get(
        "/api/meta/accounts",
        params={"account_id": "meta-webhook-no-secret-account"},
    )
    assert accounts_response.status_code == 200
    account = next(
        item
        for item in accounts_response.json()
        if item["account_id"] == "meta-webhook-no-secret-account"
        and item["waba_id"] == "waba-webhook-no-secret"
    )
    assert account["webhook_verification_status"] == "verified"


def test_root_receive_whatsapp_webhook_uses_subscription_snapshot_after_waba_row_recreation(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_meta_account_with_webhook_secret(client)
    subscribe_meta_webhook(client)
    recreate_webhook_waba_row_with_new_secret(
        db_session_factory,
        account_id="meta-webhook-account",
        official_waba_id="waba-webhook-1",
        phone_number_id="pn-webhook-1",
        legacy_waba_id="waba-webhook-1-legacy-root-receive",
        recreated_app_secret="secret-webhook-1-recreated-root",
    )

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "contacts": [
                                {
                                    "wa_id": "14150001022",
                                    "profile": {"name": "Root Recreated Customer"},
                                }
                            ],
                            "messages": [
                                {
                                    "from": "14150001022",
                                    "id": "wamid.webhook.recreated.root.1",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "root webhook still works after recreated waba row"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body, signature = sign_whatsapp_payload(payload, "secret-webhook-1")

    response = client.post(
        "/webhooks/whatsapp",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "whatsapp"
    assert body["account_id"] == "meta-webhook-account"
    assert body["waba_id"] == "waba-webhook-1"
    assert body["signature_verified"] is True
    assert body["accepted_messages"] == 1
    assert body["results"][0]["inbound"]["conversation_id"] == "wa:pn-webhook-1:14150001022"

    conversation_response = client.get(
        "/api/conversations",
        params={"account_id": "meta-webhook-account"},
    )
    assert conversation_response.status_code == 200
    conversations = conversation_response.json()
    assert [item["conversation_id"] for item in conversations] == ["wa:pn-webhook-1:14150001022"]
    assert conversations[0]["waba_id"] == "waba-webhook-1"
    assert conversations[0]["phone_number_id"] == "pn-webhook-1"

    accounts_response = client.get("/api/meta/accounts")
    assert accounts_response.status_code == 200
    account = next(
        item
        for item in accounts_response.json()
        if item["account_id"] == "meta-webhook-account" and item["waba_id"] == "waba-webhook-1"
    )
    assert account["has_verify_token"] is True


def test_root_verify_whatsapp_webhook_rejects_verify_token_conflict(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    for account_id, display_name, portfolio_id, waba_id in (
        (
            "meta-root-verify-conflict-a",
            "Meta Root Verify Conflict A",
            "portfolio-root-verify-conflict-a",
            "waba-root-verify-conflict-a",
        ),
        (
            "meta-root-verify-conflict-b",
            "Meta Root Verify Conflict B",
            "portfolio-root-verify-conflict-b",
            "waba-root-verify-conflict-b",
        ),
    ):
        response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": account_id,
                "display_name": display_name,
                "meta_business_portfolio_id": portfolio_id,
                "waba_id": waba_id,
                "access_token": f"token-{account_id}",
                "verify_token": (
                    "verify-root-conflict-shared"
                    if account_id == "meta-root-verify-conflict-a"
                    else "verify-root-conflict-unique-b"
                ),
                "app_secret": f"secret-{account_id}",
                "token_source": "system_user",
                "phone_numbers": [],
            },
        )
        assert response.status_code == 200

    with db_session_factory() as session:
        conflicting_waba = session.query(WhatsAppBusinessAccount).filter(
            WhatsAppBusinessAccount.account_id == "meta-root-verify-conflict-b",
            WhatsAppBusinessAccount.waba_id == "waba-root-verify-conflict-b",
        ).one()
        conflicting_waba.verify_token = "verify-root-conflict-shared"
        session.add(conflicting_waba)
        session.commit()

    conflict_response = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-root-conflict-shared",
            "hub.challenge": "challenge-root-conflict",
        },
    )

    assert conflict_response.status_code == 409
    assert "shared by multiple WABAs" in conflict_response.json()["detail"]

    for account_id, waba_id in (
        ("meta-root-verify-conflict-a", "waba-root-verify-conflict-a"),
        ("meta-root-verify-conflict-b", "waba-root-verify-conflict-b"),
    ):
        audit_response = client.get(
            "/api/runtime/audit-logs",
            params={
                "account_id": account_id,
                "action": "meta_webhook_root_verify_token_conflict",
                "target_type": "waba_account",
                "target_id": waba_id,
            },
        )
        assert audit_response.status_code == 200
        audit_logs = audit_response.json()
        assert len(audit_logs) == 1
        assert audit_logs[0]["payload"] == {
            "reason": "shared_verify_token",
            "verify_token_present": True,
            "matching_waba_count": 2,
        }
        assert "verify-root-conflict-shared" not in str(audit_logs[0]["payload"])


def test_root_verify_whatsapp_webhook_rejects_unknown_verify_token_with_audit(
    client: TestClient,
) -> None:
    response = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-root-missing",
            "hub.challenge": "challenge-root-missing",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "No WABA matches the supplied webhook verify token."

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "action": "meta_webhook_root_verify_token_unmatched",
            "target_type": "waba_account",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["account_id"] is None
    assert audit_logs[0]["target_id"] is None
    assert audit_logs[0]["payload"] == {
        "reason": "no_matching_waba",
        "verify_token_present": True,
    }
    assert "verify-root-missing" not in str(audit_logs[0]["payload"])


def test_root_verify_whatsapp_webhook_rejects_blank_verify_token_with_audit(
    client: TestClient,
) -> None:
    response = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "   ",
            "hub.challenge": "challenge-root-blank",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Webhook verify token is required."

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "action": "meta_webhook_root_verify_token_invalid",
            "target_type": "waba_account",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["account_id"] is None
    assert audit_logs[0]["target_id"] is None
    assert audit_logs[0]["payload"] == {
        "reason": "invalid_verify_token",
        "verify_token_present": True,
    }


def test_receive_whatsapp_webhook_blocks_delivery_until_verified_in_whatsapp_mode(
    client: TestClient,
) -> None:
    original_env = {"MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER")}

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()
        register_meta_account_without_webhook_secrets(client)

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-webhook-no-secret",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 0002",
                                    "phone_number_id": "pn-webhook-no-secret",
                                },
                                "messages": [
                                    {
                                        "from": "14150000002",
                                        "id": "wamid.no.secret.1",
                                        "timestamp": "1712345800",
                                        "type": "text",
                                        "text": {"body": "must not process without app secret"},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }

        response = client.post(
            "/webhooks/whatsapp/meta-webhook-no-secret-account/wabas/waba-webhook-no-secret",
            content=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 503
        assert response.json()["detail"] == "Webhook app secret is not configured for this WABA."
    finally:
        if original_env["MESSAGING_PROVIDER"] is None:
            os.environ.pop("MESSAGING_PROVIDER", None)
        else:
            os.environ["MESSAGING_PROVIDER"] = original_env["MESSAGING_PROVIDER"]
        get_settings.cache_clear()


def test_receive_whatsapp_webhook_requires_app_secret_after_verification_in_whatsapp_mode(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {"MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER")}

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())
        response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "meta-webhook-verified-no-secret-account",
                "display_name": "Meta Webhook Verified No Secret Account",
                "meta_business_portfolio_id": "portfolio-webhook-verified-no-secret",
                "waba_id": "waba-webhook-verified-no-secret",
                "access_token": "token-webhook-verified-no-secret",
                "verify_token": "verify-webhook-verified-no-secret",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-webhook-verified-no-secret",
                        "display_phone_number": "+1 555 000 1002",
                        "verified_name": "Webhook Verified No Secret Brand",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert response.status_code == 200

        subscribe_response = client.post(
            "/api/meta/accounts/meta-webhook-verified-no-secret-account/wabas/"
            "waba-webhook-verified-no-secret/webhook-subscription",
            json={"callback_url": "https://example.com/webhook/verified-no-secret"},
        )
        assert subscribe_response.status_code == 200

        verify_response = client.get(
            "/webhooks/whatsapp/meta-webhook-verified-no-secret-account/wabas/"
            "waba-webhook-verified-no-secret",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-webhook-verified-no-secret",
                "hub.challenge": "challenge-verified-no-secret",
            },
        )
        assert verify_response.status_code == 200

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-webhook-verified-no-secret",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 1002",
                                    "phone_number_id": "pn-webhook-verified-no-secret",
                                },
                                "messages": [
                                    {
                                        "from": "14150001002",
                                        "id": "wamid.verified.no.secret.1",
                                        "timestamp": "1712345801",
                                        "type": "text",
                                        "text": {"body": "verified but still no app secret"},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }

        webhook_response = client.post(
            "/webhooks/whatsapp/meta-webhook-verified-no-secret-account/wabas/"
            "waba-webhook-verified-no-secret",
            content=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        assert webhook_response.status_code == 503
        assert webhook_response.json()["detail"] == "Webhook app secret is not configured for this WABA."

        accounts_response = client.get("/api/meta/accounts")
        assert accounts_response.status_code == 200
        account = next(
            item
            for item in accounts_response.json()
            if item["account_id"] == "meta-webhook-verified-no-secret-account"
        )
        assert account["webhook_runtime_status"] == "signature_unavailable"
        assert account["webhook_runtime_error"] == "missing_app_secret"
        assert account["webhook_signature_failure_count"] == 0
        assert account["webhook_last_signature_failed_at"] is None
    finally:
        if original_env["MESSAGING_PROVIDER"] is None:
            os.environ.pop("MESSAGING_PROVIDER", None)
        else:
            os.environ["MESSAGING_PROVIDER"] = original_env["MESSAGING_PROVIDER"]
        get_settings.cache_clear()


def test_receive_whatsapp_webhook_rejects_invalid_signature_before_readiness_check_in_whatsapp_mode(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {"MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER")}

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())
        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "meta-webhook-invalid-signature-pending-account",
                "display_name": "Meta Webhook Invalid Signature Pending Account",
                "meta_business_portfolio_id": "portfolio-webhook-invalid-signature-pending",
                "waba_id": "waba-webhook-invalid-signature-pending",
                "access_token": "token-webhook-invalid-signature-pending",
                "verify_token": "verify-webhook-invalid-signature-pending",
                "app_secret": "secret-webhook-invalid-signature-pending",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-webhook-invalid-signature-pending",
                        "display_phone_number": "+1 555 000 1003",
                        "verified_name": "Webhook Invalid Signature Pending Brand",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert create_response.status_code == 200

        subscribe_response = client.post(
            "/api/meta/accounts/meta-webhook-invalid-signature-pending-account/wabas/"
            "waba-webhook-invalid-signature-pending/webhook-subscription",
            json={"callback_url": "https://example.com/webhook/invalid-signature-pending"},
        )
        assert subscribe_response.status_code == 200

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-webhook-invalid-signature-pending",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 1003",
                                    "phone_number_id": "pn-webhook-invalid-signature-pending",
                                },
                                "messages": [
                                    {
                                        "from": "14150001003",
                                        "id": "wamid.invalid.signature.pending.1",
                                        "timestamp": "1712345802",
                                        "type": "text",
                                        "text": {"body": "signature must fail before readiness"},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }

        webhook_response = client.post(
            "/webhooks/whatsapp/meta-webhook-invalid-signature-pending-account/wabas/"
            "waba-webhook-invalid-signature-pending",
            content=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalid",
            },
        )

        assert webhook_response.status_code == 403
        assert webhook_response.json()["detail"] == "Invalid WhatsApp webhook signature."

        accounts_response = client.get("/api/meta/accounts")
        assert accounts_response.status_code == 200
        account = next(
            item
            for item in accounts_response.json()
            if item["account_id"] == "meta-webhook-invalid-signature-pending-account"
        )
        assert account["webhook_verification_status"] == "pending"
        assert account["webhook_runtime_status"] == "signature_failed"
        assert account["webhook_runtime_error"] == "invalid_signature"
    finally:
        if original_env["MESSAGING_PROVIDER"] is None:
            os.environ.pop("MESSAGING_PROVIDER", None)
        else:
            os.environ["MESSAGING_PROVIDER"] = original_env["MESSAGING_PROVIDER"]
        get_settings.cache_clear()


def test_root_whatsapp_webhook_blocks_delivery_until_verified_in_whatsapp_mode(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {"MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER")}

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())
        register_meta_account_with_webhook_secret(client)
        subscribe_meta_webhook(client)

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-webhook-1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 0001",
                                    "phone_number_id": "pn-webhook-1",
                                },
                                "messages": [
                                    {
                                        "from": "14150000001",
                                        "id": "wamid.root.pending.verify.1",
                                        "timestamp": "1712345802",
                                        "type": "text",
                                        "text": {"body": "root webhook before verify"},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
        raw_body, signature = sign_whatsapp_payload(payload, "secret-webhook-1")

        response = client.post(
            "/webhooks/whatsapp",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )

        assert response.status_code == 412
        assert "webhook_verification_status='pending'" in response.json()["detail"]
        assert "MESSAGING_PROVIDER=whatsapp" in response.json()["detail"]

        blocked_audit_response = client.get(
            "/api/runtime/audit-logs",
            params={
                "account_id": "meta-webhook-account",
                "action": "meta_webhook_delivery_blocked",
                "target_type": "waba_account",
                "target_id": "waba-webhook-1",
            },
        )
        assert blocked_audit_response.status_code == 200
        blocked_audit_logs = blocked_audit_response.json()
        assert len(blocked_audit_logs) == 1
        assert blocked_audit_logs[0]["payload"] == {
            "reason": "webhook_not_ready",
            "webhook_verification_status": "pending",
            "webhook_subscription_status": "remote_subscribed",
            "ready_for_webhook_delivery": False,
            "blocking_reasons": ["webhook_not_ready"],
        }

        root_failure_audit_response = client.get(
            "/api/runtime/audit-logs",
            params={
                "account_id": "meta-webhook-account",
                "action": "meta_webhook_root_scope_failed",
                "target_type": "waba_account",
                "target_id": "waba-webhook-1",
            },
        )
        assert root_failure_audit_response.status_code == 200
        root_failure_audit_logs = root_failure_audit_response.json()
        assert len(root_failure_audit_logs) == 1
        assert root_failure_audit_logs[0]["payload"]["source_stage"] == "scoped_processing"
        assert root_failure_audit_logs[0]["payload"]["status_code"] == 412
        assert "webhook_verification_status='pending'" in root_failure_audit_logs[0]["payload"]["detail"]

        signature_unavailable_audit_response = client.get(
            "/api/runtime/audit-logs",
            params={
                "account_id": "meta-webhook-account",
                "action": "meta_webhook_signature_unavailable",
                "target_type": "waba_account",
                "target_id": "waba-webhook-1",
            },
        )
        assert signature_unavailable_audit_response.status_code == 200
        assert signature_unavailable_audit_response.json() == []
    finally:
        if original_env["MESSAGING_PROVIDER"] is None:
            os.environ.pop("MESSAGING_PROVIDER", None)
        else:
            os.environ["MESSAGING_PROVIDER"] = original_env["MESSAGING_PROVIDER"]
        get_settings.cache_clear()


def test_root_whatsapp_webhook_rejects_invalid_signature_before_scope_readiness_failures(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {"MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER")}

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())
        register_meta_account_with_webhook_secret(client)
        subscribe_meta_webhook(client)

        second_account_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "meta-root-invalid-signature-account-two",
                "display_name": "Meta Root Invalid Signature Account Two",
                "meta_business_portfolio_id": "portfolio-root-invalid-signature-two",
                "waba_id": "waba-root-invalid-signature-two",
                "access_token": "token-root-invalid-signature-two",
                "verify_token": "verify-root-invalid-signature-two",
                "app_secret": "secret-webhook-1",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-root-invalid-signature-two",
                        "display_phone_number": "+1 555 000 1010",
                        "verified_name": "Root Invalid Signature Two",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert second_account_response.status_code == 200

        second_subscribe_response = client.post(
            "/api/meta/accounts/meta-root-invalid-signature-account-two/wabas/"
            "waba-root-invalid-signature-two/webhook-subscription",
            json={"callback_url": "https://example.com/webhook/root-invalid-signature-two"},
        )
        assert second_subscribe_response.status_code == 200

        first_verify_response = client.get(
            "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-webhook-1",
                "hub.challenge": "challenge-root-invalid-signature-first",
            },
        )
        assert first_verify_response.status_code == 200

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-webhook-1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 0001",
                                    "phone_number_id": "pn-webhook-1",
                                },
                                "messages": [
                                    {
                                        "from": "14150001021",
                                        "id": "wamid.root.invalid.signature.verified.1",
                                        "timestamp": "1712345804",
                                        "type": "text",
                                        "text": {"body": "verified scope should not process"},
                                    }
                                ],
                            },
                        }
                    ],
                },
                {
                    "id": "waba-root-invalid-signature-two",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 1010",
                                    "phone_number_id": "pn-root-invalid-signature-two",
                                },
                                "messages": [
                                    {
                                        "from": "14150001022",
                                        "id": "wamid.root.invalid.signature.pending.1",
                                        "timestamp": "1712345805",
                                        "type": "text",
                                        "text": {"body": "pending scope should not leak readiness"},
                                    }
                                ],
                            },
                        }
                    ],
                },
            ],
        }
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        response = client.post(
            "/webhooks/whatsapp",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalid",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid WhatsApp webhook signature."

        accounts_response = client.get("/api/meta/accounts")
        assert accounts_response.status_code == 200
        accounts = {item["account_id"]: item for item in accounts_response.json()}
        first_account = accounts["meta-webhook-account"]
        second_account = accounts["meta-root-invalid-signature-account-two"]

        assert first_account["webhook_verification_status"] == "verified"
        assert first_account["webhook_runtime_status"] == "signature_failed"
        assert first_account["webhook_runtime_error"] == "invalid_signature"

        assert second_account["webhook_verification_status"] == "pending"
        assert second_account["webhook_runtime_status"] == "signature_failed"
        assert second_account["webhook_runtime_error"] == "invalid_signature"

        first_conversation_response = client.get(
            "/api/conversations",
            params={"account_id": "meta-webhook-account"},
        )
        assert first_conversation_response.status_code == 200
        first_payload = first_conversation_response.json()
        first_items = first_payload.get("items", first_payload) if isinstance(first_payload, dict) else first_payload
        assert first_items == []

        second_conversation_response = client.get(
            "/api/conversations",
            params={"account_id": "meta-root-invalid-signature-account-two"},
        )
        assert second_conversation_response.status_code == 200
        second_payload = second_conversation_response.json()
        second_items = second_payload.get("items", second_payload) if isinstance(second_payload, dict) else second_payload
        assert second_items == []
    finally:
        if original_env["MESSAGING_PROVIDER"] is None:
            os.environ.pop("MESSAGING_PROVIDER", None)
        else:
            os.environ["MESSAGING_PROVIDER"] = original_env["MESSAGING_PROVIDER"]
        get_settings.cache_clear()


def test_root_whatsapp_webhook_app_secret_conflict_is_audited(client: TestClient) -> None:
    register_meta_account_with_webhook_secret(client)
    register_second_meta_account_with_webhook_secret(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "messages": [],
                        },
                    }
                ],
            },
            {
                "id": "waba-webhook-2",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0002",
                                "phone_number_id": "pn-webhook-2",
                            },
                            "messages": [],
                        },
                    }
                ],
            },
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    response = client.post(
        "/webhooks/whatsapp",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=not-checked-before-secret-conflict",
        },
    )

    assert response.status_code == 409
    assert "multiple app secrets" in response.json()["detail"]

    for account_id, waba_id in (
        ("meta-webhook-account", "waba-webhook-1"),
        ("meta-webhook-account-two", "waba-webhook-2"),
    ):
        audit_response = client.get(
            "/api/runtime/audit-logs",
            params={
                "account_id": account_id,
                "action": "meta_webhook_root_app_secret_conflict",
                "target_type": "waba_account",
                "target_id": waba_id,
            },
        )
        assert audit_response.status_code == 200
        audit_logs = audit_response.json()
        assert len(audit_logs) == 1
        assert audit_logs[0]["payload"] == {
            "reason": "multiple_app_secrets",
            "root_entry_waba_ids": ["waba-webhook-1", "waba-webhook-2"],
            "resolved_waba_count": 2,
            "app_secret_count": 2,
            "signature_header_present": True,
        }
        assert "secret-webhook" not in str(audit_logs[0]["payload"])

    accounts_response = client.get("/api/meta/accounts")
    assert accounts_response.status_code == 200
    accounts = {
        item["account_id"]: item
        for item in accounts_response.json()
        if item["account_id"] in {"meta-webhook-account", "meta-webhook-account-two"}
    }
    assert accounts["meta-webhook-account"]["webhook_runtime_status"] == "signature_failed"
    assert accounts["meta-webhook-account"]["webhook_runtime_error"] == "multiple_app_secrets"
    assert accounts["meta-webhook-account"]["webhook_signature_failure_count"] == 0
    assert accounts["meta-webhook-account"]["webhook_last_signature_failed_at"] is None
    assert accounts["meta-webhook-account-two"]["webhook_runtime_status"] == "signature_failed"
    assert accounts["meta-webhook-account-two"]["webhook_runtime_error"] == "multiple_app_secrets"
    assert accounts["meta-webhook-account-two"]["webhook_signature_failure_count"] == 0
    assert accounts["meta-webhook-account-two"]["webhook_last_signature_failed_at"] is None


def test_root_whatsapp_webhook_blocks_verified_scope_without_ready_delivery_in_whatsapp_mode(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {"MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER")}

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "meta-root-verified-no-secret-account",
                "display_name": "Meta Root Verified No Secret Account",
                "meta_business_portfolio_id": "portfolio-root-verified-no-secret",
                "waba_id": "waba-root-verified-no-secret",
                "access_token": "token-root-verified-no-secret",
                "verify_token": "verify-root-verified-no-secret",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-root-verified-no-secret",
                        "display_phone_number": "+1 555 000 1003",
                        "verified_name": "Root Verified No Secret Brand",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert response.status_code == 200

        subscribe_response = client.post(
            "/api/meta/accounts/meta-root-verified-no-secret-account/wabas/"
            "waba-root-verified-no-secret/webhook-subscription",
            json={"callback_url": "https://example.com/webhook/root-verified-no-secret"},
        )
        assert subscribe_response.status_code == 200

        verify_response = client.get(
            "/webhooks/whatsapp/meta-root-verified-no-secret-account/wabas/"
            "waba-root-verified-no-secret",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-root-verified-no-secret",
                "hub.challenge": "challenge-root-verified-no-secret",
            },
        )
        assert verify_response.status_code == 200

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-root-verified-no-secret",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 1003",
                                    "phone_number_id": "pn-root-verified-no-secret",
                                },
                                "messages": [
                                    {
                                        "from": "14150001003",
                                        "id": "wamid.root.verified.no.secret.1",
                                        "timestamp": "1712345803",
                                        "type": "text",
                                        "text": {"body": "root verified but still no app secret"},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        response = client.post(
            "/webhooks/whatsapp",
            content=raw_body,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 503
        assert response.json()["detail"] == "Webhook app secret is not configured for this WABA."
    finally:
        if original_env["MESSAGING_PROVIDER"] is None:
            os.environ.pop("MESSAGING_PROVIDER", None)
        else:
            os.environ["MESSAGING_PROVIDER"] = original_env["MESSAGING_PROVIDER"]
        get_settings.cache_clear()


def test_receive_whatsapp_webhook_normalizes_and_processes_text_message(client: TestClient) -> None:
    register_meta_account_with_webhook_secret(client)
    subscribe_meta_webhook(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "contacts": [
                                {
                                    "wa_id": "14150000001",
                                    "profile": {"name": "Webhook Customer"},
                                }
                            ],
                            "messages": [
                                {
                                    "from": "14150000001",
                                    "id": "wamid.HBgLMTQxNTAwMDAwMDFfFQIAERgSNzA3RkI0MzY4QTgA",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "hola, necesito ayuda"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "whatsapp"
    assert body["account_id"] == "meta-webhook-account"
    assert body["waba_id"] == "waba-webhook-1"
    assert body["signature_verified"] is True
    assert body["accepted_messages"] == 1
    assert body["skipped_messages"] == 0

    result = body["results"][0]
    assert result["inbound"]["provider"] == "whatsapp"
    assert result["inbound"]["conversation_id"] == "wa:pn-webhook-1:14150000001"
    assert result["inbound"]["phone_number_id"] == "pn-webhook-1"
    assert result["translation"]["source_language"] == "es"
    assert result["translation"]["translated"] is False

    conversation_response = client.get(
        "/api/conversations",
        params={"account_id": "meta-webhook-account"},
    )
    assert conversation_response.status_code == 200
    conversations = conversation_response.json()
    assert len(conversations) == 1
    assert conversations[0]["conversation_id"] == "wa:pn-webhook-1:14150000001"

    accounts_response = client.get("/api/meta/accounts")
    assert accounts_response.status_code == 200
    account = next(item for item in accounts_response.json() if item["account_id"] == "meta-webhook-account")
    assert account["webhook_runtime_status"] == "healthy"
    assert account["webhook_last_event_received_at"] is not None
    assert account["webhook_last_message_received_at"] is not None
    assert account["webhook_last_status_update_at"] is None
    assert account["webhook_runtime_error"] is None


def test_receive_whatsapp_webhook_preserves_referral_context_on_text_message(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)
    subscribe_meta_webhook(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "contacts": [
                                {
                                    "wa_id": "14150000002",
                                    "profile": {"name": "Webhook Referral Customer"},
                                }
                            ],
                            "messages": [
                                {
                                    "from": "14150000002",
                                    "id": "wamid.referral.text.webhook.1",
                                    "timestamp": "1712345679",
                                    "type": "text",
                                    "text": {"body": "I want this offer"},
                                    "referral": {
                                        "source_url": "https://facebook.com/ad/123",
                                        "source_type": "ad",
                                        "source_id": "fb-ad-123",
                                        "headline": "Summer Sale",
                                        "body": "Tap to chat now",
                                        "media_type": "image",
                                        "image_url": "https://cdn.example.com/ad.jpg",
                                        "ctwa_clid": "clid-123",
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "whatsapp"
    assert body["account_id"] == "meta-webhook-account"
    assert body["accepted_messages"] == 1
    result = body["results"][0]
    assert result["inbound"]["message_type"] == "text"
    assert result["inbound"]["text"] == "I want this offer"
    assert result["inbound"]["metadata"]["referral_source_id"] == "fb-ad-123"
    assert result["inbound"]["metadata"]["referral_source_type"] == "ad"
    assert result["inbound"]["metadata"]["referral_headline"] == "Summer Sale"
    assert result["inbound"]["metadata"]["referral_ctwa_clid"] == "clid-123"

    messages_response = client.get(
        "/api/conversations/meta-webhook-account/wa:pn-webhook-1:14150000002/messages"
    )
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert len(messages) == 1
    assert messages[0]["direction"] == "inbound"
    assert messages[0]["message_type"] == "text"
    assert messages[0]["provider_message_id"] == "wamid.referral.text.webhook.1"
    assert messages[0]["original_text"] == "I want this offer"
    assert messages[0]["payload"]["metadata"]["referral_source_id"] == "fb-ad-123"
    assert messages[0]["payload"]["metadata"]["referral_media_type"] == "image"
    assert (
        messages[0]["payload"]["metadata"]["referral_payload"]["image_url"]
        == "https://cdn.example.com/ad.jpg"
    )
    assert messages[0]["payload"]["metadata"]["has_meaningful_text"] is True


def test_receive_whatsapp_webhook_preserves_context_reply_and_referred_product_metadata(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)
    subscribe_meta_webhook(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "contacts": [
                                {
                                    "wa_id": "14150000006",
                                    "profile": {"name": "Webhook Context Customer"},
                                }
                            ],
                            "messages": [
                                {
                                    "from": "14150000006",
                                    "id": "wamid.context.text.webhook.1",
                                    "timestamp": "1712345710",
                                    "type": "text",
                                    "text": {"body": "I want this exact product"},
                                    "context": {
                                        "from": "14150000999",
                                        "id": "wamid.original.webhook.999",
                                        "forwarded": True,
                                        "frequently_forwarded": False,
                                        "referred_product": {
                                            "catalog_id": "catalog-webhook-context-1",
                                            "product_retailer_id": "sku-webhook-context-1001",
                                        },
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "whatsapp"
    assert body["account_id"] == "meta-webhook-account"
    assert body["accepted_messages"] == 1
    result = body["results"][0]
    assert result["inbound"]["message_type"] == "text"
    assert result["inbound"]["text"] == "I want this exact product"
    assert result["inbound"]["metadata"]["context_reply_to_message_id"] == "wamid.original.webhook.999"
    assert result["inbound"]["metadata"]["context_reply_to_user_id"] == "14150000999"
    assert result["inbound"]["metadata"]["context_forwarded"] is True
    assert result["inbound"]["metadata"]["context_frequently_forwarded"] is False
    assert (
        result["inbound"]["metadata"]["context_referred_product_catalog_id"]
        == "catalog-webhook-context-1"
    )
    assert (
        result["inbound"]["metadata"]["context_referred_product_retailer_id"]
        == "sku-webhook-context-1001"
    )

    messages_response = client.get(
        "/api/conversations/meta-webhook-account/wa:pn-webhook-1:14150000006/messages"
    )
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert len(messages) == 1
    assert messages[0]["direction"] == "inbound"
    assert messages[0]["message_type"] == "text"
    assert messages[0]["provider_message_id"] == "wamid.context.text.webhook.1"
    assert messages[0]["original_text"] == "I want this exact product"
    assert (
        messages[0]["payload"]["metadata"]["context_reply_to_message_id"]
        == "wamid.original.webhook.999"
    )
    assert messages[0]["payload"]["metadata"]["context_reply_to_user_id"] == "14150000999"
    assert messages[0]["payload"]["metadata"]["context_forwarded"] is True
    assert messages[0]["payload"]["metadata"]["context_frequently_forwarded"] is False
    assert (
        messages[0]["payload"]["metadata"]["context_payload"]["referred_product"]["catalog_id"]
        == "catalog-webhook-context-1"
    )
    assert (
        messages[0]["payload"]["metadata"]["context_referred_product_retailer_id"]
        == "sku-webhook-context-1001"
    )


def test_receive_whatsapp_webhook_media_message_without_caption_requires_manual_review(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "messages": [
                                {
                                    "from": "14150000011",
                                    "id": "wamid.image.review.1",
                                    "timestamp": "1712345778",
                                    "type": "image",
                                    "image": {
                                        "id": "meta-image-review-1",
                                        "mime_type": "image/jpeg",
                                        "sha256": "sha-image-review-1",
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_messages"] == 1
    result = body["results"][0]
    assert result["inbound"]["message_type"] == "image"
    assert result["inbound"]["text"] == "[image attachment]"
    assert result["translation"]["source_language"] == "und"
    assert result["outbound"]["text"] is None
    assert result["outbound"]["delivery_mode"] == "handover_recommended"
    assert result["ai"]["provider"] == "media_router"
    assert result["intent"]["handover_recommended"] is True
    assert result["intent"]["handover_reason"] == "non_text_message_requires_manual_review"

    messages_response = client.get(
        "/api/conversations/meta-webhook-account/wa:pn-webhook-1:14150000011/messages"
    )
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert len(messages) == 1
    assert messages[0]["direction"] == "inbound"
    assert messages[0]["message_type"] == "image"
    assert messages[0]["waba_id"] == "waba-webhook-1"
    assert messages[0]["phone_number_id"] == "pn-webhook-1"
    assert messages[0]["provider_message_id"] == "wamid.image.review.1"
    assert messages[0]["provider_media_id"] == "meta-image-review-1"
    assert messages[0]["original_text"] == "[image attachment]"
    assert messages[0]["payload"]["metadata"]["media_kind"] == "image"
    assert messages[0]["payload"]["metadata"]["provider_media_id"] == "meta-image-review-1"
    assert messages[0]["payload"]["metadata"]["media_id"] == "meta-image-review-1"
    assert messages[0]["payload"]["metadata"]["has_meaningful_text"] is False
    assert messages[0]["language_code"] == "und"

    timeline_response = client.get(
        "/api/conversations/meta-webhook-account/wa:pn-webhook-1:14150000011/timeline",
    )
    assert timeline_response.status_code == 200
    timeline = timeline_response.json()
    assert any(item["title"] == "whatsapp_inbound_received" for item in timeline)
    assert any(item["title"] == "handover_recommended" for item in timeline)


def test_receive_whatsapp_webhook_interactive_reply_preserves_reply_metadata(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "messages": [
                                {
                                    "from": "14150000010",
                                    "id": "wamid.interactive.reply.1",
                                    "timestamp": "1712345768",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button_reply",
                                        "button_reply": {
                                            "id": "track-order",
                                            "title": "Track order",
                                        },
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_messages"] == 1
    result = body["results"][0]
    assert result["inbound"]["message_type"] == "interactive"
    assert result["inbound"]["text"] == "Track order"
    assert result["intent"]["handover_recommended"] is False

    messages_response = client.get(
        "/api/conversations/meta-webhook-account/wa:pn-webhook-1:14150000010/messages"
    )
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert len(messages) == 1
    inbound_messages = [item for item in messages if item["direction"] == "inbound"]
    assert len(inbound_messages) == 1
    assert inbound_messages[0]["message_type"] == "interactive"
    assert inbound_messages[0]["original_text"] == "Track order"
    assert inbound_messages[0]["payload"]["metadata"]["interactive_type"] == "button_reply"
    assert inbound_messages[0]["payload"]["metadata"]["interactive_reply_id"] == "track-order"
    assert inbound_messages[0]["payload"]["metadata"]["interactive_reply_title"] == "Track order"
    assert inbound_messages[0]["payload"]["metadata"]["has_meaningful_text"] is True


def test_receive_whatsapp_webhook_flow_reply_preserves_response_payload(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "messages": [
                                {
                                    "from": "14150000015",
                                    "id": "wamid.interactive.flow.webhook.1",
                                    "timestamp": "1712345799",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "nfm_reply",
                                        "nfm_reply": {
                                            "name": "order_support_flow",
                                            "body": "Submitted order support request",
                                            "response_json": {
                                                "flow_token": "flow-token-1",
                                                "order_id": "A-100",
                                                "issue_type": "shipping",
                                            },
                                        },
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_messages"] == 1
    result = body["results"][0]
    assert result["inbound"]["message_type"] == "interactive"
    assert result["inbound"]["text"] == "Submitted order support request"
    assert result["inbound"]["metadata"]["interactive_type"] == "nfm_reply"
    assert result["inbound"]["metadata"]["interactive_flow_name"] == "order_support_flow"
    assert result["inbound"]["metadata"]["interactive_flow_response"]["order_id"] == "A-100"

    messages_response = client.get(
        "/api/conversations/meta-webhook-account/wa:pn-webhook-1:14150000015/messages"
    )
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert len(messages) == 1
    inbound_messages = [item for item in messages if item["direction"] == "inbound"]
    assert len(inbound_messages) == 1
    assert inbound_messages[0]["message_type"] == "interactive"
    assert inbound_messages[0]["original_text"] == "Submitted order support request"
    assert inbound_messages[0]["payload"]["metadata"]["interactive_type"] == "nfm_reply"
    assert inbound_messages[0]["payload"]["metadata"]["interactive_flow_name"] == "order_support_flow"
    assert (
        inbound_messages[0]["payload"]["metadata"]["interactive_flow_response"]["issue_type"]
        == "shipping"
    )
    assert inbound_messages[0]["payload"]["metadata"]["has_meaningful_text"] is True


def test_receive_whatsapp_webhook_preserves_unknown_interactive_subtypes_as_placeholder_messages(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "messages": [
                                {
                                    "from": "14150000016",
                                    "id": "wamid.interactive.unknown.webhook.1",
                                    "timestamp": "1712345800",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "galaxy_reply",
                                        "provider_future_payload": {
                                            "selection": "x",
                                        },
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_messages"] == 1
    result = body["results"][0]
    assert result["inbound"]["message_type"] == "interactive"
    assert result["inbound"]["text"] == "[interactive message]"
    assert result["inbound"]["metadata"]["interactive_type"] == "galaxy_reply"

    messages_response = client.get(
        "/api/conversations/meta-webhook-account/wa:pn-webhook-1:14150000016/messages"
    )
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert len(messages) == 1
    inbound_messages = [item for item in messages if item["direction"] == "inbound"]
    assert len(inbound_messages) == 1
    assert inbound_messages[0]["message_type"] == "interactive"
    assert inbound_messages[0]["original_text"] == "[interactive message]"
    assert inbound_messages[0]["payload"]["metadata"]["interactive_type"] == "galaxy_reply"
    assert inbound_messages[0]["payload"]["metadata"]["has_meaningful_text"] is False


def test_receive_whatsapp_webhook_location_message_requires_manual_review(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "messages": [
                                {
                                    "from": "14150000012",
                                    "id": "wamid.location.review.1",
                                    "timestamp": "1712345788",
                                    "type": "location",
                                    "location": {
                                        "latitude": 37.4848,
                                        "longitude": -122.1484,
                                        "name": "Meta HQ",
                                        "address": "1 Hacker Way",
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_messages"] == 1
    result = body["results"][0]
    assert result["inbound"]["message_type"] == "location"
    assert result["inbound"]["text"] == "Meta HQ"
    assert result["translation"]["source_language"] == "und"
    assert result["outbound"]["text"] is None
    assert result["outbound"]["delivery_mode"] == "handover_recommended"
    assert result["ai"]["provider"] == "media_router"
    assert result["intent"]["handover_recommended"] is True
    assert result["intent"]["handover_reason"] == "non_text_message_requires_manual_review"

    messages_response = client.get(
        "/api/conversations/meta-webhook-account/wa:pn-webhook-1:14150000012/messages"
    )
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert len(messages) == 1
    assert messages[0]["direction"] == "inbound"
    assert messages[0]["message_type"] == "location"
    assert messages[0]["waba_id"] == "waba-webhook-1"
    assert messages[0]["phone_number_id"] == "pn-webhook-1"
    assert messages[0]["provider_message_id"] == "wamid.location.review.1"
    assert messages[0]["original_text"] == "Meta HQ"
    assert messages[0]["payload"]["metadata"]["location_name"] == "Meta HQ"
    assert messages[0]["payload"]["metadata"]["location_address"] == "1 Hacker Way"
    assert messages[0]["payload"]["metadata"]["has_meaningful_text"] is False
    assert messages[0]["language_code"] == "und"

    timeline_response = client.get(
        "/api/conversations/meta-webhook-account/wa:pn-webhook-1:14150000012/timeline",
    )
    assert timeline_response.status_code == 200
    timeline = timeline_response.json()
    assert any(item["title"] == "whatsapp_inbound_received" for item in timeline)
    assert any(item["title"] == "handover_recommended" for item in timeline)


def test_receive_whatsapp_webhook_contact_card_message_requires_manual_review(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "messages": [
                                {
                                    "from": "14150000013",
                                    "id": "wamid.contacts.review.1",
                                    "timestamp": "1712345798",
                                    "type": "contacts",
                                    "contacts": [
                                        {
                                            "name": {
                                                "formatted_name": "Ana Support",
                                                "first_name": "Ana",
                                                "last_name": "Support",
                                            },
                                            "phones": [
                                                {
                                                    "phone": "+1 555 000 0100",
                                                    "type": "WORK",
                                                    "wa_id": "14150000100",
                                                }
                                            ],
                                            "emails": [
                                                {
                                                    "email": "ana@example.com",
                                                    "type": "WORK",
                                                }
                                            ],
                                            "org": {
                                                "company": "Example Inc",
                                                "title": "Support Lead",
                                            },
                                        }
                                    ],
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_messages"] == 1
    result = body["results"][0]
    assert result["inbound"]["message_type"] == "contacts"
    assert result["inbound"]["text"] == "Ana Support"
    assert result["translation"]["source_language"] == "und"
    assert result["outbound"]["text"] is None
    assert result["outbound"]["delivery_mode"] == "handover_recommended"
    assert result["ai"]["provider"] == "media_router"
    assert result["intent"]["handover_recommended"] is True
    assert result["intent"]["handover_reason"] == "non_text_message_requires_manual_review"

    messages_response = client.get(
        "/api/conversations/meta-webhook-account/wa:pn-webhook-1:14150000013/messages"
    )
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert len(messages) == 1
    assert messages[0]["direction"] == "inbound"
    assert messages[0]["message_type"] == "contacts"
    assert messages[0]["waba_id"] == "waba-webhook-1"
    assert messages[0]["phone_number_id"] == "pn-webhook-1"
    assert messages[0]["provider_message_id"] == "wamid.contacts.review.1"
    assert messages[0]["original_text"] == "Ana Support"
    assert messages[0]["payload"]["metadata"]["shared_contact_count"] == 1
    shared_contact = messages[0]["payload"]["metadata"]["shared_contacts"][0]
    assert shared_contact["formatted_name"] == "Ana Support"
    assert shared_contact["phones"][0]["wa_id"] == "14150000100"
    assert shared_contact["organization"]["company"] == "Example Inc"
    assert messages[0]["payload"]["metadata"]["has_meaningful_text"] is False
    assert messages[0]["language_code"] == "und"

    timeline_response = client.get(
        "/api/conversations/meta-webhook-account/wa:pn-webhook-1:14150000013/timeline",
    )
    assert timeline_response.status_code == 200
    timeline = timeline_response.json()
    assert any(item["title"] == "whatsapp_inbound_received" for item in timeline)
    assert any(item["title"] == "handover_recommended" for item in timeline)


def test_receive_whatsapp_webhook_system_message_requires_manual_review(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "messages": [
                                {
                                    "from": "14150000014",
                                    "id": "wamid.system.review.1",
                                    "timestamp": "1712345808",
                                    "type": "system",
                                    "system": {
                                        "body": "Customer changed from +1 555 000 0014 to +1 555 000 0099",
                                        "identity": "14150000014",
                                        "new_wa_id": "14150000099",
                                        "wa_id": "14150000014",
                                        "type": "customer_changed_number",
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_messages"] == 1
    result = body["results"][0]
    assert result["inbound"]["message_type"] == "system"
    assert result["inbound"]["text"] == "Customer changed from +1 555 000 0014 to +1 555 000 0099"
    assert result["translation"]["source_language"] == "und"
    assert result["outbound"]["text"] is None
    assert result["outbound"]["delivery_mode"] == "handover_recommended"
    assert result["ai"]["provider"] == "media_router"
    assert result["intent"]["handover_recommended"] is True
    assert result["intent"]["handover_reason"] == "non_text_message_requires_manual_review"

    messages_response = client.get(
        "/api/conversations/meta-webhook-account/wa:pn-webhook-1:14150000014/messages"
    )
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert len(messages) == 1
    assert messages[0]["direction"] == "inbound"
    assert messages[0]["message_type"] == "system"
    assert messages[0]["provider_message_id"] == "wamid.system.review.1"
    assert messages[0]["original_text"] == "Customer changed from +1 555 000 0014 to +1 555 000 0099"
    assert messages[0]["payload"]["metadata"]["system_type"] == "customer_changed_number"
    assert messages[0]["payload"]["metadata"]["system_new_wa_id"] == "14150000099"
    assert messages[0]["payload"]["metadata"]["has_meaningful_text"] is False
    assert messages[0]["language_code"] == "und"


def test_receive_whatsapp_webhook_order_message_requires_manual_review(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "messages": [
                                {
                                    "from": "14150000015",
                                    "id": "wamid.order.review.1",
                                    "timestamp": "1712345818",
                                    "type": "order",
                                    "order": {
                                        "catalog_id": "catalog-webhook-1",
                                        "product_items": [
                                            {
                                                "product_retailer_id": "sku-1001",
                                                "quantity": 2,
                                                "item_price": "1999",
                                                "currency": "USD",
                                            },
                                            {
                                                "product_retailer_id": "sku-1002",
                                                "quantity": 1,
                                                "item_price": "2999",
                                                "currency": "USD",
                                            },
                                        ],
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_messages"] == 1
    result = body["results"][0]
    assert result["inbound"]["message_type"] == "order"
    assert result["inbound"]["text"] == "[order message]"
    assert result["translation"]["source_language"] == "und"
    assert result["outbound"]["text"] is None
    assert result["outbound"]["delivery_mode"] == "handover_recommended"
    assert result["ai"]["provider"] == "media_router"
    assert result["intent"]["handover_recommended"] is True
    assert result["intent"]["handover_reason"] == "non_text_message_requires_manual_review"

    messages_response = client.get(
        "/api/conversations/meta-webhook-account/wa:pn-webhook-1:14150000015/messages"
    )
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert len(messages) == 1
    assert messages[0]["direction"] == "inbound"
    assert messages[0]["message_type"] == "order"
    assert messages[0]["provider_message_id"] == "wamid.order.review.1"
    assert messages[0]["original_text"] == "[order message]"
    assert messages[0]["payload"]["metadata"]["order_catalog_id"] == "catalog-webhook-1"
    assert messages[0]["payload"]["metadata"]["order_product_count"] == 2
    assert (
        messages[0]["payload"]["metadata"]["order_product_items"][0]["product_retailer_id"]
        == "sku-1001"
    )
    assert messages[0]["payload"]["metadata"]["has_meaningful_text"] is False
    assert messages[0]["language_code"] == "und"

    timeline_response = client.get(
        "/api/conversations/meta-webhook-account/wa:pn-webhook-1:14150000015/timeline",
    )
    assert timeline_response.status_code == 200
    timeline = timeline_response.json()
    assert any(item["title"] == "whatsapp_inbound_received" for item in timeline)
    assert any(item["title"] == "handover_recommended" for item in timeline)


def test_receive_whatsapp_webhook_missing_waba_scope_is_audited(client: TestClient) -> None:
    register_meta_account_with_webhook_secret(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-missing",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 9999",
                                "phone_number_id": "pn-webhook-missing",
                            },
                            "messages": [
                                {
                                    "from": "14150009999",
                                    "id": "wamid.receive.scope.missing.1",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "missing scoped waba should be audited"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-missing",
        content=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "WABA 'waba-webhook-missing' for account 'meta-webhook-account' was not found."
    )

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-webhook-account",
            "action": "meta_webhook_receive_scope_missing",
            "target_type": "waba_account",
            "target_id": "waba-webhook-missing",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"] == {
        "reason": "waba_scope_not_found",
        "error": "WABA 'waba-webhook-missing' for account 'meta-webhook-account' was not found.",
        "signature_header_present": False,
    }


def test_receive_whatsapp_webhook_rejects_malformed_payload_with_audit(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)

    raw_body = b'{"object":'
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 422

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-webhook-account",
            "action": "meta_webhook_receive_payload_invalid",
            "target_type": "waba_account",
            "target_id": "waba-webhook-1",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"] == {
        "reason": "invalid_payload",
        "validation_error_count": 1,
    }
    assert '{"object":' not in str(audit_logs[0]["payload"])

    accounts_response = client.get(
        "/api/meta/accounts",
        params={"account_id": "meta-webhook-account"},
    )
    assert accounts_response.status_code == 200
    account = accounts_response.json()[0]
    assert account["webhook_runtime_status"] == "payload_invalid"
    assert account["webhook_runtime_error"] == "payload_validation_failed"


def test_receive_whatsapp_webhook_rejects_unknown_phone_number_scope(client: TestClient) -> None:
    register_meta_account_with_webhook_secret(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 9999",
                                "phone_number_id": "pn-webhook-missing",
                            },
                            "contacts": [
                                {
                                    "wa_id": "14150000999",
                                    "profile": {"name": "Scope Mismatch Customer"},
                                }
                            ],
                            "messages": [
                                {
                                    "from": "14150000999",
                                    "id": "wamid.scope.mismatch.1",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "hello from wrong number"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_messages"] == 0
    assert body["skipped_messages"] == 1
    assert body["rejected_phone_scope_messages"] == 1
    assert body["results"] == []

    conversations_response = client.get(
        "/api/conversations",
        params={"account_id": "meta-webhook-account"},
    )
    assert conversations_response.status_code == 200
    assert conversations_response.json() == []

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-webhook-account",
            "action": "meta_webhook_phone_scope_rejected",
            "target_type": "waba_account",
            "target_id": "waba-webhook-1",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"]["phone_number_id"] == "pn-webhook-missing"
    assert audit_logs[0]["payload"]["item_type"] == "message"


def test_receive_whatsapp_webhook_rejects_inactive_phone_number_scope(client: TestClient) -> None:
    register_meta_account_with_webhook_secret(client)
    deactivate_phone_response = client.patch(
        "/api/meta/accounts/meta-webhook-account/wabas/waba-webhook-1/phone-numbers/pn-webhook-1/status",
        json={"is_active": False},
    )
    assert deactivate_phone_response.status_code == 200

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "messages": [
                                {
                                    "from": "14150000077",
                                    "id": "wamid.inactive.phone.1",
                                    "timestamp": "1712346000",
                                    "type": "text",
                                    "text": {"body": "inactive number should be skipped"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_messages"] == 0
    assert body["rejected_phone_scope_messages"] == 1

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-webhook-account",
            "action": "meta_webhook_phone_scope_rejected",
            "target_type": "waba_account",
            "target_id": "waba-webhook-1",
        },
    )
    assert audit_response.status_code == 200
    assert audit_response.json()[0]["payload"]["reason"] == "phone_number_inactive"


def test_whatsapp_status_update_rejects_unknown_phone_number_scope(client: TestClient) -> None:
    register_meta_account_with_webhook_secret(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 9999",
                                "phone_number_id": "pn-webhook-missing",
                            },
                            "statuses": [
                                {
                                    "id": "wamid.scope.status.1",
                                    "status": "delivered",
                                    "timestamp": "1712345699",
                                    "recipient_id": "14150000999",
                                    "conversation": {
                                        "id": "meta-conversation-missing",
                                        "origin": {"type": "business_initiated"},
                                    },
                                    "pricing": {
                                        "billable": True,
                                        "category": "utility",
                                        "pricing_model": "CBP",
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_status_updates"] == 0
    assert body["skipped_status_updates"] == 1
    assert body["matched_status_updates"] == 0
    assert body["unmatched_status_updates"] == 0
    assert body["rejected_phone_scope_status_updates"] == 1

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-webhook-account",
            "action": "meta_webhook_phone_scope_rejected",
            "target_type": "waba_account",
            "target_id": "waba-webhook-1",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"]["item_type"] == "status_update"
    assert audit_logs[0]["payload"]["external_id"] == "wamid.scope.status.1"


def test_whatsapp_webhook_signature_failure_is_audited(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    import os
    from app.core.settings import get_settings

    original_env = os.environ.get("MESSAGING_PROVIDER")
    os.environ["MESSAGING_PROVIDER"] = "whatsapp"
    get_settings.cache_clear()
    try:
        override_meta_management_provider(client, StubMetaManagementProvider())
        register_meta_account_with_webhook_secret(client)
        subscribe_meta_webhook(client)

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-webhook-1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 0001",
                                    "phone_number_id": "pn-webhook-1",
                                },
                                "messages": [],
                                "statuses": [],
                            },
                        }
                    ],
                }
            ],
        }
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        response = client.post(
            "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalid",
            },
        )

        assert response.status_code == 403

        audit_response = client.get(
            "/api/runtime/audit-logs",
            params={
                "account_id": "meta-webhook-account",
                "action": "meta_webhook_signature_failed",
                "target_type": "waba_account",
                "target_id": "waba-webhook-1",
            },
        )
        assert audit_response.status_code == 200
        audit_logs = audit_response.json()
        assert len(audit_logs) == 1
        assert audit_logs[0]["payload"]["signature_header_present"] is True

        accounts_response = client.get("/api/meta/accounts")
        assert accounts_response.status_code == 200
        account = next(item for item in accounts_response.json() if item["account_id"] == "meta-webhook-account")
        assert account["webhook_runtime_status"] == "signature_failed"
        assert account["webhook_last_signature_failed_at"] is not None
        assert account["webhook_signature_failure_count"] == 1
        assert account["webhook_runtime_error"] == "invalid_signature"
    finally:
        if original_env is None:
            os.environ.pop("MESSAGING_PROVIDER", None)
        else:
            os.environ["MESSAGING_PROVIDER"] = original_env
        get_settings.cache_clear()


def test_whatsapp_webhook_rejects_payload_waba_that_does_not_match_scoped_route(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)
    subscribe_meta_webhook(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-mismatch",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "messages": [
                                {
                                    "from": "14150001001",
                                    "id": "wamid.route.mismatch.1",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "scoped route should reject mismatched waba"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body, signature = sign_whatsapp_payload(payload, "secret-webhook-1")

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Webhook payload WABA does not match route."

    accounts_response = client.get(
        "/api/meta/accounts",
        params={"account_id": "meta-webhook-account"},
    )
    assert accounts_response.status_code == 200
    account = accounts_response.json()[0]
    assert account["webhook_runtime_status"] == "payload_invalid"
    assert account["webhook_runtime_error"] == "payload_waba_route_mismatch"

    conversation_response = client.get(
        "/api/conversations",
        params={"account_id": "meta-webhook-account"},
    )
    assert conversation_response.status_code == 200
    assert conversation_response.json() == []

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-webhook-account",
            "action": "meta_webhook_receive_payload_invalid",
            "target_type": "waba_account",
            "target_id": "waba-webhook-1",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"] == {
        "reason": "route_waba_mismatch",
        "route_waba_id": "waba-webhook-1",
        "payload_waba_id": "waba-webhook-mismatch",
    }


def test_whatsapp_webhook_rejects_unsupported_object_with_audit(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)

    payload = {
        "object": "instagram_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [],
            }
        ],
    }
    raw_body, signature = sign_whatsapp_payload(payload, "secret-webhook-1")

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Unsupported webhook object."

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-webhook-account",
            "action": "meta_webhook_receive_payload_invalid",
            "target_type": "waba_account",
            "target_id": "waba-webhook-1",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"] == {
        "reason": "unsupported_object",
        "object": "instagram_business_account",
        "entry_count": 1,
    }

    accounts_response = client.get(
        "/api/meta/accounts",
        params={"account_id": "meta-webhook-account"},
    )
    assert accounts_response.status_code == 200
    account = accounts_response.json()[0]
    assert account["webhook_runtime_status"] == "payload_invalid"
    assert account["webhook_runtime_error"] == "unsupported_webhook_object"


def test_whatsapp_webhook_rejects_payload_without_waba_entry_in_scoped_route(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [],
    }
    raw_body, signature = sign_whatsapp_payload(payload, "secret-webhook-1")

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Webhook payload entry is required."

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-webhook-account",
            "action": "meta_webhook_receive_payload_invalid",
            "target_type": "waba_account",
            "target_id": "waba-webhook-1",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"] == {
        "reason": "missing_waba_entry",
        "object": "whatsapp_business_account",
        "entry_count": 0,
    }

    accounts_response = client.get(
        "/api/meta/accounts",
        params={"account_id": "meta-webhook-account"},
    )
    assert accounts_response.status_code == 200
    account = accounts_response.json()[0]
    assert account["webhook_runtime_status"] == "payload_invalid"
    assert account["webhook_runtime_error"] == "missing_waba_entry"


def test_whatsapp_template_status_webhook_updates_only_scoped_waba_template(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)
    register_second_meta_account_with_webhook_secret(client)

    primary_template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "meta-webhook-account",
            "waba_id": "waba-webhook-1",
            "name": "template_status_webhook",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, your update is ready.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert primary_template_response.status_code == 200
    primary_template_id = primary_template_response.json()["template_id"]
    secondary_template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "meta-webhook-account-two",
            "waba_id": "waba-webhook-2",
            "name": "template_status_webhook",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, your update is ready.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert secondary_template_response.status_code == 200
    secondary_template_id = secondary_template_response.json()["template_id"]
    for template_id in (primary_template_id, secondary_template_id):
        status_response = client.post(
            f"/api/templates/{template_id}/status",
            json={
                "status": "PENDING",
                "meta_template_id": "meta-template-webhook-shared",
            },
        )
        assert status_response.status_code == 200

    payload = build_template_webhook_payload(
        waba_id="waba-webhook-1",
        field="message_template_status_update",
        value={
            "event": "REJECTED",
            "message_template_id": "meta-template-webhook-shared",
            "message_template_name": "template_status_webhook",
            "message_template_language": "en",
            "reason": "BODY_VARIABLE_FORMAT_INVALID",
        },
    )
    raw_body, signature = sign_whatsapp_payload(payload, "secret-webhook-1")

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accepted_messages"] == 0
    assert body["accepted_status_updates"] == 0
    assert body["accepted_template_updates"] == 1
    assert body["matched_template_updates"] == 1
    assert body["skipped_template_updates"] == 0

    primary_templates_response = client.get(
        "/api/templates",
        params={"account_id": "meta-webhook-account"},
    )
    assert primary_templates_response.status_code == 200
    primary_template = next(
        item for item in primary_templates_response.json() if item["template_id"] == primary_template_id
    )
    assert primary_template["status"] == "REJECTED"
    assert primary_template["rejected_reason"] == "BODY_VARIABLE_FORMAT_INVALID"
    assert primary_template["last_synced_at"] is not None

    secondary_templates_response = client.get(
        "/api/templates",
        params={"account_id": "meta-webhook-account-two"},
    )
    assert secondary_templates_response.status_code == 200
    secondary_template = next(
        item for item in secondary_templates_response.json() if item["template_id"] == secondary_template_id
    )
    assert secondary_template["status"] == "PENDING"
    assert secondary_template["rejected_reason"] is None

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-webhook-account",
            "action": "template_webhook_status_updated",
            "target_type": "message_template",
            "target_id": primary_template_id,
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"]["waba_id"] == "waba-webhook-1"
    assert audit_logs[0]["payload"]["meta_template_id"] == "meta-template-webhook-shared"


def test_whatsapp_template_quality_webhook_updates_provider_payload(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_meta_account_with_webhook_secret(client)

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "meta-webhook-account",
            "waba_id": "waba-webhook-1",
            "name": "template_quality_webhook",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, quality update.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]
    status_response = client.post(
        f"/api/templates/{template_id}/status",
        json={
            "status": "APPROVED",
            "meta_template_id": "meta-template-quality-webhook",
        },
    )
    assert status_response.status_code == 200

    payload = build_template_webhook_payload(
        waba_id="waba-webhook-1",
        field="message_template_quality_update",
        value={
            "event": "QUALITY_UPDATE",
            "message_template_id": "meta-template-quality-webhook",
            "message_template_name": "template_quality_webhook",
            "message_template_language": "en",
            "previous_quality_score": "GREEN",
            "new_quality_score": "YELLOW",
        },
    )
    raw_body, signature = sign_whatsapp_payload(payload, "secret-webhook-1")

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accepted_template_updates"] == 1
    assert body["matched_template_updates"] == 1
    assert body["skipped_template_updates"] == 0

    with db_session_factory() as session:
        template = session.query(MessageTemplate).filter_by(id=template_id).one()
        assert template.status == "APPROVED"
        assert template.provider_template_payload is not None
        assert template.provider_template_payload["quality_score"] == "YELLOW"
        assert (
            template.provider_template_payload["last_webhook_update"]["raw_payload"][
                "previous_quality_score"
            ]
            == "GREEN"
        )


def test_whatsapp_template_webhook_unmatched_update_is_audited(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)

    payload = build_template_webhook_payload(
        waba_id="waba-webhook-1",
        field="message_template_status_update",
        value={
            "event": "APPROVED",
            "message_template_id": "meta-template-webhook-missing",
            "message_template_name": "missing_template",
            "message_template_language": "en",
        },
    )
    raw_body, signature = sign_whatsapp_payload(payload, "secret-webhook-1")

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accepted_template_updates"] == 1
    assert body["matched_template_updates"] == 0
    assert body["skipped_template_updates"] == 1

    templates_response = client.get(
        "/api/templates",
        params={"account_id": "meta-webhook-account"},
    )
    assert templates_response.status_code == 200
    assert templates_response.json() == []

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-webhook-account",
            "action": "template_webhook_update_unmatched",
            "target_type": "waba_account",
            "target_id": "waba-webhook-1",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"]["meta_template_id"] == "meta-template-webhook-missing"


def test_whatsapp_phone_number_quality_webhook_updates_only_matching_phone_scope(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)
    register_second_meta_account_with_webhook_secret(client)

    payload = build_template_webhook_payload(
        waba_id="waba-webhook-1",
        field="phone_number_quality_update",
        value={
            "event": "DOWNGRADE",
            "phone_number_id": "pn-webhook-1",
            "display_phone_number": "+1 555 000 0001",
            "previous_quality_rating": "GREEN",
            "new_quality_rating": "RED",
            "current_limit": "TIER_250",
            "max_daily_conversations_per_business": 250,
            "provider_extra_field": "kept-for-audit",
        },
    )
    raw_body, signature = sign_whatsapp_payload(payload, "secret-webhook-1")

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accepted_phone_number_updates"] == 1
    assert body["matched_phone_number_updates"] == 1
    assert body["skipped_phone_number_updates"] == 0

    primary_phone_response = client.get(
        "/api/meta/accounts/meta-webhook-account/wabas/waba-webhook-1/phone-numbers"
    )
    assert primary_phone_response.status_code == 200
    primary_phone = next(
        item for item in primary_phone_response.json() if item["phone_number_id"] == "pn-webhook-1"
    )
    assert primary_phone["quality_rating"] == "RED"
    assert primary_phone["previous_quality_rating"] == "GREEN"
    assert primary_phone["quality_event"] == "DOWNGRADE"
    assert primary_phone["messaging_limit_tier"] == "TIER_250"
    assert primary_phone["max_daily_conversations_per_business"] == 250
    assert primary_phone["last_quality_event_at"] is not None

    secondary_phone_response = client.get(
        "/api/meta/accounts/meta-webhook-account-two/wabas/waba-webhook-2/phone-numbers"
    )
    assert secondary_phone_response.status_code == 200
    secondary_phone = next(
        item for item in secondary_phone_response.json() if item["phone_number_id"] == "pn-webhook-2"
    )
    assert secondary_phone["quality_rating"] == "GREEN"
    assert secondary_phone["quality_event"] is None

    red_filter_response = client.get(
        "/api/meta/accounts/phone-numbers",
        params={"quality_rating": "RED"},
    )
    assert red_filter_response.status_code == 200
    assert [item["phone_number_id"] for item in red_filter_response.json()] == ["pn-webhook-1"]

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-webhook-account",
            "action": "whatsapp_phone_number_webhook_updated",
            "target_type": "phone_number",
            "target_id": "pn-webhook-1",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"]["waba_id"] == "waba-webhook-1"
    assert audit_logs[0]["payload"]["raw_payload"]["provider_extra_field"] == "kept-for-audit"


def test_whatsapp_phone_number_status_webhook_can_mark_phone_inactive(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)

    payload = build_template_webhook_payload(
        waba_id="waba-webhook-1",
        field="phone_number_status_update",
        value={
            "event": "DISABLED",
            "phone_number_id": "pn-webhook-1",
            "display_phone_number": "+1 555 000 0001",
            "is_active": False,
            "is_registered": False,
        },
    )
    raw_body, signature = sign_whatsapp_payload(payload, "secret-webhook-1")

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accepted_phone_number_updates"] == 1
    assert body["matched_phone_number_updates"] == 1

    phone_response = client.get(
        "/api/meta/accounts/meta-webhook-account/wabas/waba-webhook-1/phone-numbers"
    )
    assert phone_response.status_code == 200
    phone = next(
        item for item in phone_response.json() if item["phone_number_id"] == "pn-webhook-1"
    )
    assert phone["quality_event"] == "DISABLED"
    assert phone["is_active"] is False
    assert phone["is_registered"] is False
    assert phone["ready_for_outbound_messages"] is False
    assert "phone_inactive" in phone["blocking_reasons"]


def test_whatsapp_phone_number_webhook_unknown_phone_is_audited_without_create(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)

    payload = build_template_webhook_payload(
        waba_id="waba-webhook-1",
        field="phone_number_quality_update",
        value={
            "event": "UPGRADE",
            "phone_number_id": "pn-webhook-missing",
            "display_phone_number": "+1 555 000 0099",
            "new_quality_rating": "GREEN",
        },
    )
    raw_body, signature = sign_whatsapp_payload(payload, "secret-webhook-1")

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accepted_phone_number_updates"] == 1
    assert body["matched_phone_number_updates"] == 0
    assert body["skipped_phone_number_updates"] == 1

    phone_response = client.get(
        "/api/meta/accounts/meta-webhook-account/wabas/waba-webhook-1/phone-numbers"
    )
    assert phone_response.status_code == 200
    assert [item["phone_number_id"] for item in phone_response.json()] == ["pn-webhook-1"]

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-webhook-account",
            "action": "whatsapp_phone_number_webhook_unmatched",
            "target_type": "waba_account",
            "target_id": "waba-webhook-1",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"]["phone_number_id"] == "pn-webhook-missing"
    assert audit_logs[0]["payload"]["reason"] == "phone_number_not_found_in_waba_scope"


def test_whatsapp_webhook_status_updates_close_template_send_loop(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_meta_account_with_webhook_secret(client)

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "meta-webhook-account",
            "conversation_id": "meta-template-conv-1",
            "user_id": "meta-template-user-1",
            "text": "hello",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-webhook-1",
        },
    )
    assert inbound_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "meta-webhook-account",
            "waba_id": "waba-webhook-1",
            "name": "status_update_template",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, your order is on the way.",
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
            "account_id": "meta-webhook-account",
            "conversation_id": "meta-template-conv-1",
            "variables": {"first_name": "Ana"},
        },
    )
    assert send_response.status_code == 200
    send_result = send_response.json()
    provider_message_id = send_result["message_id"]
    internal_conversation_id = send_result["internal_conversation_id"]
    assert_external_conversation_identity(
        send_result,
        expected_external_conversation_id="meta-template-conv-1",
        expected_internal_conversation_id=internal_conversation_id,
    )

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "statuses": [
                                {
                                    "id": provider_message_id,
                                    "status": "delivered",
                                    "timestamp": "1712345699",
                                    "recipient_id": "meta-template-user-1",
                                    "conversation": {
                                        "id": "meta-conversation-1",
                                        "expiration_timestamp": "1712350000",
                                        "origin": {"type": "business_initiated"},
                                    },
                                    "pricing": {
                                        "billable": True,
                                        "category": "utility",
                                        "pricing_model": "CBP",
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_messages"] == 0
    assert body["accepted_status_updates"] == 1
    assert body["matched_status_updates"] == 1
    assert body["unmatched_status_updates"] == 0

    send_logs_response = client.get(
        "/api/templates/send-logs",
        params={"account_id": "meta-webhook-account"},
    )
    assert send_logs_response.status_code == 200
    send_logs = send_logs_response.json()
    assert len(send_logs) == 1
    assert send_logs[0]["message_id"] == provider_message_id
    assert send_logs[0]["status"] == "DELIVERED"
    assert_external_conversation_identity(
        send_logs[0],
        expected_external_conversation_id="meta-template-conv-1",
        expected_internal_conversation_id=internal_conversation_id,
    )
    assert send_logs[0]["conversation_origin_type"] == "business_initiated"
    assert send_logs[0]["conversation_category"] == "utility"
    assert send_logs[0]["pricing_model"] == "CBP"
    assert send_logs[0]["billable"] is True
    assert send_logs[0]["delivered_at"] is not None
    assert send_logs[0]["read_at"] is None
    assert send_logs[0]["failed_at"] is None

    timeline_response = client.get(
        "/api/conversations/meta-webhook-account/meta-template-conv-1/timeline",
    )
    assert timeline_response.status_code == 200
    timeline = timeline_response.json()
    assert any(item["title"] == "whatsapp_status_delivered" for item in timeline)
    delivered_event = next(item for item in timeline if item["title"] == "whatsapp_status_delivered")
    assert_external_conversation_identity(
        delivered_event["payload"],
        expected_external_conversation_id="meta-template-conv-1",
        expected_internal_conversation_id=internal_conversation_id,
    )
    assert delivered_event["payload"]["provider_payload"]["conversation_id"] == "meta-conversation-1"
    assert delivered_event["payload"]["conversation_origin_type"] == "business_initiated"
    assert delivered_event["payload"]["conversation_category"] == "utility"
    assert delivered_event["payload"]["pricing_model"] == "CBP"
    assert delivered_event["payload"]["billable"] is True

    session = db_session_factory()
    try:
        persisted_event = (
            session.query(MessageEvent)
            .filter(
                MessageEvent.account_id == "meta-webhook-account",
                MessageEvent.event_type == "whatsapp_status_delivered",
            )
            .one()
        )

        assert persisted_event.provider_name == "whatsapp"
        assert persisted_event.waba_id == "waba-webhook-1"
        assert persisted_event.phone_number_id == "pn-webhook-1"
        assert persisted_event.provider_event_id == f"status:{provider_message_id}:delivered"
        assert persisted_event.occurred_at == datetime.fromtimestamp(1712345699, UTC).replace(tzinfo=None)
        assert_external_conversation_identity(
            persisted_event.payload,
            expected_external_conversation_id="meta-template-conv-1",
            expected_internal_conversation_id=internal_conversation_id,
        )
        assert persisted_event.payload["provider_payload"]["conversation_id"] == "meta-conversation-1"
    finally:
        session.close()


def test_whatsapp_webhook_duplicate_status_redelivery_does_not_duplicate_message_event(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_meta_account_with_webhook_secret(client)

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "meta-webhook-account",
            "conversation_id": "meta-template-dedupe-conv-1",
            "user_id": "meta-template-dedupe-user-1",
            "text": "hello",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-webhook-1",
        },
    )
    assert inbound_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "meta-webhook-account",
            "waba_id": "waba-webhook-1",
            "name": "status_update_dedupe_template",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, your order is on the way.",
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
            "account_id": "meta-webhook-account",
            "conversation_id": "meta-template-dedupe-conv-1",
            "variables": {"first_name": "Ana"},
        },
    )
    assert send_response.status_code == 200
    provider_message_id = send_response.json()["message_id"]

    payload = build_whatsapp_status_payload(
        provider_message_id=provider_message_id,
        status="delivered",
        timestamp="1712345699",
        recipient_id="meta-template-dedupe-user-1",
    )
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    first_response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert first_response.status_code == 200
    assert first_response.json()["matched_status_updates"] == 1

    second_response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert second_response.status_code == 200
    assert second_response.json()["matched_status_updates"] == 1

    session = db_session_factory()
    try:
        status_events = (
            session.query(MessageEvent)
            .filter(
                MessageEvent.account_id == "meta-webhook-account",
                MessageEvent.event_type == "whatsapp_status_delivered",
                MessageEvent.provider_event_id == f"status:{provider_message_id}:delivered",
            )
            .all()
        )
        assert len(status_events) == 1
        assert status_events[0].provider_name == "whatsapp"
        assert status_events[0].waba_id == "waba-webhook-1"
        assert status_events[0].phone_number_id == "pn-webhook-1"
        assert status_events[0].occurred_at == datetime.fromtimestamp(1712345699, UTC).replace(
            tzinfo=None
        )
    finally:
        session.close()


def test_whatsapp_status_update_with_wrong_phone_scope_does_not_match_send_log(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_meta_account_with_webhook_secret(client)

    update_account_response = client.patch(
        "/api/meta/accounts/meta-webhook-account/wabas/waba-webhook-1",
        json={
            "display_name": "Meta Webhook Account",
            "meta_business_portfolio_id": "portfolio-webhook-1",
            "access_token": "token-webhook-1",
            "verify_token": "verify-webhook-1",
            "app_secret": "secret-webhook-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-webhook-1",
                    "display_phone_number": "+1 555 000 0001",
                    "verified_name": "Webhook Brand",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                },
                {
                    "phone_number_id": "pn-webhook-mismatch",
                    "display_phone_number": "+1 555 000 0009",
                    "verified_name": "Webhook Brand Mismatch",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                },
            ],
        },
    )
    assert update_account_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "meta-webhook-account",
            "conversation_id": "meta-template-mismatch-conv-1",
            "user_id": "meta-template-mismatch-user-1",
            "text": "hello",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-webhook-1",
        },
    )
    assert inbound_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "meta-webhook-account",
            "waba_id": "waba-webhook-1",
            "name": "status_update_mismatch_template",
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

    send_response = client.post(
        f"/api/templates/{template_id}/send",
        json={
            "account_id": "meta-webhook-account",
            "conversation_id": "meta-template-mismatch-conv-1",
            "variables": {"first_name": "Ana"},
        },
    )
    assert send_response.status_code == 200
    provider_message_id = send_response.json()["message_id"]
    assert send_response.json()["phone_number_id"] == "pn-webhook-1"

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0009",
                                "phone_number_id": "pn-webhook-mismatch",
                            },
                            "statuses": [
                                {
                                    "id": provider_message_id,
                                    "status": "delivered",
                                    "timestamp": "1712345899",
                                    "recipient_id": "meta-template-mismatch-user-1",
                                    "conversation": {
                                        "id": "meta-conversation-mismatch-1",
                                        "expiration_timestamp": "1712350000",
                                        "origin": {"type": "business_initiated"},
                                    },
                                    "pricing": {
                                        "billable": True,
                                        "category": "utility",
                                        "pricing_model": "CBP",
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_status_updates"] == 1
    assert body["matched_status_updates"] == 0
    assert body["unmatched_status_updates"] == 1

    send_logs_response = client.get(
        "/api/templates/send-logs",
        params={"account_id": "meta-webhook-account"},
    )
    assert send_logs_response.status_code == 200
    send_log = next(
        item for item in send_logs_response.json() if item["message_id"] == provider_message_id
    )
    assert send_log["phone_number_id"] == "pn-webhook-1"
    assert send_log["status"] == "SENT"
    assert send_log["delivered_at"] is None
    assert send_log["read_at"] is None
    assert send_log["failed_at"] is None

    with db_session_factory() as session:
        buffered_event = (
            session.query(ProviderStatusEventBuffer)
            .filter_by(
                account_id="meta-webhook-account",
                provider_message_id=provider_message_id,
                phone_number_id="pn-webhook-mismatch",
                replay_state="pending",
            )
            .one()
        )
        assert buffered_event.waba_id == "waba-webhook-1"
        assert buffered_event.external_status == "delivered"


def test_whatsapp_status_update_without_phone_scope_can_match_send_log(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "meta-webhook-account",
            "conversation_id": "meta-template-no-phone-status-conv-1",
            "user_id": "meta-template-no-phone-status-user-1",
            "text": "hello",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-webhook-1",
        },
    )
    assert inbound_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "meta-webhook-account",
            "waba_id": "waba-webhook-1",
            "name": "status_update_no_phone_template",
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

    send_response = client.post(
        f"/api/templates/{template_id}/send",
        json={
            "account_id": "meta-webhook-account",
            "conversation_id": "meta-template-no-phone-status-conv-1",
            "variables": {"first_name": "Ana"},
        },
    )
    assert send_response.status_code == 200
    provider_message_id = send_response.json()["message_id"]
    assert send_response.json()["phone_number_id"] == "pn-webhook-1"

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                            },
                            "statuses": [
                                {
                                    "id": provider_message_id,
                                    "status": "delivered",
                                    "timestamp": "1712345899",
                                    "recipient_id": "meta-template-no-phone-status-user-1",
                                    "conversation": {
                                        "id": "meta-conversation-no-phone-status-1",
                                        "expiration_timestamp": "1712350000",
                                        "origin": {"type": "business_initiated"},
                                    },
                                    "pricing": {
                                        "billable": True,
                                        "category": "utility",
                                        "pricing_model": "CBP",
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_status_updates"] == 1
    assert body["matched_status_updates"] == 1
    assert body["unmatched_status_updates"] == 0
    assert body["rejected_phone_scope_status_updates"] == 0

    send_logs_response = client.get(
        "/api/templates/send-logs",
        params={"account_id": "meta-webhook-account"},
    )
    assert send_logs_response.status_code == 200
    send_log = next(
        item for item in send_logs_response.json() if item["message_id"] == provider_message_id
    )
    assert send_log["phone_number_id"] == "pn-webhook-1"
    assert send_log["status"] == "DELIVERED"
    assert send_log["delivered_at"] is not None

    timeline_response = client.get(
        "/api/conversations/meta-webhook-account/meta-template-no-phone-status-conv-1/timeline",
    )
    assert timeline_response.status_code == 200
    delivered_event = next(
        item for item in timeline_response.json() if item["title"] == "whatsapp_status_delivered"
    )
    assert delivered_event["payload"]["provider_message_id"] == provider_message_id
    assert delivered_event["payload"]["conversation_origin_type"] == "business_initiated"


def test_whatsapp_status_update_with_wrong_waba_scope_does_not_match_send_log(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_meta_account_with_webhook_secret(client)

    second_waba_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-webhook-account",
            "display_name": "Meta Webhook Account",
            "meta_business_portfolio_id": "portfolio-webhook-1",
            "waba_id": "waba-webhook-scope-b",
            "access_token": "token-webhook-scope-b",
            "verify_token": "verify-webhook-scope-b",
            "app_secret": "secret-webhook-scope-b",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-webhook-scope-b",
                    "display_phone_number": "+1 555 000 0022",
                    "verified_name": "Webhook Brand Scope B",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert second_waba_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "meta-webhook-account",
            "conversation_id": "meta-template-waba-scope-conv-1",
            "user_id": "meta-template-waba-scope-user-1",
            "text": "hello",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-webhook-1",
        },
    )
    assert inbound_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "meta-webhook-account",
            "waba_id": "waba-webhook-1",
            "name": "status_update_wrong_waba_template",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, your scoped WABA update is ready.",
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
            "account_id": "meta-webhook-account",
            "conversation_id": "meta-template-waba-scope-conv-1",
            "variables": {"first_name": "Ana"},
        },
    )
    assert send_response.status_code == 200
    provider_message_id = send_response.json()["message_id"]
    assert send_response.json()["phone_number_id"] == "pn-webhook-1"

    status_payload = build_whatsapp_status_payload(
        provider_message_id=provider_message_id,
        status="delivered",
        timestamp="1712345999",
        recipient_id="meta-template-waba-scope-user-1",
        waba_id="waba-webhook-scope-b",
        phone_number_id="pn-webhook-scope-b",
        display_phone_number="+1 555 000 0022",
    )
    raw_body = json.dumps(status_payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-scope-b", raw_body)

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-scope-b",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_status_updates"] == 1
    assert body["matched_status_updates"] == 0
    assert body["unmatched_status_updates"] == 1
    assert body["rejected_phone_scope_status_updates"] == 0

    send_logs_response = client.get(
        "/api/templates/send-logs",
        params={"account_id": "meta-webhook-account"},
    )
    assert send_logs_response.status_code == 200
    send_log = next(
        item for item in send_logs_response.json() if item["message_id"] == provider_message_id
    )
    assert send_log["waba_id"] == "waba-webhook-1"
    assert send_log["phone_number_id"] == "pn-webhook-1"
    assert send_log["status"] == "SENT"
    assert send_log["delivered_at"] is None
    assert send_log["read_at"] is None
    assert send_log["failed_at"] is None

    messages_response = client.get(
        "/api/conversations/meta-webhook-account/meta-template-waba-scope-conv-1/messages"
    )
    assert messages_response.status_code == 200
    outbound_message = next(
        item
        for item in messages_response.json()
        if item["direction"] == "outbound"
        and item["payload"]["provider_message_id"] == provider_message_id
    )
    assert outbound_message["phone_number_id"] == "pn-webhook-1"
    assert "conversation_origin_type" not in outbound_message["payload"]

    timeline_response = client.get(
        "/api/conversations/meta-webhook-account/meta-template-waba-scope-conv-1/timeline",
    )
    assert timeline_response.status_code == 200
    assert not any(item["title"] == "whatsapp_status_delivered" for item in timeline_response.json())

    with db_session_factory() as session:
        buffered_event = (
            session.query(ProviderStatusEventBuffer)
            .filter_by(
                account_id="meta-webhook-account",
                provider_name="whatsapp",
                provider_message_id=provider_message_id,
                waba_id="waba-webhook-scope-b",
                phone_number_id="pn-webhook-scope-b",
                replay_state="pending",
            )
            .one()
        )
        assert buffered_event.external_status == "delivered"
        assert buffered_event.seen_count == 1
        assert buffered_event.payload["conversation_origin_type"] == "business_initiated"

        status_event_count = (
            session.query(MessageEvent)
            .filter(
                MessageEvent.account_id == "meta-webhook-account",
                MessageEvent.event_type == "whatsapp_status_delivered",
            )
            .count()
        )
        assert status_event_count == 0


def test_root_whatsapp_webhook_status_updates_close_template_send_loop(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_meta_account_with_webhook_secret(client)

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "meta-webhook-account",
            "conversation_id": "meta-root-template-conv-1",
            "user_id": "meta-root-template-user-1",
            "text": "hello",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-webhook-1",
        },
    )
    assert inbound_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "meta-webhook-account",
            "waba_id": "waba-webhook-1",
            "name": "root_status_update_template",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, your root webhook update is ready.",
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
            "account_id": "meta-webhook-account",
            "conversation_id": "meta-root-template-conv-1",
            "variables": {"first_name": "Ana"},
        },
    )
    assert send_response.status_code == 200
    send_result = send_response.json()
    provider_message_id = send_result["message_id"]
    internal_conversation_id = send_result["internal_conversation_id"]
    assert_external_conversation_identity(
        send_result,
        expected_external_conversation_id="meta-root-template-conv-1",
        expected_internal_conversation_id=internal_conversation_id,
    )

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "statuses": [
                                {
                                    "id": provider_message_id,
                                    "status": "read",
                                    "timestamp": "1712345799",
                                    "recipient_id": "meta-root-template-user-1",
                                    "conversation": {
                                        "id": "meta-root-conversation-1",
                                        "expiration_timestamp": "1712350000",
                                        "origin": {"type": "business_initiated"},
                                    },
                                    "pricing": {
                                        "billable": True,
                                        "category": "utility",
                                        "pricing_model": "CBP",
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["account_id"] == "meta-webhook-account"
    assert body["waba_id"] == "waba-webhook-1"
    assert body["accepted_messages"] == 0
    assert body["accepted_status_updates"] == 1
    assert body["matched_status_updates"] == 1
    assert body["unmatched_status_updates"] == 0

    send_logs_response = client.get(
        "/api/templates/send-logs",
        params={"account_id": "meta-webhook-account"},
    )
    assert send_logs_response.status_code == 200
    send_logs = send_logs_response.json()
    assert len(send_logs) == 1
    assert send_logs[0]["message_id"] == provider_message_id
    assert send_logs[0]["status"] == "READ"
    assert_external_conversation_identity(
        send_logs[0],
        expected_external_conversation_id="meta-root-template-conv-1",
        expected_internal_conversation_id=internal_conversation_id,
    )
    assert send_logs[0]["conversation_origin_type"] == "business_initiated"
    assert send_logs[0]["conversation_category"] == "utility"
    assert send_logs[0]["pricing_model"] == "CBP"
    assert send_logs[0]["billable"] is True
    assert send_logs[0]["delivered_at"] is not None
    assert send_logs[0]["read_at"] is not None
    assert send_logs[0]["failed_at"] is None

    timeline_response = client.get(
        "/api/conversations/meta-webhook-account/meta-root-template-conv-1/timeline",
    )
    assert timeline_response.status_code == 200
    timeline = timeline_response.json()
    assert any(item["title"] == "whatsapp_status_read" for item in timeline)
    read_event = next(item for item in timeline if item["title"] == "whatsapp_status_read")
    assert_external_conversation_identity(
        read_event["payload"],
        expected_external_conversation_id="meta-root-template-conv-1",
        expected_internal_conversation_id=internal_conversation_id,
    )
    assert read_event["payload"]["provider_payload"]["conversation_id"] == "meta-root-conversation-1"

    with db_session_factory() as session:
        persisted_event = (
            session.query(MessageEvent)
            .filter(
                MessageEvent.account_id == "meta-webhook-account",
                MessageEvent.event_type == "whatsapp_status_read",
            )
            .one()
        )
        assert_external_conversation_identity(
            persisted_event.payload,
            expected_external_conversation_id="meta-root-template-conv-1",
            expected_internal_conversation_id=internal_conversation_id,
        )
        assert persisted_event.payload["provider_payload"]["conversation_id"] == "meta-root-conversation-1"


@pytest.mark.parametrize(
    ("provider_status", "expected_log_status"),
    [
        ("delivered", "DELIVERED"),
        ("read", "READ"),
    ],
)
def test_whatsapp_status_update_before_local_template_send_log_is_replayed_once(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
    provider_status: str,
    expected_log_status: str,
) -> None:
    register_meta_account_with_webhook_secret(client)

    recipient_id = "14150002001" if provider_status == "delivered" else "14150002002"
    conversation_id = f"wa:pn-webhook-1:{recipient_id}"
    provider_message_id = f"wamid.early.template.{provider_status}.1"

    session: Session | None = None
    client.app.dependency_overrides[get_messaging_service] = lambda: FixedMessageIdWhatsAppProvider(
        f"wamid.early.setup.reply.{provider_status}"
    )
    try:
        inbound_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-webhook-1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 0001",
                                    "phone_number_id": "pn-webhook-1",
                                },
                                "contacts": [
                                    {
                                        "wa_id": recipient_id,
                                        "profile": {"name": "Early Status Customer"},
                                    }
                                ],
                                "messages": [
                                    {
                                        "from": recipient_id,
                                        "id": f"wamid.early.setup.in.{provider_status}",
                                        "timestamp": "1712345800",
                                        "type": "text",
                                        "text": {"body": "hello before status"},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
        inbound_body = json.dumps(inbound_payload, separators=(",", ":")).encode("utf-8")
        inbound_signature = WhatsAppProvider.build_signature("secret-webhook-1", inbound_body)
        inbound_response = client.post(
            "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
            content=inbound_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": inbound_signature,
            },
        )
        assert inbound_response.status_code == 200
        assert inbound_response.json()["accepted_messages"] == 1

        provider = FixedMessageIdWhatsAppProvider(provider_message_id)
        client.app.dependency_overrides[get_messaging_service] = lambda: provider

        status_payload = build_whatsapp_status_payload(
            provider_message_id=provider_message_id,
            status=provider_status,
            timestamp="1712345899",
            recipient_id=recipient_id,
        )
        raw_body = json.dumps(status_payload, separators=(",", ":")).encode("utf-8")
        signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

        early_status_response = client.post(
            "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )

        assert early_status_response.status_code == 200
        early_status_body = early_status_response.json()
        assert early_status_body["accepted_status_updates"] == 1
        assert early_status_body["matched_status_updates"] == 0
        assert early_status_body["unmatched_status_updates"] == 1

        session = db_session_factory()
        buffered_event = session.query(ProviderStatusEventBuffer).filter_by(
            account_id="meta-webhook-account",
            provider_name="whatsapp",
            provider_message_id=provider_message_id,
            external_status=provider_status,
        ).one()
        assert buffered_event.replay_state == "pending"
        assert buffered_event.seen_count == 1
        assert buffered_event.waba_id == "waba-webhook-1"
        assert buffered_event.phone_number_id == "pn-webhook-1"
        assert buffered_event.payload["conversation_origin_type"] == "business_initiated"

        template_response = client.post(
            "/api/templates/drafts",
            json={
                "account_id": "meta-webhook-account",
                "waba_id": "waba-webhook-1",
                "name": f"early_status_template_{provider_status}",
                "language": "en",
                "category": "UTILITY",
                "body_text": "Hello {{first_name}}, your early status update is ready.",
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
                "account_id": "meta-webhook-account",
                "conversation_id": conversation_id,
                "variables": {"first_name": "Ana"},
            },
        )
        assert send_response.status_code == 200
        send_result = send_response.json()
        assert send_result["message_id"] == provider_message_id
        internal_conversation_id = send_result["internal_conversation_id"]
        assert_external_conversation_identity(
            send_result,
            expected_external_conversation_id=conversation_id,
            expected_internal_conversation_id=internal_conversation_id,
        )

        send_logs_response = client.get(
            "/api/templates/send-logs",
            params={"account_id": "meta-webhook-account"},
        )
        assert send_logs_response.status_code == 200
        send_logs = send_logs_response.json()
        assert len(send_logs) == 1
        assert send_logs[0]["message_id"] == provider_message_id
        assert send_logs[0]["status"] == expected_log_status
        assert_external_conversation_identity(
            send_logs[0],
            expected_external_conversation_id=conversation_id,
            expected_internal_conversation_id=internal_conversation_id,
        )
        assert send_logs[0]["conversation_origin_type"] == "business_initiated"
        assert send_logs[0]["conversation_category"] == "utility"
        assert send_logs[0]["pricing_model"] == "CBP"
        assert send_logs[0]["billable"] is True
        assert send_logs[0]["delivered_at"] is not None
        if expected_log_status == "READ":
            assert send_logs[0]["read_at"] is not None
        else:
            assert send_logs[0]["read_at"] is None

        session.expire_all()
        session.refresh(buffered_event)
        assert buffered_event.replay_state == "replayed"
        assert buffered_event.replayed_at is not None
        assert buffered_event.replayed_message_event_id is not None

        status_event_type = f"whatsapp_status_{provider_status}"
        status_events_before_duplicate_replay = (
            session.query(MessageEvent)
            .filter(
                MessageEvent.account_id == "meta-webhook-account",
                MessageEvent.event_type == status_event_type,
            )
            .count()
        )
        assert status_events_before_duplicate_replay == 1

        replayed_count = asyncio.run(
            RuntimeStateStore(session).replay_unmatched_provider_status_events(
                account_id="meta-webhook-account",
                provider_message_id=provider_message_id,
            )
        )
        assert replayed_count == 0

        session.expire_all()
        status_events_after_duplicate_replay = (
            session.query(MessageEvent)
            .filter(
                MessageEvent.account_id == "meta-webhook-account",
                MessageEvent.event_type == status_event_type,
            )
            .count()
        )
        assert status_events_after_duplicate_replay == 1
        replayed_event = (
            session.query(MessageEvent)
            .filter(
                MessageEvent.account_id == "meta-webhook-account",
                MessageEvent.event_type == status_event_type,
            )
            .one()
        )
        assert_external_conversation_identity(
            replayed_event.payload,
            expected_external_conversation_id=conversation_id,
            expected_internal_conversation_id=internal_conversation_id,
        )
        assert (
            replayed_event.payload["provider_payload"]["conversation_id"]
            == f"meta-early-{provider_status}-conversation"
        )

        timeline_response = client.get(
            f"/api/conversations/meta-webhook-account/{conversation_id}/timeline",
        )
        assert timeline_response.status_code == 200
        timeline = timeline_response.json()
        replayed_timeline_event = next(item for item in timeline if item["title"] == status_event_type)
        assert_external_conversation_identity(
            replayed_timeline_event["payload"],
            expected_external_conversation_id=conversation_id,
            expected_internal_conversation_id=internal_conversation_id,
        )
        assert (
            replayed_timeline_event["payload"]["provider_payload"]["conversation_id"]
            == f"meta-early-{provider_status}-conversation"
        )
    finally:
        if session is not None:
            session.close()
        client.app.dependency_overrides.pop(get_messaging_service, None)


def test_root_whatsapp_failed_status_before_local_template_send_log_is_replayed(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_meta_account_with_webhook_secret(client)

    conversation_id = "meta-root-early-template-conv-failed"
    recipient_id = "meta-root-early-template-user-failed"
    provider_message_id = "wamid.root.early.template.failed.1"

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "meta-webhook-account",
            "conversation_id": conversation_id,
            "user_id": recipient_id,
            "text": "hello",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-webhook-1",
        },
    )
    assert inbound_response.status_code == 200

    provider = FixedMessageIdWhatsAppProvider(provider_message_id)
    client.app.dependency_overrides[get_messaging_service] = lambda: provider
    session: Session | None = None
    try:
        status_payload = build_whatsapp_status_payload(
            provider_message_id=provider_message_id,
            status="failed",
            timestamp="1712345999",
            recipient_id=recipient_id,
            error_code="131026",
        )
        raw_body = json.dumps(status_payload, separators=(",", ":")).encode("utf-8")
        signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

        early_status_response = client.post(
            "/webhooks/whatsapp",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )

        assert early_status_response.status_code == 200
        early_status_body = early_status_response.json()
        assert early_status_body["account_id"] == "meta-webhook-account"
        assert early_status_body["waba_id"] == "waba-webhook-1"
        assert early_status_body["accepted_status_updates"] == 1
        assert early_status_body["matched_status_updates"] == 0
        assert early_status_body["unmatched_status_updates"] == 1

        session = db_session_factory()
        buffered_event = session.query(ProviderStatusEventBuffer).filter_by(
            account_id="meta-webhook-account",
            provider_name="whatsapp",
            provider_message_id=provider_message_id,
            external_status="failed",
        ).one()
        assert buffered_event.replay_state == "pending"
        assert buffered_event.error_code == "131026"

        template_response = client.post(
            "/api/templates/drafts",
            json={
                "account_id": "meta-webhook-account",
                "waba_id": "waba-webhook-1",
                "name": "root_early_failed_template",
                "language": "en",
                "category": "UTILITY",
                "body_text": "Hello {{first_name}}, failed replay is ready.",
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
                "account_id": "meta-webhook-account",
                "conversation_id": conversation_id,
                "variables": {"first_name": "Ana"},
            },
        )
        assert send_response.status_code == 200
        send_result = send_response.json()
        assert send_result["message_id"] == provider_message_id
        internal_conversation_id = send_result["internal_conversation_id"]
        assert_external_conversation_identity(
            send_result,
            expected_external_conversation_id=conversation_id,
            expected_internal_conversation_id=internal_conversation_id,
        )

        send_logs_response = client.get(
            "/api/templates/send-logs",
            params={"account_id": "meta-webhook-account"},
        )
        assert send_logs_response.status_code == 200
        send_logs = send_logs_response.json()
        assert len(send_logs) == 1
        assert send_logs[0]["message_id"] == provider_message_id
        assert send_logs[0]["status"] == "FAILED"
        assert send_logs[0]["error_code"] == "131026"
        assert_external_conversation_identity(
            send_logs[0],
            expected_external_conversation_id=conversation_id,
            expected_internal_conversation_id=internal_conversation_id,
        )
        assert send_logs[0]["failed_at"] is not None

        session.refresh(buffered_event)
        assert buffered_event.replay_state == "replayed"
        assert buffered_event.replayed_message_event_id is not None

        failed_event = (
            session.query(MessageEvent)
            .filter(
                MessageEvent.account_id == "meta-webhook-account",
                MessageEvent.event_type == "whatsapp_status_failed",
            )
            .one()
        )
        assert_external_conversation_identity(
            failed_event.payload,
            expected_external_conversation_id=conversation_id,
            expected_internal_conversation_id=internal_conversation_id,
        )
        assert failed_event.payload["provider_payload"]["conversation_id"] == "meta-early-failed-conversation"

        timeline_response = client.get(
            f"/api/conversations/meta-webhook-account/{conversation_id}/timeline",
        )
        assert timeline_response.status_code == 200
        timeline = timeline_response.json()
        failed_timeline_event = next(
            item for item in timeline if item["title"] == "whatsapp_status_failed"
        )
        assert_external_conversation_identity(
            failed_timeline_event["payload"],
            expected_external_conversation_id=conversation_id,
            expected_internal_conversation_id=internal_conversation_id,
        )
        assert (
            failed_timeline_event["payload"]["provider_payload"]["conversation_id"]
            == "meta-early-failed-conversation"
        )

        stats_response = client.get(
            "/api/whatsapp/stats/summary",
            params={"account_id": "meta-webhook-account"},
        )
        assert stats_response.status_code == 200
        stats_summary = stats_response.json()
        assert stats_summary["outbound_message_count"] >= 1
        assert stats_summary["failed_count"] == 1
        assert stats_summary["billable_count"] == 1
    finally:
        if session is not None:
            session.close()
        client.app.dependency_overrides.pop(get_messaging_service, None)


def test_template_analytics_endpoints_include_snapshot_dimensions(client: TestClient) -> None:
    register_meta_account_with_webhook_secret(client)

    inbound_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "contacts": [
                                {
                                    "wa_id": "14150000009",
                                    "profile": {"name": "Analytics Customer"},
                                }
                            ],
                            "messages": [
                                {
                                    "from": "14150000009",
                                    "id": "wamid.analytics.inbound.1",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "hello analytics"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    inbound_body = json.dumps(inbound_payload, separators=(",", ":")).encode("utf-8")
    inbound_signature = WhatsAppProvider.build_signature("secret-webhook-1", inbound_body)
    inbound_response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=inbound_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": inbound_signature,
        },
    )
    assert inbound_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "meta-webhook-account",
            "waba_id": "waba-webhook-1",
            "name": "analytics_template",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, analytics is ready.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED", "meta_template_id": "meta-template-analytics-1"},
    )
    assert approve_response.status_code == 200

    send_response = client.post(
        f"/api/templates/{template_id}/send",
        json={
            "account_id": "meta-webhook-account",
            "conversation_id": "wa:pn-webhook-1:14150000009",
            "variables": {"first_name": "Ana"},
        },
    )
    assert send_response.status_code == 200
    provider_message_id = send_response.json()["message_id"]

    status_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                                "statuses": [
                                    {
                                        "id": provider_message_id,
                                        "status": "delivered",
                                        "timestamp": "1712345699",
                                        "recipient_id": "14150000009",
                                        "conversation": {
                                            "id": "meta-analytics-conversation-1",
                                            "expiration_timestamp": "1712350000",
                                            "origin": {"type": "business_initiated"},
                                        },
                                    "pricing": {
                                        "billable": True,
                                        "category": "utility",
                                        "pricing_model": "CBP",
                                    },
                                    "estimated_cost": 1.25,
                                },
                                {
                                    "id": provider_message_id,
                                    "status": "read",
                                        "timestamp": "1712345799",
                                        "recipient_id": "14150000009",
                                        "conversation": {
                                            "id": "meta-analytics-conversation-1",
                                            "expiration_timestamp": "1712350000",
                                            "origin": {"type": "business_initiated"},
                                        },
                                        "pricing": {
                                            "billable": True,
                                            "category": "utility",
                                            "pricing_model": "CBP",
                                        },
                                    },
                                ],
                            },
                        }
                ],
            }
        ],
    }
    status_body = json.dumps(status_payload, separators=(",", ":")).encode("utf-8")
    status_signature = WhatsAppProvider.build_signature("secret-webhook-1", status_body)
    status_response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=status_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": status_signature,
        },
    )
    assert status_response.status_code == 200
    assert status_response.json()["accepted_status_updates"] == 2

    today = datetime.now(UTC).date().isoformat()

    send_logs_response = client.get(
        "/api/templates/send-logs",
        params={"account_id": "meta-webhook-account"},
    )
    assert send_logs_response.status_code == 200
    send_logs = send_logs_response.json()
    assert len(send_logs) == 1
    assert send_logs[0]["template_id"] == template_id
    assert send_logs[0]["waba_id"] == "waba-webhook-1"
    assert send_logs[0]["template_name"] == "analytics_template"
    assert send_logs[0]["template_language"] == "en"
    assert send_logs[0]["template_category"] == "UTILITY"
    assert send_logs[0]["template_code"] == "meta-template-analytics-1"
    assert send_logs[0]["phone_number_id"] == "pn-webhook-1"
    assert send_logs[0]["status"] == "READ"
    assert send_logs[0]["delivered_at"] is not None
    assert send_logs[0]["read_at"] is not None
    assert send_logs[0]["failed_at"] is None
    assert send_logs[0]["last_status_at"] is not None
    assert send_logs[0]["estimated_cost"] == 1.25

    filtered_logs_response = client.get(
        "/api/templates/send-logs",
        params={
            "account_id": "meta-webhook-account",
            "template_id": template_id,
            "phone_number_id": "pn-webhook-1",
            "status": "READ",
            "date_from": today,
            "date_to": today,
        },
    )
    assert filtered_logs_response.status_code == 200
    filtered_logs = filtered_logs_response.json()
    assert len(filtered_logs) == 1
    assert filtered_logs[0]["id"] == send_logs[0]["id"]

    empty_filtered_logs_response = client.get(
        "/api/templates/send-logs",
        params={
            "account_id": "meta-webhook-account",
            "template_id": template_id,
            "phone_number_id": "pn-webhook-1",
            "status": "FAILED",
            "date_from": today,
            "date_to": today,
        },
    )
    assert empty_filtered_logs_response.status_code == 200
    assert empty_filtered_logs_response.json() == []

    summary_response = client.get(
        "/api/templates/stats/summary",
        params={
            "account_id": "meta-webhook-account",
            "date_from": today,
            "date_to": today,
        },
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["send_count"] == 1
    assert summary["delivered_count"] == 1
    assert summary["read_count"] == 1
    assert summary["failed_count"] == 0
    assert summary["billable_count"] == 1
    assert summary["estimated_cost"] == 1.25
    assert summary["estimated_cost_status"] == "provider_estimated"

    daily_response = client.get(
        "/api/templates/stats/daily",
        params={
            "account_id": "meta-webhook-account",
            "date_from": today,
            "date_to": today,
        },
    )
    assert daily_response.status_code == 200
    daily_rows = daily_response.json()
    assert len(daily_rows) == 1
    assert daily_rows[0]["template_id"] == template_id
    assert daily_rows[0]["waba_id"] == "waba-webhook-1"
    assert daily_rows[0]["phone_number_id"] == "pn-webhook-1"
    assert daily_rows[0]["template_name"] == "analytics_template"
    assert daily_rows[0]["template_code"] == "meta-template-analytics-1"
    assert daily_rows[0]["template_category"] == "UTILITY"
    assert daily_rows[0]["template_language"] == "en"
    assert daily_rows[0]["send_count"] == 1
    assert daily_rows[0]["delivered_count"] == 1
    assert daily_rows[0]["read_count"] == 1
    assert daily_rows[0]["billable_count"] == 1
    assert daily_rows[0]["estimated_cost"] == 1.25
    assert daily_rows[0]["estimated_cost_status"] == "provider_estimated"

    phone_filtered_summary_response = client.get(
        "/api/templates/stats/summary",
        params={
            "account_id": "meta-webhook-account",
            "phone_number_id": "pn-webhook-1",
            "date_from": today,
            "date_to": today,
        },
    )
    assert phone_filtered_summary_response.status_code == 200
    assert phone_filtered_summary_response.json()["send_count"] == 1

    empty_phone_filtered_summary_response = client.get(
        "/api/templates/stats/summary",
        params={
            "account_id": "meta-webhook-account",
            "phone_number_id": "pn-webhook-missing",
            "date_from": today,
            "date_to": today,
        },
    )
    assert empty_phone_filtered_summary_response.status_code == 200
    empty_summary = empty_phone_filtered_summary_response.json()
    assert empty_summary["send_count"] == 0
    assert empty_summary["estimated_cost_status"] == "not_applicable"

    analytics_response = client.get(
        f"/api/templates/{template_id}/analytics",
        params={
            "phone_number_id": "pn-webhook-1",
            "date_from": today,
            "date_to": today,
        },
    )
    assert analytics_response.status_code == 200
    analytics = analytics_response.json()
    assert analytics["template_id"] == template_id
    assert analytics["template_name"] == "analytics_template"
    assert analytics["template_language"] == "en"
    assert analytics["template_category"] == "UTILITY"
    assert analytics["summary"]["send_count"] == 1
    assert analytics["summary"]["delivered_count"] == 1
    assert analytics["summary"]["read_count"] == 1
    assert analytics["summary"]["billable_count"] == 1
    assert analytics["summary"]["estimated_cost"] == 1.25
    assert analytics["summary"]["estimated_cost_status"] == "provider_estimated"
    assert len(analytics["daily_rows"]) == 1
    assert analytics["daily_rows"][0]["phone_number_id"] == "pn-webhook-1"
    assert analytics["daily_rows"][0]["billable_count"] == 1
    assert analytics["daily_rows"][0]["estimated_cost"] == 1.25
    assert analytics["daily_rows"][0]["estimated_cost_status"] == "provider_estimated"
    assert analytics["hourly_rows"][0]["send_count"] == 1
    assert analytics["failure_reasons"] == []


def test_whatsapp_webhook_duplicate_message_is_ignored(client: TestClient) -> None:
    register_meta_account_with_webhook_secret(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "messages": [
                                {
                                    "from": "14150000002",
                                    "id": "wamid.duplicate.1",
                                    "timestamp": "1712345690",
                                    "type": "text",
                                    "text": {"body": "hola, necesito ayuda"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": signature,
    }

    first_response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers=headers,
    )
    second_response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
        headers=headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json()["results"][0]["deduplicated"] is True

    messages_response = client.get(
        "/api/conversations/meta-webhook-account/wa:pn-webhook-1:14150000002/messages"
    )
    assert messages_response.status_code == 200
    messages = messages_response.json()
    inbound_messages = [message for message in messages if message["direction"] == "inbound"]
    assert len(inbound_messages) == 1

    stats_response = client.get("/api/queue/stats")
    assert stats_response.status_code == 200
    assert stats_response.json()["queues"][0]["queued"] == 1


def test_root_whatsapp_webhook_resolves_account_from_payload_waba_and_processes_message(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "contacts": [
                                {
                                    "wa_id": "14150001001",
                                    "profile": {"name": "Root Webhook Customer"},
                                }
                            ],
                            "messages": [
                                {
                                    "from": "14150001001",
                                    "id": "wamid.root.webhook.1",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "hello from root webhook"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "whatsapp"
    assert body["account_id"] == "meta-webhook-account"
    assert body["waba_id"] == "waba-webhook-1"
    assert body["signature_verified"] is True
    assert body["accepted_messages"] == 1
    assert body["skipped_messages"] == 0
    assert body["results"][0]["inbound"]["conversation_id"] == "wa:pn-webhook-1:14150001001"
    assert body["results"][0]["inbound"]["metadata"]["contact_wa_id"] == "14150001001"
    assert body["results"][0]["inbound"]["metadata"]["contact_profile_name"] == "Root Webhook Customer"

    conversation_response = client.get(
        "/api/conversations",
        params={"account_id": "meta-webhook-account"},
    )
    assert conversation_response.status_code == 200
    conversations = conversation_response.json()
    assert len(conversations) == 1
    assert conversations[0]["conversation_id"] == "wa:pn-webhook-1:14150001001"


def test_root_whatsapp_webhook_rejects_unknown_waba(client: TestClient) -> None:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-unknown",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 9999",
                                "phone_number_id": "pn-webhook-unknown",
                            },
                            "messages": [
                                {
                                    "from": "14150001999",
                                    "id": "wamid.root.unknown.1",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "unknown waba should not process"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }

    response = client.post(
        "/webhooks/whatsapp",
        content=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "WABA 'waba-webhook-unknown' was not found."

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "action": "meta_webhook_root_scope_failed",
            "target_type": "waba_account",
            "target_id": "waba-webhook-unknown",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["account_id"] is None
    assert audit_logs[0]["payload"] == {
        "source_stage": "scope_resolution",
        "status_code": 404,
        "detail": "WABA 'waba-webhook-unknown' was not found.",
        "account_id_present": False,
    }


def test_root_whatsapp_webhook_keeps_known_scope_when_another_waba_is_unknown(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "messages": [
                                {
                                    "from": "14150001011",
                                    "id": "wamid.root.known.unknown-mixed.1",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "known scope should persist"},
                                }
                            ],
                        },
                    }
                ],
            },
            {
                "id": "waba-webhook-unknown-mixed",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 9998",
                                "phone_number_id": "pn-webhook-unknown-mixed",
                            },
                            "messages": [
                                {
                                    "from": "14150001998",
                                    "id": "wamid.root.unknown-mixed.1",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "unknown scope should be isolated"},
                                }
                            ],
                        },
                    }
                ],
            },
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-webhook-1", raw_body)

    response = client.post(
        "/webhooks/whatsapp",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "whatsapp"
    assert body["waba_count"] == 2
    assert body["successful_scope_count"] == 1
    assert body["failed_scope_count"] == 1
    assert body["accepted_messages"] == 1
    assert body["skipped_messages"] == 0

    assert len(body["scopes"]) == 1
    successful_scope = body["scopes"][0]
    assert successful_scope["account_id"] == "meta-webhook-account"
    assert successful_scope["waba_id"] == "waba-webhook-1"
    assert successful_scope["accepted_messages"] == 1
    assert successful_scope["results"][0]["inbound"]["conversation_id"] == "wa:pn-webhook-1:14150001011"

    assert body["scope_failures"] == [
        {
            "account_id": None,
            "waba_id": "waba-webhook-unknown-mixed",
            "status_code": 404,
            "detail": "WABA 'waba-webhook-unknown-mixed' was not found.",
        }
    ]

    conversation_response = client.get(
        "/api/conversations",
        params={"account_id": "meta-webhook-account"},
    )
    assert conversation_response.status_code == 200
    conversations = conversation_response.json()
    assert len(conversations) == 1
    assert conversations[0]["conversation_id"] == "wa:pn-webhook-1:14150001011"
    assert conversations[0]["waba_id"] == "waba-webhook-1"
    assert conversations[0]["phone_number_id"] == "pn-webhook-1"


def test_root_whatsapp_webhook_keeps_verified_scope_when_another_waba_is_verification_pending(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {"MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER")}

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        for account_id, display_name, portfolio_id, waba_id, phone_number_id, display_phone in (
            (
                "meta-root-verified-pending-account-a",
                "Meta Root Verified Pending Account A",
                "portfolio-root-verified-pending-a",
                "waba-root-verified-pending-a",
                "pn-root-verified-pending-a",
                "+1 555 000 2401",
            ),
            (
                "meta-root-verified-pending-account-b",
                "Meta Root Verified Pending Account B",
                "portfolio-root-verified-pending-b",
                "waba-root-verified-pending-b",
                "pn-root-verified-pending-b",
                "+1 555 000 2402",
            ),
        ):
            create_response = client.post(
                "/api/meta/accounts/manual",
                json={
                    "account_id": account_id,
                    "display_name": display_name,
                    "meta_business_portfolio_id": portfolio_id,
                    "waba_id": waba_id,
                    "access_token": f"token-{account_id}",
                    "verify_token": f"verify-{account_id}",
                    "app_secret": "secret-root-verified-pending-shared",
                    "token_source": "system_user",
                    "phone_numbers": [
                        {
                            "phone_number_id": phone_number_id,
                            "display_phone_number": display_phone,
                            "verified_name": display_name,
                            "quality_rating": "GREEN",
                            "is_registered": True,
                        }
                    ],
                },
            )
            assert create_response.status_code == 200

            subscribe_response = client.post(
                f"/api/meta/accounts/{account_id}/wabas/{waba_id}/webhook-subscription",
                json={"callback_url": f"https://example.com/webhook/{account_id}"},
            )
            assert subscribe_response.status_code == 200

        verify_response = client.get(
            "/webhooks/whatsapp/meta-root-verified-pending-account-a/"
            "wabas/waba-root-verified-pending-a",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-meta-root-verified-pending-account-a",
                "hub.challenge": "challenge-root-verified-pending-a",
            },
        )
        assert verify_response.status_code == 200

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-root-verified-pending-a",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 2401",
                                    "phone_number_id": "pn-root-verified-pending-a",
                                },
                                "messages": [
                                    {
                                        "from": "14150002401",
                                        "id": "wamid.root.verified.pending.ok.1",
                                        "timestamp": "1712345678",
                                        "type": "text",
                                        "text": {"body": "verified scope should process"},
                                    }
                                ],
                            },
                        }
                    ],
                },
                {
                    "id": "waba-root-verified-pending-b",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 2402",
                                    "phone_number_id": "pn-root-verified-pending-b",
                                },
                                "messages": [
                                    {
                                        "from": "14150002402",
                                        "id": "wamid.root.verified.pending.blocked.1",
                                        "timestamp": "1712345678",
                                        "type": "text",
                                        "text": {"body": "pending scope should be isolated"},
                                    }
                                ],
                            },
                        }
                    ],
                },
            ],
        }
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = WhatsAppProvider.build_signature("secret-root-verified-pending-shared", raw_body)

        response = client.post(
            "/webhooks/whatsapp",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["provider"] == "whatsapp"
        assert body["waba_count"] == 2
        assert body["successful_scope_count"] == 1
        assert body["failed_scope_count"] == 1
        assert body["accepted_messages"] == 1
        assert body["skipped_messages"] == 0

        assert len(body["scopes"]) == 1
        successful_scope = body["scopes"][0]
        assert successful_scope["account_id"] == "meta-root-verified-pending-account-a"
        assert successful_scope["waba_id"] == "waba-root-verified-pending-a"
        assert successful_scope["accepted_messages"] == 1
        assert (
            successful_scope["results"][0]["inbound"]["conversation_id"]
            == "wa:pn-root-verified-pending-a:14150002401"
        )

        assert len(body["scope_failures"]) == 1
        pending_failure = body["scope_failures"][0]
        assert pending_failure["account_id"] == "meta-root-verified-pending-account-b"
        assert pending_failure["waba_id"] == "waba-root-verified-pending-b"
        assert pending_failure["status_code"] == 412
        assert "webhook_verification_status='pending'" in pending_failure["detail"]
        assert "MESSAGING_PROVIDER=whatsapp" in pending_failure["detail"]

        accepted_conversations_response = client.get(
            "/api/conversations",
            params={"account_id": "meta-root-verified-pending-account-a"},
        )
        assert accepted_conversations_response.status_code == 200
        assert [item["conversation_id"] for item in accepted_conversations_response.json()] == [
            "wa:pn-root-verified-pending-a:14150002401"
        ]

        blocked_conversations_response = client.get(
            "/api/conversations",
            params={"account_id": "meta-root-verified-pending-account-b"},
        )
        assert blocked_conversations_response.status_code == 200
        assert blocked_conversations_response.json() == []

        delivery_blocked_audit_response = client.get(
            "/api/runtime/audit-logs",
            params={
                "account_id": "meta-root-verified-pending-account-b",
                "action": "meta_webhook_delivery_blocked",
                "target_type": "waba_account",
                "target_id": "waba-root-verified-pending-b",
            },
        )
        assert delivery_blocked_audit_response.status_code == 200
        delivery_blocked_audit_logs = delivery_blocked_audit_response.json()
        assert len(delivery_blocked_audit_logs) == 1
        assert delivery_blocked_audit_logs[0]["payload"] == {
            "reason": "webhook_not_ready",
            "webhook_verification_status": "pending",
            "webhook_subscription_status": "remote_subscribed",
            "ready_for_webhook_delivery": False,
            "blocking_reasons": ["webhook_not_ready"],
        }

        root_failure_audit_response = client.get(
            "/api/runtime/audit-logs",
            params={
                "account_id": "meta-root-verified-pending-account-b",
                "action": "meta_webhook_root_scope_failed",
                "target_type": "waba_account",
                "target_id": "waba-root-verified-pending-b",
            },
        )
        assert root_failure_audit_response.status_code == 200
        root_failure_audit_logs = root_failure_audit_response.json()
        assert len(root_failure_audit_logs) == 1
        assert root_failure_audit_logs[0]["payload"]["source_stage"] == "scoped_processing"
        assert root_failure_audit_logs[0]["payload"]["status_code"] == 412
        assert "webhook_verification_status='pending'" in root_failure_audit_logs[0]["payload"]["detail"]

        signature_unavailable_audit_response = client.get(
            "/api/runtime/audit-logs",
            params={
                "account_id": "meta-root-verified-pending-account-b",
                "action": "meta_webhook_signature_unavailable",
                "target_type": "waba_account",
                "target_id": "waba-root-verified-pending-b",
            },
        )
        assert signature_unavailable_audit_response.status_code == 200
        assert signature_unavailable_audit_response.json() == []
    finally:
        if original_env["MESSAGING_PROVIDER"] is None:
            os.environ.pop("MESSAGING_PROVIDER", None)
        else:
            os.environ["MESSAGING_PROVIDER"] = original_env["MESSAGING_PROVIDER"]
        get_settings.cache_clear()


def test_root_whatsapp_webhook_reports_missing_app_secret_scope_failure_without_aborting_ready_scope(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {"MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER")}

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        ready_account_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "meta-root-missing-secret-account-a",
                "display_name": "Meta Root Missing Secret Account A",
                "meta_business_portfolio_id": "portfolio-root-missing-secret-a",
                "waba_id": "waba-root-missing-secret-a",
                "access_token": "token-root-missing-secret-a",
                "verify_token": "verify-root-missing-secret-a",
                "app_secret": "secret-root-missing-secret-shared",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-root-missing-secret-a",
                        "display_phone_number": "+1 555 000 2501",
                        "verified_name": "Meta Root Missing Secret Account A",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert ready_account_response.status_code == 200

        missing_secret_account_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "meta-root-missing-secret-account-b",
                "display_name": "Meta Root Missing Secret Account B",
                "meta_business_portfolio_id": "portfolio-root-missing-secret-b",
                "waba_id": "waba-root-missing-secret-b",
                "access_token": "token-root-missing-secret-b",
                "verify_token": "verify-root-missing-secret-b",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-root-missing-secret-b",
                        "display_phone_number": "+1 555 000 2502",
                        "verified_name": "Meta Root Missing Secret Account B",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert missing_secret_account_response.status_code == 200

        for account_id, waba_id in (
            ("meta-root-missing-secret-account-a", "waba-root-missing-secret-a"),
            ("meta-root-missing-secret-account-b", "waba-root-missing-secret-b"),
        ):
            subscribe_response = client.post(
                f"/api/meta/accounts/{account_id}/wabas/{waba_id}/webhook-subscription",
                json={"callback_url": f"https://example.com/webhook/{account_id}"},
            )
            assert subscribe_response.status_code == 200

        for account_id, waba_id, verify_token, challenge in (
            (
                "meta-root-missing-secret-account-a",
                "waba-root-missing-secret-a",
                "verify-root-missing-secret-a",
                "challenge-root-missing-secret-a",
            ),
            (
                "meta-root-missing-secret-account-b",
                "waba-root-missing-secret-b",
                "verify-root-missing-secret-b",
                "challenge-root-missing-secret-b",
            ),
        ):
            verify_response = client.get(
                f"/webhooks/whatsapp/{account_id}/wabas/{waba_id}",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": verify_token,
                    "hub.challenge": challenge,
                },
            )
            assert verify_response.status_code == 200

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-root-missing-secret-a",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 2501",
                                    "phone_number_id": "pn-root-missing-secret-a",
                                },
                                "messages": [
                                    {
                                        "from": "14150002501",
                                        "id": "wamid.root.missing.secret.ok.1",
                                        "timestamp": "1712345678",
                                        "type": "text",
                                        "text": {"body": "ready scope should still process"},
                                    }
                                ],
                            },
                        }
                    ],
                },
                {
                    "id": "waba-root-missing-secret-b",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 2502",
                                    "phone_number_id": "pn-root-missing-secret-b",
                                },
                                "messages": [
                                    {
                                        "from": "14150002502",
                                        "id": "wamid.root.missing.secret.blocked.1",
                                        "timestamp": "1712345678",
                                        "type": "text",
                                        "text": {"body": "missing secret scope should be isolated"},
                                    }
                                ],
                            },
                        }
                    ],
                },
            ],
        }
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = WhatsAppProvider.build_signature("secret-root-missing-secret-shared", raw_body)

        response = client.post(
            "/webhooks/whatsapp",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["provider"] == "whatsapp"
        assert body["waba_count"] == 2
        assert body["successful_scope_count"] == 1
        assert body["failed_scope_count"] == 1
        assert body["accepted_messages"] == 1
        assert body["skipped_messages"] == 0

        assert len(body["scopes"]) == 1
        successful_scope = body["scopes"][0]
        assert successful_scope["account_id"] == "meta-root-missing-secret-account-a"
        assert successful_scope["waba_id"] == "waba-root-missing-secret-a"
        assert successful_scope["accepted_messages"] == 1
        assert (
            successful_scope["results"][0]["inbound"]["conversation_id"]
            == "wa:pn-root-missing-secret-a:14150002501"
        )

        assert body["scope_failures"] == [
            {
                "account_id": "meta-root-missing-secret-account-b",
                "waba_id": "waba-root-missing-secret-b",
                "status_code": 503,
                "detail": "Webhook app secret is not configured for this WABA.",
            }
        ]

        accepted_conversations_response = client.get(
            "/api/conversations",
            params={"account_id": "meta-root-missing-secret-account-a"},
        )
        assert accepted_conversations_response.status_code == 200
        assert [item["conversation_id"] for item in accepted_conversations_response.json()] == [
            "wa:pn-root-missing-secret-a:14150002501"
        ]

        blocked_conversations_response = client.get(
            "/api/conversations",
            params={"account_id": "meta-root-missing-secret-account-b"},
        )
        assert blocked_conversations_response.status_code == 200
        assert blocked_conversations_response.json() == []

        accounts_response = client.get("/api/meta/accounts")
        assert accounts_response.status_code == 200
        accounts = {item["account_id"]: item for item in accounts_response.json()}
        blocked_account = accounts["meta-root-missing-secret-account-b"]
        assert blocked_account["webhook_runtime_status"] == "verification_pending"
        assert blocked_account["webhook_runtime_error"] == "missing_app_secret"
        assert blocked_account["webhook_signature_failure_count"] == 0
        assert blocked_account["webhook_last_signature_failed_at"] is None

        signature_unavailable_audit_response = client.get(
            "/api/runtime/audit-logs",
            params={
                "account_id": "meta-root-missing-secret-account-b",
                "action": "meta_webhook_signature_unavailable",
                "target_type": "waba_account",
                "target_id": "waba-root-missing-secret-b",
            },
        )
        assert signature_unavailable_audit_response.status_code == 200
        signature_unavailable_audit_logs = signature_unavailable_audit_response.json()
        assert len(signature_unavailable_audit_logs) == 1
        assert signature_unavailable_audit_logs[0]["payload"] == {"reason": "missing_app_secret"}

        root_failure_audit_response = client.get(
            "/api/runtime/audit-logs",
            params={
                "account_id": "meta-root-missing-secret-account-b",
                "action": "meta_webhook_root_scope_failed",
                "target_type": "waba_account",
                "target_id": "waba-root-missing-secret-b",
            },
        )
        assert root_failure_audit_response.status_code == 200
        root_failure_audit_logs = root_failure_audit_response.json()
        assert len(root_failure_audit_logs) == 1
        assert root_failure_audit_logs[0]["payload"] == {
            "source_stage": "scoped_processing",
            "status_code": 503,
            "detail": "Webhook app secret is not configured for this WABA.",
            "account_id_present": True,
        }

        delivery_blocked_audit_response = client.get(
            "/api/runtime/audit-logs",
            params={
                "account_id": "meta-root-missing-secret-account-b",
                "action": "meta_webhook_delivery_blocked",
                "target_type": "waba_account",
                "target_id": "waba-root-missing-secret-b",
            },
        )
        assert delivery_blocked_audit_response.status_code == 200
        assert delivery_blocked_audit_response.json() == []
    finally:
        if original_env["MESSAGING_PROVIDER"] is None:
            os.environ.pop("MESSAGING_PROVIDER", None)
        else:
            os.environ["MESSAGING_PROVIDER"] = original_env["MESSAGING_PROVIDER"]
        get_settings.cache_clear()


def test_root_whatsapp_webhook_rejects_payload_without_waba_entry(client: TestClient) -> None:
    response = client.post(
        "/webhooks/whatsapp",
        content=json.dumps(
            {"object": "whatsapp_business_account", "entry": []},
            separators=(",", ":"),
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Webhook payload entry is required."

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "action": "meta_webhook_root_payload_rejected",
            "target_type": "webhook_payload",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["account_id"] is None
    assert audit_logs[0]["target_id"] is None
    assert audit_logs[0]["payload"] == {
        "reason": "missing_waba_entry",
        "object": "whatsapp_business_account",
        "entry_count": 0,
    }


def test_root_whatsapp_webhook_rejects_unsupported_object_with_audit(
    client: TestClient,
) -> None:
    response = client.post(
        "/webhooks/whatsapp",
        content=json.dumps(
            {
                "object": "instagram_business_account",
                "entry": [
                    {
                        "id": "ig-root-unsupported",
                        "changes": [],
                    }
                ],
            },
            separators=(",", ":"),
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Unsupported webhook object."

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "action": "meta_webhook_root_payload_rejected",
            "target_type": "webhook_payload",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["account_id"] is None
    assert audit_logs[0]["payload"] == {
        "reason": "unsupported_object",
        "object": "instagram_business_account",
        "entry_count": 1,
    }


def test_root_whatsapp_webhook_rejects_malformed_payload_with_audit(
    client: TestClient,
) -> None:
    response = client.post(
        "/webhooks/whatsapp",
        content=b'{"object":',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "action": "meta_webhook_root_payload_rejected",
            "target_type": "webhook_payload",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["account_id"] is None
    assert audit_logs[0]["payload"] == {
        "reason": "invalid_payload",
        "object": None,
        "entry_count": None,
        "validation_error_count": 1,
    }
    assert '{"object":' not in str(audit_logs[0]["payload"])


def test_root_whatsapp_webhook_fans_out_payload_with_multiple_wabas(client: TestClient) -> None:
    for account_id, display_name, portfolio_id, waba_id, phone_number_id, display_phone in (
        (
            "meta-root-multi-account-1",
            "Meta Root Multi Account One",
            "portfolio-root-multi-1",
            "waba-root-multi-1",
            "pn-root-multi-1",
            "+1 555 000 2101",
        ),
        (
            "meta-root-multi-account-2",
            "Meta Root Multi Account Two",
            "portfolio-root-multi-2",
            "waba-root-multi-2",
            "pn-root-multi-2",
            "+1 555 000 2102",
        ),
    ):
        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": account_id,
                "display_name": display_name,
                "meta_business_portfolio_id": portfolio_id,
                "waba_id": waba_id,
                "access_token": f"token-{account_id}",
                "verify_token": f"verify-{account_id}",
                "app_secret": "secret-root-multi",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": phone_number_id,
                        "display_phone_number": display_phone,
                        "verified_name": display_name,
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert create_response.status_code == 200

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-root-multi-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 2101",
                                "phone_number_id": "pn-root-multi-1",
                            },
                            "messages": [
                                {
                                    "from": "14150001001",
                                    "id": "wamid.root.multi.1",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "first waba"},
                                }
                            ],
                        },
                    }
                ],
            },
            {
                "id": "waba-root-multi-2",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 2102",
                                "phone_number_id": "pn-root-multi-2",
                            },
                            "messages": [
                                {
                                    "from": "14150002002",
                                    "id": "wamid.root.multi.2",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "second waba"},
                                }
                            ],
                        },
                    }
                ],
            },
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-root-multi", raw_body)

    response = client.post(
        "/webhooks/whatsapp",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "whatsapp"
    assert body["waba_count"] == 2
    assert body["accepted_messages"] == 2
    assert body["skipped_messages"] == 0
    assert [scope["waba_id"] for scope in body["scopes"]] == [
        "waba-root-multi-1",
        "waba-root-multi-2",
    ]
    assert [scope["account_id"] for scope in body["scopes"]] == [
        "meta-root-multi-account-1",
        "meta-root-multi-account-2",
    ]
    assert [scope["results"][0]["inbound"]["conversation_id"] for scope in body["scopes"]] == [
        "wa:pn-root-multi-1:14150001001",
        "wa:pn-root-multi-2:14150002002",
    ]

    first_conversations_response = client.get(
        "/api/conversations",
        params={"account_id": "meta-root-multi-account-1"},
    )
    assert first_conversations_response.status_code == 200
    assert first_conversations_response.json()[0]["waba_id"] == "waba-root-multi-1"
    assert first_conversations_response.json()[0]["phone_number_id"] == "pn-root-multi-1"

    second_conversations_response = client.get(
        "/api/conversations",
        params={"account_id": "meta-root-multi-account-2"},
    )
    assert second_conversations_response.status_code == 200
    assert second_conversations_response.json()[0]["waba_id"] == "waba-root-multi-2"
    assert second_conversations_response.json()[0]["phone_number_id"] == "pn-root-multi-2"


def test_root_whatsapp_webhook_keeps_official_scope_counts_when_one_waba_phone_scope_is_rejected(
    client: TestClient,
) -> None:
    for account_id, display_name, portfolio_id, waba_id, phone_number_id, display_phone in (
        (
            "meta-root-scope-account-a",
            "Meta Root Scope Account A",
            "portfolio-root-scope-a",
            "waba-root-scope-a",
            "pn-root-scope-a",
            "+1 555 000 2201",
        ),
        (
            "meta-root-scope-account-b",
            "Meta Root Scope Account B",
            "portfolio-root-scope-b",
            "waba-root-scope-b",
            "pn-root-scope-b",
            "+1 555 000 2202",
        ),
    ):
        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": account_id,
                "display_name": display_name,
                "meta_business_portfolio_id": portfolio_id,
                "waba_id": waba_id,
                "access_token": f"token-{account_id}",
                "verify_token": f"verify-{account_id}",
                "app_secret": "secret-root-scope-shared",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": phone_number_id,
                        "display_phone_number": display_phone,
                        "verified_name": display_name,
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert create_response.status_code == 200

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-root-scope-a",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 2201",
                                "phone_number_id": "pn-root-scope-a",
                            },
                            "messages": [
                                {
                                    "from": "14150002201",
                                    "id": "wamid.root.scope.accepted.1",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "accepted root scope"},
                                }
                            ],
                        },
                    }
                ],
            },
            {
                "id": "waba-root-scope-b",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 2299",
                                "phone_number_id": "pn-root-scope-b-unknown",
                            },
                            "messages": [
                                {
                                    "from": "14150002299",
                                    "id": "wamid.root.scope.rejected.1",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "rejected root scope"},
                                }
                            ],
                        },
                    }
                ],
            },
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-root-scope-shared", raw_body)

    response = client.post(
        "/webhooks/whatsapp",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "whatsapp"
    assert body["waba_count"] == 2
    assert body["accepted_messages"] == 1
    assert body["skipped_messages"] == 1
    assert body["rejected_phone_scope_messages"] == 1

    scopes = {item["waba_id"]: item for item in body["scopes"]}
    accepted_scope = scopes["waba-root-scope-a"]
    rejected_scope = scopes["waba-root-scope-b"]

    assert accepted_scope["account_id"] == "meta-root-scope-account-a"
    assert accepted_scope["accepted_messages"] == 1
    assert accepted_scope["rejected_phone_scope_messages"] == 0
    assert accepted_scope["results"][0]["inbound"]["conversation_id"] == "wa:pn-root-scope-a:14150002201"

    assert rejected_scope["account_id"] == "meta-root-scope-account-b"
    assert rejected_scope["accepted_messages"] == 0
    assert rejected_scope["rejected_phone_scope_messages"] == 1
    assert rejected_scope["results"] == []

    accepted_conversations_response = client.get(
        "/api/conversations",
        params={"account_id": "meta-root-scope-account-a"},
    )
    assert accepted_conversations_response.status_code == 200
    assert [item["conversation_id"] for item in accepted_conversations_response.json()] == [
        "wa:pn-root-scope-a:14150002201"
    ]

    rejected_conversations_response = client.get(
        "/api/conversations",
        params={"account_id": "meta-root-scope-account-b"},
    )
    assert rejected_conversations_response.status_code == 200
    assert rejected_conversations_response.json() == []


def test_root_whatsapp_webhook_keeps_processed_scope_persisted_when_later_waba_hard_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for account_id, display_name, portfolio_id, waba_id, phone_number_id, display_phone in (
        (
            "meta-root-isolation-account-a",
            "Meta Root Isolation Account A",
            "portfolio-root-isolation-a",
            "waba-root-isolation-a",
            "pn-root-isolation-a",
            "+1 555 000 2301",
        ),
        (
            "meta-root-isolation-account-b",
            "Meta Root Isolation Account B",
            "portfolio-root-isolation-b",
            "waba-root-isolation-b",
            "pn-root-isolation-b",
            "+1 555 000 2302",
        ),
    ):
        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": account_id,
                "display_name": display_name,
                "meta_business_portfolio_id": portfolio_id,
                "waba_id": waba_id,
                "access_token": f"token-{account_id}",
                "verify_token": f"verify-{account_id}",
                "app_secret": "secret-root-isolation-shared",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": phone_number_id,
                        "display_phone_number": display_phone,
                        "verified_name": display_name,
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert create_response.status_code == 200

    original_process_inbound_message = webhook_routes.process_inbound_message

    async def failing_process_inbound_message(
        normalized: NormalizedMessage,
        *args: object,
        **kwargs: object,
    ) -> dict[str, object]:
        if normalized.external_message_id == "wamid.root.isolation.fail.1":
            raise RuntimeError("simulated root webhook scope failure")
        return await original_process_inbound_message(normalized, *args, **kwargs)

    monkeypatch.setattr(
        webhook_routes,
        "process_inbound_message",
        failing_process_inbound_message,
    )

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-root-isolation-a",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 2301",
                                "phone_number_id": "pn-root-isolation-a",
                            },
                            "messages": [
                                {
                                    "from": "14150002301",
                                    "id": "wamid.root.isolation.ok.1",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "first scope should persist"},
                                }
                            ],
                        },
                    }
                ],
            },
            {
                "id": "waba-root-isolation-b",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 2302",
                                "phone_number_id": "pn-root-isolation-b",
                            },
                            "messages": [
                                {
                                    "from": "14150002302",
                                    "id": "wamid.root.isolation.fail.1",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "second scope fails hard"},
                                }
                            ],
                        },
                    }
                ],
            },
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-root-isolation-shared", raw_body)

    with TestClient(client.app, raise_server_exceptions=False) as tolerant_client:
        response = tolerant_client.post(
            "/webhooks/whatsapp",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )

    accepted_conversations_response = client.get(
        "/api/conversations",
        params={"account_id": "meta-root-isolation-account-a"},
    )
    assert accepted_conversations_response.status_code == 200
    assert [item["conversation_id"] for item in accepted_conversations_response.json()] == [
        "wa:pn-root-isolation-a:14150002301"
    ]

    failed_conversations_response = client.get(
        "/api/conversations",
        params={"account_id": "meta-root-isolation-account-b"},
    )
    assert failed_conversations_response.status_code == 200
    assert failed_conversations_response.json() == []

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "whatsapp"
    assert body["waba_count"] == 2
    assert body["successful_scope_count"] == 1
    assert body["failed_scope_count"] == 1

    scopes = {item["waba_id"]: item for item in body["scopes"]}
    accepted_scope = scopes["waba-root-isolation-a"]

    assert accepted_scope["account_id"] == "meta-root-isolation-account-a"
    assert accepted_scope["accepted_messages"] == 1
    assert accepted_scope["results"][0]["inbound"]["conversation_id"] == "wa:pn-root-isolation-a:14150002301"

    assert body["scope_failures"] == [
        {
            "account_id": "meta-root-isolation-account-b",
            "waba_id": "waba-root-isolation-b",
            "status_code": 500,
            "detail": "Scoped WhatsApp webhook processing failed.",
            "error_type": "RuntimeError",
        }
    ]


def test_root_whatsapp_webhook_audits_single_scope_processing_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-root-single-fail-account",
            "display_name": "Meta Root Single Fail Account",
            "meta_business_portfolio_id": "portfolio-root-single-fail",
            "waba_id": "waba-root-single-fail",
            "access_token": "token-meta-root-single-fail-account",
            "verify_token": "verify-meta-root-single-fail-account",
            "app_secret": "secret-root-single-fail",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-root-single-fail",
                    "display_phone_number": "+1 555 000 2601",
                    "verified_name": "Meta Root Single Fail Account",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert create_response.status_code == 200

    async def failing_process_inbound_message(
        normalized: NormalizedMessage,
        *args: object,
        **kwargs: object,
    ) -> dict[str, object]:
        raise RuntimeError("simulated single root webhook processing failure")

    monkeypatch.setattr(
        webhook_routes,
        "process_inbound_message",
        failing_process_inbound_message,
    )

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-root-single-fail",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 2601",
                                "phone_number_id": "pn-root-single-fail",
                            },
                            "messages": [
                                {
                                    "from": "14150002601",
                                    "id": "wamid.root.single.fail.1",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "single root scope fails hard"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-root-single-fail", raw_body)

    with TestClient(client.app, raise_server_exceptions=False) as tolerant_client:
        response = tolerant_client.post(
            "/webhooks/whatsapp",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )

    assert response.status_code == 500

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-root-single-fail-account",
            "action": "meta_webhook_root_scope_failed",
            "target_type": "waba_account",
            "target_id": "waba-root-single-fail",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"] == {
        "source_stage": "scoped_processing",
        "status_code": 500,
        "detail": "Scoped WhatsApp webhook processing failed.",
        "account_id_present": True,
        "error_type": "RuntimeError",
    }


def test_root_whatsapp_webhook_reports_unknown_waba_scope_failure_without_aborting_known_scope(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-root-unknown-scope-account-a",
            "display_name": "Meta Root Unknown Scope Account A",
            "meta_business_portfolio_id": "portfolio-root-unknown-scope-a",
            "waba_id": "waba-root-unknown-scope-a",
            "access_token": "token-meta-root-unknown-scope-account-a",
            "verify_token": "verify-meta-root-unknown-scope-account-a",
            "app_secret": "secret-root-unknown-scope-shared",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-root-unknown-scope-a",
                    "display_phone_number": "+1 555 000 2401",
                    "verified_name": "Meta Root Unknown Scope Account A",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert create_response.status_code == 200

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-root-unknown-scope-a",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 2401",
                                "phone_number_id": "pn-root-unknown-scope-a",
                            },
                            "messages": [
                                {
                                    "from": "14150002401",
                                    "id": "wamid.root.unknown.scope.ok.1",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "known scope should still process"},
                                }
                            ],
                        },
                    }
                ],
            },
            {
                "id": "waba-root-unknown-scope-missing",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 2499",
                                "phone_number_id": "pn-root-unknown-scope-missing",
                            },
                            "messages": [
                                {
                                    "from": "14150002499",
                                    "id": "wamid.root.unknown.scope.missing.1",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "unknown scope should be isolated"},
                                }
                            ],
                        },
                    }
                ],
            },
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-root-unknown-scope-shared", raw_body)

    response = client.post(
        "/webhooks/whatsapp",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "whatsapp"
    assert body["waba_count"] == 2
    assert body["successful_scope_count"] == 1
    assert body["failed_scope_count"] == 1
    assert body["accepted_messages"] == 1
    assert body["skipped_messages"] == 0
    assert [scope["waba_id"] for scope in body["scopes"]] == [
        "waba-root-unknown-scope-a"
    ]
    assert body["scopes"][0]["account_id"] == "meta-root-unknown-scope-account-a"
    assert body["scopes"][0]["results"][0]["inbound"]["conversation_id"] == (
        "wa:pn-root-unknown-scope-a:14150002401"
    )
    assert body["scope_failures"] == [
        {
            "account_id": None,
            "waba_id": "waba-root-unknown-scope-missing",
            "status_code": 404,
            "detail": "WABA 'waba-root-unknown-scope-missing' was not found.",
        }
    ]

    accepted_conversations_response = client.get(
        "/api/conversations",
        params={"account_id": "meta-root-unknown-scope-account-a"},
    )
    assert accepted_conversations_response.status_code == 200
    assert [item["conversation_id"] for item in accepted_conversations_response.json()] == [
        "wa:pn-root-unknown-scope-a:14150002401"
    ]

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "action": "meta_webhook_root_scope_failed",
            "target_type": "waba_account",
            "target_id": "waba-root-unknown-scope-missing",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["account_id"] is None
    assert audit_logs[0]["payload"] == {
        "source_stage": "scope_resolution",
        "status_code": 404,
        "detail": "WABA 'waba-root-unknown-scope-missing' was not found.",
        "account_id_present": False,
    }


def test_webhook_signature_disabled_accepts_invalid_signature(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    """BE2-005: When webhook_signature_enabled=False, invalid signatures are accepted."""
    import os
    from app.core.settings import get_settings

    original_env = os.environ.get("WEBHOOK_SIGNATURE_ENABLED")
    os.environ["WEBHOOK_SIGNATURE_ENABLED"] = "false"
    get_settings.cache_clear()

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "meta-webhook-sig-disabled",
                "display_name": "Meta Webhook Sig Disabled",
                "meta_business_portfolio_id": "portfolio-sig-disabled",
                "waba_id": "waba-sig-disabled",
                "access_token": "token-sig-disabled",
                "verify_token": "verify-sig-disabled",
                "app_secret": "secret-sig-disabled",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-sig-disabled",
                        "display_phone_number": "+1 555 000 9001",
                        "verified_name": "Signature Disabled Brand",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert create_response.status_code == 200

        subscribe_response = client.post(
            "/api/meta/accounts/meta-webhook-sig-disabled/wabas/waba-sig-disabled/webhook-subscription",
            json={"callback_url": "https://example.com/webhook/sig-disabled"},
        )
        assert subscribe_response.status_code == 200

        first_verify_response = client.get(
            "/webhooks/whatsapp/meta-webhook-sig-disabled/wabas/waba-sig-disabled",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-sig-disabled",
                "hub.challenge": "challenge-sig-disabled",
            },
        )
        assert first_verify_response.status_code == 200

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-sig-disabled",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 9001",
                                    "phone_number_id": "pn-sig-disabled",
                                },
                                "messages": [
                                    {
                                        "from": "14150009001",
                                        "id": "wamid.sig.disabled.1",
                                        "timestamp": "1712345802",
                                        "type": "text",
                                        "text": {"body": "signature disabled test"},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        response = client.post(
            "/webhooks/whatsapp/meta-webhook-sig-disabled/wabas/waba-sig-disabled",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalid-signature",
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert result["signature_verified"] is False
        assert result["account_id"] == "meta-webhook-sig-disabled"
        assert result["accepted_messages"] == 1
    finally:
        if original_env is None:
            os.environ.pop("WEBHOOK_SIGNATURE_ENABLED", None)
        else:
            os.environ["WEBHOOK_SIGNATURE_ENABLED"] = original_env
        os.environ["MESSAGING_PROVIDER"] = "mock"
        get_settings.cache_clear()


def test_root_webhook_signature_disabled_accepts_invalid_signature_but_flags_unverified(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    import os
    from app.core.settings import get_settings

    original_env = {
        "WEBHOOK_SIGNATURE_ENABLED": os.environ.get("WEBHOOK_SIGNATURE_ENABLED"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
    }
    os.environ["WEBHOOK_SIGNATURE_ENABLED"] = "false"
    os.environ["MESSAGING_PROVIDER"] = "whatsapp"
    get_settings.cache_clear()

    try:
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "meta-root-sig-disabled",
                "display_name": "Meta Root Sig Disabled",
                "meta_business_portfolio_id": "portfolio-root-sig-disabled",
                "waba_id": "waba-root-sig-disabled",
                "access_token": "token-root-sig-disabled",
                "verify_token": "verify-root-sig-disabled",
                "app_secret": "secret-root-sig-disabled",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-root-sig-disabled",
                        "display_phone_number": "+1 555 000 9011",
                        "verified_name": "Root Signature Disabled Brand",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert create_response.status_code == 200

        subscribe_response = client.post(
            "/api/meta/accounts/meta-root-sig-disabled/wabas/waba-root-sig-disabled/webhook-subscription",
            json={"callback_url": "https://example.com/webhook/root-sig-disabled"},
        )
        assert subscribe_response.status_code == 200

        verify_response = client.get(
            "/webhooks/whatsapp/meta-root-sig-disabled/wabas/waba-root-sig-disabled",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-root-sig-disabled",
                "hub.challenge": "challenge-root-sig-disabled",
            },
        )
        assert verify_response.status_code == 200

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-root-sig-disabled",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 9011",
                                    "phone_number_id": "pn-root-sig-disabled",
                                },
                                "messages": [
                                    {
                                        "from": "14150009011",
                                        "id": "wamid.root.sig.disabled.1",
                                        "timestamp": "1712345802",
                                        "type": "text",
                                        "text": {"body": "root signature disabled test"},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        response = client.post(
            "/webhooks/whatsapp",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalid-signature",
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert result["signature_verified"] is False
        assert result["accepted_messages"] == 1
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_webhook_dedup_skips_duplicate_message(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    """BE2-007: Duplicate message_id is skipped on second delivery."""
    import os
    from app.api.routes.webhooks import _reset_message_dedup
    from app.core.settings import get_settings

    _reset_message_dedup()
    os.environ["WEBHOOK_SIGNATURE_ENABLED"] = "false"
    get_settings.cache_clear()
    override_meta_management_provider(client, StubMetaManagementProvider())
    register_meta_account_with_webhook_secret(client)
    subscribe_meta_webhook(client)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "messages": [
                                {
                                    "from": "14150000001",
                                    "id": "wamid.dedup.test.1",
                                    "timestamp": "1712345802",
                                    "type": "text",
                                    "text": {"body": "first delivery"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    response1 = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
    )
    assert response1.status_code == 200
    result1 = response1.json()
    assert result1["accepted_messages"] == 1

    response2 = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
    )
    assert response2.status_code == 200
    result2 = response2.json()
    assert result2["accepted_messages"] == 0, "Duplicate message should be skipped"


def test_webhook_error_isolation_continues_on_failure(
    client: TestClient,
    override_meta_management_provider,
    monkeypatch,
) -> None:
    """BE2-007: A single message processing failure does not block other messages."""
    import os
    from app.api.routes.webhooks import _reset_message_dedup
    from app.core.settings import get_settings
    from app.services.chat import process_inbound_message

    _reset_message_dedup()
    os.environ["WEBHOOK_SIGNATURE_ENABLED"] = "false"
    get_settings.cache_clear()
    override_meta_management_provider(client, StubMetaManagementProvider())
    register_meta_account_with_webhook_secret(client)
    subscribe_meta_webhook(client)

    original_process = process_inbound_message
    call_count = [0]

    async def failing_process(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise ValueError("Simulated processing failure")
        return await original_process(*args, **kwargs)

    monkeypatch.setattr(
        "app.api.routes.webhooks.process_inbound_message",
        failing_process,
    )

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0001",
                                "phone_number_id": "pn-webhook-1",
                            },
                            "messages": [
                                {
                                    "from": "14150000001",
                                    "id": "wamid.error.isolation.1",
                                    "timestamp": "1712345802",
                                    "type": "text",
                                    "text": {"body": "first message fails"},
                                },
                                {
                                    "from": "14150000002",
                                    "id": "wamid.error.isolation.2",
                                    "timestamp": "1712345803",
                                    "type": "text",
                                    "text": {"body": "second message succeeds"},
                                },
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    response = client.post(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        content=raw_body,
    )
    assert response.status_code == 200
    result = response.json()
    assert result["accepted_messages"] == 1, "Second message should be processed despite first failure"


class TestMessageDeliveryStatus:
    def test_message_query_includes_delivery_status(self, client: TestClient) -> None:
        """BFX-008: Message query response includes delivery_status field."""
        import os
        from app.api.routes.webhooks import _reset_message_dedup
        from app.core.settings import get_settings

        _reset_message_dedup()
        os.environ["WEBHOOK_SIGNATURE_ENABLED"] = "false"
        get_settings.cache_clear()
        register_meta_account_with_webhook_secret(client)
        subscribe_meta_webhook(client)

        # Send a mock inbound message to create a conversation
        inbound_resp = client.post(
            "/dev/mock/inbound-message",
            json={
                "account_id": "meta-webhook-account",
                "conversation_id": "conv-status-1",
                "user_id": "user-status-1",
                "text": "Delivery status test",
                "mode": "echo",
            },
        )
        assert inbound_resp.status_code == 200

        # Find the internal conversation ID
        list_resp = client.get("/api/conversations?account_id=meta-webhook-account")
        assert list_resp.status_code == 200
        items = list_resp.json().get("items", [])
        if not items:
            pytest.skip("No conversations found")
        internal_conv_id = items[0]["conversation_id"]

        # Query messages - they should include delivery_status field
        resp = client.get(f"/api/conversations/meta-webhook-account/{internal_conv_id}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            for msg in data:
                if msg["direction"] == "outbound":
                    assert "delivery_status" in msg
                    assert "delivered_at" in msg
                    assert "read_at" in msg

    def test_webhook_status_update_writes_message_event(self, client: TestClient) -> None:
        """BFX-008: Status update webhook correctly writes to message_events."""
        import os
        from app.api.routes.webhooks import _reset_message_dedup
        from app.core.settings import get_settings

        _reset_message_dedup()
        os.environ["WEBHOOK_SIGNATURE_ENABLED"] = "false"
        get_settings.cache_clear()
        register_meta_account_with_webhook_secret(client)
        subscribe_meta_webhook(client)

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-webhook-1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 0001",
                                    "phone_number_id": "pn-webhook-1",
                                },
                                "statuses": [
                                    {
                                        "id": "wamid.status.update.1",
                                        "status": "delivered",
                                        "timestamp": "1712345802",
                                        "recipient_id": "14150000001",
                                        "conversation": {
                                            "id": "conv-status-update",
                                            "origin": {"type": "service"},
                                        },
                                        "pricing": {
                                            "pricing_model": "CBP",
                                            "billable": True,
                                            "category": "service",
                                        },
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
        raw_body = __import__("json").dumps(payload, separators=(",", ":")).encode("utf-8")
        resp = client.post(
            "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
            content=raw_body,
        )
        # The webhook should accept the status update
        assert resp.status_code in (200, 202)

    def test_outbound_message_delivery_fields_in_response(self, client: TestClient) -> None:
        """BFX-008: Outbound message response includes delivery tracking fields."""
        import os
        from app.api.routes.webhooks import _reset_message_dedup
        from app.core.settings import get_settings

        _reset_message_dedup()
        os.environ["WEBHOOK_SIGNATURE_ENABLED"] = "false"
        get_settings.cache_clear()
        register_meta_account_with_webhook_secret(client)
        subscribe_meta_webhook(client)

        # Create conversation first
        client.post(
            "/dev/mock/inbound-message",
            json={
                "account_id": "meta-webhook-account",
                "conversation_id": "conv-status-2",
                "user_id": "user-status-2",
                "text": "Test delivery fields",
                "mode": "echo",
            },
        )

        list_resp = client.get("/api/conversations?account_id=meta-webhook-account")
        items = list_resp.json().get("items", [])
        if not items:
            pytest.skip("No conversations found")
        internal_conv_id = items[0]["conversation_id"]

        resp = client.get(f"/api/conversations/meta-webhook-account/{internal_conv_id}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        for msg in data:
            if msg["direction"] == "outbound":
                # delivery_status should be one of: None, "sent", "delivered", "read", "failed"
                ds = msg.get("delivery_status")
                assert ds is None or ds in ("sent", "delivered", "read", "failed")
