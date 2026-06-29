import json
import os

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings
from app.db.models import EmbeddedSignupSession as EmbeddedSignupSessionModel
from app.db.models import WebhookSubscription, WhatsAppBusinessAccount, WhatsAppPhoneNumber
from app.providers.meta_management.base import (
    MetaEmbeddedSignupCompletionCommand,
    MetaEmbeddedSignupCompletionResult,
    MetaWebhookSubscriptionCommand,
    MetaWebhookSubscriptionResult,
)
from app.providers.messaging.whatsapp_provider import WhatsAppProvider
from tests.conftest import StubMetaManagementProvider


class CapturingEmbeddedSignupProvider(StubMetaManagementProvider):
    def __init__(self) -> None:
        super().__init__()
        self.last_completion_payload: MetaEmbeddedSignupCompletionCommand | None = None

    async def complete_embedded_signup_session(
        self,
        payload: MetaEmbeddedSignupCompletionCommand,
    ) -> MetaEmbeddedSignupCompletionResult:
        self.last_completion_payload = payload
        return MetaEmbeddedSignupCompletionResult(
            provider_name=self.provider_name,
            completion_status="remote_confirmed",
            remote_confirmed=True,
            resolved_waba_id=payload.requested_waba_id,
            resolved_portfolio_id=payload.meta_business_portfolio_id,
            access_token="token-exchanged-from-code",
            phone_number_ids=["pn-code-only-1"],
            raw_response={
                "session_id": payload.session_id,
                "authorization_code_present": bool(payload.authorization_code),
            },
            message="Stub authorization-code completion confirmed remotely.",
        )


class CapturingRawPayloadEmbeddedSignupProvider(StubMetaManagementProvider):
    def __init__(self) -> None:
        super().__init__()
        self.last_completion_payload: MetaEmbeddedSignupCompletionCommand | None = None

    async def complete_embedded_signup_session(
        self,
        payload: MetaEmbeddedSignupCompletionCommand,
    ) -> MetaEmbeddedSignupCompletionResult:
        self.last_completion_payload = payload
        return MetaEmbeddedSignupCompletionResult(
            provider_name=self.provider_name,
            completion_status="remote_confirmed",
            remote_confirmed=True,
            resolved_waba_id=payload.requested_waba_id,
            resolved_portfolio_id=payload.meta_business_portfolio_id,
            access_token=payload.system_user_access_token,
            phone_number_ids=list(payload.phone_number_ids),
            raw_response={"session_id": payload.session_id},
            message="Stub raw-payload callback completion confirmed remotely.",
        )


class CapturingEmbeddedSignupActivationProvider(StubMetaManagementProvider):
    def __init__(self) -> None:
        super().__init__(
            completion_phone_number_ids=["pn-embedded-activation-1"],
        )
        self.webhook_subscription_commands: list[MetaWebhookSubscriptionCommand] = []

    async def subscribe_webhook(
        self,
        payload: MetaWebhookSubscriptionCommand,
    ) -> MetaWebhookSubscriptionResult:
        self.webhook_subscription_commands.append(payload)
        return await super().subscribe_webhook(payload)


def sign_whatsapp_payload(payload: dict[str, object], app_secret: str) -> tuple[bytes, str]:
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return raw_body, WhatsAppProvider.build_signature(app_secret, raw_body)


def assert_webhook_signature_conflict(detail: str) -> None:
    normalized_detail = detail.lower()
    assert "callback" in normalized_detail
    assert any(keyword in normalized_detail for keyword in ("app secret", "app_secret", "signature"))
    assert any(keyword in normalized_detail for keyword in ("shared", "conflict", "already"))


def assert_embedded_signup_webhook_activation_pending(
    *,
    client: TestClient,
    session_payload: dict[str, object],
    account_id: str,
    waba_id: str,
    callback_url: str,
    app_id: str,
    expected_event_source: str,
) -> None:
    assert session_payload["completion_stage"] == "webhook_verification_pending"
    assert session_payload["event_source"] == expected_event_source
    assert session_payload["remote_confirmed"] is True
    assert session_payload["webhook_callback_url"] == callback_url
    assert session_payload["webhook_verify_token_present"] is True
    assert session_payload["webhook_app_secret_present"] is True
    assert session_payload["webhook_app_id"] == app_id
    assert session_payload["webhook_subscription_status"] == "remote_subscribed"
    assert session_payload["webhook_verification_status"] == "pending"
    assert session_payload["ready_for_webhook_delivery"] is False
    assert session_payload["ready_for_meta_activation"] is False
    assert "webhook_not_ready" in session_payload["webhook_blocking_reasons"]
    assert session_payload["completion_webhook_subscription_status"] == "remote_subscribed"
    assert session_payload["completion_webhook_verification_status"] == "pending"
    assert session_payload["completion_webhook_runtime_status"] == "pending"
    assert session_payload["completion_ready_for_webhook_delivery"] is False
    assert session_payload["completion_ready_for_outbound_messages"] is False
    assert session_payload["completion_ready_for_meta_activation"] is False
    assert "webhook_not_ready" in session_payload["completion_webhook_blocking_reasons"]
    assert session_payload["session_snapshot"]["webhook_callback_url"] == callback_url
    assert session_payload["session_snapshot"]["webhook_app_secret_present"] is True
    assert session_payload["session_snapshot"]["webhook_app_id"] == app_id
    assert session_payload["session_snapshot"]["webhook_subscription_status"] == "remote_subscribed"
    assert session_payload["session_snapshot"]["webhook_verification_status"] == "pending"
    assert session_payload["session_snapshot"]["ready_for_webhook_delivery"] is False
    assert session_payload["current_waba_state"]["webhook_verification_status"] == "pending"
    assert session_payload["current_waba_state"]["webhook_app_secret_present"] is True
    assert session_payload["current_waba_state"]["ready_for_webhook_delivery"] is False

    account_response = client.get(
        "/api/meta/accounts",
        params={"account_id": account_id},
    )
    assert account_response.status_code == 200
    account_payload = account_response.json()[0]
    assert account_payload["waba_id"] == waba_id
    assert account_payload["webhook_callback_url"] == callback_url
    assert account_payload["has_verify_token"] is True
    assert account_payload["has_app_secret"] is True
    assert account_payload["webhook_subscription_status"] == "remote_subscribed"
    assert account_payload["webhook_verification_status"] == "pending"
    assert account_payload["ready_for_webhook_delivery"] is False
    assert account_payload["ready_for_meta_activation"] is False
    assert "webhook_not_ready" in account_payload["blocking_reasons"]

    subscriptions_response = client.get(
        "/api/meta/accounts/webhook-subscriptions",
        params={"account_id": account_id, "waba_id": waba_id},
    )
    assert subscriptions_response.status_code == 200
    subscriptions = subscriptions_response.json()
    assert len(subscriptions) == 1
    assert subscriptions[0]["callback_url"] == callback_url
    assert subscriptions[0]["verify_token_present"] is True
    assert subscriptions[0]["app_secret_present"] is True
    assert subscriptions[0]["app_id"] == app_id
    assert subscriptions[0]["status"] == "remote_subscribed"
    assert subscriptions[0]["webhook_verification_status"] == "pending"


def test_create_manual_meta_account(client: TestClient) -> None:
    response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-account-1",
            "display_name": "Brand A",
            "meta_business_portfolio_id": "biz-portfolio-1",
            "waba_id": "waba-1",
            "access_token": "token-123",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-1",
                    "display_phone_number": "+1 555 000 0001",
                    "verified_name": "Brand A",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["waba_id"] == "waba-1"
    assert response.json()["phone_numbers"][0]["phone_number_id"] == "pn-1"
    assert response.json()["has_access_token"] is True
    assert response.json()["has_verify_token"] is False
    assert response.json()["phone_number_count"] == 1
    assert response.json()["registered_phone_number_count"] == 1
    assert response.json()["ready_for_outbound_messages"] is True
    assert response.json()["ready_for_meta_activation"] is False
    assert response.json()["webhook_verify_path"] == "/webhooks/whatsapp/meta-account-1/wabas/waba-1"
    assert response.json()["blocking_reasons"] == [
        "missing_verify_token",
        "missing_app_secret",
        "missing_webhook_subscription",
    ]

    phone_numbers_response = client.get("/api/meta/accounts/meta-account-1/wabas/waba-1/phone-numbers")
    assert phone_numbers_response.status_code == 200
    assert phone_numbers_response.json()[0]["phone_number_id"] == "pn-1"
    assert phone_numbers_response.json()[0]["blocking_reasons"] == [
        "missing_verify_token",
        "missing_app_secret",
        "missing_webhook_subscription",
    ]


def test_manual_meta_account_rejects_cross_account_portfolio_reuse(client: TestClient) -> None:
    first_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-portfolio-owner-a",
            "display_name": "Portfolio Owner A",
            "meta_business_portfolio_id": "biz-cross-account-owned",
            "waba_id": "waba-cross-account-owned-a",
            "access_token": "token-owner-a",
            "token_source": "system_user",
            "phone_numbers": [],
        },
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-portfolio-owner-b",
            "display_name": "Portfolio Owner B",
            "meta_business_portfolio_id": "biz-cross-account-owned",
            "waba_id": "waba-cross-account-owned-b",
            "access_token": "token-owner-b",
            "token_source": "system_user",
            "phone_numbers": [],
        },
    )

    assert second_response.status_code == 409
    assert "already linked to account 'meta-portfolio-owner-a'" in second_response.json()["detail"]


def test_manual_meta_account_rejects_verify_token_reuse_across_wabas(client: TestClient) -> None:
    first_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-verify-owner-a",
            "display_name": "Verify Owner A",
            "meta_business_portfolio_id": "biz-verify-owner-a",
            "waba_id": "waba-verify-owner-a",
            "access_token": "token-verify-owner-a",
            "verify_token": "verify-shared-cross-waba",
            "app_secret": "secret-verify-owner-a",
            "token_source": "system_user",
            "phone_numbers": [],
        },
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-verify-owner-b",
            "display_name": "Verify Owner B",
            "meta_business_portfolio_id": "biz-verify-owner-b",
            "waba_id": "waba-verify-owner-b",
            "access_token": "token-verify-owner-b",
            "verify_token": "verify-shared-cross-waba",
            "app_secret": "secret-verify-owner-b",
            "token_source": "system_user",
            "phone_numbers": [],
        },
    )

    assert second_response.status_code == 409
    assert "already used by WABA 'waba-verify-owner-a'" in second_response.json()["detail"]


def test_update_meta_account_replaces_current_phone_scope_and_preserves_omitted_secrets(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-account-update-1",
            "display_name": "Brand Update 1",
            "meta_business_portfolio_id": "biz-update-1",
            "waba_id": "waba-update-1",
            "access_token": "token-update-1",
            "verify_token": "verify-update-1",
            "app_secret": "secret-update-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-update-1a",
                    "display_phone_number": "+1 555 000 0101",
                    "verified_name": "Brand Update 1 Primary",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                },
                {
                    "phone_number_id": "pn-update-1b",
                    "display_phone_number": "+1 555 000 0102",
                    "verified_name": "Brand Update 1 Backup",
                    "quality_rating": "YELLOW",
                    "is_registered": False,
                },
            ],
        },
    )
    assert create_response.status_code == 200

    update_response = client.patch(
        "/api/meta/accounts/meta-account-update-1/wabas/waba-update-1",
        json={
            "display_name": "Brand Update 1 Revised",
            "meta_business_portfolio_id": "biz-update-1-revised",
            "access_token": "token-update-1-rotated",
            "token_source": "user_access_token",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-update-1b",
                    "display_phone_number": "+1 555 000 0199",
                    "verified_name": "Brand Update 1 Shared",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                },
                {
                    "phone_number_id": "pn-update-1c",
                    "display_phone_number": "+1 555 000 0103",
                    "verified_name": "Brand Update 1 New",
                    "quality_rating": "UNKNOWN",
                    "is_registered": False,
                },
            ],
        },
    )

    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["display_name"] == "Brand Update 1 Revised"
    assert payload["meta_business_portfolio_id"] == "biz-update-1-revised"
    assert payload["token_source"] == "user_access_token"
    assert payload["has_access_token"] is True
    assert payload["has_verify_token"] is True
    assert payload["has_app_secret"] is True
    assert payload["phone_number_count"] == 2
    assert [item["phone_number_id"] for item in payload["phone_numbers"]] == [
        "pn-update-1c",
        "pn-update-1b",
    ]
    assert payload["phone_numbers"][1]["display_phone_number"] == "+1 555 000 0199"

    phone_numbers_response = client.get(
        "/api/meta/accounts/meta-account-update-1/wabas/waba-update-1/phone-numbers"
    )
    assert phone_numbers_response.status_code == 200
    assert [item["phone_number_id"] for item in phone_numbers_response.json()] == [
        "pn-update-1c",
        "pn-update-1b",
    ]

    all_phone_numbers_response = client.get(
        "/api/meta/accounts/phone-numbers",
        params={"account_id": "meta-account-update-1"},
    )
    assert all_phone_numbers_response.status_code == 200
    assert [item["phone_number_id"] for item in all_phone_numbers_response.json()] == [
        "pn-update-1c",
        "pn-update-1b",
    ]

    audit_logs_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-account-update-1",
            "action": "meta_account_updated",
            "target_type": "waba_account",
            "target_id": "waba-update-1",
            "limit": 10,
        },
    )
    assert audit_logs_response.status_code == 200
    audit_logs = audit_logs_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"]["phone_number_ids"] == ["pn-update-1b", "pn-update-1c"]
    assert audit_logs[0]["payload"]["previous_phone_number_ids"] == [
        "pn-update-1a",
        "pn-update-1b",
    ]
    assert audit_logs[0]["payload"]["access_token_updated"] is True
    assert audit_logs[0]["payload"]["verify_token_updated"] is False
    assert audit_logs[0]["payload"]["app_secret_updated"] is False


def test_update_meta_account_rejects_verify_token_reuse_across_wabas(client: TestClient) -> None:
    for account_id, display_name, portfolio_id, waba_id, verify_token in (
        (
            "meta-update-verify-owner-a",
            "Update Verify Owner A",
            "biz-update-verify-owner-a",
            "waba-update-verify-owner-a",
            "verify-update-owner-a",
        ),
        (
            "meta-update-verify-owner-b",
            "Update Verify Owner B",
            "biz-update-verify-owner-b",
            "waba-update-verify-owner-b",
            "verify-update-owner-b",
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
                "verify_token": verify_token,
                "app_secret": f"secret-{account_id}",
                "token_source": "system_user",
                "phone_numbers": [],
            },
        )
        assert response.status_code == 200

    update_response = client.patch(
        "/api/meta/accounts/meta-update-verify-owner-b/wabas/waba-update-verify-owner-b",
        json={
            "display_name": "Update Verify Owner B Revised",
            "meta_business_portfolio_id": "biz-update-verify-owner-b",
            "verify_token": "verify-update-owner-a",
            "phone_numbers": [],
        },
    )

    assert update_response.status_code == 409
    assert "already used by WABA 'waba-update-verify-owner-a'" in update_response.json()["detail"]


def test_update_waba_and_phone_runtime_status(client: TestClient) -> None:
    create_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-account-status-1",
            "display_name": "Brand Status 1",
            "meta_business_portfolio_id": "biz-status-1",
            "waba_id": "waba-status-1",
            "access_token": "token-status-1",
            "verify_token": "verify-status-1",
            "app_secret": "secret-status-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-status-1",
                    "display_phone_number": "+1 555 000 0201",
                    "verified_name": "Brand Status Primary",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert create_response.status_code == 200

    deactivate_waba_response = client.patch(
        "/api/meta/accounts/meta-account-status-1/wabas/waba-status-1/status",
        json={"is_active": False},
    )
    assert deactivate_waba_response.status_code == 200
    assert deactivate_waba_response.json()["is_active"] is False
    assert "waba_inactive" in deactivate_waba_response.json()["blocking_reasons"]

    phone_numbers_response = client.get(
        "/api/meta/accounts/meta-account-status-1/wabas/waba-status-1/phone-numbers"
    )
    assert phone_numbers_response.status_code == 200
    assert phone_numbers_response.json()[0]["is_active"] is True
    assert "waba_inactive" in phone_numbers_response.json()[0]["blocking_reasons"]

    deactivate_phone_response = client.patch(
        "/api/meta/accounts/meta-account-status-1/wabas/waba-status-1/phone-numbers/pn-status-1/status",
        json={"is_active": False},
    )
    assert deactivate_phone_response.status_code == 200
    assert deactivate_phone_response.json()["is_active"] is False
    assert "phone_inactive" in deactivate_phone_response.json()["blocking_reasons"]

    all_phone_numbers_response = client.get(
        "/api/meta/accounts/phone-numbers",
        params={"account_id": "meta-account-status-1"},
    )
    assert all_phone_numbers_response.status_code == 200
    assert all_phone_numbers_response.json()[0]["is_active"] is False

    active_only_response = client.get(
        "/api/meta/accounts/phone-numbers",
        params={"account_id": "meta-account-status-1", "is_active": True},
    )
    assert active_only_response.status_code == 200
    assert active_only_response.json() == []

    audit_logs_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-account-status-1",
            "limit": 20,
        },
    )
    assert audit_logs_response.status_code == 200
    actions = [item["action"] for item in audit_logs_response.json()]
    assert "meta_waba_status_updated" in actions
    assert "meta_phone_number_status_updated" in actions


def test_update_phone_number_runtime_status_rejects_cross_scope_phone_reference(
    client: TestClient,
) -> None:
    for account_id, display_name, portfolio_id, waba_id, phone_number_id in (
        (
            "meta-account-phone-status-scope-a",
            "Phone Status Scope A",
            "biz-phone-status-scope-a",
            "waba-phone-status-scope-a",
            "pn-phone-status-scope-a",
        ),
        (
            "meta-account-phone-status-scope-b",
            "Phone Status Scope B",
            "biz-phone-status-scope-b",
            "waba-phone-status-scope-b",
            "pn-phone-status-scope-b",
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
                "app_secret": f"secret-{account_id}",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": phone_number_id,
                        "display_phone_number": f"+1 555 {phone_number_id[-4:]}",
                        "verified_name": display_name,
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert create_response.status_code == 200

    mismatch_response = client.patch(
        "/api/meta/accounts/meta-account-phone-status-scope-a/"
        "wabas/waba-phone-status-scope-a/phone-numbers/pn-phone-status-scope-b/status",
        json={"is_active": False},
    )
    assert mismatch_response.status_code == 404
    assert mismatch_response.json()["detail"] == (
        "Phone number 'pn-phone-status-scope-b' for WABA 'waba-phone-status-scope-a' "
        "and account 'meta-account-phone-status-scope-a' was not found."
    )


def test_update_account_runtime_status_reflects_in_meta_views(client: TestClient) -> None:
    create_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-account-status-2",
            "display_name": "Brand Status 2",
            "meta_business_portfolio_id": "biz-status-2",
            "waba_id": "waba-status-2",
            "access_token": "token-status-2",
            "verify_token": "verify-status-2",
            "app_secret": "secret-status-2",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-status-2",
                    "display_phone_number": "+1 555 000 0202",
                    "verified_name": "Brand Status Secondary",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert create_response.status_code == 200
    assert create_response.json()["account_is_active"] is True

    deactivate_account_response = client.patch(
        "/api/meta/accounts/meta-account-status-2/status",
        json={"is_active": False},
    )
    assert deactivate_account_response.status_code == 200
    assert deactivate_account_response.json()["account_id"] == "meta-account-status-2"
    assert deactivate_account_response.json()["is_active"] is False
    assert deactivate_account_response.json()["wabas"][0]["account_is_active"] is False
    assert "account_inactive" in deactivate_account_response.json()["wabas"][0]["blocking_reasons"]

    list_accounts_response = client.get("/api/meta/accounts")
    assert list_accounts_response.status_code == 200
    account_rows = [
        item
        for item in list_accounts_response.json()
        if item["account_id"] == "meta-account-status-2"
    ]
    assert len(account_rows) == 1
    assert account_rows[0]["account_is_active"] is False
    assert "account_inactive" in account_rows[0]["blocking_reasons"]

    phone_numbers_response = client.get(
        "/api/meta/accounts/meta-account-status-2/wabas/waba-status-2/phone-numbers"
    )
    assert phone_numbers_response.status_code == 200
    assert phone_numbers_response.json()[0]["account_is_active"] is False
    assert "account_inactive" in phone_numbers_response.json()[0]["blocking_reasons"]

    audit_logs_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-account-status-2",
            "action": "account_status_updated",
            "target_type": "account",
            "target_id": "meta-account-status-2",
            "limit": 10,
        },
    )
    assert audit_logs_response.status_code == 200
    audit_logs = audit_logs_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"]["is_active"] is False


def test_subscribe_meta_account_webhook(client: TestClient) -> None:
    client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-account-2",
            "display_name": "Brand B",
            "meta_business_portfolio_id": "biz-portfolio-2",
            "waba_id": "waba-2",
            "access_token": "token-456",
            "token_source": "system_user",
            "phone_numbers": [],
        },
    )

    response = client.post(
        "/api/meta/accounts/meta-account-2/wabas/waba-2/webhook-subscription",
        json={
            "callback_url": "https://example.com/webhook",
            "verify_token": "verify-123",
            "app_id": "app-123",
        },
    )

    assert response.status_code == 200
    assert response.json()["webhook_subscribed"] is True
    assert response.json()["webhook_subscription_status"] == "remote_subscribed"
    assert response.json()["webhook_callback_url"] == "https://example.com/webhook"

    all_phone_numbers_response = client.get("/api/meta/accounts/phone-numbers")
    assert all_phone_numbers_response.status_code == 200
    phone_numbers = all_phone_numbers_response.json()
    assert phone_numbers == []


def test_subscribe_meta_account_webhook_rejects_verify_token_reuse_across_wabas(
    client: TestClient,
) -> None:
    owner_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-webhook-verify-owner-a",
            "display_name": "Webhook Verify Owner A",
            "meta_business_portfolio_id": "biz-webhook-verify-owner-a",
            "waba_id": "waba-webhook-verify-owner-a",
            "access_token": "token-webhook-verify-owner-a",
            "verify_token": "verify-webhook-shared-conflict",
            "app_secret": "secret-webhook-verify-owner-a",
            "token_source": "system_user",
            "phone_numbers": [],
        },
    )
    assert owner_response.status_code == 200

    candidate_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-webhook-verify-owner-b",
            "display_name": "Webhook Verify Owner B",
            "meta_business_portfolio_id": "biz-webhook-verify-owner-b",
            "waba_id": "waba-webhook-verify-owner-b",
            "access_token": "token-webhook-verify-owner-b",
            "app_secret": "secret-webhook-verify-owner-b",
            "token_source": "system_user",
            "phone_numbers": [],
        },
    )
    assert candidate_response.status_code == 200

    subscribe_response = client.post(
        "/api/meta/accounts/meta-webhook-verify-owner-b/wabas/waba-webhook-verify-owner-b/webhook-subscription",
        json={
            "callback_url": "https://example.com/webhook-verify-owner-b",
            "verify_token": "verify-webhook-shared-conflict",
            "app_id": "app-webhook-verify-owner-b",
        },
    )

    assert subscribe_response.status_code == 409
    assert "already used by WABA 'waba-webhook-verify-owner-a'" in subscribe_response.json()["detail"]


def test_subscribe_meta_account_webhook_rejects_shared_callback_with_different_app_secrets(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    shared_callback_url = "https://example.com/webhooks/whatsapp"

    for account_id, display_name, portfolio_id, waba_id, verify_token, app_secret in (
        (
            "meta-webhook-signature-owner-a",
            "Webhook Signature Owner A",
            "biz-webhook-signature-owner-a",
            "waba-webhook-signature-owner-a",
            "verify-webhook-signature-owner-a",
            "secret-webhook-signature-owner-a",
        ),
        (
            "meta-webhook-signature-owner-b",
            "Webhook Signature Owner B",
            "biz-webhook-signature-owner-b",
            "waba-webhook-signature-owner-b",
            "verify-webhook-signature-owner-b",
            "secret-webhook-signature-owner-b",
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
                "verify_token": verify_token,
                "app_secret": app_secret,
                "token_source": "system_user",
                "phone_numbers": [],
            },
        )
        assert create_response.status_code == 200

    first_subscribe_response = client.post(
        "/api/meta/accounts/meta-webhook-signature-owner-a/wabas/waba-webhook-signature-owner-a/webhook-subscription",
        json={"callback_url": shared_callback_url},
    )
    assert first_subscribe_response.status_code == 200, first_subscribe_response.text

    conflicting_response = client.post(
        "/api/meta/accounts/meta-webhook-signature-owner-b/wabas/waba-webhook-signature-owner-b/webhook-subscription",
        json={"callback_url": shared_callback_url},
    )
    assert conflicting_response.status_code == 409
    assert_webhook_signature_conflict(str(conflicting_response.json()["detail"]))

    session = db_session_factory()
    try:
        stored_rows = (
            session.query(WebhookSubscription)
            .filter(WebhookSubscription.callback_url == shared_callback_url)
            .order_by(WebhookSubscription.account_id.asc(), WebhookSubscription.waba_id.asc())
            .all()
        )
    finally:
        session.close()

    assert len(stored_rows) == 1
    assert stored_rows[0].account_id == "meta-webhook-signature-owner-a"
    assert stored_rows[0].waba_id == "waba-webhook-signature-owner-a"


def test_subscribe_meta_account_webhook_allows_shared_callback_with_same_app_secret(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    shared_callback_url = "https://example.com/webhooks/whatsapp"
    shared_app_secret = "secret-webhook-signature-shared"

    for account_id, display_name, portfolio_id, waba_id, verify_token in (
        (
            "meta-webhook-signature-shared-a",
            "Webhook Signature Shared A",
            "biz-webhook-signature-shared-a",
            "waba-webhook-signature-shared-a",
            "verify-webhook-signature-shared-a",
        ),
        (
            "meta-webhook-signature-shared-b",
            "Webhook Signature Shared B",
            "biz-webhook-signature-shared-b",
            "waba-webhook-signature-shared-b",
            "verify-webhook-signature-shared-b",
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
                "verify_token": verify_token,
                "app_secret": shared_app_secret,
                "token_source": "system_user",
                "phone_numbers": [],
            },
        )
        assert create_response.status_code == 200

    first_subscribe_response = client.post(
        "/api/meta/accounts/meta-webhook-signature-shared-a/wabas/waba-webhook-signature-shared-a/webhook-subscription",
        json={"callback_url": shared_callback_url},
    )
    assert first_subscribe_response.status_code == 200, first_subscribe_response.text

    second_subscribe_response = client.post(
        "/api/meta/accounts/meta-webhook-signature-shared-b/wabas/waba-webhook-signature-shared-b/webhook-subscription",
        json={"callback_url": shared_callback_url},
    )
    assert second_subscribe_response.status_code == 200, second_subscribe_response.text

    session = db_session_factory()
    try:
        stored_rows = (
            session.query(WebhookSubscription)
            .filter(WebhookSubscription.callback_url == shared_callback_url)
            .order_by(WebhookSubscription.account_id.asc(), WebhookSubscription.waba_id.asc())
            .all()
        )
    finally:
        session.close()

    assert len(stored_rows) == 2
    assert [(row.account_id, row.waba_id) for row in stored_rows] == [
        ("meta-webhook-signature-shared-a", "waba-webhook-signature-shared-a"),
        ("meta-webhook-signature-shared-b", "waba-webhook-signature-shared-b"),
    ]


def test_subscribe_meta_account_webhook_rejects_root_callback_query_variants_with_different_app_secrets(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    shared_root_callback_base = "https://example.com/webhooks/whatsapp"

    for account_id, display_name, portfolio_id, waba_id, verify_token, app_secret in (
        (
            "meta-webhook-signature-query-owner-a",
            "Webhook Signature Query Owner A",
            "biz-webhook-signature-query-owner-a",
            "waba-webhook-signature-query-owner-a",
            "verify-webhook-signature-query-owner-a",
            "secret-webhook-signature-query-owner-a",
        ),
        (
            "meta-webhook-signature-query-owner-b",
            "Webhook Signature Query Owner B",
            "biz-webhook-signature-query-owner-b",
            "waba-webhook-signature-query-owner-b",
            "verify-webhook-signature-query-owner-b",
            "secret-webhook-signature-query-owner-b",
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
                "verify_token": verify_token,
                "app_secret": app_secret,
                "token_source": "system_user",
                "phone_numbers": [],
            },
        )
        assert create_response.status_code == 200

    first_subscribe_response = client.post(
        "/api/meta/accounts/meta-webhook-signature-query-owner-a/"
        "wabas/waba-webhook-signature-query-owner-a/webhook-subscription",
        json={"callback_url": f"{shared_root_callback_base}?tenant=alpha"},
    )
    assert first_subscribe_response.status_code == 200, first_subscribe_response.text

    conflicting_response = client.post(
        "/api/meta/accounts/meta-webhook-signature-query-owner-b/"
        "wabas/waba-webhook-signature-query-owner-b/webhook-subscription",
        json={"callback_url": f"{shared_root_callback_base}?tenant=beta"},
    )
    assert conflicting_response.status_code == 409
    assert_webhook_signature_conflict(str(conflicting_response.json()["detail"]))
    assert shared_root_callback_base in str(conflicting_response.json()["detail"])

    session = db_session_factory()
    try:
        stored_rows = (
            session.query(WebhookSubscription)
            .filter(
                WebhookSubscription.account_id.in_(
                    [
                        "meta-webhook-signature-query-owner-a",
                        "meta-webhook-signature-query-owner-b",
                    ]
                )
            )
            .order_by(WebhookSubscription.account_id.asc(), WebhookSubscription.waba_id.asc())
            .all()
        )
    finally:
        session.close()

    assert len(stored_rows) == 1
    assert stored_rows[0].account_id == "meta-webhook-signature-query-owner-a"
    assert stored_rows[0].callback_url == f"{shared_root_callback_base}?tenant=alpha"


def test_embedded_signup_complete_rejects_shared_callback_with_different_app_secrets(
    client: TestClient,
    override_meta_management_provider,
    db_session_factory: sessionmaker[Session],
) -> None:
    shared_callback_url = "https://example.com/webhooks/whatsapp"
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "META_APP_SECRET": os.environ.get("META_APP_SECRET"),
        "WA_APP_SECRET": os.environ.get("WA_APP_SECRET"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["META_APP_SECRET"] = "secret-webhook-signature-signup-complete-b"
        os.environ["WA_APP_SECRET"] = "secret-webhook-signature-signup-complete-b"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "meta-webhook-signature-signup-complete-a",
                "display_name": "Webhook Signature Signup Complete A",
                "meta_business_portfolio_id": "biz-webhook-signature-signup-complete-a",
                "waba_id": "waba-webhook-signature-signup-complete-a",
                "access_token": "token-meta-webhook-signature-signup-complete-a",
                "verify_token": "verify-webhook-signature-signup-complete-a",
                "app_secret": "secret-webhook-signature-signup-complete-a",
                "token_source": "system_user",
                "phone_numbers": [],
            },
        )
        assert create_response.status_code == 200, create_response.text

        subscribe_response = client.post(
            "/api/meta/accounts/meta-webhook-signature-signup-complete-a/"
            "wabas/waba-webhook-signature-signup-complete-a/webhook-subscription",
            json={"callback_url": shared_callback_url},
        )
        assert subscribe_response.status_code == 200, subscribe_response.text

        signup_response = client.post(
            "/api/meta/accounts/embedded-signup/session",
            json={
                "account_id": "meta-webhook-signature-signup-complete-b",
                "display_name": "Webhook Signature Signup Complete B",
                "redirect_uri": "https://example.com/embedded-signup/webhook-signature-complete",
                "webhook_subscription": {
                    "callback_url": shared_callback_url,
                    "verify_token": "verify-webhook-signature-signup-complete-b",
                    "app_id": "app-webhook-signature-signup-complete-b",
                },
            },
        )
        assert signup_response.status_code == 200, signup_response.text
        session_id = signup_response.json()["session_id"]

        conflicting_response = client.post(
            f"/api/meta/accounts/embedded-signup/session/{session_id}/complete",
            json={
                "waba_id": "waba-webhook-signature-signup-complete-b",
                "meta_business_portfolio_id": "biz-webhook-signature-signup-complete-b",
                "phone_number_ids": ["pn-webhook-signature-signup-complete-b"],
                "system_user_access_token": "token-webhook-signature-signup-complete-b",
            },
        )
        assert conflicting_response.status_code == 409
        assert_webhook_signature_conflict(str(conflicting_response.json()["detail"]))

        sessions_response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={"account_id": "meta-webhook-signature-signup-complete-b"},
        )
        assert sessions_response.status_code == 200, sessions_response.text
        session_payload = sessions_response.json()[0]
        assert session_payload["session_id"] == session_id
        assert session_payload["status"] == "created"
        assert session_payload["completion_stage"] == "pending_callback"

        with db_session_factory() as session:
            created_wabas = session.query(WhatsAppBusinessAccount).filter(
                WhatsAppBusinessAccount.account_id == "meta-webhook-signature-signup-complete-b"
            ).all()
            created_subscriptions = session.query(WebhookSubscription).filter(
                WebhookSubscription.account_id == "meta-webhook-signature-signup-complete-b"
            ).all()

        assert created_wabas == []
        assert created_subscriptions == []
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
        get_settings.cache_clear()


def test_embedded_signup_callback_rejects_shared_callback_with_different_app_secrets(
    client: TestClient,
    override_meta_management_provider,
    db_session_factory: sessionmaker[Session],
) -> None:
    shared_callback_url = "https://example.com/webhooks/whatsapp"
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "META_APP_SECRET": os.environ.get("META_APP_SECRET"),
        "WA_APP_SECRET": os.environ.get("WA_APP_SECRET"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["META_APP_SECRET"] = "secret-webhook-signature-signup-callback-b"
        os.environ["WA_APP_SECRET"] = "secret-webhook-signature-signup-callback-b"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "meta-webhook-signature-signup-callback-a",
                "display_name": "Webhook Signature Signup Callback A",
                "meta_business_portfolio_id": "biz-webhook-signature-signup-callback-a",
                "waba_id": "waba-webhook-signature-signup-callback-a",
                "access_token": "token-meta-webhook-signature-signup-callback-a",
                "verify_token": "verify-webhook-signature-signup-callback-a",
                "app_secret": "secret-webhook-signature-signup-callback-a",
                "token_source": "system_user",
                "phone_numbers": [],
            },
        )
        assert create_response.status_code == 200, create_response.text

        subscribe_response = client.post(
            "/api/meta/accounts/meta-webhook-signature-signup-callback-a/"
            "wabas/waba-webhook-signature-signup-callback-a/webhook-subscription",
            json={"callback_url": shared_callback_url},
        )
        assert subscribe_response.status_code == 200, subscribe_response.text

        signup_response = client.post(
            "/api/meta/accounts/embedded-signup/session",
            json={
                "account_id": "meta-webhook-signature-signup-callback-b",
                "display_name": "Webhook Signature Signup Callback B",
                "redirect_uri": "https://example.com/embedded-signup/webhook-signature-callback",
                "webhook_subscription": {
                    "callback_url": shared_callback_url,
                    "verify_token": "verify-webhook-signature-signup-callback-b",
                    "app_id": "app-webhook-signature-signup-callback-b",
                },
            },
        )
        assert signup_response.status_code == 200, signup_response.text
        signup_payload = signup_response.json()
        session_id = signup_payload["session_id"]
        launch_state = signup_payload["launch_context"]["state"]

        conflicting_response = client.post(
            f"/webhooks/meta/embedded-signup/session/{session_id}",
            json={
                "status": "completed",
                "state": launch_state,
                "waba_id": "waba-webhook-signature-signup-callback-b",
                "meta_business_portfolio_id": "biz-webhook-signature-signup-callback-b",
                "phone_number_ids": ["pn-webhook-signature-signup-callback-b"],
                "authorization_code": "code-webhook-signature-signup-callback-b",
                "raw_payload": {"source": "callback-shared-signature-conflict"},
            },
        )
        assert conflicting_response.status_code == 409
        assert_webhook_signature_conflict(str(conflicting_response.json()["detail"]))

        sessions_response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={"account_id": "meta-webhook-signature-signup-callback-b"},
        )
        assert sessions_response.status_code == 200, sessions_response.text
        session_payload = sessions_response.json()[0]
        assert session_payload["session_id"] == session_id
        assert session_payload["status"] == "created"
        assert session_payload["completion_stage"] == "pending_callback"

        with db_session_factory() as session:
            created_wabas = session.query(WhatsAppBusinessAccount).filter(
                WhatsAppBusinessAccount.account_id == "meta-webhook-signature-signup-callback-b"
            ).all()
            created_subscriptions = session.query(WebhookSubscription).filter(
                WebhookSubscription.account_id == "meta-webhook-signature-signup-callback-b"
            ).all()

        assert created_wabas == []
        assert created_subscriptions == []
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_subscribe_meta_account_webhook_keeps_whatsapp_mode_account_pending_until_verification(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_messaging_provider = os.environ.get("MESSAGING_PROVIDER")

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "meta-account-whatsapp-mode",
                "display_name": "Brand WhatsApp Mode",
                "meta_business_portfolio_id": "biz-whatsapp-mode",
                "waba_id": "waba-whatsapp-mode",
                "access_token": "token-whatsapp-mode",
                "verify_token": "verify-whatsapp-mode",
                "app_secret": "secret-whatsapp-mode",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-whatsapp-mode",
                        "display_phone_number": "+1 555 000 3001",
                        "verified_name": "Brand WhatsApp Mode",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert create_response.status_code == 200

        subscribe_response = client.post(
            "/api/meta/accounts/meta-account-whatsapp-mode/wabas/waba-whatsapp-mode/webhook-subscription",
            json={"callback_url": "https://example.com/whatsapp-mode/webhook"},
        )

        assert subscribe_response.status_code == 200
        payload = subscribe_response.json()
        assert payload["webhook_subscribed"] is True
        assert payload["webhook_subscription_status"] == "remote_subscribed"
        assert payload["webhook_callback_url"] == "https://example.com/whatsapp-mode/webhook"
        assert payload["ready_for_webhook_delivery"] is False
        assert payload["ready_for_outbound_messages"] is True
        assert payload["ready_for_meta_activation"] is False
        assert payload["webhook_verification_status"] == "pending"
        assert payload["webhook_runtime_status"] == "pending"
        assert payload["blocking_reasons"] == ["webhook_not_ready"]

        phone_numbers_response = client.get(
            "/api/meta/accounts/meta-account-whatsapp-mode/wabas/waba-whatsapp-mode/phone-numbers"
        )
        assert phone_numbers_response.status_code == 200
        phone_numbers = phone_numbers_response.json()
        assert len(phone_numbers) == 1
        assert phone_numbers[0]["phone_number_id"] == "pn-whatsapp-mode"
        assert phone_numbers[0]["webhook_subscription_status"] == "remote_subscribed"
        assert phone_numbers[0]["ready_for_webhook_delivery"] is False
        assert phone_numbers[0]["ready_for_outbound_messages"] is True
        assert phone_numbers[0]["ready_for_meta_activation"] is False
        assert phone_numbers[0]["blocking_reasons"] == ["webhook_not_ready"]

        accounts_response = client.get(
            "/api/meta/accounts",
            params={"account_id": "meta-account-whatsapp-mode"},
        )
        assert accounts_response.status_code == 200
        accounts = accounts_response.json()
        assert len(accounts) == 1
        assert accounts[0]["account_id"] == "meta-account-whatsapp-mode"
        assert accounts[0]["waba_id"] == "waba-whatsapp-mode"
        assert accounts[0]["webhook_subscription_status"] == "remote_subscribed"
        assert accounts[0]["ready_for_webhook_delivery"] is False
        assert accounts[0]["ready_for_outbound_messages"] is True
        assert accounts[0]["ready_for_meta_activation"] is False
        assert accounts[0]["webhook_verification_status"] == "pending"
        assert accounts[0]["webhook_runtime_status"] == "pending"
        assert accounts[0]["phone_number_count"] == 1
        assert accounts[0]["registered_phone_number_count"] == 1
        assert accounts[0]["blocking_reasons"] == ["webhook_not_ready"]

        blocked_delivery_accounts_response = client.get(
            "/api/meta/accounts",
            params={"ready_for_webhook_delivery": False},
        )
        assert blocked_delivery_accounts_response.status_code == 200
        assert "meta-account-whatsapp-mode" in [
            item["account_id"] for item in blocked_delivery_accounts_response.json()
        ]

        pending_activation_phone_numbers_response = client.get(
            "/api/meta/accounts/phone-numbers",
            params={"ready_for_meta_activation": False},
        )
        assert pending_activation_phone_numbers_response.status_code == 200
        assert "pn-whatsapp-mode" in [
            item["phone_number_id"] for item in pending_activation_phone_numbers_response.json()
        ]

        verify_response = client.get(
            "/webhooks/whatsapp/meta-account-whatsapp-mode/wabas/waba-whatsapp-mode",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-whatsapp-mode",
                "hub.challenge": "challenge-whatsapp-mode",
            },
        )
        assert verify_response.status_code == 200

        verified_accounts_response = client.get(
            "/api/meta/accounts",
            params={"account_id": "meta-account-whatsapp-mode"},
        )
        assert verified_accounts_response.status_code == 200
        verified_accounts = verified_accounts_response.json()
        assert verified_accounts[0]["ready_for_webhook_delivery"] is True
        assert verified_accounts[0]["ready_for_meta_activation"] is True
        assert verified_accounts[0]["webhook_verification_status"] == "verified"
        assert verified_accounts[0]["blocking_reasons"] == []
    finally:
        if original_messaging_provider is None:
            os.environ.pop("MESSAGING_PROVIDER", None)
        else:
            os.environ["MESSAGING_PROVIDER"] = original_messaging_provider
        get_settings.cache_clear()


def test_account_and_phone_readiness_follow_current_subscription_when_webhook_subscribed_flag_drifts(
    client: TestClient,
    override_meta_management_provider,
    db_session_factory: sessionmaker[Session],
) -> None:
    original_messaging_provider = os.environ.get("MESSAGING_PROVIDER")

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "meta-account-webhook-flag-drift",
                "display_name": "Brand Webhook Flag Drift",
                "meta_business_portfolio_id": "biz-webhook-flag-drift",
                "waba_id": "waba-webhook-flag-drift",
                "access_token": "token-webhook-flag-drift",
                "verify_token": "verify-webhook-flag-drift",
                "app_secret": "secret-webhook-flag-drift",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-webhook-flag-drift",
                        "display_phone_number": "+1 555 000 3002",
                        "verified_name": "Brand Webhook Flag Drift",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert create_response.status_code == 200

        subscribe_response = client.post(
            "/api/meta/accounts/meta-account-webhook-flag-drift/"
            "wabas/waba-webhook-flag-drift/webhook-subscription",
            json={"callback_url": "https://example.com/webhook-flag-drift"},
        )
        assert subscribe_response.status_code == 200

        verify_response = client.get(
            "/webhooks/whatsapp/meta-account-webhook-flag-drift/wabas/waba-webhook-flag-drift",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-webhook-flag-drift",
                "hub.challenge": "challenge-webhook-flag-drift",
            },
        )
        assert verify_response.status_code == 200

        with db_session_factory() as session:
            waba_account = session.query(WhatsAppBusinessAccount).filter(
                WhatsAppBusinessAccount.account_id == "meta-account-webhook-flag-drift",
                WhatsAppBusinessAccount.waba_id == "waba-webhook-flag-drift",
            ).one()
            assert waba_account.webhook_subscribed is True
            waba_account.webhook_subscribed = False
            session.add(waba_account)
            session.commit()

        accounts_response = client.get(
            "/api/meta/accounts",
            params={
                "account_id": "meta-account-webhook-flag-drift",
                "ready_for_webhook_delivery": True,
                "ready_for_meta_activation": True,
            },
        )
        assert accounts_response.status_code == 200
        accounts = accounts_response.json()
        assert len(accounts) == 1
        assert accounts[0]["webhook_subscribed"] is True
        assert accounts[0]["webhook_subscription_status"] == "remote_subscribed"
        assert accounts[0]["ready_for_webhook_delivery"] is True
        assert accounts[0]["ready_for_meta_activation"] is True
        assert accounts[0]["blocking_reasons"] == []

        phone_numbers_response = client.get(
            "/api/meta/accounts/phone-numbers",
            params={
                "account_id": "meta-account-webhook-flag-drift",
                "ready_for_webhook_delivery": True,
                "ready_for_meta_activation": True,
            },
        )
        assert phone_numbers_response.status_code == 200
        phone_numbers = phone_numbers_response.json()
        assert len(phone_numbers) == 1
        assert phone_numbers[0]["phone_number_id"] == "pn-webhook-flag-drift"
        assert phone_numbers[0]["webhook_subscribed"] is True
        assert phone_numbers[0]["webhook_subscription_status"] == "remote_subscribed"
        assert phone_numbers[0]["ready_for_webhook_delivery"] is True
        assert phone_numbers[0]["ready_for_meta_activation"] is True
        assert phone_numbers[0]["blocking_reasons"] == []
    finally:
        if original_messaging_provider is None:
            os.environ.pop("MESSAGING_PROVIDER", None)
        else:
            os.environ["MESSAGING_PROVIDER"] = original_messaging_provider
        get_settings.cache_clear()


def test_embedded_signup_session_create_persists_webhook_subscription_context(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-embedded-webhook-context",
            "display_name": "Embedded Webhook Context",
            "redirect_uri": "https://example.com/embedded-signup/context",
            "webhook_subscription": {
                "callback_url": "https://example.com/embedded-signup/context/webhook",
                "verify_token": "verify-embedded-context",
                "app_id": "app-embedded-context",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "created"
    assert payload["completion_stage"] == "pending_callback"
    assert payload["webhook_callback_url"] == "https://example.com/embedded-signup/context/webhook"
    assert payload["webhook_verify_token_present"] is True
    assert payload["webhook_app_id"] == "app-embedded-context"
    assert payload["webhook_subscription_status"] is None
    assert payload["ready_for_webhook_delivery"] is False
    assert payload["ready_for_meta_activation"] is False

    list_response = client.get(
        "/api/meta/accounts/embedded-signup/sessions",
        params={"account_id": "meta-account-embedded-webhook-context"},
    )
    assert list_response.status_code == 200
    rows = list_response.json()
    assert len(rows) == 1
    assert rows[0]["session_id"] == payload["session_id"]
    assert rows[0]["webhook_callback_url"] == "https://example.com/embedded-signup/context/webhook"
    assert rows[0]["webhook_verify_token_present"] is True
    assert rows[0]["webhook_app_id"] == "app-embedded-context"


def test_embedded_signup_complete_uses_session_webhook_context_and_marks_activation_pending(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    provider = CapturingEmbeddedSignupActivationProvider()
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "WA_APP_SECRET": os.environ.get("WA_APP_SECRET"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["WA_APP_SECRET"] = "embedded-activation-secret"
        get_settings.cache_clear()
        override_meta_management_provider(client, provider)

        create_response = client.post(
            "/api/meta/accounts/embedded-signup/session",
            json={
                "account_id": "meta-account-embedded-activation-complete",
                "display_name": "Embedded Activation Complete",
                "redirect_uri": "https://example.com/embedded-signup/activation-complete",
                "webhook_subscription": {
                    "callback_url": "https://example.com/embedded-signup/activation-complete/webhook",
                    "verify_token": "verify-embedded-activation-complete",
                    "app_id": "app-embedded-activation-complete",
                },
            },
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]

        complete_response = client.post(
            f"/api/meta/accounts/embedded-signup/session/{session_id}/complete",
            json={
                "waba_id": "waba-embedded-activation-complete",
                "meta_business_portfolio_id": "biz-embedded-activation-complete",
                "phone_number_ids": ["pn-embedded-activation-complete-request"],
                "system_user_access_token": "token-embedded-activation-complete",
            },
        )

        assert complete_response.status_code == 200
        assert len(provider.webhook_subscription_commands) == 1
        webhook_command = provider.webhook_subscription_commands[0]
        assert webhook_command.account_id == "meta-account-embedded-activation-complete"
        assert webhook_command.waba_id == "waba-embedded-activation-complete"
        assert (
            webhook_command.callback_url
            == "https://example.com/embedded-signup/activation-complete/webhook"
        )
        assert webhook_command.verify_token == "verify-embedded-activation-complete"
        assert webhook_command.app_id == "app-embedded-activation-complete"

        assert_embedded_signup_webhook_activation_pending(
            client=client,
            session_payload=complete_response.json(),
            account_id="meta-account-embedded-activation-complete",
            waba_id="waba-embedded-activation-complete",
            callback_url="https://example.com/embedded-signup/activation-complete/webhook",
            app_id="app-embedded-activation-complete",
            expected_event_source="operator",
        )
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_embedded_signup_callback_complete_uses_session_webhook_context_and_marks_activation_pending(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    provider = CapturingEmbeddedSignupActivationProvider()
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "WA_APP_SECRET": os.environ.get("WA_APP_SECRET"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["WA_APP_SECRET"] = "embedded-callback-secret"
        get_settings.cache_clear()
        override_meta_management_provider(client, provider)

        create_response = client.post(
            "/api/meta/accounts/embedded-signup/session",
            json={
                "account_id": "meta-account-embedded-activation-callback",
                "display_name": "Embedded Activation Callback",
                "redirect_uri": "https://example.com/embedded-signup/activation-callback",
                "webhook_subscription": {
                    "callback_url": "https://example.com/embedded-signup/activation-callback/webhook",
                    "verify_token": "verify-embedded-activation-callback",
                    "app_id": "app-embedded-activation-callback",
                },
            },
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]

        callback_response = client.post(
            f"/api/meta/accounts/embedded-signup/session/{session_id}/callback",
            json={
                "status": "completed",
                "waba_id": "waba-embedded-activation-callback",
                "meta_business_portfolio_id": "biz-embedded-activation-callback",
                "phone_number_ids": ["pn-embedded-activation-callback-request"],
                "system_user_access_token": "token-embedded-activation-callback",
            },
        )

        assert callback_response.status_code == 200
        assert callback_response.json()["event_source"] == "provider_callback"
        assert len(provider.webhook_subscription_commands) == 1
        webhook_command = provider.webhook_subscription_commands[0]
        assert webhook_command.account_id == "meta-account-embedded-activation-callback"
        assert webhook_command.waba_id == "waba-embedded-activation-callback"
        assert (
            webhook_command.callback_url
            == "https://example.com/embedded-signup/activation-callback/webhook"
        )
        assert webhook_command.verify_token == "verify-embedded-activation-callback"
        assert webhook_command.app_id == "app-embedded-activation-callback"

        assert_embedded_signup_webhook_activation_pending(
            client=client,
            session_payload=callback_response.json(),
            account_id="meta-account-embedded-activation-callback",
            waba_id="waba-embedded-activation-callback",
            callback_url="https://example.com/embedded-signup/activation-callback/webhook",
            app_id="app-embedded-activation-callback",
            expected_event_source="provider_callback",
        )
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_embedded_signup_session_keeps_created_webhook_subscription_snapshot_after_later_resubscribe(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    provider = CapturingEmbeddedSignupActivationProvider()
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "WA_APP_SECRET": os.environ.get("WA_APP_SECRET"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["WA_APP_SECRET"] = "embedded-stable-subscription-secret"
        get_settings.cache_clear()
        override_meta_management_provider(client, provider)

        create_response = client.post(
            "/api/meta/accounts/embedded-signup/session",
            json={
                "account_id": "meta-account-embedded-stable-subscription",
                "display_name": "Embedded Stable Subscription",
                "redirect_uri": "https://example.com/embedded-signup/stable-subscription",
                "webhook_subscription": {
                    "callback_url": "https://example.com/embedded-signup/stable-subscription/original",
                    "verify_token": "verify-embedded-stable-subscription",
                    "app_id": "app-embedded-stable-subscription",
                },
            },
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]

        complete_response = client.post(
            f"/api/meta/accounts/embedded-signup/session/{session_id}/complete",
            json={
                "waba_id": "waba-embedded-stable-subscription",
                "meta_business_portfolio_id": "biz-embedded-stable-subscription",
                "phone_number_ids": ["pn-embedded-stable-subscription-1"],
                "system_user_access_token": "token-embedded-stable-subscription",
            },
        )
        assert complete_response.status_code == 200
        original_session_payload = complete_response.json()
        assert original_session_payload["webhook_callback_url"] == (
            "https://example.com/embedded-signup/stable-subscription/original"
        )
        assert original_session_payload["webhook_app_id"] == "app-embedded-stable-subscription"

        resubscribe_response = client.post(
            "/api/meta/accounts/meta-account-embedded-stable-subscription/"
            "wabas/waba-embedded-stable-subscription/webhook-subscription",
            json={
                "callback_url": "https://example.com/embedded-signup/stable-subscription/later",
                "verify_token": "verify-embedded-stable-subscription-later",
                "app_id": "app-embedded-stable-subscription-later",
            },
        )
        assert resubscribe_response.status_code == 200

        sessions_response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={"account_id": "meta-account-embedded-stable-subscription"},
        )
        assert sessions_response.status_code == 200
        sessions = sessions_response.json()
        assert len(sessions) == 1
        session_payload = sessions[0]
        assert session_payload["session_id"] == session_id
        assert session_payload["webhook_callback_url"] == (
            "https://example.com/embedded-signup/stable-subscription/original"
        )
        assert session_payload["webhook_app_id"] == "app-embedded-stable-subscription"
        assert session_payload["webhook_subscription_status"] == "remote_subscribed"

        subscriptions_response = client.get(
            "/api/meta/accounts/webhook-subscriptions",
            params={"account_id": "meta-account-embedded-stable-subscription"},
        )
        assert subscriptions_response.status_code == 200
        callback_urls = {item["callback_url"] for item in subscriptions_response.json()}
        assert callback_urls == {
            "https://example.com/embedded-signup/stable-subscription/original",
            "https://example.com/embedded-signup/stable-subscription/later",
        }
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_embedded_signup_session_exposes_layered_snapshot_and_current_waba_state_after_resubscribe(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "META_APP_SECRET": os.environ.get("META_APP_SECRET"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["META_APP_SECRET"] = "embedded-snapshot-status-secret"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/embedded-signup/session",
            json={
                "account_id": "meta-account-embedded-snapshot-status",
                "display_name": "Embedded Snapshot Status",
                "redirect_uri": "https://example.com/embedded-signup/snapshot-status",
                "webhook_subscription": {
                    "callback_url": "https://example.com/embedded-signup/snapshot-status/original",
                    "verify_token": "verify-embedded-snapshot-status",
                    "app_id": "app-embedded-snapshot-status",
                },
            },
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]

        complete_response = client.post(
            f"/api/meta/accounts/embedded-signup/session/{session_id}/complete",
            json={
                "waba_id": "waba-embedded-snapshot-status",
                "meta_business_portfolio_id": "biz-embedded-snapshot-status",
                "phone_number_ids": ["pn-embedded-snapshot-status-1"],
                "system_user_access_token": "token-embedded-snapshot-status",
            },
        )
        assert complete_response.status_code == 200

        verify_response = client.get(
            "/webhooks/whatsapp/meta-account-embedded-snapshot-status/"
            "wabas/waba-embedded-snapshot-status",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-embedded-snapshot-status",
                "hub.challenge": "challenge-embedded-snapshot-status",
            },
        )
        assert verify_response.status_code == 200

        resubscribe_response = client.post(
            "/api/meta/accounts/meta-account-embedded-snapshot-status/"
            "wabas/waba-embedded-snapshot-status/webhook-subscription",
            json={
                "callback_url": "https://example.com/embedded-signup/snapshot-status/later",
                "verify_token": "verify-embedded-snapshot-status-later",
                "app_id": "app-embedded-snapshot-status-later",
            },
        )
        assert resubscribe_response.status_code == 200

        sessions_response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={"account_id": "meta-account-embedded-snapshot-status"},
        )
        assert sessions_response.status_code == 200
        sessions = sessions_response.json()
        assert len(sessions) == 1
        session_payload = sessions[0]
        session_snapshot = session_payload["session_snapshot"]
        current_waba_state = session_payload["current_waba_state"]

        assert session_payload["session_id"] == session_id
        assert session_payload["webhook_callback_url"] == (
            "https://example.com/embedded-signup/snapshot-status/original"
        )
        assert session_snapshot == {
            "waba_id": "waba-embedded-snapshot-status",
            "meta_business_portfolio_id": "biz-embedded-snapshot-status",
            "linked_phone_number_ids": ["pn-embedded-snapshot-status-1"],
            "webhook_callback_url": "https://example.com/embedded-signup/snapshot-status/original",
            "webhook_verify_token_present": True,
            "webhook_app_secret_present": True,
            "webhook_app_id": "app-embedded-snapshot-status",
            "webhook_subscription_status": "remote_subscribed",
            "webhook_verification_status": "pending",
            "webhook_runtime_status": "pending",
            "ready_for_webhook_delivery": False,
            "ready_for_outbound_messages": False,
            "ready_for_meta_activation": False,
            "webhook_blocking_reasons": ["webhook_not_ready"],
        }
        assert current_waba_state == {
            "waba_id": "waba-embedded-snapshot-status",
            "meta_business_portfolio_id": "biz-embedded-snapshot-status",
            "webhook_callback_url": "https://example.com/embedded-signup/snapshot-status/later",
            "webhook_verify_token_present": True,
            "webhook_app_secret_present": True,
            "webhook_app_id": "app-embedded-snapshot-status-later",
            "webhook_subscription_status": "remote_subscribed",
            "webhook_verification_status": "pending",
            "webhook_runtime_status": "pending",
            "ready_for_webhook_delivery": False,
            "ready_for_outbound_messages": False,
            "ready_for_meta_activation": False,
            "webhook_blocking_reasons": ["webhook_not_ready"],
        }
        assert session_snapshot["webhook_callback_url"] != current_waba_state["webhook_callback_url"]
        assert session_payload["completion_webhook_subscription_status"] == "remote_subscribed"
        assert session_payload["completion_webhook_verification_status"] == "pending"
        assert session_payload["completion_webhook_runtime_status"] == "pending"
        assert session_payload["completion_ready_for_webhook_delivery"] is False
        assert "webhook_not_ready" in session_payload["completion_webhook_blocking_reasons"]
        assert session_payload["session_snapshot"]["webhook_callback_url"] == (
            "https://example.com/embedded-signup/snapshot-status/original"
        )
        assert session_payload["session_snapshot"]["webhook_verification_status"] == "pending"
        assert session_payload["session_snapshot"]["ready_for_webhook_delivery"] is False
        assert session_payload["webhook_verification_status"] == "pending"
        assert session_payload["ready_for_webhook_delivery"] is False
        assert session_payload["current_waba_state"]["webhook_callback_url"] == (
            "https://example.com/embedded-signup/snapshot-status/later"
        )
        assert session_payload["current_waba_state"]["webhook_verification_status"] == "pending"
        assert session_payload["current_waba_state"]["ready_for_webhook_delivery"] is False
        assert session_payload["webhook_callback_url"] == session_snapshot["webhook_callback_url"]
        assert session_payload["webhook_verify_token_present"] == session_snapshot["webhook_verify_token_present"]
        assert session_payload["webhook_app_id"] == session_snapshot["webhook_app_id"]
        assert (
            session_payload["completion_webhook_subscription_status"]
            == session_snapshot["webhook_subscription_status"]
        )
        assert (
            session_payload["completion_webhook_verification_status"]
            == session_snapshot["webhook_verification_status"]
        )
        assert (
            session_payload["completion_webhook_runtime_status"]
            == session_snapshot["webhook_runtime_status"]
        )
        assert (
            session_payload["completion_ready_for_webhook_delivery"]
            == session_snapshot["ready_for_webhook_delivery"]
        )
        assert (
            session_payload["completion_ready_for_outbound_messages"]
            == session_snapshot["ready_for_outbound_messages"]
        )
        assert (
            session_payload["completion_ready_for_meta_activation"]
            == session_snapshot["ready_for_meta_activation"]
        )
        assert (
            session_payload["completion_webhook_blocking_reasons"]
            == session_snapshot["webhook_blocking_reasons"]
        )
        assert session_payload["waba_id"] == current_waba_state["waba_id"]
        assert session_payload["meta_business_portfolio_id"] == current_waba_state["meta_business_portfolio_id"]
        assert (
            session_payload["webhook_subscription_status"]
            == current_waba_state["webhook_subscription_status"]
        )
        assert (
            session_payload["webhook_verification_status"]
            == current_waba_state["webhook_verification_status"]
        )
        assert session_payload["webhook_runtime_status"] == current_waba_state["webhook_runtime_status"]
        assert (
            session_payload["ready_for_webhook_delivery"]
            == current_waba_state["ready_for_webhook_delivery"]
        )
        assert (
            session_payload["ready_for_outbound_messages"]
            == current_waba_state["ready_for_outbound_messages"]
        )
        assert (
            session_payload["ready_for_meta_activation"]
            == current_waba_state["ready_for_meta_activation"]
        )
        assert session_payload["webhook_blocking_reasons"] == current_waba_state["webhook_blocking_reasons"]
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_embedded_signup_session_records_remote_confirmation_in_whatsapp_mode(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_messaging_provider = os.environ.get("MESSAGING_PROVIDER")

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()
        override_meta_management_provider(
            client,
            StubMetaManagementProvider(
                completion_phone_number_ids=["pn-embedded-remote-1", "pn-embedded-remote-2"],
            ),
        )

        create_response = client.post(
            "/api/meta/accounts/embedded-signup/session",
            json={
                "account_id": "meta-account-embedded-remote",
                "display_name": "Brand Embedded Remote",
                "redirect_uri": "https://example.com/embedded-signup/remote",
            },
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]

        complete_response = client.post(
            f"/api/meta/accounts/embedded-signup/session/{session_id}/complete",
            json={
                "waba_id": "waba-embedded-remote",
                "meta_business_portfolio_id": "biz-embedded-remote",
                "phone_number_ids": ["pn-local-placeholder"],
                "setup_session_id": "setup-embedded-remote",
                "system_user_access_token": "token-embedded-remote",
            },
        )
        assert complete_response.status_code == 200
        payload = complete_response.json()
        assert payload["status"] == "completed"
        assert payload["completion_stage"] == "local_waba_linked"
        assert payload["remote_confirmed"] is True
        assert payload["waba_id"] == "waba-embedded-remote"
        assert payload["provider_waba_id"] == "waba-embedded-remote"
        assert payload["meta_business_portfolio_id"] == "biz-embedded-remote"
        assert payload["linked_phone_number_ids"] == [
            "pn-embedded-remote-1",
            "pn-embedded-remote-2",
        ]

        phone_numbers_response = client.get(
            "/api/meta/accounts/meta-account-embedded-remote/wabas/waba-embedded-remote/phone-numbers"
        )
        assert phone_numbers_response.status_code == 200
        assert [item["phone_number_id"] for item in phone_numbers_response.json()] == [
            "pn-embedded-remote-1",
            "pn-embedded-remote-2",
        ]
    finally:
        if original_messaging_provider is None:
            os.environ.pop("MESSAGING_PROVIDER", None)
        else:
            os.environ["MESSAGING_PROVIDER"] = original_messaging_provider
        get_settings.cache_clear()


def test_embedded_signup_session_accepts_authorization_code_without_system_user_token(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_messaging_provider = os.environ.get("MESSAGING_PROVIDER")
    provider = CapturingEmbeddedSignupProvider()

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()
        override_meta_management_provider(client, provider)

        create_response = client.post(
            "/api/meta/accounts/embedded-signup/session",
            json={
                "account_id": "meta-account-code-only",
                "display_name": "Brand Code Only",
                "redirect_uri": "https://example.com/embedded-signup/code-only",
            },
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]

        complete_response = client.post(
            f"/api/meta/accounts/embedded-signup/session/{session_id}/complete",
            json={
                "waba_id": "waba-code-only",
                "meta_business_portfolio_id": "biz-code-only",
                "setup_session_id": "setup-code-only",
                "authorization_code": "auth-code-only",
            },
        )

        assert complete_response.status_code == 200
        payload = complete_response.json()
        assert payload["status"] == "completed"
        assert payload["completion_stage"] == "local_waba_linked"
        assert payload["remote_confirmed"] is True
        assert payload["waba_id"] == "waba-code-only"
        assert payload["provider_waba_id"] == "waba-code-only"
        assert payload["meta_business_portfolio_id"] == "biz-code-only"
        assert payload["linked_phone_number_ids"] == ["pn-code-only-1"]
        assert payload["authorization_code_present"] is True
        assert payload["system_user_access_token_present"] is True

        assert provider.last_completion_payload is not None
        assert provider.last_completion_payload.account_id == "meta-account-code-only"
        assert provider.last_completion_payload.session_id == session_id
        assert provider.last_completion_payload.redirect_uri == (
            "https://example.com/embedded-signup/code-only"
        )
        assert provider.last_completion_payload.requested_waba_id == "waba-code-only"
        assert provider.last_completion_payload.meta_business_portfolio_id == "biz-code-only"
        assert provider.last_completion_payload.authorization_code == "auth-code-only"
        assert provider.last_completion_payload.system_user_access_token is None
        assert provider.last_completion_payload.phone_number_ids == []

        phone_numbers_response = client.get(
            "/api/meta/accounts/meta-account-code-only/wabas/waba-code-only/phone-numbers"
        )
        assert phone_numbers_response.status_code == 200
        assert [item["phone_number_id"] for item in phone_numbers_response.json()] == [
            "pn-code-only-1",
        ]

        accounts_response = client.get("/api/meta/accounts")
        assert accounts_response.status_code == 200
        embedded_account = next(
            item
            for item in accounts_response.json()
            if item["account_id"] == "meta-account-code-only"
        )
        assert embedded_account["has_access_token"] is True
    finally:
        if original_messaging_provider is None:
            os.environ.pop("MESSAGING_PROVIDER", None)
        else:
            os.environ["MESSAGING_PROVIDER"] = original_messaging_provider
        get_settings.cache_clear()


def test_embedded_signup_session_complete_extracts_fields_from_raw_payload(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_messaging_provider = os.environ.get("MESSAGING_PROVIDER")
    provider = CapturingRawPayloadEmbeddedSignupProvider()

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()
        override_meta_management_provider(client, provider)

        create_response = client.post(
            "/api/meta/accounts/embedded-signup/session",
            json={
                "account_id": "meta-account-complete-raw-payload",
                "display_name": "Brand Complete Raw Payload",
                "redirect_uri": "https://example.com/embedded-signup/complete-raw-payload",
            },
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]

        complete_response = client.post(
            f"/api/meta/accounts/embedded-signup/session/{session_id}/complete",
            json={
                "raw_payload": {
                    "data": {
                        "waba_id": "waba-complete-raw-payload",
                        "meta_business_portfolio_id": "biz-complete-raw-payload",
                        "phone_number_ids": [
                            "pn-complete-raw-payload-1",
                            "pn-complete-raw-payload-2",
                        ],
                        "setup_session_id": "setup-complete-raw-payload",
                        "authorization": {"code": "code-complete-raw-payload"},
                        "access_token": "token-complete-raw-payload",
                    }
                }
            },
        )

        assert complete_response.status_code == 200, complete_response.text
        payload = complete_response.json()
        assert payload["status"] == "completed"
        assert payload["waba_id"] == "waba-complete-raw-payload"
        assert payload["meta_business_portfolio_id"] == "biz-complete-raw-payload"
        assert payload["linked_phone_number_ids"] == [
            "pn-complete-raw-payload-1",
            "pn-complete-raw-payload-2",
        ]
        assert payload["setup_session_id"] == "setup-complete-raw-payload"
        assert payload["authorization_code_present"] is True
        assert payload["system_user_access_token_present"] is True

        assert provider.last_completion_payload is not None
        assert provider.last_completion_payload.requested_waba_id == "waba-complete-raw-payload"
        assert (
            provider.last_completion_payload.meta_business_portfolio_id
            == "biz-complete-raw-payload"
        )
        assert provider.last_completion_payload.phone_number_ids == [
            "pn-complete-raw-payload-1",
            "pn-complete-raw-payload-2",
        ]
        assert (
            provider.last_completion_payload.setup_session_id
            == "setup-complete-raw-payload"
        )
        assert (
            provider.last_completion_payload.authorization_code
            == "code-complete-raw-payload"
        )
        assert (
            provider.last_completion_payload.system_user_access_token
            == "token-complete-raw-payload"
        )
    finally:
        if original_messaging_provider is None:
            os.environ.pop("MESSAGING_PROVIDER", None)
        else:
            os.environ["MESSAGING_PROVIDER"] = original_messaging_provider
        get_settings.cache_clear()


def test_sync_meta_account_phone_numbers_returns_provider_sync_result(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-account-phone-sync",
            "display_name": "Brand Phone Sync",
            "meta_business_portfolio_id": "biz-phone-sync",
            "waba_id": "waba-phone-sync",
            "access_token": "token-phone-sync",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-phone-sync-1",
                    "display_phone_number": "+1 555 000 4001",
                    "verified_name": "Brand Phone Sync Primary",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                },
                {
                    "phone_number_id": "pn-phone-sync-2",
                    "display_phone_number": "+1 555 000 4002",
                    "verified_name": "Brand Phone Sync Backup",
                    "quality_rating": "YELLOW",
                    "is_registered": False,
                },
            ],
        },
    )
    assert create_response.status_code == 200

    sync_path = "/api/meta/accounts/meta-account-phone-sync/wabas/waba-phone-sync/phone-numbers/sync"
    sync_response = client.post(sync_path)
    assert sync_response.status_code == 200
    payload = sync_response.json()
    assert payload["provider_name"] == "whatsapp"
    assert payload["sync_mode"] == "remote_fetch"
    assert payload["status"] == "success"
    assert [item["phone_number_id"] for item in payload["phone_numbers"]] == [
        "pn-phone-sync-1",
        "pn-phone-sync-2",
    ]
    assert payload["phone_numbers"][0]["display_phone_number"] == "+1 555 000 4001"
    assert payload["phone_numbers"][0]["is_registered"] is True
    assert payload["phone_numbers"][1]["quality_rating"] == "YELLOW"
    assert payload["phone_numbers"][1]["is_registered"] is False

    phone_numbers_response = client.get(
        "/api/meta/accounts/meta-account-phone-sync/wabas/waba-phone-sync/phone-numbers"
    )
    assert phone_numbers_response.status_code == 200
    assert [item["phone_number_id"] for item in phone_numbers_response.json()] == [
        "pn-phone-sync-1",
        "pn-phone-sync-2",
    ]


def test_list_webhook_subscription_history_rows(client: TestClient) -> None:
    create_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-account-webhook-history",
            "display_name": "Brand Webhook History",
            "meta_business_portfolio_id": "biz-webhook-history",
            "waba_id": "waba-webhook-history",
            "access_token": "token-webhook-history",
            "app_secret": "secret-webhook-history",
            "token_source": "system_user",
            "phone_numbers": [],
        },
    )
    assert create_response.status_code == 200

    first_response = client.post(
        "/api/meta/accounts/meta-account-webhook-history/wabas/waba-webhook-history/webhook-subscription",
        json={
            "callback_url": "https://example.com/webhook/first",
            "verify_token": "verify-first",
            "app_id": "app-first",
        },
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/api/meta/accounts/meta-account-webhook-history/wabas/waba-webhook-history/webhook-subscription",
        json={
            "callback_url": "https://example.com/webhook/second",
        },
    )
    assert second_response.status_code == 200

    list_response = client.get(
        "/api/meta/accounts/webhook-subscriptions",
        params={"account_id": "meta-account-webhook-history"},
    )
    assert list_response.status_code == 200
    rows = list_response.json()
    assert len(rows) == 2

    latest_row = rows[0]
    previous_row = rows[1]
    assert latest_row["account_id"] == "meta-account-webhook-history"
    assert latest_row["account_display_name"] == "Brand Webhook History"
    assert latest_row["waba_id"] == "waba-webhook-history"
    assert latest_row["callback_url"] == "https://example.com/webhook/second"
    assert latest_row["verify_token_present"] is True
    assert latest_row["app_secret_present"] is True
    assert latest_row["app_id"] == "app-first"
    assert latest_row["status"] == "remote_subscribed"
    assert latest_row["current_scope_state_applied"] is True
    assert latest_row["subscribed_at"] is not None
    assert latest_row["webhook_verification_status"] == "pending"
    assert latest_row["webhook_runtime_status"] == "pending"
    assert latest_row["webhook_last_verified_at"] is None
    assert latest_row["webhook_last_event_received_at"] is None
    assert latest_row["webhook_signature_failure_count"] == 0
    assert latest_row["created_at"] is not None
    assert latest_row["updated_at"] is not None

    assert previous_row["callback_url"] == "https://example.com/webhook/first"
    assert previous_row["verify_token_present"] is True
    assert previous_row["app_secret_present"] is True
    assert previous_row["app_id"] == "app-first"
    assert previous_row["status"] == "remote_subscribed"
    assert previous_row["current_scope_state_applied"] is False
    assert previous_row["webhook_verification_status"] == "pending"
    assert previous_row["webhook_runtime_status"] == "pending"


def test_webhook_subscription_status_filters_only_return_current_history_row(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-account-webhook-history-filter",
            "display_name": "Brand Webhook History Filter",
            "meta_business_portfolio_id": "biz-webhook-history-filter",
            "waba_id": "waba-webhook-history-filter",
            "access_token": "token-webhook-history-filter",
            "verify_token": "verify-webhook-history-filter",
            "app_secret": "secret-webhook-history-filter",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-webhook-history-filter",
                    "display_phone_number": "+1 555 000 0951",
                    "verified_name": "Brand Webhook History Filter",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert create_response.status_code == 200

    first_response = client.post(
        (
            "/api/meta/accounts/meta-account-webhook-history-filter/"
            "wabas/waba-webhook-history-filter/webhook-subscription"
        ),
        json={"callback_url": "https://example.com/webhook/history-filter/first"},
    )
    assert first_response.status_code == 200

    second_response = client.post(
        (
            "/api/meta/accounts/meta-account-webhook-history-filter/"
            "wabas/waba-webhook-history-filter/webhook-subscription"
        ),
        json={"callback_url": "https://example.com/webhook/history-filter/second"},
    )
    assert second_response.status_code == 200

    verify_response = client.get(
        "/webhooks/whatsapp/meta-account-webhook-history-filter/wabas/waba-webhook-history-filter",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-webhook-history-filter",
            "hub.challenge": "challenge-webhook-history-filter",
        },
    )
    assert verify_response.status_code == 200

    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-webhook-history-filter",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0951",
                                "phone_number_id": "pn-webhook-history-filter",
                            },
                            "messages": [
                                {
                                    "from": "14150000951",
                                    "id": "wamid.webhook.history.filter.1",
                                    "timestamp": "1712346777",
                                    "type": "text",
                                    "text": {"body": "history filter health check"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body, signature = sign_whatsapp_payload(
        webhook_payload,
        "secret-webhook-history-filter",
    )
    webhook_response = client.post(
        "/webhooks/whatsapp/meta-account-webhook-history-filter/wabas/waba-webhook-history-filter",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert webhook_response.status_code == 200

    list_response = client.get(
        "/api/meta/accounts/webhook-subscriptions",
        params={"account_id": "meta-account-webhook-history-filter"},
    )
    assert list_response.status_code == 200
    rows = list_response.json()
    assert len(rows) == 2
    assert [item["callback_url"] for item in rows] == [
        "https://example.com/webhook/history-filter/second",
        "https://example.com/webhook/history-filter/first",
    ]
    assert rows[0]["current_scope_state_applied"] is True
    assert rows[0]["webhook_verification_status"] == "verified"
    assert rows[0]["webhook_runtime_status"] == "healthy"
    assert rows[1]["current_scope_state_applied"] is False
    assert rows[1]["webhook_verification_status"] == "pending"
    assert rows[1]["webhook_runtime_status"] == "pending"

    verified_response = client.get(
        "/api/meta/accounts/webhook-subscriptions",
        params={
            "account_id": "meta-account-webhook-history-filter",
            "waba_id": "waba-webhook-history-filter",
            "webhook_verification_status": "verified",
        },
    )
    assert verified_response.status_code == 200
    verified_rows = verified_response.json()
    assert [item["callback_url"] for item in verified_rows] == [
        "https://example.com/webhook/history-filter/second"
    ]
    assert verified_rows[0]["current_scope_state_applied"] is True

    healthy_response = client.get(
        "/api/meta/accounts/webhook-subscriptions",
        params={
            "account_id": "meta-account-webhook-history-filter",
            "waba_id": "waba-webhook-history-filter",
            "webhook_runtime_status": "healthy",
        },
    )
    assert healthy_response.status_code == 200
    healthy_rows = healthy_response.json()
    assert [item["callback_url"] for item in healthy_rows] == [
        "https://example.com/webhook/history-filter/second"
    ]
    assert healthy_rows[0]["current_scope_state_applied"] is True


def test_repeat_webhook_subscription_reuses_recreated_local_waba_row(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    create_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-account-webhook-recreated",
            "display_name": "Brand Webhook Recreated",
            "meta_business_portfolio_id": "biz-webhook-recreated",
            "waba_id": "waba-webhook-recreated",
            "access_token": "token-webhook-recreated",
            "app_secret": "secret-webhook-recreated-first",
            "token_source": "system_user",
            "phone_numbers": [],
        },
    )
    assert create_response.status_code == 200

    first_response = client.post(
        "/api/meta/accounts/meta-account-webhook-recreated/wabas/waba-webhook-recreated/webhook-subscription",
        json={
            "callback_url": "https://example.com/webhook/recreated",
            "verify_token": "verify-recreated-first",
            "app_id": "app-recreated-first",
        },
    )
    assert first_response.status_code == 200

    session = db_session_factory()
    try:
        legacy_waba = session.query(WhatsAppBusinessAccount).filter_by(
            account_id="meta-account-webhook-recreated",
            waba_id="waba-webhook-recreated",
        ).one()
        legacy_waba.waba_id = "waba-webhook-recreated-legacy"
        session.commit()

        recreated_waba = WhatsAppBusinessAccount(
            account_id="meta-account-webhook-recreated",
            portfolio_id=legacy_waba.portfolio_id,
            waba_id="waba-webhook-recreated",
            onboarding_mode="manual",
            token_source="system_user",
            access_token="token-webhook-recreated-current",
            app_secret="secret-webhook-recreated-current",
            webhook_subscribed=False,
            is_active=True,
            ai_enabled=True,
        )
        session.add(recreated_waba)
        session.commit()
        recreated_waba_id = recreated_waba.id
    finally:
        session.close()

    repeated_response = client.post(
        "/api/meta/accounts/meta-account-webhook-recreated/wabas/waba-webhook-recreated/webhook-subscription",
        json={
            "callback_url": "https://example.com/webhook/recreated",
            "verify_token": "verify-recreated-second",
            "app_id": "app-recreated-second",
        },
    )
    assert repeated_response.status_code == 200

    list_response = client.get(
        "/api/meta/accounts/webhook-subscriptions",
        params={"account_id": "meta-account-webhook-recreated"},
    )
    assert list_response.status_code == 200
    rows = list_response.json()
    assert len(rows) == 1
    assert rows[0]["waba_id"] == "waba-webhook-recreated"
    assert rows[0]["callback_url"] == "https://example.com/webhook/recreated"
    assert rows[0]["app_id"] == "app-recreated-second"
    assert rows[0]["verify_token_present"] is True
    assert rows[0]["app_secret_present"] is True

    session = db_session_factory()
    try:
        stored_rows = session.query(WebhookSubscription).filter_by(
            account_id="meta-account-webhook-recreated",
            waba_id="waba-webhook-recreated",
            callback_url="https://example.com/webhook/recreated",
        ).all()

        assert len(stored_rows) == 1
        assert stored_rows[0].waba_account_id == recreated_waba_id
        assert stored_rows[0].verify_token == "verify-recreated-second"
        assert stored_rows[0].app_secret == "secret-webhook-recreated-current"
        assert stored_rows[0].app_id == "app-recreated-second"
    finally:
        session.close()


def test_list_all_meta_phone_numbers_with_scope_and_filters(client: TestClient) -> None:
    client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-account-scope-1",
            "display_name": "Brand Scope 1",
            "meta_business_portfolio_id": "biz-scope-1",
            "waba_id": "waba-scope-1",
            "access_token": "token-scope-1",
            "verify_token": "verify-scope-1",
            "app_secret": "secret-scope-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-scope-1",
                    "display_phone_number": "+1 555 000 1001",
                    "verified_name": "Brand Scope 1",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                },
                {
                    "phone_number_id": "pn-scope-2",
                    "display_phone_number": "+1 555 000 1002",
                    "verified_name": "Brand Scope 1 Alt",
                    "quality_rating": "YELLOW",
                    "is_registered": False,
                },
            ],
        },
    )
    subscribe_response = client.post(
        "/api/meta/accounts/meta-account-scope-1/wabas/waba-scope-1/webhook-subscription",
        json={
            "callback_url": "https://example.com/meta/scope-1",
        },
    )
    assert subscribe_response.status_code == 200

    client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-account-scope-2",
            "display_name": "Brand Scope 2",
            "meta_business_portfolio_id": "biz-scope-2",
            "waba_id": "waba-scope-2",
            "access_token": "token-scope-2",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-scope-3",
                    "display_phone_number": "+1 555 000 2001",
                    "verified_name": "Brand Scope 2",
                    "quality_rating": "RED",
                    "is_registered": True,
                }
            ],
        },
    )

    all_response = client.get("/api/meta/accounts/phone-numbers")
    assert all_response.status_code == 200
    all_rows = all_response.json()
    assert len(all_rows) == 3
    first_row = next(item for item in all_rows if item["phone_number_id"] == "pn-scope-1")
    assert first_row["account_id"] == "meta-account-scope-1"
    assert first_row["account_display_name"] == "Brand Scope 1"
    assert first_row["waba_id"] == "waba-scope-1"
    assert first_row["webhook_subscription_status"] == "remote_subscribed"
    assert first_row["ready_for_webhook_delivery"] is True
    assert first_row["ready_for_outbound_messages"] is True
    assert first_row["ready_for_meta_activation"] is True
    assert first_row["blocking_reasons"] == []

    unregistered_response = client.get(
        "/api/meta/accounts/phone-numbers",
        params={"account_id": "meta-account-scope-1", "is_registered": False},
    )
    assert unregistered_response.status_code == 200
    assert [item["phone_number_id"] for item in unregistered_response.json()] == ["pn-scope-2"]

    quality_response = client.get(
        "/api/meta/accounts/phone-numbers",
        params={"quality_rating": "RED"},
    )
    assert quality_response.status_code == 200
    quality_rows = quality_response.json()
    assert len(quality_rows) == 1
    assert quality_rows[0]["phone_number_id"] == "pn-scope-3"


def test_list_meta_accounts_with_account_and_active_filters(client: TestClient) -> None:
    first_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-account-filter-1",
            "display_name": "Brand Filter 1",
            "meta_business_portfolio_id": "biz-filter-1",
            "waba_id": "waba-filter-1",
            "access_token": "token-filter-1",
            "token_source": "system_user",
            "phone_numbers": [],
        },
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-account-filter-2",
            "display_name": "Brand Filter 2",
            "meta_business_portfolio_id": "biz-filter-2",
            "waba_id": "waba-filter-2",
            "access_token": "token-filter-2",
            "token_source": "system_user",
            "phone_numbers": [],
        },
    )
    assert second_response.status_code == 200

    deactivate_response = client.patch(
        "/api/meta/accounts/meta-account-filter-2/status",
        json={"is_active": False},
    )
    assert deactivate_response.status_code == 200

    scoped_response = client.get(
        "/api/meta/accounts",
        params={"account_id": "meta-account-filter-1"},
    )
    assert scoped_response.status_code == 200
    scoped_accounts = scoped_response.json()
    assert len(scoped_accounts) == 1
    assert scoped_accounts[0]["account_id"] == "meta-account-filter-1"

    inactive_response = client.get(
        "/api/meta/accounts",
        params={"is_active": False},
    )
    assert inactive_response.status_code == 200
    inactive_accounts = inactive_response.json()
    assert [item["account_id"] for item in inactive_accounts] == ["meta-account-filter-2"]

    waba_response = client.get(
        "/api/meta/accounts",
        params={"waba_id": "waba-filter-2"},
    )
    assert waba_response.status_code == 200
    waba_accounts = waba_response.json()
    assert len(waba_accounts) == 1
    assert waba_accounts[0]["waba_id"] == "waba-filter-2"


def test_manual_meta_account_rejects_cross_account_waba_reassignment(client: TestClient) -> None:
    first_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-account-conflict-1",
            "display_name": "Brand Conflict 1",
            "meta_business_portfolio_id": "biz-conflict-1",
            "waba_id": "waba-conflict-1",
            "access_token": "token-conflict-1",
            "token_source": "system_user",
            "phone_numbers": [],
        },
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-account-conflict-2",
            "display_name": "Brand Conflict 2",
            "meta_business_portfolio_id": "biz-conflict-2",
            "waba_id": "waba-conflict-1",
            "access_token": "token-conflict-2",
            "token_source": "system_user",
            "phone_numbers": [],
        },
    )

    assert second_response.status_code == 409
    assert "already assigned" in second_response.json()["detail"]


def test_embedded_signup_session_creates_local_waba_skeleton_on_completion(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    override_meta_management_provider(
        client,
        StubMetaManagementProvider(completion_remote_confirmed=False),
    )
    create_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-3",
            "display_name": "Brand C",
            "redirect_uri": "https://example.com/embedded-signup/callback",
        },
    )
    assert create_response.status_code == 200
    created_session = create_response.json()
    assert created_session["status"] == "created"
    assert created_session["provider_name"] == "whatsapp"
    assert created_session["completion_stage"] == "pending_callback"
    assert created_session["waba_id"] is None

    list_response = client.get("/api/meta/accounts/embedded-signup/sessions?account_id=meta-account-3")
    assert list_response.status_code == 200
    listed_sessions = list_response.json()
    assert len(listed_sessions) == 1
    assert listed_sessions[0]["session_id"] == created_session["session_id"]
    assert listed_sessions[0]["display_name"] == "Brand C"

    complete_response = client.post(
        f"/api/meta/accounts/embedded-signup/session/{created_session['session_id']}/complete",
        json={
            "waba_id": "waba-3",
            "meta_business_portfolio_id": "biz-portfolio-3",
            "phone_number_ids": ["pn-embedded-3a", "pn-embedded-3b"],
            "setup_session_id": "setup-embedded-3",
            "authorization_code": "code-embedded-3",
            "system_user_access_token": "token-embedded-3",
        },
    )
    assert complete_response.status_code == 200
    completed_session = complete_response.json()
    assert completed_session["status"] == "completed"
    assert completed_session["waba_id"] == "waba-3"
    assert completed_session["provider_waba_id"] == "waba-3"
    assert completed_session["meta_business_portfolio_id"] == "biz-portfolio-3"
    assert completed_session["completion_stage"] == "local_waba_linked"
    assert completed_session["remote_confirmed"] is False
    assert completed_session["linked_phone_number_ids"] == ["pn-embedded-3a", "pn-embedded-3b"]
    assert completed_session["setup_session_id"] == "setup-embedded-3"
    assert completed_session["authorization_code_present"] is True
    assert completed_session["system_user_access_token_present"] is True
    assert completed_session["callback_received_at"] is not None
    assert completed_session["completed_at"] is not None
    assert completed_session["completion_message"] is not None

    accounts_response = client.get("/api/meta/accounts")
    assert accounts_response.status_code == 200
    embedded_account = next(
        item for item in accounts_response.json() if item["account_id"] == "meta-account-3"
    )
    assert embedded_account["waba_id"] == "waba-3"
    assert embedded_account["onboarding_mode"] == "embedded_signup"
    assert embedded_account["token_source"] == "embedded_signup"
    assert embedded_account["phone_number_count"] == 2

    phone_numbers_response = client.get(
        "/api/meta/accounts/meta-account-3/wabas/waba-3/phone-numbers"
    )
    assert phone_numbers_response.status_code == 200
    assert [item["phone_number_id"] for item in phone_numbers_response.json()] == [
        "pn-embedded-3a",
        "pn-embedded-3b",
    ]


def test_embedded_signup_session_list_persists_waba_scope_fields_after_completion(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-snapshot",
            "display_name": "Brand Snapshot",
            "redirect_uri": "https://example.com/embedded-signup/snapshot",
        },
    )
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    complete_response = client.post(
        f"/api/meta/accounts/embedded-signup/session/{session_id}/complete",
        json={
            "waba_id": "waba-snapshot",
            "meta_business_portfolio_id": "biz-snapshot",
            "phone_number_ids": ["pn-snapshot-1", "pn-snapshot-2"],
            "setup_session_id": "setup-snapshot",
            "raw_payload": {"source": "snapshot-regression"},
        },
    )
    assert complete_response.status_code == 200
    completed_session = complete_response.json()
    assert completed_session["waba_id"] == "waba-snapshot"
    assert completed_session["linked_waba_id"] == "waba-snapshot"
    assert completed_session["provider_waba_id"] == "waba-snapshot"
    assert completed_session["meta_business_portfolio_id"] == "biz-snapshot"

    list_response = client.get(
        "/api/meta/accounts/embedded-signup/sessions",
        params={"account_id": "meta-account-snapshot"},
    )
    assert list_response.status_code == 200
    rows = list_response.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["session_id"] == session_id
    assert row["account_id"] == "meta-account-snapshot"
    assert row["waba_id"] == "waba-snapshot"
    assert row["linked_waba_id"] == "waba-snapshot"
    assert row["provider_waba_id"] == "waba-snapshot"
    assert row["meta_business_portfolio_id"] == "biz-snapshot"
    assert row["linked_phone_number_ids"] == ["pn-snapshot-1", "pn-snapshot-2"]
    assert row["setup_session_id"] == "setup-snapshot"
    assert row["status"] == "completed"
    assert row["completion_stage"] == "local_waba_linked"


def test_embedded_signup_session_create_exposes_requested_webhook_subscription_context(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-signup-webhook-context",
            "display_name": "Brand Signup Webhook Context",
            "redirect_uri": "https://example.com/embedded-signup/webhook-context",
            "webhook_subscription": {
                "callback_url": "https://example.com/webhooks/embedded-signup-context",
                "verify_token": "verify-signup-context",
                "app_id": "app-signup-context",
            },
        },
    )
    assert create_response.status_code == 200
    payload = create_response.json()
    assert payload["status"] == "created"
    assert payload["completion_stage"] == "pending_callback"
    assert payload["webhook_callback_url"] == "https://example.com/webhooks/embedded-signup-context"
    assert payload["webhook_verify_token_present"] is True
    assert payload["webhook_app_secret_present"] is False
    assert payload["webhook_app_id"] == "app-signup-context"
    assert payload["webhook_subscription_status"] is None
    assert payload["ready_for_webhook_delivery"] is False
    assert payload["ready_for_meta_activation"] is False

    list_response = client.get(
        "/api/meta/accounts/embedded-signup/sessions",
        params={"account_id": "meta-account-signup-webhook-context"},
    )
    assert list_response.status_code == 200
    rows = list_response.json()
    assert len(rows) == 1
    assert rows[0]["session_id"] == payload["session_id"]
    assert rows[0]["webhook_callback_url"] == "https://example.com/webhooks/embedded-signup-context"
    assert rows[0]["webhook_verify_token_present"] is True
    assert rows[0]["webhook_app_secret_present"] is False
    assert rows[0]["webhook_app_id"] == "app-signup-context"


def test_embedded_signup_session_create_exposes_launch_context_and_public_callback_requires_state(
    client: TestClient,
) -> None:
    first_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-signup-launch-context",
            "display_name": "Brand Signup Launch Context",
            "redirect_uri": "https://example.com/embedded-signup/launch-context",
        },
    )
    second_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-signup-launch-context",
            "display_name": "Brand Signup Launch Context",
            "redirect_uri": "https://example.com/embedded-signup/launch-context-2",
        },
    )
    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_payload = first_response.json()
    second_payload = second_response.json()
    session_id = first_payload["session_id"]
    launch_context = first_payload["launch_context"]

    assert launch_context["session_id"] == session_id
    assert launch_context["state"]
    assert launch_context["state"] != second_payload["launch_context"]["state"]
    assert launch_context["redirect_uri"] == "https://example.com/embedded-signup/launch-context"
    assert launch_context["callback_url"] == f"/webhooks/meta/embedded-signup/session/{session_id}"
    assert launch_context["expires_at"]
    assert launch_context["parameters"]["state"] == launch_context["state"]
    assert launch_context["parameters"]["redirect_uri"] == launch_context["redirect_uri"]
    assert launch_context["parameters"]["callback_url"] == launch_context["callback_url"]

    missing_state_response = client.post(
        f"/webhooks/meta/embedded-signup/session/{session_id}",
        json={
            "status": "completed",
            "waba_id": "waba-launch-context-missing-state",
            "phone_number_ids": ["pn-launch-context-missing-state"],
        },
    )
    assert missing_state_response.status_code == 409
    assert "state" in missing_state_response.json()["detail"]

    wrong_state_response = client.post(
        f"/webhooks/meta/embedded-signup/session/{session_id}",
        json={
            "status": "completed",
            "state": "wrong-launch-state",
            "waba_id": "waba-launch-context-wrong-state",
            "phone_number_ids": ["pn-launch-context-wrong-state"],
        },
    )
    assert wrong_state_response.status_code == 409
    assert "state" in wrong_state_response.json()["detail"]

    webhook_response = client.post(
        f"/webhooks/meta/embedded-signup/session/{session_id}",
        json={
            "status": "completed",
            "state": launch_context["state"],
            "waba_id": "waba-launch-context",
            "meta_business_portfolio_id": "biz-launch-context",
            "phone_number_ids": ["pn-launch-context-1"],
            "raw_payload": {"source": "launch_context_state"},
        },
    )
    assert webhook_response.status_code == 200, webhook_response.text
    payload = webhook_response.json()
    assert payload["session_id"] == session_id
    assert payload["status"] == "completed"
    assert payload["event_source"] == "provider_callback"
    assert payload["waba_id"] == "waba-launch-context"
    assert payload["linked_phone_number_ids"] == ["pn-launch-context-1"]
    assert payload.get("launch_context") is None

    list_response = client.get(
        "/api/meta/accounts/embedded-signup/sessions",
        params={"account_id": "meta-account-signup-launch-context"},
    )
    assert list_response.status_code == 200
    rows = list_response.json()
    completed_row = next(row for row in rows if row["session_id"] == session_id)
    assert completed_row["launch_context"] == launch_context


def test_embedded_signup_public_callback_rejects_expired_launch_context(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    create_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-signup-expired-launch-context",
            "display_name": "Brand Signup Expired Launch Context",
            "redirect_uri": "https://example.com/embedded-signup/expired-launch-context",
        },
    )
    assert create_response.status_code == 200
    created_payload = create_response.json()
    session_id = created_payload["session_id"]
    launch_state = created_payload["launch_context"]["state"]

    with db_session_factory() as session:
        stored_session = session.query(EmbeddedSignupSessionModel).filter_by(
            session_id=session_id
        ).one()
        payload_snapshot = dict(stored_session.completion_payload or {})
        session_request = dict(payload_snapshot["session_request"])
        launch_context = dict(session_request["launch_context"])
        launch_context["expires_at"] = "2000-01-01T00:00:00"
        session_request["launch_context"] = launch_context
        payload_snapshot["session_request"] = session_request
        stored_session.completion_payload = payload_snapshot
        session.commit()

    expired_response = client.post(
        f"/webhooks/meta/embedded-signup/session/{session_id}",
        json={
            "status": "completed",
            "state": launch_state,
            "waba_id": "waba-expired-launch-context",
            "phone_number_ids": ["pn-expired-launch-context"],
        },
    )
    assert expired_response.status_code == 409
    assert "expired" in expired_response.json()["detail"]

    sessions_response = client.get(
        "/api/meta/accounts/embedded-signup/sessions",
        params={"account_id": "meta-account-signup-expired-launch-context"},
    )
    assert sessions_response.status_code == 200
    session_payload = sessions_response.json()[0]
    assert session_payload["session_id"] == session_id
    assert session_payload["status"] == "created"
    assert session_payload["completion_stage"] == "pending_callback"
    assert session_payload["waba_id"] is None


def test_embedded_signup_public_callback_state_rejection_is_audited(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-signup-state-rejection-audit",
            "display_name": "Brand Signup State Rejection Audit",
            "redirect_uri": "https://example.com/embedded-signup/state-rejection-audit",
        },
    )
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    response = client.post(
        f"/webhooks/meta/embedded-signup/session/{session_id}",
        json={
            "status": "completed",
            "state": "wrong-state-for-audit",
            "waba_id": "waba-state-rejection-audit",
            "phone_number_ids": ["pn-state-rejection-audit"],
        },
    )
    assert response.status_code == 409

    audit_logs_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-account-signup-state-rejection-audit",
            "action": "embedded_signup_callback_rejected",
            "target_id": session_id,
            "limit": 10,
        },
    )
    assert audit_logs_response.status_code == 200
    audit_logs = audit_logs_response.json()
    assert len(audit_logs) == 1
    audit_log = audit_logs[0]
    assert audit_log["actor_type"] == "system"
    assert audit_log["target_type"] == "embedded_signup_session"
    assert audit_log["payload"] == {
        "reason": "state_mismatch",
        "incoming_status": "completed",
        "event_source": "provider_callback",
        "state_present": True,
        "raw_payload_present": False,
    }
    assert "wrong-state-for-audit" not in str(audit_log["payload"])


def test_embedded_signup_public_callback_rejects_launch_context_session_mismatch(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    create_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-signup-launch-session-mismatch",
            "display_name": "Brand Signup Launch Session Mismatch",
            "redirect_uri": "https://example.com/embedded-signup/launch-session-mismatch",
        },
    )
    assert create_response.status_code == 200
    created_payload = create_response.json()
    session_id = created_payload["session_id"]
    launch_state = created_payload["launch_context"]["state"]

    with db_session_factory() as session:
        stored_session = session.query(EmbeddedSignupSessionModel).filter_by(
            session_id=session_id
        ).one()
        payload_snapshot = dict(stored_session.completion_payload or {})
        session_request = dict(payload_snapshot["session_request"])
        launch_context = dict(session_request["launch_context"])
        launch_context["session_id"] = "different-embedded-signup-session"
        session_request["launch_context"] = launch_context
        payload_snapshot["session_request"] = session_request
        stored_session.completion_payload = payload_snapshot
        session.commit()

    response = client.post(
        f"/webhooks/meta/embedded-signup/session/{session_id}",
        json={
            "status": "completed",
            "state": launch_state,
            "waba_id": "waba-launch-session-mismatch",
            "phone_number_ids": ["pn-launch-session-mismatch"],
        },
    )
    assert response.status_code == 409
    assert "launch context" in response.json()["detail"]

    sessions_response = client.get(
        "/api/meta/accounts/embedded-signup/sessions",
        params={"account_id": "meta-account-signup-launch-session-mismatch"},
    )
    assert sessions_response.status_code == 200
    session_payload = sessions_response.json()[0]
    assert session_payload["session_id"] == session_id
    assert session_payload["status"] == "created"
    assert session_payload["completion_stage"] == "pending_callback"
    assert session_payload["waba_id"] is None

    audit_logs_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "meta-account-signup-launch-session-mismatch",
            "action": "embedded_signup_callback_rejected",
            "target_id": session_id,
            "limit": 10,
        },
    )
    assert audit_logs_response.status_code == 200
    audit_logs = audit_logs_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"] == {
        "reason": "launch_context_mismatch",
        "incoming_status": "completed",
        "event_source": "provider_callback",
        "state_present": True,
        "raw_payload_present": False,
    }
    assert "different-embedded-signup-session" not in str(audit_logs[0]["payload"])


def test_embedded_signup_public_callback_rejects_missing_launch_context(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    create_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-signup-missing-launch-context",
            "display_name": "Brand Signup Missing Launch Context",
            "redirect_uri": "https://example.com/embedded-signup/missing-launch-context",
        },
    )
    assert create_response.status_code == 200
    created_payload = create_response.json()
    session_id = created_payload["session_id"]
    launch_state = created_payload["launch_context"]["state"]

    with db_session_factory() as session:
        stored_session = session.query(EmbeddedSignupSessionModel).filter_by(
            session_id=session_id
        ).one()
        payload_snapshot = dict(stored_session.completion_payload or {})
        session_request = dict(payload_snapshot["session_request"])
        session_request.pop("launch_context")
        payload_snapshot["session_request"] = session_request
        stored_session.completion_payload = payload_snapshot
        session.commit()

    response = client.post(
        f"/webhooks/meta/embedded-signup/session/{session_id}",
        json={
            "status": "completed",
            "state": launch_state,
            "waba_id": "waba-missing-launch-context",
            "phone_number_ids": ["pn-missing-launch-context"],
        },
    )
    assert response.status_code == 409
    assert "launch context" in response.json()["detail"]

    sessions_response = client.get(
        "/api/meta/accounts/embedded-signup/sessions",
        params={"account_id": "meta-account-signup-missing-launch-context"},
    )
    assert sessions_response.status_code == 200
    session_payload = sessions_response.json()[0]
    assert session_payload["session_id"] == session_id
    assert session_payload["status"] == "created"
    assert session_payload["completion_stage"] == "pending_callback"
    assert session_payload["waba_id"] is None


def test_embedded_signup_public_callback_rejects_malformed_launch_context(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    create_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-signup-malformed-launch-context",
            "display_name": "Brand Signup Malformed Launch Context",
            "redirect_uri": "https://example.com/embedded-signup/malformed-launch-context",
        },
    )
    assert create_response.status_code == 200
    created_payload = create_response.json()
    session_id = created_payload["session_id"]
    launch_state = created_payload["launch_context"]["state"]

    with db_session_factory() as session:
        stored_session = session.query(EmbeddedSignupSessionModel).filter_by(
            session_id=session_id
        ).one()
        payload_snapshot = dict(stored_session.completion_payload or {})
        session_request = dict(payload_snapshot["session_request"])
        session_request["launch_context"] = {
            "session_id": session_id,
            "state": launch_state,
        }
        payload_snapshot["session_request"] = session_request
        stored_session.completion_payload = payload_snapshot
        session.commit()

    response = client.post(
        f"/webhooks/meta/embedded-signup/session/{session_id}",
        json={
            "status": "completed",
            "state": launch_state,
            "waba_id": "waba-malformed-launch-context",
            "phone_number_ids": ["pn-malformed-launch-context"],
        },
    )
    assert response.status_code == 409
    assert "launch context" in response.json()["detail"]

    sessions_response = client.get(
        "/api/meta/accounts/embedded-signup/sessions",
        params={"account_id": "meta-account-signup-malformed-launch-context"},
    )
    assert sessions_response.status_code == 200
    session_payload = sessions_response.json()[0]
    assert session_payload["session_id"] == session_id
    assert session_payload["status"] == "created"
    assert session_payload["completion_stage"] == "pending_callback"
    assert session_payload["waba_id"] is None


def test_embedded_signup_session_list_supports_status_and_waba_filters(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    override_meta_management_provider(
        client,
        StubMetaManagementProvider(completion_remote_confirmed=False),
    )
    pending_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-signup-filter",
            "display_name": "Brand Signup Filter",
            "redirect_uri": "https://example.com/embedded-signup/filter/pending",
        },
    )
    assert pending_response.status_code == 200
    pending_session_id = pending_response.json()["session_id"]

    local_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-signup-filter",
            "display_name": "Brand Signup Filter",
            "redirect_uri": "https://example.com/embedded-signup/filter/local",
        },
    )
    assert local_response.status_code == 200
    local_session_id = local_response.json()["session_id"]

    local_complete_response = client.post(
        f"/api/meta/accounts/embedded-signup/session/{local_session_id}/complete",
        json={
            "waba_id": "waba-signup-filter-local",
            "meta_business_portfolio_id": "biz-signup-filter-local",
            "phone_number_ids": ["pn-signup-filter-local-1"],
            "raw_payload": {"source": "local-filter"},
        },
    )
    assert local_complete_response.status_code == 200
    assert local_complete_response.json()["remote_confirmed"] is False

    override_meta_management_provider(
        client,
        StubMetaManagementProvider(
            completion_status="remote_confirmed",
            completion_remote_confirmed=True,
            completion_phone_number_ids=["pn-signup-filter-remote-1"],
            completion_resolved_waba_id="waba-signup-filter-remote",
            completion_resolved_portfolio_id="biz-signup-filter-remote",
        ),
    )
    remote_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-signup-filter",
            "display_name": "Brand Signup Filter",
            "redirect_uri": "https://example.com/embedded-signup/filter/remote",
        },
    )
    assert remote_response.status_code == 200
    remote_session_id = remote_response.json()["session_id"]

    remote_complete_response = client.post(
        f"/api/meta/accounts/embedded-signup/session/{remote_session_id}/complete",
        json={
            "waba_id": "waba-signup-filter-remote",
            "meta_business_portfolio_id": "biz-signup-filter-remote",
            "phone_number_ids": ["pn-signup-filter-remote-request"],
            "authorization_code": "code-signup-filter-remote",
            "raw_payload": {"source": "remote-filter"},
        },
    )
    assert remote_complete_response.status_code == 200
    assert remote_complete_response.json()["remote_confirmed"] is True

    failed_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-signup-filter",
            "display_name": "Brand Signup Filter",
            "redirect_uri": "https://example.com/embedded-signup/filter/failed",
        },
    )
    assert failed_response.status_code == 200
    failed_session_id = failed_response.json()["session_id"]

    fail_terminal_response = client.post(
        f"/api/meta/accounts/embedded-signup/session/{failed_session_id}/fail",
        json={
            "error_message": "filter-failed-session",
            "raw_payload": {"source": "failed-filter"},
        },
    )
    assert fail_terminal_response.status_code == 200

    completed_rows_response = client.get(
        "/api/meta/accounts/embedded-signup/sessions",
        params={"account_id": "meta-account-signup-filter", "status": "completed"},
    )
    assert completed_rows_response.status_code == 200
    assert {item["session_id"] for item in completed_rows_response.json()} == {
        local_session_id,
        remote_session_id,
    }

    pending_rows_response = client.get(
        "/api/meta/accounts/embedded-signup/sessions",
        params={"account_id": "meta-account-signup-filter", "status": "created"},
    )
    assert pending_rows_response.status_code == 200
    assert [item["session_id"] for item in pending_rows_response.json()] == [pending_session_id]

    failed_rows_response = client.get(
        "/api/meta/accounts/embedded-signup/sessions",
        params={"account_id": "meta-account-signup-filter", "completion_stage": "failed"},
    )
    assert failed_rows_response.status_code == 200
    assert [item["session_id"] for item in failed_rows_response.json()] == [failed_session_id]

    remote_confirmed_rows_response = client.get(
        "/api/meta/accounts/embedded-signup/sessions",
        params={"account_id": "meta-account-signup-filter", "remote_confirmed": True},
    )
    assert remote_confirmed_rows_response.status_code == 200
    assert [item["session_id"] for item in remote_confirmed_rows_response.json()] == [remote_session_id]

    remote_waba_rows_response = client.get(
        "/api/meta/accounts/embedded-signup/sessions",
        params={"account_id": "meta-account-signup-filter", "waba_id": "waba-signup-filter-remote"},
    )
    assert remote_waba_rows_response.status_code == 200
    assert [item["session_id"] for item in remote_waba_rows_response.json()] == [remote_session_id]


def test_embedded_signup_callback_alias_auto_subscribes_webhook_from_session_context_in_whatsapp_mode(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "META_APP_SECRET": os.environ.get("META_APP_SECRET"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["META_APP_SECRET"] = "meta-app-secret-signup-context"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/embedded-signup/session",
            json={
                "account_id": "meta-account-signup-alias-context",
                "display_name": "Brand Signup Alias Context",
                "redirect_uri": "https://example.com/embedded-signup/alias-context",
                "webhook_subscription": {
                    "callback_url": "https://example.com/webhooks/embedded-signup-alias",
                    "verify_token": "verify-signup-alias",
                    "app_id": "app-signup-alias",
                },
            },
        )
        assert create_response.status_code == 200
        created_payload = create_response.json()
        session_id = created_payload["session_id"]
        launch_state = created_payload["launch_context"]["state"]

        callback_response = client.post(
            f"/webhooks/meta/embedded-signup/session/{session_id}",
            json={
                "status": "completed",
                "state": launch_state,
                "waba_id": "waba-signup-alias",
                "meta_business_portfolio_id": "biz-signup-alias",
                "phone_number_ids": ["pn-signup-alias-1"],
                "authorization_code": "code-signup-alias",
                "raw_payload": {"source": "alias-callback"},
            },
        )
        assert callback_response.status_code == 200
        payload = callback_response.json()
        assert payload["status"] == "completed"
        assert payload["completion_stage"] == "webhook_verification_pending"
        assert payload["event_source"] == "provider_callback"
        assert payload["webhook_callback_url"] == "https://example.com/webhooks/embedded-signup-alias"
        assert payload["webhook_verify_token_present"] is True
        assert payload["webhook_app_id"] == "app-signup-alias"
        assert payload["webhook_subscription_status"] == "remote_subscribed"
        assert payload["webhook_verification_status"] == "pending"
        assert payload["ready_for_webhook_delivery"] is False
        assert payload["ready_for_meta_activation"] is False
        assert "webhook_not_ready" in payload["webhook_blocking_reasons"]

        subscriptions_response = client.get(
            "/api/meta/accounts/webhook-subscriptions",
            params={"account_id": "meta-account-signup-alias-context"},
        )
        assert subscriptions_response.status_code == 200
        subscriptions = subscriptions_response.json()
        assert len(subscriptions) == 1
        assert subscriptions[0]["callback_url"] == "https://example.com/webhooks/embedded-signup-alias"
        assert subscriptions[0]["status"] == "remote_subscribed"
        assert subscriptions[0]["verify_token_present"] is True
        assert subscriptions[0]["app_secret_present"] is True
        assert subscriptions[0]["webhook_verification_status"] == "pending"

        account_response = client.get(
            "/api/meta/accounts",
            params={"account_id": "meta-account-signup-alias-context"},
        )
        assert account_response.status_code == 200
        account_payload = account_response.json()[0]
        assert account_payload["waba_id"] == "waba-signup-alias"
        assert account_payload["webhook_subscribed"] is True
        assert account_payload["webhook_subscription_status"] == "remote_subscribed"
        assert account_payload["webhook_verification_status"] == "pending"
        assert account_payload["ready_for_webhook_delivery"] is False
        assert "webhook_not_ready" in account_payload["blocking_reasons"]

        repeat_subscribe_response = client.post(
            "/api/meta/accounts/meta-account-signup-alias-context/wabas/waba-signup-alias/webhook-subscription",
            json={
                "callback_url": "https://example.com/webhooks/embedded-signup-alias",
                "verify_token": "verify-signup-alias",
                "app_id": "app-signup-alias",
            },
        )
        assert repeat_subscribe_response.status_code == 200

        repeated_subscriptions_response = client.get(
            "/api/meta/accounts/webhook-subscriptions",
            params={"account_id": "meta-account-signup-alias-context"},
        )
        assert repeated_subscriptions_response.status_code == 200
        repeated_subscriptions = repeated_subscriptions_response.json()
        assert len(repeated_subscriptions) == 1
        assert repeated_subscriptions[0]["callback_url"] == "https://example.com/webhooks/embedded-signup-alias"

        filtered_sessions_response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={
                "account_id": "meta-account-signup-alias-context",
                "webhook_subscription_status": "remote_subscribed",
                "webhook_verification_status": "pending",
                "ready_for_webhook_delivery": False,
                "ready_for_meta_activation": False,
            },
        )
        assert filtered_sessions_response.status_code == 200
        filtered_sessions = filtered_sessions_response.json()
        assert len(filtered_sessions) == 1
        assert filtered_sessions[0]["session_id"] == session_id
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_meta_account_status_filters_reject_invalid_enum_values(client: TestClient) -> None:
    cases = (
        ("/api/meta/accounts", "webhook_verification_status", "verifying"),
        ("/api/meta/accounts", "webhook_runtime_status", "processing"),
        ("/api/meta/accounts/webhook-subscriptions", "status", "syncing"),
        (
            "/api/meta/accounts/webhook-subscriptions",
            "webhook_verification_status",
            "verifying",
        ),
        (
            "/api/meta/accounts/webhook-subscriptions",
            "webhook_runtime_status",
            "processing",
        ),
    )

    for path, param_name, invalid_value in cases:
        response = client.get(path, params={param_name: invalid_value})

        assert response.status_code == 422
        assert isinstance(response.json()["detail"], list)
        assert any(
            item.get("loc") == ["query", param_name]
            for item in response.json()["detail"]
        )


def test_embedded_signup_status_filters_reject_invalid_enum_values(client: TestClient) -> None:
    cases = (
        ("completion_stage", "verifying"),
        ("status", "pending"),
        ("webhook_verification_status", "verifying"),
        ("webhook_runtime_status", "processing"),
    )

    for param_name, invalid_value in cases:
        response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={param_name: invalid_value},
        )

        assert response.status_code == 422
        assert isinstance(response.json()["detail"], list)
        assert any(
            item.get("loc") == ["query", param_name]
            for item in response.json()["detail"]
        )


def test_embedded_signup_session_keeps_original_webhook_subscription_after_new_waba_subscription(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "META_APP_SECRET": os.environ.get("META_APP_SECRET"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["META_APP_SECRET"] = "meta-app-secret-signup-origin-lock"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/embedded-signup/session",
            json={
                "account_id": "meta-account-signup-origin-lock",
                "display_name": "Brand Signup Origin Lock",
                "redirect_uri": "https://example.com/embedded-signup/origin-lock",
                "webhook_subscription": {
                    "callback_url": "https://example.com/webhooks/embedded-signup-origin-lock",
                    "verify_token": "verify-signup-origin-lock",
                    "app_id": "app-signup-origin-lock",
                },
            },
        )
        assert create_response.status_code == 200
        created_payload = create_response.json()
        session_id = created_payload["session_id"]
        launch_state = created_payload["launch_context"]["state"]

        callback_response = client.post(
            f"/webhooks/meta/embedded-signup/session/{session_id}",
            json={
                "status": "completed",
                "state": launch_state,
                "waba_id": "waba-signup-origin-lock",
                "meta_business_portfolio_id": "biz-signup-origin-lock",
                "phone_number_ids": ["pn-signup-origin-lock-1"],
                "authorization_code": "code-signup-origin-lock",
                "raw_payload": {"source": "origin-lock-callback"},
            },
        )
        assert callback_response.status_code == 200
        payload = callback_response.json()
        assert payload["webhook_callback_url"] == "https://example.com/webhooks/embedded-signup-origin-lock"
        assert payload["webhook_app_id"] == "app-signup-origin-lock"

        second_subscription_response = client.post(
            "/api/meta/accounts/meta-account-signup-origin-lock/wabas/waba-signup-origin-lock/webhook-subscription",
            json={
                "callback_url": "https://example.com/webhooks/embedded-signup-origin-lock-secondary",
                "verify_token": "verify-signup-origin-lock-secondary",
                "app_id": "app-signup-origin-lock-secondary",
            },
        )
        assert second_subscription_response.status_code == 200

        subscriptions_response = client.get(
            "/api/meta/accounts/webhook-subscriptions",
            params={"account_id": "meta-account-signup-origin-lock"},
        )
        assert subscriptions_response.status_code == 200
        subscriptions = subscriptions_response.json()
        assert len(subscriptions) == 2
        assert {item["callback_url"] for item in subscriptions} == {
            "https://example.com/webhooks/embedded-signup-origin-lock",
            "https://example.com/webhooks/embedded-signup-origin-lock-secondary",
        }

        sessions_response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={
                "account_id": "meta-account-signup-origin-lock",
                "waba_id": "waba-signup-origin-lock",
            },
        )
        assert sessions_response.status_code == 200
        sessions = sessions_response.json()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == session_id
        assert sessions[0]["webhook_callback_url"] == "https://example.com/webhooks/embedded-signup-origin-lock"
        assert sessions[0]["webhook_verify_token_present"] is True
        assert sessions[0]["webhook_app_secret_present"] is True
        assert sessions[0]["webhook_app_id"] == "app-signup-origin-lock"
        assert sessions[0]["webhook_subscription_status"] == "remote_subscribed"
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_embedded_signup_session_falls_back_to_completion_snapshot_when_created_subscription_pointer_is_missing(
    client: TestClient,
    override_meta_management_provider,
    db_session_factory: sessionmaker[Session],
) -> None:
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "META_APP_SECRET": os.environ.get("META_APP_SECRET"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["META_APP_SECRET"] = "meta-app-secret-signup-missing-pointer"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/embedded-signup/session",
            json={
                "account_id": "meta-account-signup-missing-pointer",
                "display_name": "Brand Signup Missing Pointer",
                "redirect_uri": "https://example.com/embedded-signup/missing-pointer",
                "webhook_subscription": {
                    "callback_url": "https://example.com/webhooks/embedded-signup-missing-pointer",
                    "verify_token": "verify-signup-missing-pointer",
                    "app_id": "app-signup-missing-pointer",
                },
            },
        )
        assert create_response.status_code == 200
        created_payload = create_response.json()
        session_id = created_payload["session_id"]
        launch_state = created_payload["launch_context"]["state"]

        callback_response = client.post(
            f"/webhooks/meta/embedded-signup/session/{session_id}",
            json={
                "status": "completed",
                "state": launch_state,
                "waba_id": "waba-signup-missing-pointer",
                "meta_business_portfolio_id": "biz-signup-missing-pointer",
                "phone_number_ids": ["pn-signup-missing-pointer-1"],
                "authorization_code": "code-signup-missing-pointer",
                "raw_payload": {"source": "missing-pointer-callback"},
            },
        )
        assert callback_response.status_code == 200

        session = db_session_factory()
        try:
            stored_session = session.query(EmbeddedSignupSessionModel).filter_by(
                session_id=session_id
            ).one()
            stored_session.created_webhook_subscription_id = None
            session.commit()
        finally:
            session.close()

        second_subscription_response = client.post(
            "/api/meta/accounts/meta-account-signup-missing-pointer/wabas/waba-signup-missing-pointer/webhook-subscription",
            json={
                "callback_url": "https://example.com/webhooks/embedded-signup-missing-pointer-secondary",
                "verify_token": "verify-signup-missing-pointer-secondary",
                "app_id": "app-signup-missing-pointer-secondary",
            },
        )
        assert second_subscription_response.status_code == 200

        sessions_response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={
                "account_id": "meta-account-signup-missing-pointer",
                "waba_id": "waba-signup-missing-pointer",
            },
        )
        assert sessions_response.status_code == 200
        sessions = sessions_response.json()
        assert len(sessions) == 1
        payload = sessions[0]
        assert payload["session_id"] == session_id
        assert payload["webhook_callback_url"] == "https://example.com/webhooks/embedded-signup-missing-pointer"
        assert payload["webhook_verify_token_present"] is True
        assert payload["webhook_app_secret_present"] is True
        assert payload["webhook_app_id"] == "app-signup-missing-pointer"
        assert payload["session_snapshot"]["webhook_callback_url"] == payload["webhook_callback_url"]
        assert payload["session_snapshot"]["webhook_app_id"] == payload["webhook_app_id"]
        assert payload["current_waba_state"]["webhook_callback_url"] == (
            "https://example.com/webhooks/embedded-signup-missing-pointer-secondary"
        )
        assert payload["current_waba_state"]["webhook_app_id"] == "app-signup-missing-pointer-secondary"
        assert payload["webhook_subscription_status"] == "remote_subscribed"
        assert payload["webhook_verification_status"] == "pending"
        assert payload["ready_for_webhook_delivery"] is False
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_embedded_signup_resubscribe_after_verification_resets_live_webhook_state_without_mutating_session_snapshot(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "META_APP_SECRET": os.environ.get("META_APP_SECRET"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["META_APP_SECRET"] = "meta-app-secret-signup-resubscribe-reset"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/embedded-signup/session",
            json={
                "account_id": "meta-account-signup-resubscribe-reset",
                "display_name": "Brand Signup Resubscribe Reset",
                "redirect_uri": "https://example.com/embedded-signup/resubscribe-reset",
                "webhook_subscription": {
                    "callback_url": "https://example.com/webhooks/embedded-signup-resubscribe-reset",
                    "verify_token": "verify-signup-resubscribe-reset",
                    "app_id": "app-signup-resubscribe-reset",
                },
            },
        )
        assert create_response.status_code == 200
        created_payload = create_response.json()
        session_id = created_payload["session_id"]
        launch_state = created_payload["launch_context"]["state"]

        callback_response = client.post(
            f"/webhooks/meta/embedded-signup/session/{session_id}",
            json={
                "status": "completed",
                "state": launch_state,
                "waba_id": "waba-signup-resubscribe-reset",
                "meta_business_portfolio_id": "biz-signup-resubscribe-reset",
                "phone_number_ids": ["pn-signup-resubscribe-reset-1"],
                "authorization_code": "code-signup-resubscribe-reset",
                "raw_payload": {"source": "resubscribe-reset-callback"},
            },
        )
        assert callback_response.status_code == 200

        verify_response = client.get(
            "/webhooks/whatsapp/meta-account-signup-resubscribe-reset/wabas/waba-signup-resubscribe-reset",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-signup-resubscribe-reset",
                "hub.challenge": "challenge-signup-resubscribe-reset",
            },
        )
        assert verify_response.status_code == 200

        resubscribe_response = client.post(
            "/api/meta/accounts/meta-account-signup-resubscribe-reset/"
            "wabas/waba-signup-resubscribe-reset/webhook-subscription",
            json={
                "callback_url": "https://example.com/webhooks/embedded-signup-resubscribe-reset-secondary",
                "verify_token": "verify-signup-resubscribe-reset-secondary",
                "app_id": "app-signup-resubscribe-reset-secondary",
            },
        )
        assert resubscribe_response.status_code == 200

        sessions_response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={"account_id": "meta-account-signup-resubscribe-reset"},
        )
        assert sessions_response.status_code == 200
        sessions = sessions_response.json()
        assert len(sessions) == 1
        payload = sessions[0]
        assert payload["session_id"] == session_id
        assert payload["webhook_callback_url"] == "https://example.com/webhooks/embedded-signup-resubscribe-reset"
        assert payload["webhook_app_id"] == "app-signup-resubscribe-reset"
        assert payload["webhook_verification_status"] == "pending"
        assert payload["ready_for_webhook_delivery"] is False
        assert payload["session_snapshot"]["webhook_callback_url"] == payload["webhook_callback_url"]
        assert payload["session_snapshot"]["webhook_verification_status"] == "pending"
        assert payload["current_waba_state"]["webhook_callback_url"] == (
            "https://example.com/webhooks/embedded-signup-resubscribe-reset-secondary"
        )
        assert payload["current_waba_state"]["webhook_app_id"] == (
            "app-signup-resubscribe-reset-secondary"
        )
        assert payload["current_waba_state"]["webhook_verification_status"] == "pending"
        assert payload["current_waba_state"]["ready_for_webhook_delivery"] is False
        assert payload["completion_webhook_verification_status"] == "pending"

        subscriptions_response = client.get(
            "/api/meta/accounts/webhook-subscriptions",
            params={"account_id": "meta-account-signup-resubscribe-reset"},
        )
        assert subscriptions_response.status_code == 200
        rows = subscriptions_response.json()
        assert len(rows) == 2
        assert rows[0]["callback_url"] == (
            "https://example.com/webhooks/embedded-signup-resubscribe-reset-secondary"
        )
        assert rows[0]["current_scope_state_applied"] is True
        assert rows[0]["webhook_verification_status"] == "pending"
        assert rows[1]["callback_url"] == "https://example.com/webhooks/embedded-signup-resubscribe-reset"
        assert rows[1]["current_scope_state_applied"] is False

        verified_rows_response = client.get(
            "/api/meta/accounts/webhook-subscriptions",
            params={
                "account_id": "meta-account-signup-resubscribe-reset",
                "waba_id": "waba-signup-resubscribe-reset",
                "webhook_verification_status": "verified",
            },
        )
        assert verified_rows_response.status_code == 200
        assert verified_rows_response.json() == []

        pending_rows_response = client.get(
            "/api/meta/accounts/webhook-subscriptions",
            params={
                "account_id": "meta-account-signup-resubscribe-reset",
                "waba_id": "waba-signup-resubscribe-reset",
                "webhook_verification_status": "pending",
            },
        )
        assert pending_rows_response.status_code == 200
        pending_rows = pending_rows_response.json()
        assert [item["callback_url"] for item in pending_rows] == [
            "https://example.com/webhooks/embedded-signup-resubscribe-reset-secondary"
        ]
        assert pending_rows[0]["current_scope_state_applied"] is True
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_embedded_signup_session_tolerates_sparse_legacy_completion_snapshot(
    client: TestClient,
    override_meta_management_provider,
    db_session_factory: sessionmaker[Session],
) -> None:
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "META_APP_SECRET": os.environ.get("META_APP_SECRET"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["META_APP_SECRET"] = "meta-app-secret-signup-legacy-snapshot"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/embedded-signup/session",
            json={
                "account_id": "meta-account-signup-legacy-snapshot",
                "display_name": "Brand Signup Legacy Snapshot",
                "redirect_uri": "https://example.com/embedded-signup/legacy-snapshot",
                "webhook_subscription": {
                    "callback_url": "https://example.com/webhooks/embedded-signup-legacy-snapshot",
                    "verify_token": "verify-signup-legacy-snapshot",
                    "app_id": "app-signup-legacy-snapshot",
                },
            },
        )
        assert create_response.status_code == 200
        created_payload = create_response.json()
        session_id = created_payload["session_id"]
        launch_state = created_payload["launch_context"]["state"]

        callback_response = client.post(
            f"/webhooks/meta/embedded-signup/session/{session_id}",
            json={
                "status": "completed",
                "state": launch_state,
                "waba_id": "waba-signup-legacy-snapshot",
                "meta_business_portfolio_id": "biz-signup-legacy-snapshot",
                "phone_number_ids": ["pn-signup-legacy-snapshot-1"],
                "authorization_code": "code-signup-legacy-snapshot",
                "raw_payload": {"source": "legacy-snapshot-callback"},
            },
        )
        assert callback_response.status_code == 200

        session = db_session_factory()
        try:
            stored_session = session.query(EmbeddedSignupSessionModel).filter_by(
                session_id=session_id
            ).one()
            payload_snapshot = dict(stored_session.completion_payload or {})
            payload_snapshot["webhook_subscription_result"] = {
                "webhook_subscription_status": "remote_subscribed",
                "webhook_verification_status": "verified",
                "webhook_runtime_status": "healthy",
                "ready_for_webhook_delivery": True,
                "ready_for_outbound_messages": False,
                "ready_for_meta_activation": False,
                "has_app_secret": True,
                "blocking_reasons": [],
            }
            stored_session.completion_payload = payload_snapshot
            stored_session.created_webhook_subscription_id = None
            session.commit()
        finally:
            session.close()

        sessions_response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={
                "account_id": "meta-account-signup-legacy-snapshot",
                "waba_id": "waba-signup-legacy-snapshot",
            },
        )
        assert sessions_response.status_code == 200
        sessions = sessions_response.json()
        assert len(sessions) == 1
        payload = sessions[0]
        assert payload["session_id"] == session_id
        assert payload["webhook_callback_url"] == "https://example.com/webhooks/embedded-signup-legacy-snapshot"
        assert payload["webhook_app_id"] == "app-signup-legacy-snapshot"
        assert payload["webhook_app_secret_present"] is True
        assert payload["completion_webhook_subscription_status"] == "remote_subscribed"
        assert payload["completion_webhook_verification_status"] == "verified"
        assert payload["completion_webhook_runtime_status"] == "healthy"
        assert payload["completion_ready_for_webhook_delivery"] is True
        assert payload["session_snapshot"]["webhook_verification_status"] == "verified"
        assert payload["session_snapshot"]["webhook_runtime_status"] == "healthy"
        assert payload["session_snapshot"]["ready_for_webhook_delivery"] is True
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_embedded_signup_auto_subscribed_webhook_can_be_verified_and_session_turns_ready(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "META_APP_SECRET": os.environ.get("META_APP_SECRET"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["META_APP_SECRET"] = "meta-app-secret-signup-verify"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/embedded-signup/session",
            json={
                "account_id": "meta-account-signup-verify-ready",
                "display_name": "Brand Signup Verify Ready",
                "redirect_uri": "https://example.com/embedded-signup/verify-ready",
                "webhook_subscription": {
                    "callback_url": "https://example.com/webhooks/embedded-signup-verify-ready",
                    "verify_token": "verify-signup-verify-ready",
                    "app_id": "app-signup-verify-ready",
                },
            },
        )
        assert create_response.status_code == 200
        created_payload = create_response.json()
        session_id = created_payload["session_id"]
        launch_state = created_payload["launch_context"]["state"]

        callback_response = client.post(
            f"/webhooks/meta/embedded-signup/session/{session_id}",
            json={
                "status": "completed",
                "state": launch_state,
                "waba_id": "waba-signup-verify-ready",
                "meta_business_portfolio_id": "biz-signup-verify-ready",
                "phone_number_ids": ["pn-signup-verify-ready-1"],
                "authorization_code": "code-signup-verify-ready",
                "raw_payload": {"source": "alias-callback-verify-ready"},
            },
        )
        assert callback_response.status_code == 200
        assert callback_response.json()["completion_stage"] == "webhook_verification_pending"

        verify_response = client.get(
            "/webhooks/whatsapp/meta-account-signup-verify-ready/wabas/waba-signup-verify-ready",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-signup-verify-ready",
                "hub.challenge": "challenge-signup-verify-ready",
            },
        )
        assert verify_response.status_code == 200
        assert verify_response.text == "challenge-signup-verify-ready"

        accounts_response = client.get(
            "/api/meta/accounts",
            params={"account_id": "meta-account-signup-verify-ready"},
        )
        assert accounts_response.status_code == 200
        account_payload = accounts_response.json()[0]
        assert account_payload["webhook_verification_status"] == "verified"
        assert account_payload["ready_for_webhook_delivery"] is True
        assert account_payload["ready_for_meta_activation"] is False
        assert "webhook_not_ready" not in account_payload["blocking_reasons"]

        sessions_response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={
                "account_id": "meta-account-signup-verify-ready",
                "webhook_verification_status": "verified",
                "ready_for_webhook_delivery": True,
            },
        )
        assert sessions_response.status_code == 200
        sessions = sessions_response.json()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == session_id
        assert sessions[0]["webhook_verification_status"] == "verified"
        assert sessions[0]["webhook_runtime_status"] == "pending"
        assert sessions[0]["ready_for_webhook_delivery"] is True
        assert sessions[0]["ready_for_outbound_messages"] is False
        assert sessions[0]["ready_for_meta_activation"] is False
        assert sessions[0]["completion_webhook_subscription_status"] == "remote_subscribed"
        assert sessions[0]["completion_webhook_verification_status"] == "pending"
        assert sessions[0]["completion_webhook_runtime_status"] == "pending"
        assert sessions[0]["completion_ready_for_webhook_delivery"] is False
        assert sessions[0]["completion_ready_for_outbound_messages"] is False
        assert sessions[0]["completion_ready_for_meta_activation"] is False
        assert sessions[0]["session_snapshot"]["webhook_verification_status"] == "pending"
        assert sessions[0]["current_waba_state"]["webhook_verification_status"] == "verified"
        assert sessions[0]["current_waba_state"]["ready_for_webhook_delivery"] is True

        runtime_pending_sessions_response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={
                "account_id": "meta-account-signup-verify-ready",
                "webhook_runtime_status": "pending",
                "ready_for_outbound_messages": False,
            },
        )
        assert runtime_pending_sessions_response.status_code == 200
        runtime_pending_sessions = runtime_pending_sessions_response.json()
        assert len(runtime_pending_sessions) == 1
        assert runtime_pending_sessions[0]["session_id"] == session_id

        runtime_healthy_sessions_response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={
                "account_id": "meta-account-signup-verify-ready",
                "webhook_runtime_status": "healthy",
            },
        )
        assert runtime_healthy_sessions_response.status_code == 200
        assert runtime_healthy_sessions_response.json() == []
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_embedded_signup_session_and_subscription_list_keep_snapshot_secret_after_waba_secret_drift(
    client: TestClient,
    override_meta_management_provider,
    db_session_factory: sessionmaker[Session],
) -> None:
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "META_APP_SECRET": os.environ.get("META_APP_SECRET"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["META_APP_SECRET"] = "meta-app-secret-signup-secret-drift"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/embedded-signup/session",
            json={
                "account_id": "meta-account-signup-secret-drift",
                "display_name": "Brand Signup Secret Drift",
                "redirect_uri": "https://example.com/embedded-signup/secret-drift",
                "webhook_subscription": {
                    "callback_url": "https://example.com/webhooks/embedded-signup-secret-drift",
                    "verify_token": "verify-signup-secret-drift",
                    "app_id": "app-signup-secret-drift",
                },
            },
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]

        complete_response = client.post(
            f"/api/meta/accounts/embedded-signup/session/{session_id}/complete",
            json={
                "waba_id": "waba-signup-secret-drift",
                "meta_business_portfolio_id": "biz-signup-secret-drift",
                "phone_number_ids": ["pn-signup-secret-drift-1"],
                "system_user_access_token": "token-signup-secret-drift",
            },
        )
        assert complete_response.status_code == 200
        assert complete_response.json()["completion_stage"] == "webhook_verification_pending"

        verify_response = client.get(
            "/webhooks/whatsapp/meta-account-signup-secret-drift/wabas/waba-signup-secret-drift",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-signup-secret-drift",
                "hub.challenge": "challenge-signup-secret-drift",
            },
        )
        assert verify_response.status_code == 200

        session = db_session_factory()
        try:
            waba_account = session.query(WhatsAppBusinessAccount).filter(
                WhatsAppBusinessAccount.account_id == "meta-account-signup-secret-drift",
                WhatsAppBusinessAccount.waba_id == "waba-signup-secret-drift",
            ).one()
            subscription = session.query(WebhookSubscription).filter(
                WebhookSubscription.account_id == "meta-account-signup-secret-drift",
                WebhookSubscription.waba_id == "waba-signup-secret-drift",
            ).one()
            phone_number = session.query(WhatsAppPhoneNumber).filter(
                WhatsAppPhoneNumber.account_id == "meta-account-signup-secret-drift",
                WhatsAppPhoneNumber.phone_number_id == "pn-signup-secret-drift-1",
            ).one()

            assert subscription.app_secret == "meta-app-secret-signup-secret-drift"

            waba_account.app_secret = None
            waba_account.webhook_subscribed = True
            waba_account.webhook_verification_status = "verified"
            phone_number.is_registered = True

            session.add(waba_account)
            session.add(phone_number)
            session.commit()
        finally:
            session.close()

        sessions_response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={
                "account_id": "meta-account-signup-secret-drift",
                "waba_id": "waba-signup-secret-drift",
                "ready_for_webhook_delivery": True,
                "ready_for_meta_activation": True,
            },
        )
        assert sessions_response.status_code == 200
        sessions = sessions_response.json()
        assert len(sessions) == 1
        session_payload = sessions[0]
        assert session_payload["session_id"] == session_id
        assert session_payload["webhook_callback_url"] == (
            "https://example.com/webhooks/embedded-signup-secret-drift"
        )
        assert session_payload["webhook_verify_token_present"] is True
        assert session_payload["webhook_app_secret_present"] is True
        assert session_payload["webhook_app_id"] == "app-signup-secret-drift"
        assert session_payload["webhook_subscription_status"] == "remote_subscribed"
        assert session_payload["webhook_verification_status"] == "verified"
        assert session_payload["ready_for_webhook_delivery"] is True
        assert session_payload["ready_for_outbound_messages"] is True
        assert session_payload["ready_for_meta_activation"] is True
        assert session_payload["webhook_blocking_reasons"] == []
        assert session_payload["completion_webhook_subscription_status"] == "remote_subscribed"
        assert session_payload["completion_webhook_verification_status"] == "pending"
        assert session_payload["completion_ready_for_webhook_delivery"] is False
        assert session_payload["completion_ready_for_meta_activation"] is False
        assert session_payload["session_snapshot"]["webhook_verification_status"] == "pending"
        assert session_payload["session_snapshot"]["ready_for_webhook_delivery"] is False
        assert session_payload["current_waba_state"]["webhook_verify_token_present"] is True
        assert session_payload["current_waba_state"]["webhook_app_secret_present"] is True
        assert session_payload["current_waba_state"]["webhook_verification_status"] == "verified"
        assert session_payload["current_waba_state"]["ready_for_webhook_delivery"] is True
        assert session_payload["current_waba_state"]["ready_for_meta_activation"] is True

        accounts_response = client.get(
            "/api/meta/accounts",
            params={
                "account_id": "meta-account-signup-secret-drift",
                "waba_id": "waba-signup-secret-drift",
                "ready_for_webhook_delivery": True,
                "ready_for_meta_activation": True,
            },
        )
        assert accounts_response.status_code == 200
        accounts = accounts_response.json()
        assert len(accounts) == 1
        assert accounts[0]["has_verify_token"] is True
        assert accounts[0]["has_app_secret"] is True
        assert accounts[0]["ready_for_webhook_delivery"] is True
        assert accounts[0]["ready_for_meta_activation"] is True

        subscriptions_response = client.get(
            "/api/meta/accounts/webhook-subscriptions",
            params={
                "account_id": "meta-account-signup-secret-drift",
                "waba_id": "waba-signup-secret-drift",
            },
        )
        assert subscriptions_response.status_code == 200
        subscriptions = subscriptions_response.json()
        assert len(subscriptions) == 1
        assert subscriptions[0]["callback_url"] == (
            "https://example.com/webhooks/embedded-signup-secret-drift"
        )
        assert subscriptions[0]["verify_token_present"] is True
        assert subscriptions[0]["app_secret_present"] is True
        assert subscriptions[0]["app_id"] == "app-signup-secret-drift"
        assert subscriptions[0]["status"] == "remote_subscribed"
        assert subscriptions[0]["webhook_verification_status"] == "verified"
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_embedded_signup_source_only_history_is_not_misclassified_as_ready(
    client: TestClient,
    override_meta_management_provider,
    db_session_factory: sessionmaker[Session],
) -> None:
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "META_APP_SECRET": os.environ.get("META_APP_SECRET"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["META_APP_SECRET"] = "meta-app-secret-signup-source-history"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/embedded-signup/session",
            json={
                "account_id": "meta-account-signup-source-history",
                "display_name": "Brand Signup Source History",
                "redirect_uri": "https://example.com/embedded-signup/source-history",
                "webhook_subscription": {
                    "callback_url": "https://example.com/webhooks/embedded-signup-source-history",
                    "verify_token": "verify-signup-source-history",
                    "app_id": "app-signup-source-history",
                },
            },
        )
        assert create_response.status_code == 200
        created_payload = create_response.json()
        session_id = created_payload["session_id"]
        launch_state = created_payload["launch_context"]["state"]

        callback_response = client.post(
            f"/webhooks/meta/embedded-signup/session/{session_id}",
            json={
                "status": "completed",
                "state": launch_state,
                "waba_id": "waba-signup-source-history",
                "meta_business_portfolio_id": "biz-signup-source-history",
                "phone_number_ids": ["pn-signup-source-history-1"],
                "authorization_code": "code-signup-source-history",
                "raw_payload": {"source": "source-only-history"},
            },
        )
        assert callback_response.status_code == 200
        assert callback_response.json()["completion_stage"] == "webhook_verification_pending"

        verify_response = client.get(
            "/webhooks/whatsapp/meta-account-signup-source-history/wabas/waba-signup-source-history",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-signup-source-history",
                "hub.challenge": "challenge-signup-source-history",
            },
        )
        assert verify_response.status_code == 200

        initially_ready_response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={
                "account_id": "meta-account-signup-source-history",
                "waba_id": "waba-signup-source-history",
                "ready_for_webhook_delivery": True,
            },
        )
        assert initially_ready_response.status_code == 200
        assert [item["session_id"] for item in initially_ready_response.json()] == [session_id]

        session = db_session_factory()
        try:
            stored_session = session.query(EmbeddedSignupSessionModel).filter(
                EmbeddedSignupSessionModel.session_id == session_id
            ).one()
            stored_session.waba_account_id = None

            linked_waba = session.query(WhatsAppBusinessAccount).filter(
                WhatsAppBusinessAccount.account_id == "meta-account-signup-source-history",
                WhatsAppBusinessAccount.waba_id == "waba-signup-source-history",
            ).one()
            linked_waba.waba_id = "waba-signup-source-history-current"
            session.commit()
        finally:
            session.close()

        historical_blocked_response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={
                "account_id": "meta-account-signup-source-history",
                "waba_id": "waba-signup-source-history",
                "ready_for_webhook_delivery": False,
            },
        )
        assert historical_blocked_response.status_code == 200
        historical_rows = historical_blocked_response.json()
        assert len(historical_rows) == 1
        historical_row = historical_rows[0]
        assert historical_row["session_id"] == session_id
        assert historical_row["waba_id"] == "waba-signup-source-history"
        assert historical_row["linked_waba_id"] is None
        assert historical_row["provider_waba_id"] == "waba-signup-source-history"
        assert historical_row["webhook_subscription_status"] == "remote_subscribed"
        assert historical_row["webhook_verification_status"] is None
        assert historical_row["ready_for_webhook_delivery"] is False
        assert historical_row["ready_for_meta_activation"] is False
        assert historical_row["webhook_blocking_reasons"] == []
        assert historical_row["completion_webhook_subscription_status"] == "remote_subscribed"
        assert historical_row["completion_webhook_verification_status"] == "pending"
        assert historical_row["completion_webhook_runtime_status"] == "pending"
        assert historical_row["completion_ready_for_webhook_delivery"] is False
        assert historical_row["completion_ready_for_meta_activation"] is False
        assert "webhook_not_ready" in historical_row["completion_webhook_blocking_reasons"]
        assert historical_row["session_snapshot"]["waba_id"] == "waba-signup-source-history"
        assert historical_row["session_snapshot"]["webhook_verification_status"] == "pending"
        assert historical_row["current_waba_state"] is None

        historical_ready_response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={
                "account_id": "meta-account-signup-source-history",
                "waba_id": "waba-signup-source-history",
                "ready_for_webhook_delivery": True,
            },
        )
        assert historical_ready_response.status_code == 200
        assert historical_ready_response.json() == []
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_embedded_signup_session_filters_follow_webhook_verification_retry_state(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "META_APP_SECRET": os.environ.get("META_APP_SECRET"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["META_APP_SECRET"] = "meta-app-secret-signup-filter-retry"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/embedded-signup/session",
            json={
                "account_id": "meta-account-signup-filter-retry",
                "display_name": "Brand Signup Filter Retry",
                "redirect_uri": "https://example.com/embedded-signup/filter-retry",
                "webhook_subscription": {
                    "callback_url": "https://example.com/webhooks/embedded-signup-filter-retry",
                    "verify_token": "verify-signup-filter-retry",
                    "app_id": "app-signup-filter-retry",
                },
            },
        )
        assert create_response.status_code == 200
        created_payload = create_response.json()
        session_id = created_payload["session_id"]
        launch_state = created_payload["launch_context"]["state"]

        callback_response = client.post(
            f"/webhooks/meta/embedded-signup/session/{session_id}",
            json={
                "status": "completed",
                "state": launch_state,
                "waba_id": "waba-signup-filter-retry",
                "meta_business_portfolio_id": "biz-signup-filter-retry",
                "phone_number_ids": ["pn-signup-filter-retry-1"],
                "authorization_code": "code-signup-filter-retry",
                "raw_payload": {"source": "filter-retry-callback"},
            },
        )
        assert callback_response.status_code == 200
        assert callback_response.json()["webhook_verification_status"] == "pending"

        failed_verify_response = client.get(
            "/webhooks/whatsapp/meta-account-signup-filter-retry/wabas/waba-signup-filter-retry",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-signup-filter-retry-token",
                "hub.challenge": "signup-filter-retry-failed",
            },
        )
        assert failed_verify_response.status_code == 403

        failed_sessions_response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={
                "account_id": "meta-account-signup-filter-retry",
                "webhook_verification_status": "failed",
            },
        )
        assert failed_sessions_response.status_code == 200
        failed_sessions = failed_sessions_response.json()
        assert [item["session_id"] for item in failed_sessions] == [session_id]
        assert failed_sessions[0]["webhook_verification_status"] == "failed"
        assert failed_sessions[0]["webhook_callback_url"] == (
            "https://example.com/webhooks/embedded-signup-filter-retry"
        )
        assert failed_sessions[0]["webhook_verify_token_present"] is True

        success_verify_response = client.get(
            "/webhooks/whatsapp/meta-account-signup-filter-retry/wabas/waba-signup-filter-retry",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-signup-filter-retry",
                "hub.challenge": "signup-filter-retry-success",
            },
        )
        assert success_verify_response.status_code == 200

        verified_sessions_response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={
                "account_id": "meta-account-signup-filter-retry",
                "webhook_verification_status": "verified",
                "ready_for_webhook_delivery": True,
            },
        )
        assert verified_sessions_response.status_code == 200
        verified_sessions = verified_sessions_response.json()
        assert [item["session_id"] for item in verified_sessions] == [session_id]
        assert verified_sessions[0]["webhook_verification_status"] == "verified"
        assert verified_sessions[0]["ready_for_webhook_delivery"] is True

        stale_failed_filter_response = client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={
                "account_id": "meta-account-signup-filter-retry",
                "webhook_verification_status": "failed",
            },
        )
        assert stale_failed_filter_response.status_code == 200
        assert stale_failed_filter_response.json() == []
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_embedded_signup_completion_with_authorization_code_stores_provider_token(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    override_meta_management_provider(client, CapturingEmbeddedSignupProvider())
    create_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-code-only",
            "display_name": "Brand Code Only",
            "redirect_uri": "https://example.com/embedded-signup/code-only",
        },
    )
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    complete_response = client.post(
        f"/api/meta/accounts/embedded-signup/session/{session_id}/complete",
        json={
            "waba_id": "waba-code-only",
            "meta_business_portfolio_id": "biz-code-only",
            "phone_number_ids": ["pn-code-only"],
            "authorization_code": "code-only-1",
        },
    )

    assert complete_response.status_code == 200
    completed_session = complete_response.json()
    assert completed_session["status"] == "completed"
    assert completed_session["waba_id"] == "waba-code-only"
    assert completed_session["authorization_code_present"] is True
    assert completed_session["system_user_access_token_present"] is True

    accounts_response = client.get("/api/meta/accounts")
    assert accounts_response.status_code == 200
    embedded_account = next(
        item
        for item in accounts_response.json()
        if item["account_id"] == "meta-account-code-only"
    )
    assert embedded_account["waba_id"] == "waba-code-only"
    assert embedded_account["has_access_token"] is True


def test_embedded_signup_session_links_existing_local_waba(client: TestClient) -> None:
    manual_account_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-account-3b",
            "display_name": "Brand C Existing",
            "meta_business_portfolio_id": "biz-portfolio-3b",
            "waba_id": "waba-3b",
            "access_token": "token-3b",
            "token_source": "system_user",
            "phone_numbers": [],
        },
    )
    assert manual_account_response.status_code == 200

    create_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-3b",
            "display_name": "Brand C Existing",
            "redirect_uri": "https://example.com/embedded-signup/existing",
        },
    )
    assert create_response.status_code == 200
    created_session = create_response.json()

    complete_response = client.post(
        f"/api/meta/accounts/embedded-signup/session/{created_session['session_id']}/complete",
        json={
            "waba_id": "waba-3b",
            "phone_number_ids": ["pn-3b"],
            "event_source": "provider_callback",
        },
    )
    assert complete_response.status_code == 200
    completed_session = complete_response.json()
    assert completed_session["waba_id"] == "waba-3b"
    assert completed_session["completion_stage"] == "local_waba_linked"
    assert completed_session["event_source"] == "provider_callback"

    accounts_response = client.get("/api/meta/accounts")
    assert accounts_response.status_code == 200
    updated_account = next(
        item for item in accounts_response.json() if item["account_id"] == "meta-account-3b"
    )
    assert updated_account["waba_id"] == "waba-3b"
    assert updated_account["onboarding_mode"] == "embedded_signup"
    assert updated_account["phone_number_count"] == 1


def test_embedded_signup_callback_ingestion_completes_session(client: TestClient) -> None:
    create_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-callback-complete",
            "display_name": "Brand Callback Complete",
            "redirect_uri": "https://example.com/embedded-signup/callback-complete",
        },
    )
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    callback_response = client.post(
        f"/api/meta/accounts/embedded-signup/session/{session_id}/callback",
        json={
            "status": "completed",
            "waba_id": "waba-callback-complete",
            "meta_business_portfolio_id": "biz-callback-complete",
            "phone_number_ids": ["pn-callback-1", "pn-callback-2"],
            "setup_session_id": "setup-callback-complete",
            "authorization_code": "code-callback-complete",
            "system_user_access_token": "token-callback-complete",
            "raw_payload": {"source": "provider", "event": "FINISH"},
        },
    )
    assert callback_response.status_code == 200
    payload = callback_response.json()
    assert payload["status"] == "completed"
    assert payload["event_source"] == "provider_callback"
    assert payload["waba_id"] == "waba-callback-complete"
    assert payload["meta_business_portfolio_id"] == "biz-callback-complete"
    assert payload["linked_phone_number_ids"] == ["pn-callback-1", "pn-callback-2"]
    assert payload["authorization_code_present"] is True
    assert payload["system_user_access_token_present"] is True
    assert payload["callback_received_at"] is not None

    accounts_response = client.get("/api/meta/accounts")
    assert accounts_response.status_code == 200
    account_payload = next(
        item
        for item in accounts_response.json()
        if item["account_id"] == "meta-account-callback-complete"
    )
    assert account_payload["waba_id"] == "waba-callback-complete"
    assert account_payload["phone_number_count"] == 2


def test_webhook_subscription_list_filters_preserve_account_and_waba_scope_fields(
    client: TestClient,
) -> None:
    for account_id, display_name, portfolio_id, waba_id, callback_url in (
        (
            "meta-account-webhook-scope-a",
            "Webhook Scope A",
            "biz-webhook-scope-a",
            "waba-webhook-scope-a",
            "https://example.com/webhook-scope-a",
        ),
        (
            "meta-account-webhook-scope-b",
            "Webhook Scope B",
            "biz-webhook-scope-b",
            "waba-webhook-scope-b",
            "https://example.com/webhook-scope-b",
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
                "app_secret": f"secret-{account_id}",
                "token_source": "system_user",
                "phone_numbers": [],
            },
        )
        assert create_response.status_code == 200

        subscribe_response = client.post(
            f"/api/meta/accounts/{account_id}/wabas/{waba_id}/webhook-subscription",
            json={"callback_url": callback_url},
        )
        assert subscribe_response.status_code == 200

    filtered_response = client.get(
        "/api/meta/accounts/webhook-subscriptions",
        params={
            "account_id": "meta-account-webhook-scope-a",
            "waba_id": "waba-webhook-scope-a",
            "status": "remote_subscribed",
        },
    )
    assert filtered_response.status_code == 200
    rows = filtered_response.json()
    assert len(rows) == 1
    assert rows[0]["account_id"] == "meta-account-webhook-scope-a"
    assert rows[0]["waba_id"] == "waba-webhook-scope-a"
    assert rows[0]["callback_url"] == "https://example.com/webhook-scope-a"
    assert rows[0]["status"] == "remote_subscribed"
    assert rows[0]["verify_token_present"] is True

    cross_scope_response = client.get(
        "/api/meta/accounts/webhook-subscriptions",
        params={"account_id": "meta-account-webhook-scope-a", "waba_id": "waba-webhook-scope-b"},
    )
    assert cross_scope_response.status_code == 400
    assert (
        cross_scope_response.json()["detail"]
        == "WABA 'waba-webhook-scope-b' belongs to account 'meta-account-webhook-scope-b', not 'meta-account-webhook-scope-a'."
    )


def test_meta_scope_lists_support_readiness_and_webhook_health_filters(
    client: TestClient,
) -> None:
    ready_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-account-filter-ready",
            "display_name": "Meta Filter Ready",
            "meta_business_portfolio_id": "biz-filter-ready",
            "waba_id": "waba-filter-ready",
            "access_token": "token-filter-ready",
            "verify_token": "verify-filter-ready",
            "app_secret": "secret-filter-ready",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-filter-ready",
                    "display_phone_number": "+1 555 000 0901",
                    "verified_name": "Meta Filter Ready",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert ready_response.status_code == 200

    pending_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-account-filter-pending",
            "display_name": "Meta Filter Pending",
            "meta_business_portfolio_id": "biz-filter-pending",
            "waba_id": "waba-filter-pending",
            "access_token": "token-filter-pending",
            "verify_token": "verify-filter-pending",
            "app_secret": "secret-filter-pending",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-filter-pending",
                    "display_phone_number": "+1 555 000 0902",
                    "verified_name": "Meta Filter Pending",
                    "quality_rating": "YELLOW",
                    "is_registered": False,
                }
            ],
        },
    )
    assert pending_response.status_code == 200

    for account_id, waba_id in (
        ("meta-account-filter-ready", "waba-filter-ready"),
        ("meta-account-filter-pending", "waba-filter-pending"),
    ):
        subscribe_response = client.post(
            f"/api/meta/accounts/{account_id}/wabas/{waba_id}/webhook-subscription",
            json={"callback_url": f"https://example.com/{waba_id}/webhook"},
        )
        assert subscribe_response.status_code == 200

    verify_response = client.get(
        "/webhooks/whatsapp/meta-account-filter-ready/wabas/waba-filter-ready",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-filter-ready",
            "hub.challenge": "challenge-filter-ready",
        },
    )
    assert verify_response.status_code == 200

    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-filter-ready",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0901",
                                "phone_number_id": "pn-filter-ready",
                            },
                            "messages": [
                                {
                                    "from": "14150000901",
                                    "id": "wamid.filter.ready.1",
                                    "timestamp": "1712345777",
                                    "type": "text",
                                    "text": {"body": "hola"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body, signature = sign_whatsapp_payload(webhook_payload, "secret-filter-ready")
    webhook_response = client.post(
        "/webhooks/whatsapp/meta-account-filter-ready/wabas/waba-filter-ready",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert webhook_response.status_code == 200

    ready_accounts_response = client.get(
        "/api/meta/accounts",
        params={"ready_for_meta_activation": True},
    )
    assert ready_accounts_response.status_code == 200
    assert [item["account_id"] for item in ready_accounts_response.json()] == [
        "meta-account-filter-ready"
    ]

    pending_accounts_response = client.get(
        "/api/meta/accounts",
        params={"ready_for_meta_activation": False},
    )
    assert pending_accounts_response.status_code == 200
    assert "meta-account-filter-pending" in [
        item["account_id"] for item in pending_accounts_response.json()
    ]

    verified_accounts_response = client.get(
        "/api/meta/accounts",
        params={"webhook_verification_status": "verified"},
    )
    assert verified_accounts_response.status_code == 200
    assert [item["account_id"] for item in verified_accounts_response.json()] == [
        "meta-account-filter-ready"
    ]

    healthy_accounts_response = client.get(
        "/api/meta/accounts",
        params={"webhook_runtime_status": "healthy"},
    )
    assert healthy_accounts_response.status_code == 200
    assert [item["account_id"] for item in healthy_accounts_response.json()] == [
        "meta-account-filter-ready"
    ]

    ready_phone_numbers_response = client.get(
        "/api/meta/accounts/phone-numbers",
        params={"ready_for_meta_activation": True},
    )
    assert ready_phone_numbers_response.status_code == 200
    assert [item["phone_number_id"] for item in ready_phone_numbers_response.json()] == [
        "pn-filter-ready"
    ]

    pending_phone_numbers_response = client.get(
        "/api/meta/accounts/phone-numbers",
        params={"ready_for_outbound_messages": False},
    )
    assert pending_phone_numbers_response.status_code == 200
    assert "pn-filter-pending" in [
        item["phone_number_id"] for item in pending_phone_numbers_response.json()
    ]

    verified_subscriptions_response = client.get(
        "/api/meta/accounts/webhook-subscriptions",
        params={"webhook_verification_status": "verified"},
    )
    assert verified_subscriptions_response.status_code == 200
    assert [item["account_id"] for item in verified_subscriptions_response.json()] == [
        "meta-account-filter-ready"
    ]

    pending_runtime_subscriptions_response = client.get(
        "/api/meta/accounts/webhook-subscriptions",
        params={"webhook_runtime_status": "pending"},
    )
    assert pending_runtime_subscriptions_response.status_code == 200
    assert "meta-account-filter-pending" in [
        item["account_id"] for item in pending_runtime_subscriptions_response.json()
    ]


def test_meta_account_list_exposes_formal_activation_fields_for_root_webhook_conflicts(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    shared_root_callback_url = "https://example.com/webhooks/whatsapp"
    for account_id, display_name, portfolio_id, waba_id, phone_number_id, callback_url in (
        (
            "meta-account-formal-ready-a",
            "Formal Ready A",
            "biz-formal-ready-a",
            "waba-formal-ready-a",
            "pn-formal-ready-a",
            shared_root_callback_url,
        ),
        (
            "meta-account-formal-ready-b",
            "Formal Ready B",
            "biz-formal-ready-b",
            "waba-formal-ready-b",
            "pn-formal-ready-b",
            "https://example.net/webhooks/whatsapp",
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
                "app_secret": f"secret-{account_id}",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": phone_number_id,
                        "display_phone_number": f"+1 555 000 {phone_number_id[-1] * 4}",
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
            json={"callback_url": callback_url},
        )
        assert subscribe_response.status_code == 200

    with db_session_factory() as session:
        drifted_subscription = session.query(WebhookSubscription).filter_by(
            account_id="meta-account-formal-ready-b",
            waba_id="waba-formal-ready-b",
        ).one()
        drifted_subscription.callback_url = shared_root_callback_url
        session.commit()

    response = client.get("/api/meta/accounts")
    assert response.status_code == 200
    accounts_by_id = {item["account_id"]: item for item in response.json()}
    for account_id in ("meta-account-formal-ready-a", "meta-account-formal-ready-b"):
        account = accounts_by_id[account_id]
        assert account["ready_for_meta_activation"] is True
        assert account["has_root_webhook_routing_conflict"] is True
        assert account["ready_for_formal_activation"] is False


def test_meta_scope_lists_reject_account_waba_scope_mismatch_with_explicit_error(
    client: TestClient,
) -> None:
    for account_id, waba_id, phone_number_id in (
        ("meta-account-scope-error-a", "waba-scope-error-a", "pn-scope-error-a"),
        ("meta-account-scope-error-b", "waba-scope-error-b", "pn-scope-error-b"),
    ):
        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": account_id,
                "display_name": account_id,
                "meta_business_portfolio_id": f"biz-{account_id}",
                "waba_id": waba_id,
                "access_token": f"token-{account_id}",
                "verify_token": f"verify-{account_id}",
                "app_secret": f"secret-{account_id}",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": phone_number_id,
                        "display_phone_number": f"+1 555 {phone_number_id[-4:]}",
                        "verified_name": account_id,
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert create_response.status_code == 200

    signup_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-scope-error-b",
            "display_name": "scope error signup",
            "redirect_uri": "https://example.com/embedded-signup/scope-error",
        },
    )
    assert signup_response.status_code == 200
    session_id = signup_response.json()["session_id"]

    complete_response = client.post(
        f"/api/meta/accounts/embedded-signup/session/{session_id}/complete",
        json={
            "waba_id": "waba-scope-error-b",
            "phone_number_ids": ["pn-scope-error-b"],
        },
    )
    assert complete_response.status_code == 200

    expected_detail = (
        "WABA 'waba-scope-error-b' belongs to account 'meta-account-scope-error-b', "
        "not 'meta-account-scope-error-a'."
    )

    accounts_response = client.get(
        "/api/meta/accounts",
        params={
            "account_id": "meta-account-scope-error-a",
            "waba_id": "waba-scope-error-b",
        },
    )
    assert accounts_response.status_code == 400
    assert accounts_response.json()["detail"] == expected_detail

    phone_numbers_response = client.get(
        "/api/meta/accounts/phone-numbers",
        params={
            "account_id": "meta-account-scope-error-a",
            "waba_id": "waba-scope-error-b",
        },
    )
    assert phone_numbers_response.status_code == 400
    assert phone_numbers_response.json()["detail"] == expected_detail

    subscriptions_response = client.get(
        "/api/meta/accounts/webhook-subscriptions",
        params={
            "account_id": "meta-account-scope-error-a",
            "waba_id": "waba-scope-error-b",
        },
    )
    assert subscriptions_response.status_code == 400
    assert subscriptions_response.json()["detail"] == expected_detail

    signup_sessions_response = client.get(
        "/api/meta/accounts/embedded-signup/sessions",
        params={
            "account_id": "meta-account-scope-error-a",
            "waba_id": "waba-scope-error-b",
        },
    )
    assert signup_sessions_response.status_code == 400
    assert signup_sessions_response.json()["detail"] == expected_detail

def test_embedded_signup_callback_ingestion_is_idempotent_for_duplicate_terminal_callback(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-callback-duplicate",
            "display_name": "Brand Callback Duplicate",
            "redirect_uri": "https://example.com/embedded-signup/callback-duplicate",
        },
    )
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    first_callback_response = client.post(
        f"/api/meta/accounts/embedded-signup/session/{session_id}/callback",
        json={
            "status": "completed",
            "waba_id": "waba-callback-duplicate",
            "phone_number_ids": ["pn-callback-duplicate-1"],
        },
    )
    assert first_callback_response.status_code == 200

    second_callback_response = client.post(
        f"/api/meta/accounts/embedded-signup/session/{session_id}/callback",
        json={
            "status": "completed",
            "waba_id": "waba-callback-duplicate",
            "phone_number_ids": ["pn-callback-duplicate-1"],
        },
    )
    assert second_callback_response.status_code == 200
    duplicate_payload = second_callback_response.json()
    assert duplicate_payload["status"] == "completed"
    assert duplicate_payload["waba_id"] == "waba-callback-duplicate"
    assert duplicate_payload["event_source"] == "provider_callback"


def test_embedded_signup_callback_ingestion_records_failure(client: TestClient) -> None:
    create_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-callback-failure",
            "display_name": "Brand Callback Failure",
            "redirect_uri": "https://example.com/embedded-signup/callback-failure",
        },
    )
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    callback_response = client.post(
        f"/api/meta/accounts/embedded-signup/session/{session_id}/callback",
        json={
            "status": "failed",
            "error_message": "provider_denied_signup",
            "raw_payload": {"source": "provider", "error": "denied"},
        },
    )
    assert callback_response.status_code == 200
    payload = callback_response.json()
    assert payload["status"] == "failed"
    assert payload["completion_stage"] == "failed"
    assert payload["event_source"] == "provider_callback"
    assert payload["error_message"] == "provider_denied_signup"
    assert payload["callback_received_at"] is not None


def test_embedded_signup_callback_extracts_completion_fields_from_raw_payload(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    provider = CapturingRawPayloadEmbeddedSignupProvider()
    override_meta_management_provider(client, provider)

    create_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-callback-raw-payload",
            "display_name": "Brand Callback Raw Payload",
            "redirect_uri": "https://example.com/embedded-signup/callback-raw-payload",
        },
    )
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    callback_response = client.post(
        f"/api/meta/accounts/embedded-signup/session/{session_id}/callback",
        json={
            "status": "completed",
            "raw_payload": {
                "data": {
                    "waba_id": "waba-callback-raw-payload",
                    "meta_business_portfolio_id": "biz-callback-raw-payload",
                    "phone_number_ids": [
                        "pn-callback-raw-payload-1",
                        "pn-callback-raw-payload-2",
                    ],
                    "setup_session_id": "setup-callback-raw-payload",
                    "authorization": {"code": "code-callback-raw-payload"},
                    "access_token": "token-callback-raw-payload",
                }
            },
        },
    )
    assert callback_response.status_code == 200, callback_response.text
    payload = callback_response.json()
    assert payload["status"] == "completed"
    assert payload["waba_id"] == "waba-callback-raw-payload"
    assert payload["meta_business_portfolio_id"] == "biz-callback-raw-payload"
    assert payload["linked_phone_number_ids"] == [
        "pn-callback-raw-payload-1",
        "pn-callback-raw-payload-2",
    ]
    assert payload["setup_session_id"] == "setup-callback-raw-payload"
    assert payload["authorization_code_present"] is True
    assert payload["system_user_access_token_present"] is True

    assert provider.last_completion_payload is not None
    assert provider.last_completion_payload.requested_waba_id == "waba-callback-raw-payload"
    assert (
        provider.last_completion_payload.meta_business_portfolio_id
        == "biz-callback-raw-payload"
    )
    assert provider.last_completion_payload.phone_number_ids == [
        "pn-callback-raw-payload-1",
        "pn-callback-raw-payload-2",
    ]
    assert (
        provider.last_completion_payload.setup_session_id
        == "setup-callback-raw-payload"
    )
    assert (
        provider.last_completion_payload.authorization_code
        == "code-callback-raw-payload"
    )
    assert (
        provider.last_completion_payload.system_user_access_token
        == "token-callback-raw-payload"
    )


def test_embedded_signup_webhook_alias_accepts_callback_payload(client: TestClient) -> None:
    create_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-callback-webhook",
            "display_name": "Brand Callback Webhook",
            "redirect_uri": "https://example.com/embedded-signup/callback-webhook",
        },
    )
    assert create_response.status_code == 200
    created_payload = create_response.json()
    session_id = created_payload["session_id"]
    launch_state = created_payload["launch_context"]["state"]

    webhook_response = client.post(
        f"/webhooks/meta/embedded-signup/session/{session_id}",
        json={
            "status": "completed",
            "state": launch_state,
            "waba_id": "waba-callback-webhook",
            "phone_number_ids": ["pn-callback-webhook-1"],
            "raw_payload": {"source": "webhook_alias"},
        },
    )
    assert webhook_response.status_code == 200
    payload = webhook_response.json()
    assert payload["status"] == "completed"
    assert payload["event_source"] == "provider_callback"
    assert payload["waba_id"] == "waba-callback-webhook"
    assert payload["linked_phone_number_ids"] == ["pn-callback-webhook-1"]
    assert payload.get("launch_context") is None


def test_embedded_signup_session_rejects_terminal_status_transitions(client: TestClient) -> None:
    create_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-3c",
            "display_name": "Brand C Terminal",
            "redirect_uri": "https://example.com/embedded-signup/terminal",
        },
    )
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    first_fail_response = client.post(
        f"/api/meta/accounts/embedded-signup/session/{session_id}/fail",
        json={"error_message": "user_canceled_signup"},
    )
    assert first_fail_response.status_code == 200

    second_complete_response = client.post(
        f"/api/meta/accounts/embedded-signup/session/{session_id}/complete",
        json={"waba_id": "waba-terminal"},
    )
    assert second_complete_response.status_code == 409
    assert "terminal status" in second_complete_response.json()["detail"]


def test_embedded_signup_session_failure(client: TestClient) -> None:
    create_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-4",
            "display_name": "Brand D",
            "redirect_uri": "https://example.com/embedded-signup/failure",
        },
    )
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    fail_response = client.post(
        f"/api/meta/accounts/embedded-signup/session/{session_id}/fail",
        json={"error_message": "user_canceled_signup"},
    )
    assert fail_response.status_code == 200
    failed_session = fail_response.json()
    assert failed_session["status"] == "failed"
    assert failed_session["completion_stage"] == "failed"
    assert failed_session["event_source"] == "operator"
    assert failed_session["callback_received_at"] is not None
    assert failed_session["error_message"] == "user_canceled_signup"


def test_embedded_signup_status_endpoint_returns_session(client: TestClient) -> None:
    """BE2-006: GET embedded-signup status endpoint returns session details."""
    create_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-account-status-endpoint",
            "display_name": "Status Endpoint Test",
            "redirect_uri": "https://example.com/status-endpoint",
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    session_id = created["session_id"]

    status_response = client.get(
        f"/api/meta/accounts/embedded-signup/session/{session_id}/status",
    )
    assert status_response.status_code == 200
    status = status_response.json()
    assert status["session_id"] == session_id
    assert status["status"] == "created"
    assert status["completion_stage"] == "pending_callback"
    assert status["account_id"] == "meta-account-status-endpoint"

    # Verify 404 for non-existent session
    not_found = client.get(
        "/api/meta/accounts/embedded-signup/session/non-existent-session/status",
    )
    assert not_found.status_code == 404
