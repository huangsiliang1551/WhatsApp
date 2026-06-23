from collections.abc import Generator
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db_session
from app.core.settings import Settings, get_settings
from app.db.base import Base
from app.db.models import (
    Conversation,
    Message,
    MessageEvent,
    ProviderStatusEventBuffer,
    WebhookSubscription,
    WhatsAppBusinessAccount,
    WhatsAppPhoneNumber,
    utc_now,
)
from app.main import app
from app.providers.messaging.whatsapp_provider import WhatsAppProvider
from app.services.runtime_state import RuntimeStateStore
from tests.conftest import StubMetaManagementProvider


@pytest.fixture
def strict_runtime_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "strict_runtime.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    original_env = {
        "AUTH_REQUIRED": os.environ.get("AUTH_REQUIRED"),
        "TEST_MODE": os.environ.get("TEST_MODE"),
        "LIVE_TRANSLATION_ENABLED": os.environ.get("LIVE_TRANSLATION_ENABLED"),
        "TRANSLATION_PROVIDER": os.environ.get("TRANSLATION_PROVIDER"),
    }
    os.environ["AUTH_REQUIRED"] = "true"
    os.environ["TEST_MODE"] = "false"
    os.environ["LIVE_TRANSLATION_ENABLED"] = "false"
    os.environ["TRANSLATION_PROVIDER"] = "fallback"
    get_settings.cache_clear()

    def override_get_db_session() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    engine.dispose()


def test_runtime_state_tracks_account_and_conversation_overrides(client: TestClient) -> None:
    account_response = client.post(
        "/api/runtime/accounts",
        json={
            "account_id": "ops-account-1",
            "display_name": "Ops Account",
            "provider_type": "whatsapp",
        },
    )
    assert account_response.status_code == 200

    toggle_response = client.post(
        "/api/runtime/accounts/ops-account-1/ai",
        json={"enabled": False},
    )
    assert toggle_response.status_code == 200
    assert toggle_response.json()["ai_enabled"] is False

    agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-42",
            "display_name": "Agent 42",
            "status": "online",
            "is_active": True,
        },
    )
    assert agent_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "ops-account-1",
            "conversation_id": "conv-ops-1",
            "user_id": "ops-user-1",
            "text": "need help",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    handover_response = client.post(
        "/api/runtime/conversations/conv-ops-1/handover?account_id=ops-account-1",
        json={
            "management_mode": "human_managed",
            "agent_id": "agent-42",
            "reason": "runtime_takeover",
        },
    )
    assert handover_response.status_code == 200
    assert handover_response.json()["management_mode"] == "human_managed"

    state_response = client.get("/api/runtime/state")
    assert state_response.status_code == 200
    payload = state_response.json()

    account = next(item for item in payload["accounts"] if item["account_id"] == "ops-account-1")
    conversation = next(
        item for item in payload["conversations"] if item["conversation_id"] == "conv-ops-1"
    )

    assert account["ai_enabled"] is False
    assert conversation["management_mode"] == "human_managed"
    assert conversation["assigned_agent_id"] == "agent-42"

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "ops-account-1",
            "action": "conversation_management_updated",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"]["reason"] == "runtime_takeover"


def test_runtime_conversation_controls_require_existing_conversation(client: TestClient) -> None:
    account_response = client.post(
        "/api/runtime/accounts",
        json={
            "account_id": "ops-account-missing",
            "display_name": "Ops Missing",
            "provider_type": "mock",
        },
    )
    assert account_response.status_code == 200

    toggle_response = client.post(
        "/api/runtime/conversations/conv-missing/ai?account_id=ops-account-missing",
        json={"enabled": False},
    )
    assert toggle_response.status_code == 404

    handover_response = client.post(
        "/api/runtime/conversations/conv-missing/handover?account_id=ops-account-missing",
        json={
            "management_mode": "human_managed",
            "agent_id": "agent-404",
            "reason": "missing_conversation",
        },
    )
    assert handover_response.status_code == 404


def test_runtime_conversation_ai_status_exposes_backend_reason_and_phone_number(
    client: TestClient,
) -> None:
    manual_account_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "ops-meta-account-1",
            "display_name": "Ops Meta Account",
            "meta_business_portfolio_id": "portfolio-ops-1",
            "waba_id": "waba-ops-1",
            "access_token": "token-ops-1",
            "verify_token": "verify-ops-1",
            "app_secret": "secret-ops-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-ops-1",
                    "display_phone_number": "+1 555 000 0001",
                    "verified_name": "Ops Number",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert manual_account_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "ops-meta-account-1",
            "conversation_id": "conv-ops-meta-1",
            "user_id": "ops-meta-user-1",
            "text": "need human follow-up",
            "mode": "echo",
            "phone_number_id": "pn-ops-1",
        },
    )
    assert inbound_response.status_code == 200

    disable_account_ai_response = client.post(
        "/api/runtime/accounts/ops-meta-account-1/ai",
        json={"enabled": False},
    )
    assert disable_account_ai_response.status_code == 200

    status_response = client.get(
        "/api/runtime/conversations/conv-ops-meta-1/ai-status",
        params={"account_id": "ops-meta-account-1"},
    )
    assert status_response.status_code == 200
    payload = status_response.json()

    assert payload["account_id"] == "ops-meta-account-1"
    assert payload["conversation_id"] == "conv-ops-meta-1"
    assert payload["phone_number_id"] == "pn-ops-1"
    assert payload["effective_ai_enabled"] is False
    assert payload["primary_blocking_reason"]["code"] == "account_ai_disabled"
    assert payload["blocking_reasons"][0]["scope"] == "account"

    state_response = client.get("/api/runtime/state")
    assert state_response.status_code == 200
    state_payload = state_response.json()
    conversation = next(
        item
        for item in state_payload["conversations"]
        if item["account_id"] == "ops-meta-account-1"
        and item["conversation_id"] == "conv-ops-meta-1"
    )
    assert conversation["phone_number_id"] == "pn-ops-1"


def test_runtime_conversation_ai_status_surfaces_waba_and_phone_number_scopes(
    client: TestClient,
) -> None:
    manual_account_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "ops-meta-account-scope-2",
            "display_name": "Ops Meta Account Scope 2",
            "meta_business_portfolio_id": "portfolio-ops-scope-2",
            "waba_id": "waba-ops-scope-2",
            "access_token": "token-ops-scope-2",
            "verify_token": "verify-ops-scope-2",
            "app_secret": "secret-ops-scope-2",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-ops-scope-2",
                    "display_phone_number": "+1 555 000 0002",
                    "verified_name": "Ops Scope Number",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert manual_account_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "ops-meta-account-scope-2",
            "conversation_id": "conv-ops-scope-2",
            "user_id": "ops-meta-user-scope-2",
            "text": "check ai scope blockers",
            "mode": "echo",
            "phone_number_id": "pn-ops-scope-2",
        },
    )
    assert inbound_response.status_code == 200

    deactivate_waba_response = client.patch(
        "/api/meta/accounts/ops-meta-account-scope-2/wabas/waba-ops-scope-2/status",
        json={"is_active": False},
    )
    assert deactivate_waba_response.status_code == 200

    waba_status_response = client.get(
        "/api/runtime/conversations/conv-ops-scope-2/ai-status",
        params={"account_id": "ops-meta-account-scope-2"},
    )
    assert waba_status_response.status_code == 200
    waba_payload = waba_status_response.json()
    assert waba_payload["effective_ai_enabled"] is False
    assert waba_payload["primary_blocking_reason"]["scope"] == "waba"
    assert waba_payload["primary_blocking_reason"]["code"] == "waba_inactive"
    assert any(
        reason["scope"] == "waba" and reason["code"] == "waba_inactive"
        for reason in waba_payload["blocking_reasons"]
    )

    reactivate_waba_response = client.patch(
        "/api/meta/accounts/ops-meta-account-scope-2/wabas/waba-ops-scope-2/status",
        json={"is_active": True},
    )
    assert reactivate_waba_response.status_code == 200

    deactivate_phone_response = client.patch(
        "/api/meta/accounts/ops-meta-account-scope-2/wabas/waba-ops-scope-2/phone-numbers/pn-ops-scope-2/status",
        json={"is_active": False},
    )
    assert deactivate_phone_response.status_code == 200

    phone_status_response = client.get(
        "/api/runtime/conversations/conv-ops-scope-2/ai-status",
        params={"account_id": "ops-meta-account-scope-2"},
    )
    assert phone_status_response.status_code == 200
    phone_payload = phone_status_response.json()
    assert phone_payload["effective_ai_enabled"] is False
    assert phone_payload["primary_blocking_reason"]["scope"] == "phone_number"
    assert phone_payload["primary_blocking_reason"]["code"] == "phone_number_inactive"
    assert any(
        reason["scope"] == "phone_number" and reason["code"] == "phone_number_inactive"
        for reason in phone_payload["blocking_reasons"]
    )


def test_runtime_config_summary_exposes_operator_safe_settings(client: TestClient) -> None:
    response = client.get("/api/runtime/config-summary")

    assert response.status_code == 200
    payload = response.json()

    assert payload["test_mode"] is True
    assert payload["queue_backend"] == "memory"
    assert payload["messaging_provider"] == "mock"
    assert payload["ecommerce_provider"] == "mock"
    assert payload["translation_provider"] == "fallback"
    assert payload["live_translation_enabled"] is True
    assert payload["console_language"] == "zh-CN"
    assert payload["auto_translate_on_human_handover"] is False
    assert payload["auto_translate_on_conversation_open"] is False
    assert payload["auto_translate_operator_outbound"] is True


def test_settings_resolve_translation_provider_name_follows_ai_provider_when_unset() -> None:
    runtime_settings = Settings(
        _env_file=None,
        AI_PROVIDER="openai",
        TRANSLATION_PROVIDER="",
        LIVE_TRANSLATION_ENABLED=True,
    )

    assert runtime_settings.resolve_translation_provider_name() == "openai"


def test_settings_resolve_translation_provider_name_reports_disabled_when_switch_is_off() -> None:
    runtime_settings = Settings(
        _env_file=None,
        AI_PROVIDER="deepseek",
        TRANSLATION_PROVIDER="openai",
        LIVE_TRANSLATION_ENABLED=False,
    )

    assert runtime_settings.resolve_translation_provider_name() == "disabled"


def test_runtime_support_knowledge_catalog_is_available(client: TestClient) -> None:
    response = client.get("/api/runtime/support-knowledge")

    assert response.status_code == 200
    payload = response.json()

    assert len(payload) >= 4
    assert {item["category"] for item in payload} >= {"faq", "knowledge_base"}
    assert any(item["route_name"] == "faq_refund_policy" for item in payload)
    assert any(item["source_type"] == "builtin" for item in payload)

    filtered_response = client.get(
        "/api/runtime/support-knowledge",
        params={"category": "faq"},
    )
    assert filtered_response.status_code == 200
    filtered_payload = filtered_response.json()
    assert filtered_payload
    assert all(item["category"] == "faq" for item in filtered_payload)


def test_runtime_support_knowledge_can_be_created_and_updated(client: TestClient) -> None:
    register_account_response = client.post(
        "/api/runtime/accounts",
        json={
            "account_id": "knowledge-account-1",
            "display_name": "Knowledge Account 1",
            "provider_type": "mock",
        },
    )
    assert register_account_response.status_code == 200

    create_response = client.post(
        "/api/runtime/support-knowledge",
        json={
            "account_id": "knowledge-account-1",
            "article_id": "kb-custom-1",
            "route_name": "knowledge_custom_shipping",
            "category": "knowledge_base",
            "title": "Custom shipping answer",
            "answer": "Use premium shipping for urgent requests.",
            "source_language": "en",
            "keywords": ["premium shipping", "urgent shipping"],
            "minimum_score": 1,
            "priority": 10,
            "is_active": True,
        },
    )
    assert create_response.status_code == 200
    created_payload = create_response.json()
    assert created_payload["account_id"] == "knowledge-account-1"
    assert created_payload["source_type"] == "database"
    assert created_payload["route_name"] == "knowledge_custom_shipping"

    list_response = client.get(
        "/api/runtime/support-knowledge",
        params={
            "account_id": "knowledge-account-1",
            "include_builtin": "false",
        },
    )
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert len(list_payload) == 1
    assert list_payload[0]["article_id"] == "kb-custom-1"

    update_response = client.post(
        "/api/runtime/support-knowledge/kb-custom-1",
        params={"account_id": "knowledge-account-1"},
        json={
            "answer": "Use premium shipping and include the order ID.",
            "priority": 5,
        },
    )
    assert update_response.status_code == 200
    updated_payload = update_response.json()
    assert updated_payload["answer"] == "Use premium shipping and include the order ID."
    assert updated_payload["priority"] == 5

    delete_response = client.delete(
        "/api/runtime/support-knowledge/kb-custom-1",
        params={"account_id": "knowledge-account-1"},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True

    deleted_list_response = client.get(
        "/api/runtime/support-knowledge",
        params={
            "account_id": "knowledge-account-1",
            "include_builtin": "false",
        },
    )
    assert deleted_list_response.status_code == 200
    assert deleted_list_response.json() == []


def test_runtime_support_knowledge_can_be_exported_and_imported(client: TestClient) -> None:
    register_account_response = client.post(
        "/api/runtime/accounts",
        json={
            "account_id": "knowledge-transfer-1",
            "display_name": "Knowledge Transfer 1",
            "provider_type": "mock",
        },
    )
    assert register_account_response.status_code == 200

    create_response = client.post(
        "/api/runtime/support-knowledge",
        json={
            "account_id": "knowledge-transfer-1",
            "article_id": "kb-transfer-1",
            "route_name": "faq_transfer_shipping",
            "category": "faq",
            "title": "Transfer shipping answer",
            "answer": "Shipping usually takes 3 to 5 business days.",
            "source_language": "en",
            "keywords": ["shipping time", "delivery time"],
            "minimum_score": 1,
            "priority": 12,
            "is_active": True,
        },
    )
    assert create_response.status_code == 200

    export_response = client.get(
        "/api/runtime/support-knowledge/export",
        params={"account_id": "knowledge-transfer-1"},
    )
    assert export_response.status_code == 200
    export_payload = export_response.json()
    assert export_payload["total_entries"] == 1
    assert export_payload["entries"][0]["article_id"] == "kb-transfer-1"
    assert export_payload["entries"][0]["account_id"] == "knowledge-transfer-1"

    delete_response = client.delete(
        "/api/runtime/support-knowledge/kb-transfer-1",
        params={"account_id": "knowledge-transfer-1"},
    )
    assert delete_response.status_code == 200

    import_response = client.post(
        "/api/runtime/support-knowledge/import",
        json={
            "entries": export_payload["entries"],
            "upsert_existing": True,
        },
    )
    assert import_response.status_code == 200
    import_payload = import_response.json()
    assert import_payload["created_count"] == 1
    assert import_payload["updated_count"] == 0
    assert import_payload["skipped_count"] == 0

    list_response = client.get(
        "/api/runtime/support-knowledge",
        params={
            "account_id": "knowledge-transfer-1",
            "include_builtin": "false",
        },
    )
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert len(list_payload) == 1
    assert list_payload[0]["route_name"] == "faq_transfer_shipping"

    mock_message_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "knowledge-transfer-1",
            "conversation_id": "conv-transfer-1",
            "user_id": "customer-transfer-1",
            "text": "shipping time please",
            "mode": "ai",
            "language_hint": "en",
        },
    )
    assert mock_message_response.status_code == 200
    assert mock_message_response.json()["ai"]["model"] == "faq_transfer_shipping"


def test_launch_readiness_in_test_mode_exposes_expected_blockers(client: TestClient) -> None:
    response = client.get("/api/runtime/launch-readiness")

    assert response.status_code == 200
    payload = response.json()
    checks = {item["key"]: item for item in payload["checks"]}

    assert payload["summary"]["scope"] == "system"
    assert payload["summary"]["account_id"] is None
    assert payload["summary"]["overall_status"] == "blocked"
    assert checks["runtime.test_mode"]["status"] == "blocker"
    assert checks["runtime.app_env"]["status"] == "warning"
    assert checks["messaging.provider_mode"]["status"] == "warning"
    assert checks["meta.accounts_present"]["status"] == "warning"
    assert checks["monitoring.alertmanager_config"]["status"] == "pass"


def test_launch_readiness_counts_ready_accounts_once_when_one_account_has_multiple_ready_wabas(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "TEST_MODE": os.environ.get("TEST_MODE"),
        "AUTH_REQUIRED": os.environ.get("AUTH_REQUIRED"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["TEST_MODE"] = "false"
        os.environ["AUTH_REQUIRED"] = "false"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        runtime_account_response = client.post(
            "/api/runtime/accounts",
            json={
                "account_id": "launch-multi-ready-account-1",
                "display_name": "Launch Multi Ready Account",
                "provider_type": "whatsapp",
            },
        )
        assert runtime_account_response.status_code == 200

        for suffix in ("a", "b"):
            create_response = client.post(
                "/api/meta/accounts/manual",
                json={
                    "account_id": "launch-multi-ready-account-1",
                    "display_name": "Launch Multi Ready Account",
                    "meta_business_portfolio_id": f"biz-launch-multi-ready-{suffix}",
                    "waba_id": f"waba-launch-multi-ready-{suffix}",
                    "access_token": f"token-launch-multi-ready-{suffix}",
                    "verify_token": f"verify-launch-multi-ready-{suffix}",
                    "app_secret": f"secret-launch-multi-ready-{suffix}",
                    "token_source": "system_user",
                    "phone_numbers": [
                        {
                            "phone_number_id": f"pn-launch-multi-ready-{suffix}",
                            "display_phone_number": f"+1 555 000 52{1 if suffix == 'a' else 2}1",
                            "verified_name": f"Launch Multi Ready {suffix.upper()}",
                            "quality_rating": "GREEN",
                            "is_registered": True,
                        }
                    ],
                },
            )
            assert create_response.status_code == 200

            subscribe_response = client.post(
                "/api/meta/accounts/launch-multi-ready-account-1/"
                f"wabas/waba-launch-multi-ready-{suffix}/webhook-subscription",
                json={"callback_url": f"https://example.com/launch-multi-ready/{suffix}/webhook"},
            )
            assert subscribe_response.status_code == 200

            verify_response = client.get(
                "/webhooks/whatsapp/launch-multi-ready-account-1/"
                f"wabas/waba-launch-multi-ready-{suffix}",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": f"verify-launch-multi-ready-{suffix}",
                    "hub.challenge": f"launch-multi-ready-challenge-{suffix}",
                },
            )
            assert verify_response.status_code == 200

        readiness_response = client.get("/api/runtime/launch-readiness")

        assert readiness_response.status_code == 200
        payload = readiness_response.json()
        assert payload["summary"]["active_account_count"] == 1
        assert payload["summary"]["meta_account_count"] == 2
        assert payload["summary"]["meta_ready_account_count"] == 1
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_warns_when_provider_status_buffer_has_pending_events(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_response = client.post(
        "/api/runtime/accounts",
        json={
            "account_id": "launch-buffer-account-1",
            "display_name": "Launch Buffer Account",
            "provider_type": "whatsapp",
        },
    )
    assert account_response.status_code == 200

    session = db_session_factory()
    try:
        now = utc_now()
        session.add(
            ProviderStatusEventBuffer(
                account_id="launch-buffer-account-1",
                provider_name="whatsapp",
                waba_id="waba-launch-buffer-1",
                phone_number_id="pn-launch-buffer-1",
                provider_message_id="wamid.launch.buffer.pending.1",
                external_status="delivered",
                payload={"conversation_category": "utility"},
                first_seen_at=now,
                last_seen_at=now,
                seen_count=1,
                replay_state="pending",
            )
        )
        session.add(
            ProviderStatusEventBuffer(
                account_id="launch-buffer-account-1",
                provider_name="whatsapp",
                waba_id="waba-launch-buffer-1",
                phone_number_id="pn-launch-buffer-1",
                provider_message_id="wamid.launch.buffer.replayed.1",
                external_status="read",
                payload={"conversation_category": "utility"},
                first_seen_at=now,
                last_seen_at=now,
                seen_count=1,
                replay_state="replayed",
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.get("/api/runtime/launch-readiness")

    assert response.status_code == 200
    checks = {item["key"]: item for item in response.json()["checks"]}
    buffer_check = checks["messaging.provider_status_buffer"]
    assert buffer_check["status"] == "warning"
    assert buffer_check["metadata"]["pending_count"] == 1
    assert buffer_check["metadata"]["pending_by_account"] == {
        "launch-buffer-account-1": 1,
    }
    assert buffer_check["metadata"]["pending_account_count"] == 1
    assert buffer_check["metadata"]["pending_accounts_ranked"] == [
        {
            "account_id": "launch-buffer-account-1",
            "pending_count": 1,
        }
    ]
    assert buffer_check["metadata"]["replayed_count"] == 1
    assert buffer_check["metadata"]["replayed_by_account"] == {
        "launch-buffer-account-1": 1,
    }
    oldest_pending_event = buffer_check["metadata"]["oldest_pending_event"]
    assert oldest_pending_event["account_id"] == "launch-buffer-account-1"
    assert oldest_pending_event["provider_message_id"] == "wamid.launch.buffer.pending.1"
    assert oldest_pending_event["external_status"] == "delivered"
    assert oldest_pending_event["pending_age_seconds"] >= 0


def test_launch_readiness_passes_when_provider_status_buffer_only_has_replayed_events(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_response = client.post(
        "/api/runtime/accounts",
        json={
            "account_id": "launch-buffer-replayed-only",
            "display_name": "Launch Buffer Replayed Only",
            "provider_type": "whatsapp",
        },
    )
    assert account_response.status_code == 200

    session = db_session_factory()
    try:
        now = utc_now()
        session.add(
            ProviderStatusEventBuffer(
                account_id="launch-buffer-replayed-only",
                provider_name="whatsapp",
                waba_id="waba-launch-buffer-replayed-only",
                phone_number_id="pn-launch-buffer-replayed-only",
                provider_message_id="wamid.launch.buffer.replayed.only.1",
                external_status="read",
                payload={"conversation_category": "utility"},
                first_seen_at=now,
                last_seen_at=now,
                seen_count=1,
                replay_state="replayed",
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.get("/api/runtime/launch-readiness")

    assert response.status_code == 200
    checks = {item["key"]: item for item in response.json()["checks"]}
    buffer_check = checks["messaging.provider_status_buffer"]
    assert buffer_check["status"] == "pass"
    assert buffer_check["metadata"]["pending_count"] == 0
    assert buffer_check["metadata"]["pending_by_account"] == {}
    assert buffer_check["metadata"]["pending_account_count"] == 0
    assert buffer_check["metadata"]["pending_accounts_ranked"] == []
    assert buffer_check["metadata"]["replayed_count"] == 1
    assert buffer_check["metadata"]["replayed_by_account"] == {
        "launch-buffer-replayed-only": 1,
    }
    assert buffer_check["metadata"]["oldest_pending_event"] is None


def test_launch_readiness_provider_status_buffer_metadata_ranks_accounts_and_reports_oldest_pending(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    for account_id in (
        "launch-buffer-rank-account-a",
        "launch-buffer-rank-account-b",
    ):
        account_response = client.post(
            "/api/runtime/accounts",
            json={
                "account_id": account_id,
                "display_name": account_id,
                "provider_type": "whatsapp",
            },
        )
        assert account_response.status_code == 200

    session = db_session_factory()
    try:
        now = utc_now()
        oldest = now - timedelta(minutes=15)
        newer = now - timedelta(minutes=2)
        session.add_all(
            [
                ProviderStatusEventBuffer(
                    account_id="launch-buffer-rank-account-a",
                    provider_name="whatsapp",
                    waba_id="waba-launch-buffer-rank-a",
                    phone_number_id="pn-launch-buffer-rank-a",
                    provider_message_id="wamid.launch.buffer.rank.a.oldest",
                    external_status="delivered",
                    payload={"conversation_category": "utility"},
                    first_seen_at=oldest,
                    last_seen_at=oldest,
                    seen_count=1,
                    replay_state="pending",
                ),
                ProviderStatusEventBuffer(
                    account_id="launch-buffer-rank-account-a",
                    provider_name="whatsapp",
                    waba_id="waba-launch-buffer-rank-a",
                    phone_number_id="pn-launch-buffer-rank-a",
                    provider_message_id="wamid.launch.buffer.rank.a.newer",
                    external_status="read",
                    payload={"conversation_category": "utility"},
                    first_seen_at=newer,
                    last_seen_at=newer,
                    seen_count=1,
                    replay_state="pending",
                ),
                ProviderStatusEventBuffer(
                    account_id="launch-buffer-rank-account-b",
                    provider_name="whatsapp",
                    waba_id="waba-launch-buffer-rank-b",
                    phone_number_id="pn-launch-buffer-rank-b",
                    provider_message_id="wamid.launch.buffer.rank.b.only",
                    external_status="sent",
                    payload={"conversation_category": "utility"},
                    first_seen_at=now,
                    last_seen_at=now,
                    seen_count=1,
                    replay_state="pending",
                ),
            ]
        )
        session.commit()
    finally:
        session.close()

    response = client.get("/api/runtime/launch-readiness")

    assert response.status_code == 200
    checks = {item["key"]: item for item in response.json()["checks"]}
    metadata = checks["messaging.provider_status_buffer"]["metadata"]
    assert metadata["pending_count"] == 3
    assert metadata["pending_account_count"] == 2
    assert metadata["pending_accounts_ranked"] == [
        {
            "account_id": "launch-buffer-rank-account-a",
            "pending_count": 2,
        },
        {
            "account_id": "launch-buffer-rank-account-b",
            "pending_count": 1,
        },
    ]
    oldest_pending_event = metadata["oldest_pending_event"]
    assert oldest_pending_event["account_id"] == "launch-buffer-rank-account-a"
    assert oldest_pending_event["provider_message_id"] == "wamid.launch.buffer.rank.a.oldest"
    assert oldest_pending_event["external_status"] == "delivered"
    assert oldest_pending_event["pending_age_seconds"] >= 14 * 60


def test_runtime_state_counts_provider_status_buffer_by_account_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    session = db_session_factory()
    try:
        runtime_state = RuntimeStateStore(session)
        for account_id in ("buffer-scope-a", "buffer-scope-b"):
            asyncio.run(
                runtime_state.ensure_account(
                    account_id=account_id,
                    display_name=account_id,
                    provider_type="whatsapp",
                )
            )
        now = utc_now()
        session.add_all(
            [
                ProviderStatusEventBuffer(
                    account_id="buffer-scope-a",
                    provider_name="whatsapp",
                    provider_message_id="wamid.buffer.scope.a",
                    external_status="delivered",
                    payload={},
                    first_seen_at=now,
                    last_seen_at=now,
                    seen_count=1,
                    replay_state="pending",
                ),
                ProviderStatusEventBuffer(
                    account_id="buffer-scope-b",
                    provider_name="whatsapp",
                    provider_message_id="wamid.buffer.scope.b",
                    external_status="read",
                    payload={},
                    first_seen_at=now,
                    last_seen_at=now,
                    seen_count=1,
                    replay_state="pending",
                ),
            ]
        )
        session.commit()

        scoped_counts = asyncio.run(
            runtime_state.count_provider_status_buffer_events(
                replay_state="pending",
                account_ids={"buffer-scope-a"},
            )
        )
        all_counts = asyncio.run(
            runtime_state.count_provider_status_buffer_events(replay_state="pending")
        )

        assert scoped_counts == {"buffer-scope-a": 1}
        assert all_counts["buffer-scope-a"] == 1
        assert all_counts["buffer-scope-b"] == 1
    finally:
        session.close()


def _seed_cross_account_phone_bound_conversation(session: Session) -> tuple[str, str]:
    runtime_state = RuntimeStateStore(session)
    asyncio.run(
        runtime_state.ensure_account(
            account_id="runtime-phone-scope-account-a",
            display_name="Runtime Phone Scope Account A",
            provider_type="whatsapp",
        )
    )
    asyncio.run(
        runtime_state.ensure_account(
            account_id="runtime-phone-scope-account-b",
            display_name="Runtime Phone Scope Account B",
            provider_type="whatsapp",
        )
    )
    waba_account = WhatsAppBusinessAccount(
        account_id="runtime-phone-scope-account-b",
        portfolio_id=None,
        waba_id="waba-runtime-phone-scope-b",
        onboarding_mode="manual",
        token_source="system_user",
        access_token="token-runtime-phone-scope-b",
        verify_token="verify-runtime-phone-scope-b",
        app_secret="secret-runtime-phone-scope-b",
        webhook_subscribed=False,
        is_active=True,
        ai_enabled=True,
    )
    session.add(waba_account)
    session.flush()
    phone_number = WhatsAppPhoneNumber(
        account_id="runtime-phone-scope-account-b",
        waba_account_id=waba_account.id,
        waba_id="waba-runtime-phone-scope-b",
        phone_number_id="pn-runtime-phone-scope-b",
        display_phone_number="+1 555 000 9802",
        verified_name="Runtime Phone Scope B",
        quality_rating="GREEN",
        is_registered=True,
        is_active=True,
    )
    session.add(phone_number)
    session.flush()
    conversation = Conversation(
        account_id="runtime-phone-scope-account-a",
        external_conversation_id="conv-runtime-phone-scope-a",
        phone_number_id=phone_number.id,
        customer_id="user-runtime-phone-scope-a",
        customer_language="en",
        customer_language_source="test",
        status="open",
        ai_enabled=True,
        management_mode="ai_managed",
    )
    session.add(conversation)
    session.commit()
    return conversation.external_conversation_id, phone_number.phone_number_id


def test_runtime_record_inbound_message_rejects_cross_account_phone_binding(
    db_session_factory: sessionmaker[Session],
) -> None:
    session = db_session_factory()
    try:
        conversation_id, provider_phone_number_id = _seed_cross_account_phone_bound_conversation(
            session
        )
        runtime_state = RuntimeStateStore(session)

        with pytest.raises(ValueError, match="references phone number .* not 'runtime-phone-scope-account-a'"):
            asyncio.run(
                runtime_state.record_inbound_message(
                    account_id="runtime-phone-scope-account-a",
                    conversation_id=conversation_id,
                    sender_id="user-runtime-phone-scope-a",
                    text="cross-account inbound should fail",
                    language_code="en",
                    translated_text=None,
                    translated_language_code=None,
                    payload={
                        "provider": "whatsapp",
                        "waba_id": "waba-runtime-phone-scope-b",
                        "phone_number_id": provider_phone_number_id,
                    },
                    provider_message_id="wamid.runtime.cross.phone.inbound.1",
                )
            )

        assert (
            session.query(Message)
            .filter(Message.account_id == "runtime-phone-scope-account-a")
            .count()
            == 0
        )
    finally:
        session.close()


def test_runtime_record_outbound_message_rejects_cross_account_phone_binding(
    db_session_factory: sessionmaker[Session],
) -> None:
    session = db_session_factory()
    try:
        conversation_id, provider_phone_number_id = _seed_cross_account_phone_bound_conversation(
            session
        )
        runtime_state = RuntimeStateStore(session)

        with pytest.raises(ValueError, match="references phone number .* not 'runtime-phone-scope-account-a'"):
            asyncio.run(
                runtime_state.record_outbound_message(
                    account_id="runtime-phone-scope-account-a",
                    conversation_id=conversation_id,
                    recipient_id="user-runtime-phone-scope-a",
                    text="cross-account outbound should fail",
                    language_code="en",
                    translated_text=None,
                    translated_language_code=None,
                    delivery_mode="manual_operator_send",
                    ai_generated=False,
                    payload={
                        "provider": "whatsapp",
                        "waba_id": "waba-runtime-phone-scope-b",
                        "phone_number_id": provider_phone_number_id,
                    },
                    provider_message_id="wamid.runtime.cross.phone.outbound.1",
                )
            )

        assert (
            session.query(Message)
            .filter(Message.account_id == "runtime-phone-scope-account-a")
            .count()
            == 0
        )
    finally:
        session.close()


def test_runtime_state_provider_status_buffer_uses_nested_payload_scope_for_filters(
    db_session_factory: sessionmaker[Session],
) -> None:
    session = db_session_factory()
    try:
        runtime_state = RuntimeStateStore(session)
        asyncio.run(
            runtime_state.ensure_account(
                account_id="buffer-nested-scope-account",
                display_name="buffer-nested-scope-account",
                provider_type="whatsapp",
            )
        )
        now = utc_now()
        session.add(
            ProviderStatusEventBuffer(
                account_id="buffer-nested-scope-account",
                provider_name="whatsapp",
                waba_id="waba-buffer-nested-scope-stale",
                phone_number_id="pn-buffer-nested-scope-stale",
                provider_message_id="wamid.buffer.nested.scope.1",
                external_status="delivered",
                payload={
                    "provider_payload": {
                        "waba_id": "waba-buffer-nested-scope-official",
                        "metadata": {
                            "phone_number_id": "pn-buffer-nested-scope-official",
                        },
                    }
                },
                first_seen_at=now,
                last_seen_at=now,
                seen_count=1,
                replay_state="pending",
            )
        )
        session.commit()

        scoped_counts = asyncio.run(
            runtime_state.count_provider_status_buffer_events(
                replay_state="pending",
                account_id="buffer-nested-scope-account",
                waba_id="waba-buffer-nested-scope-official",
                phone_number_id="pn-buffer-nested-scope-official",
            )
        )
        stale_counts = asyncio.run(
            runtime_state.count_provider_status_buffer_events(
                replay_state="pending",
                account_id="buffer-nested-scope-account",
                waba_id="waba-buffer-nested-scope-stale",
                phone_number_id="pn-buffer-nested-scope-stale",
            )
        )
        scoped_items = asyncio.run(
            runtime_state.list_provider_status_buffer_events(
                account_id="buffer-nested-scope-account",
                waba_id="waba-buffer-nested-scope-official",
                phone_number_id="pn-buffer-nested-scope-official",
            )
        )

        assert scoped_counts == {"buffer-nested-scope-account": 1}
        assert stale_counts == {}
        assert len(scoped_items) == 1
        resolved_waba_id, resolved_phone_number_id = runtime_state.resolve_provider_status_buffer_scope(
            scoped_items[0]
        )
        assert resolved_waba_id == "waba-buffer-nested-scope-official"
        assert resolved_phone_number_id == "pn-buffer-nested-scope-official"
    finally:
        session.close()


def test_runtime_provider_status_buffer_route_lists_filtered_entries(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_response = client.post(
        "/api/runtime/accounts",
        json={
            "account_id": "buffer-route-account-1",
            "display_name": "Buffer Route Account 1",
            "provider_type": "whatsapp",
        },
    )
    assert account_response.status_code == 200

    other_account_response = client.post(
        "/api/runtime/accounts",
        json={
            "account_id": "buffer-route-account-2",
            "display_name": "Buffer Route Account 2",
            "provider_type": "whatsapp",
        },
    )
    assert other_account_response.status_code == 200

    session = db_session_factory()
    try:
        now = utc_now()
        session.add_all(
            [
                ProviderStatusEventBuffer(
                    account_id="buffer-route-account-1",
                    provider_name="whatsapp",
                    waba_id="waba-buffer-route-1",
                    phone_number_id="pn-buffer-route-1",
                    provider_message_id="wamid.buffer.route.pending.1",
                    external_status="delivered",
                    payload={"conversation_category": "utility"},
                    first_seen_at=now,
                    last_seen_at=now,
                    seen_count=2,
                    replay_state="pending",
                ),
                ProviderStatusEventBuffer(
                    account_id="buffer-route-account-1",
                    provider_name="whatsapp",
                    waba_id="waba-buffer-route-1",
                    phone_number_id="pn-buffer-route-1",
                    provider_message_id="wamid.buffer.route.replayed.1",
                    external_status="read",
                    payload={"conversation_category": "utility"},
                    first_seen_at=now,
                    last_seen_at=now,
                    seen_count=1,
                    replay_state="replayed",
                ),
                ProviderStatusEventBuffer(
                    account_id="buffer-route-account-2",
                    provider_name="whatsapp",
                    waba_id="waba-buffer-route-2",
                    phone_number_id="pn-buffer-route-2",
                    provider_message_id="wamid.buffer.route.pending.2",
                    external_status="failed",
                    payload={"conversation_category": "marketing"},
                    first_seen_at=now,
                    last_seen_at=now,
                    seen_count=1,
                    replay_state="pending",
                ),
            ]
        )
        session.commit()
    finally:
        session.close()

    response = client.get(
        "/api/runtime/provider-status-buffer",
        params={
            "account_id": "buffer-route-account-1",
            "provider_name": "whatsapp",
            "replay_state": "pending",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["returned_count"] == 1
    assert payload["pending_count"] == 1
    assert payload["replayed_count"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["account_id"] == "buffer-route-account-1"
    assert payload["items"][0]["provider_message_id"] == "wamid.buffer.route.pending.1"
    assert payload["items"][0]["replay_state"] == "pending"
    assert payload["items"][0]["seen_count"] == 2
    assert payload["items"][0]["pending_age_seconds"] >= 0


def test_runtime_provider_status_buffer_route_prefers_nested_payload_scope(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_response = client.post(
        "/api/runtime/accounts",
        json={
            "account_id": "buffer-route-nested-scope-account",
            "display_name": "Buffer Route Nested Scope Account",
            "provider_type": "whatsapp",
        },
    )
    assert account_response.status_code == 200

    session = db_session_factory()
    try:
        now = utc_now()
        session.add(
            ProviderStatusEventBuffer(
                account_id="buffer-route-nested-scope-account",
                provider_name="whatsapp",
                waba_id="waba-buffer-route-nested-stale",
                phone_number_id="pn-buffer-route-nested-stale",
                provider_message_id="wamid.buffer.route.nested.scope.1",
                external_status="delivered",
                payload={
                    "provider_payload": {
                        "waba_id": "waba-buffer-route-nested-official",
                        "metadata": {
                            "phone_number_id": "pn-buffer-route-nested-official",
                        },
                    }
                },
                first_seen_at=now,
                last_seen_at=now,
                seen_count=1,
                replay_state="pending",
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.get(
        "/api/runtime/provider-status-buffer",
        params={
            "account_id": "buffer-route-nested-scope-account",
            "waba_id": "waba-buffer-route-nested-official",
            "phone_number_id": "pn-buffer-route-nested-official",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["returned_count"] == 1
    assert payload["items"][0]["provider_message_id"] == "wamid.buffer.route.nested.scope.1"
    assert payload["items"][0]["waba_id"] == "waba-buffer-route-nested-official"
    assert payload["items"][0]["phone_number_id"] == "pn-buffer-route-nested-official"


def test_runtime_provider_status_buffer_route_rejects_mismatched_waba_and_phone_scope(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    manual_account_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "buffer-scope-mismatch-account-1",
            "display_name": "Buffer Scope Mismatch Account",
            "meta_business_portfolio_id": "portfolio-buffer-scope-mismatch-1",
            "waba_id": "waba-buffer-scope-mismatch-1",
            "access_token": "token-buffer-scope-mismatch-1",
            "verify_token": "verify-buffer-scope-mismatch-1",
            "app_secret": "secret-buffer-scope-mismatch-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-buffer-scope-mismatch-1",
                    "display_phone_number": "+1 555 000 9701",
                    "verified_name": "Buffer Scope Mismatch Number",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert manual_account_response.status_code == 200

    session = db_session_factory()
    try:
        now = utc_now()
        session.add(
            ProviderStatusEventBuffer(
                account_id="buffer-scope-mismatch-account-1",
                provider_name="whatsapp",
                waba_id="waba-buffer-scope-mismatch-1",
                phone_number_id="pn-buffer-scope-mismatch-1",
                provider_message_id="wamid.buffer.scope.mismatch.1",
                external_status="delivered",
                payload={},
                first_seen_at=now,
                last_seen_at=now,
                seen_count=1,
                replay_state="pending",
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.get(
        "/api/runtime/provider-status-buffer",
        params={
            "account_id": "buffer-scope-mismatch-account-1",
            "waba_id": "waba-buffer-scope-mismatch-other",
            "phone_number_id": "pn-buffer-scope-mismatch-1",
        },
    )

    assert response.status_code == 400
    assert "belongs to WABA 'waba-buffer-scope-mismatch-1'" in str(response.json()["detail"])


def test_runtime_provider_status_buffer_route_keeps_inaccessible_phone_scope_non_leaking(
    strict_runtime_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    for account_id, waba_id, phone_number_id in (
        (
            "buffer-scope-visible-account",
            "waba-buffer-scope-visible",
            "pn-buffer-scope-visible",
        ),
        (
            "buffer-scope-hidden-account",
            "waba-buffer-scope-hidden",
            "pn-buffer-scope-hidden",
        ),
    ):
        create_response = strict_runtime_client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": account_id,
                "display_name": account_id,
                "meta_business_portfolio_id": f"portfolio-{account_id}",
                "waba_id": waba_id,
                "access_token": f"token-{account_id}",
                "verify_token": f"verify-{account_id}",
                "app_secret": f"secret-{account_id}",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": phone_number_id,
                        "display_phone_number": f"+1 555 {phone_number_id[-4:]}",
                        "verified_name": phone_number_id,
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
            headers={
                "X-Actor-Id": "runtime-super-admin",
                "X-Actor-Role": "super_admin",
            },
        )
        assert create_response.status_code == 200

    session = db_session_factory()
    try:
        now = utc_now()
        session.add_all(
            [
                ProviderStatusEventBuffer(
                    account_id="buffer-scope-visible-account",
                    provider_name="whatsapp",
                    waba_id="waba-buffer-scope-visible",
                    phone_number_id="pn-buffer-scope-visible",
                    provider_message_id="wamid.buffer.scope.visible",
                    external_status="delivered",
                    payload={},
                    first_seen_at=now,
                    last_seen_at=now,
                    seen_count=1,
                    replay_state="pending",
                ),
                ProviderStatusEventBuffer(
                    account_id="buffer-scope-hidden-account",
                    provider_name="whatsapp",
                    waba_id="waba-buffer-scope-hidden",
                    phone_number_id="pn-buffer-scope-hidden",
                    provider_message_id="wamid.buffer.scope.hidden",
                    external_status="read",
                    payload={},
                    first_seen_at=now,
                    last_seen_at=now,
                    seen_count=1,
                    replay_state="pending",
                ),
            ]
        )
        session.commit()
    finally:
        session.close()

    response = strict_runtime_client.get(
        "/api/runtime/provider-status-buffer",
        params={"phone_number_id": "pn-buffer-scope-hidden"},
        headers={
            "X-Actor-Id": "runtime-operator-visible-account",
            "X-Actor-Role": "operator",
            "X-Actor-Account-Ids": "buffer-scope-visible-account",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert payload["returned_count"] == 0


def test_runtime_provider_status_buffer_replay_route_marks_events_replayed(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    manual_account_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "buffer-replay-account-1",
            "display_name": "Buffer Replay Account",
            "meta_business_portfolio_id": "portfolio-buffer-replay-1",
            "waba_id": "waba-buffer-replay-1",
            "access_token": "token-buffer-replay-1",
            "verify_token": "verify-buffer-replay-1",
            "app_secret": "secret-buffer-replay-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-buffer-replay-1",
                    "display_phone_number": "+1 555 000 9601",
                    "verified_name": "Buffer Replay Number",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert manual_account_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "buffer-replay-account-1",
            "conversation_id": "conv-buffer-replay-1",
            "user_id": "user-buffer-replay-1",
            "text": "buffer replay",
            "mode": "echo",
            "phone_number_id": "pn-buffer-replay-1",
        },
    )
    assert inbound_response.status_code == 200

    session = db_session_factory()
    try:
        runtime_state = RuntimeStateStore(session)
        message = asyncio.run(
            runtime_state.record_outbound_message(
                account_id="buffer-replay-account-1",
                conversation_id="conv-buffer-replay-1",
                recipient_id="user-buffer-replay-1",
                text="buffer replay outbound",
                language_code="en",
                translated_text=None,
                translated_language_code=None,
                delivery_mode="manual_operator_send",
                ai_generated=False,
                payload={
                    "provider": "whatsapp",
                    "waba_id": "waba-buffer-replay-1",
                    "phone_number_id": "pn-buffer-replay-1",
                },
                provider_message_id="wamid.buffer.replay.target.1",
            )
        )
        session.add(
            ProviderStatusEventBuffer(
                account_id="buffer-replay-account-1",
                provider_name="whatsapp",
                waba_id="waba-buffer-replay-1",
                phone_number_id="pn-buffer-replay-1",
                provider_message_id=message.provider_message_id or "wamid.buffer.replay.target.1",
                external_status="delivered",
                recipient_id="user-buffer-replay-1",
                occurred_at="2026-06-09T12:00:00Z",
                payload={"conversation_category": "utility"},
                first_seen_at=utc_now(),
                last_seen_at=utc_now(),
                seen_count=1,
                replay_state="pending",
            )
        )
        session.commit()
    finally:
        session.close()

    replay_response = client.post(
        "/api/runtime/provider-status-buffer/replay",
        json={
            "account_id": "buffer-replay-account-1",
            "provider_name": "whatsapp",
            "provider_message_id": "wamid.buffer.replay.target.1",
        },
    )

    assert replay_response.status_code == 200
    replay_payload = replay_response.json()
    assert replay_payload["checked_count"] == 1
    assert replay_payload["replayed_count"] == 1
    assert replay_payload["failed_count"] == 0

    verify_session = db_session_factory()
    try:
        buffered_event = verify_session.query(ProviderStatusEventBuffer).filter_by(
            account_id="buffer-replay-account-1",
            provider_name="whatsapp",
            provider_message_id="wamid.buffer.replay.target.1",
            external_status="delivered",
        ).one()
        assert buffered_event.replay_state == "replayed"
        assert buffered_event.replayed_at is not None
        assert buffered_event.replayed_message_event_id is not None
        assert buffered_event.replay_error is None
    finally:
        verify_session.close()


def test_runtime_provider_status_buffer_replay_prefers_message_snapshot_scope_after_relationship_drift(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "buffer-replay-snapshot-drift-account-1"
    official_waba_id = "waba-buffer-replay-snapshot-drift-1"
    official_phone_number_id = "pn-buffer-replay-snapshot-drift-1"
    legacy_waba_id = "waba-buffer-replay-snapshot-drift-legacy"
    legacy_phone_number_id = "pn-buffer-replay-snapshot-drift-legacy"
    provider_message_id = "wamid.buffer.replay.snapshot.drift.1"
    message_id: str | None = None

    manual_account_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": account_id,
            "display_name": "Buffer Replay Snapshot Drift Account",
            "meta_business_portfolio_id": "portfolio-buffer-replay-snapshot-drift-1",
            "waba_id": official_waba_id,
            "access_token": "token-buffer-replay-snapshot-drift-1",
            "verify_token": "verify-buffer-replay-snapshot-drift-1",
            "app_secret": "secret-buffer-replay-snapshot-drift-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": official_phone_number_id,
                    "display_phone_number": "+1 555 000 9602",
                    "verified_name": "Buffer Replay Snapshot Drift Number",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert manual_account_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": account_id,
            "conversation_id": "conv-buffer-replay-snapshot-drift-1",
            "user_id": "user-buffer-replay-snapshot-drift-1",
            "text": "buffer replay snapshot drift",
            "mode": "echo",
            "phone_number_id": official_phone_number_id,
        },
    )
    assert inbound_response.status_code == 200

    session = db_session_factory()
    try:
        runtime_state = RuntimeStateStore(session)
        message = asyncio.run(
            runtime_state.record_outbound_message(
                account_id=account_id,
                conversation_id="conv-buffer-replay-snapshot-drift-1",
                recipient_id="user-buffer-replay-snapshot-drift-1",
                text="buffer replay snapshot drift outbound",
                language_code="en",
                translated_text=None,
                translated_language_code=None,
                delivery_mode="manual_operator_send",
                ai_generated=False,
                payload={
                    "provider": "whatsapp",
                    "waba_id": official_waba_id,
                    "phone_number_id": official_phone_number_id,
                },
                provider_message_id=provider_message_id,
            )
        )
        message_id = message.id

        legacy_waba = (
            session.query(WhatsAppBusinessAccount)
            .filter(
                WhatsAppBusinessAccount.account_id == account_id,
                WhatsAppBusinessAccount.waba_id == official_waba_id,
            )
            .one()
        )
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

        legacy_phone_number = (
            session.query(WhatsAppPhoneNumber)
            .filter(
                WhatsAppPhoneNumber.account_id == account_id,
                WhatsAppPhoneNumber.phone_number_id == official_phone_number_id,
            )
            .one()
        )
        legacy_phone_number.phone_number_id = legacy_phone_number_id
        legacy_phone_number.waba_id = legacy_waba_id
        session.flush()

        recreated_phone_number = WhatsAppPhoneNumber(
            account_id=account_id,
            waba_account_id=recreated_waba.id,
            waba_id=official_waba_id,
            phone_number_id=official_phone_number_id,
            display_phone_number=legacy_phone_number.display_phone_number,
            verified_name=legacy_phone_number.verified_name,
            quality_rating=legacy_phone_number.quality_rating,
            quality_event=legacy_phone_number.quality_event,
            previous_quality_rating=legacy_phone_number.previous_quality_rating,
            messaging_limit_tier=legacy_phone_number.messaging_limit_tier,
            max_daily_conversations_per_business=legacy_phone_number.max_daily_conversations_per_business,
            last_quality_event_at=legacy_phone_number.last_quality_event_at,
            last_status_payload=legacy_phone_number.last_status_payload,
            is_registered=legacy_phone_number.is_registered,
            is_active=legacy_phone_number.is_active,
        )
        session.add(recreated_phone_number)

        session.add(
            ProviderStatusEventBuffer(
                account_id=account_id,
                provider_name="whatsapp",
                waba_id=official_waba_id,
                phone_number_id=official_phone_number_id,
                provider_message_id=message.provider_message_id or provider_message_id,
                external_status="delivered",
                recipient_id="user-buffer-replay-snapshot-drift-1",
                occurred_at="2026-06-10T12:00:00Z",
                payload={"conversation_category": "utility"},
                first_seen_at=utc_now(),
                last_seen_at=utc_now(),
                seen_count=1,
                replay_state="pending",
            )
        )
        session.commit()
    finally:
        session.close()

    replay_response = client.post(
        "/api/runtime/provider-status-buffer/replay",
        json={
            "account_id": account_id,
            "provider_name": "whatsapp",
            "provider_message_id": provider_message_id,
        },
    )

    assert replay_response.status_code == 200
    replay_payload = replay_response.json()
    assert replay_payload["checked_count"] == 1
    assert replay_payload["replayed_count"] == 1
    assert replay_payload["failed_count"] == 0

    verify_session = db_session_factory()
    try:
        buffered_event = verify_session.query(ProviderStatusEventBuffer).filter_by(
            account_id=account_id,
            provider_name="whatsapp",
            provider_message_id=provider_message_id,
            external_status="delivered",
        ).one()
        assert buffered_event.replay_state == "replayed"
        assert buffered_event.replay_error is None

        status_event = (
            verify_session.query(MessageEvent)
            .filter_by(
                account_id=account_id,
                message_id=message_id,
                event_type="whatsapp_status_delivered",
            )
            .one()
        )
        assert status_event.waba_id == official_waba_id
        assert status_event.phone_number_id == official_phone_number_id
    finally:
        verify_session.close()


def test_runtime_provider_status_buffer_replay_rejects_mismatched_waba_and_phone_scope(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    manual_account_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "buffer-replay-scope-mismatch-account-1",
            "display_name": "Buffer Replay Scope Mismatch Account",
            "meta_business_portfolio_id": "portfolio-buffer-replay-scope-mismatch-1",
            "waba_id": "waba-buffer-replay-scope-mismatch-1",
            "access_token": "token-buffer-replay-scope-mismatch-1",
            "verify_token": "verify-buffer-replay-scope-mismatch-1",
            "app_secret": "secret-buffer-replay-scope-mismatch-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-buffer-replay-scope-mismatch-1",
                    "display_phone_number": "+1 555 000 9702",
                    "verified_name": "Buffer Replay Scope Mismatch Number",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert manual_account_response.status_code == 200

    session = db_session_factory()
    try:
        session.add(
            ProviderStatusEventBuffer(
                account_id="buffer-replay-scope-mismatch-account-1",
                provider_name="whatsapp",
                waba_id="waba-buffer-replay-scope-mismatch-1",
                phone_number_id="pn-buffer-replay-scope-mismatch-1",
                provider_message_id="wamid.buffer.replay.scope.mismatch.1",
                external_status="delivered",
                payload={},
                first_seen_at=utc_now(),
                last_seen_at=utc_now(),
                seen_count=1,
                replay_state="pending",
            )
        )
        session.commit()
    finally:
        session.close()

    replay_response = client.post(
        "/api/runtime/provider-status-buffer/replay",
        json={
            "account_id": "buffer-replay-scope-mismatch-account-1",
            "provider_name": "whatsapp",
            "waba_id": "waba-buffer-replay-scope-mismatch-other",
            "phone_number_id": "pn-buffer-replay-scope-mismatch-1",
        },
    )

    assert replay_response.status_code == 400
    assert "belongs to WABA 'waba-buffer-replay-scope-mismatch-1'" in str(
        replay_response.json()["detail"]
    )


def test_runtime_provider_status_buffer_replay_route_returns_conflict_when_message_missing(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_response = client.post(
        "/api/runtime/accounts",
        json={
            "account_id": "buffer-replay-conflict-account-1",
            "display_name": "Buffer Replay Conflict Account",
            "provider_type": "whatsapp",
        },
    )
    assert account_response.status_code == 200

    session = db_session_factory()
    try:
        session.add(
            ProviderStatusEventBuffer(
                account_id="buffer-replay-conflict-account-1",
                provider_name="whatsapp",
                waba_id="waba-buffer-replay-conflict-1",
                phone_number_id="pn-buffer-replay-conflict-1",
                provider_message_id="wamid.buffer.replay.conflict.1",
                external_status="failed",
                payload={"conversation_category": "utility"},
                first_seen_at=utc_now(),
                last_seen_at=utc_now(),
                seen_count=1,
                replay_state="pending",
            )
        )
        session.commit()
    finally:
        session.close()

    replay_response = client.post(
        "/api/runtime/provider-status-buffer/replay",
        json={
            "account_id": "buffer-replay-conflict-account-1",
            "provider_name": "whatsapp",
            "provider_message_id": "wamid.buffer.replay.conflict.1",
        },
    )

    assert replay_response.status_code == 409
    assert "none could be replayed" in replay_response.json()["detail"].lower()

    verify_session = db_session_factory()
    try:
        buffered_event = verify_session.query(ProviderStatusEventBuffer).filter_by(
            account_id="buffer-replay-conflict-account-1",
            provider_name="whatsapp",
            provider_message_id="wamid.buffer.replay.conflict.1",
            external_status="failed",
        ).one()
        assert buffered_event.replay_state == "pending"
        assert buffered_event.replay_error == "matching_message_not_found"
    finally:
        verify_session.close()


def test_launch_readiness_provider_status_buffer_oldest_event_prefers_nested_payload_scope(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_response = client.post(
        "/api/runtime/accounts",
        json={
            "account_id": "launch-buffer-nested-scope-account",
            "display_name": "Launch Buffer Nested Scope Account",
            "provider_type": "whatsapp",
        },
    )
    assert account_response.status_code == 200

    session = db_session_factory()
    try:
        now = utc_now()
        session.add(
            ProviderStatusEventBuffer(
                account_id="launch-buffer-nested-scope-account",
                provider_name="whatsapp",
                waba_id="waba-launch-buffer-nested-stale",
                phone_number_id="pn-launch-buffer-nested-stale",
                provider_message_id="wamid.launch.buffer.nested.scope.1",
                external_status="read",
                payload={
                    "provider_payload": {
                        "waba_id": "waba-launch-buffer-nested-official",
                        "metadata": {
                            "phone_number_id": "pn-launch-buffer-nested-official",
                        },
                    }
                },
                first_seen_at=now - timedelta(minutes=3),
                last_seen_at=now,
                seen_count=1,
                replay_state="pending",
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.get("/api/runtime/launch-readiness")

    assert response.status_code == 200
    checks = {item["key"]: item for item in response.json()["checks"]}
    oldest_pending_event = checks["messaging.provider_status_buffer"]["metadata"][
        "oldest_pending_event"
    ]
    assert oldest_pending_event["account_id"] == "launch-buffer-nested-scope-account"
    assert oldest_pending_event["provider_message_id"] == "wamid.launch.buffer.nested.scope.1"
    assert oldest_pending_event["waba_id"] == "waba-launch-buffer-nested-official"
    assert oldest_pending_event["phone_number_id"] == "pn-launch-buffer-nested-official"


def test_runtime_audit_logs_reject_mismatched_waba_and_phone_scope(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    manual_account_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "audit-scope-mismatch-account-1",
            "display_name": "Audit Scope Mismatch Account",
            "meta_business_portfolio_id": "portfolio-audit-scope-mismatch-1",
            "waba_id": "waba-audit-scope-mismatch-1",
            "access_token": "token-audit-scope-mismatch-1",
            "verify_token": "verify-audit-scope-mismatch-1",
            "app_secret": "secret-audit-scope-mismatch-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-audit-scope-mismatch-1",
                    "display_phone_number": "+1 555 000 9703",
                    "verified_name": "Audit Scope Mismatch Number",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert manual_account_response.status_code == 200

    session = db_session_factory()
    try:
        runtime_state = RuntimeStateStore(session)
        runtime_state.add_audit_log(
            account_id="audit-scope-mismatch-account-1",
            actor_type="system",
            actor_id=None,
            action="audit_scope_mismatch_test",
            target_type="runtime",
            target_id="audit-scope-mismatch-account-1",
            payload={
                "waba_id": "waba-audit-scope-mismatch-1",
                "phone_number_id": "pn-audit-scope-mismatch-1",
            },
        )
        session.commit()
    finally:
        session.close()

    response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "audit-scope-mismatch-account-1",
            "waba_id": "waba-audit-scope-mismatch-other",
            "phone_number_id": "pn-audit-scope-mismatch-1",
        },
    )

    assert response.status_code == 400
    assert "belongs to WABA 'waba-audit-scope-mismatch-1'" in str(response.json()["detail"])


def test_launch_readiness_keeps_remote_subscribed_account_blocked_until_webhook_is_verified(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "TEST_MODE": os.environ.get("TEST_MODE"),
        "AUTH_REQUIRED": os.environ.get("AUTH_REQUIRED"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["TEST_MODE"] = "false"
        os.environ["AUTH_REQUIRED"] = "false"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "launch-ready-account-1",
                "display_name": "Launch Ready Account",
                "meta_business_portfolio_id": "biz-launch-ready-1",
                "waba_id": "waba-launch-ready-1",
                "access_token": "token-launch-ready-1",
                "verify_token": "verify-launch-ready-1",
                "app_secret": "secret-launch-ready-1",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-launch-ready-1",
                        "display_phone_number": "+1 555 000 9001",
                        "verified_name": "Launch Ready Number",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert create_response.status_code == 200

        subscribe_response = client.post(
            "/api/meta/accounts/launch-ready-account-1/wabas/waba-launch-ready-1/webhook-subscription",
            json={
                "callback_url": "https://example.com/launch-ready/webhook",
            },
        )
        assert subscribe_response.status_code == 200

        response = client.get("/api/runtime/launch-readiness")

        assert response.status_code == 200
        payload = response.json()
        checks = {item["key"]: item for item in payload["checks"]}
        account_check_key = "meta.account.launch-ready-account-1.waba-launch-ready-1"

        verification_key = (
            "meta.account.launch-ready-account-1."
            "waba-launch-ready-1.webhook_verification"
        )

        assert payload["summary"]["overall_status"] == "blocked"
        assert payload["summary"]["queue_backend"] == "redis"
        assert payload["summary"]["messaging_provider"] == "whatsapp"
        assert payload["summary"]["meta_ready_account_count"] == 0
        assert checks["runtime.test_mode"]["status"] == "pass"
        assert checks["runtime.app_env"]["status"] == "pass"
        assert checks["ai.openai_key"]["status"] == "pass"
        assert checks["messaging.provider_mode"]["status"] == "blocker"
        assert checks["meta.accounts_present"]["status"] == "pass"
        assert checks[account_check_key]["status"] == "warning"
        assert checks[account_check_key]["metadata"]["account_is_active"] is True
        assert checks[account_check_key]["metadata"]["waba_is_active"] is True
        assert checks[account_check_key]["metadata"]["ready_for_webhook_delivery"] is False
        assert checks[account_check_key]["metadata"]["ready_for_outbound_messages"] is True
        assert checks[account_check_key]["metadata"]["ready_for_meta_activation"] is False
        assert checks[account_check_key]["metadata"]["registered_phone_number_count"] == 1
        assert checks[account_check_key]["metadata"]["phone_number_count"] == 1
        assert checks[account_check_key]["metadata"]["webhook_subscribed"] is True
        assert checks[account_check_key]["metadata"]["webhook_verification_status"] == "pending"
        assert checks[account_check_key]["metadata"]["webhook_runtime_status"] == "pending"
        assert checks[account_check_key]["metadata"]["webhook_signature_failure_count"] == 0
        assert checks[account_check_key]["metadata"]["blocking_reasons"] == ["webhook_not_ready"]
        assert checks[verification_key]["status"] == "blocker"
        assert checks[verification_key]["metadata"]["webhook_verification_status"] == "pending"
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_uses_subscription_app_secret_snapshot_when_waba_secret_drifts(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
    override_meta_management_provider,
) -> None:
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "TEST_MODE": os.environ.get("TEST_MODE"),
        "AUTH_REQUIRED": os.environ.get("AUTH_REQUIRED"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["TEST_MODE"] = "false"
        os.environ["AUTH_REQUIRED"] = "false"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "launch-secret-snapshot-account-1",
                "display_name": "Launch Secret Snapshot Account",
                "meta_business_portfolio_id": "biz-launch-secret-snapshot-1",
                "waba_id": "waba-launch-secret-snapshot-1",
                "access_token": "token-launch-secret-snapshot-1",
                "verify_token": "verify-launch-secret-snapshot-1",
                "app_secret": "secret-launch-secret-snapshot-1",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-launch-secret-snapshot-1",
                        "display_phone_number": "+1 555 000 9151",
                        "verified_name": "Launch Secret Snapshot Number",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert create_response.status_code == 200

        subscribe_response = client.post(
            "/api/meta/accounts/launch-secret-snapshot-account-1/"
            "wabas/waba-launch-secret-snapshot-1/webhook-subscription",
            json={"callback_url": "https://example.com/launch-secret-snapshot/webhook"},
        )
        assert subscribe_response.status_code == 200

        with db_session_factory() as session:
            waba_account = session.query(WhatsAppBusinessAccount).filter(
                WhatsAppBusinessAccount.account_id == "launch-secret-snapshot-account-1",
                WhatsAppBusinessAccount.waba_id == "waba-launch-secret-snapshot-1",
            ).one()
            subscription = session.query(WebhookSubscription).filter(
                WebhookSubscription.account_id == "launch-secret-snapshot-account-1",
                WebhookSubscription.waba_id == "waba-launch-secret-snapshot-1",
            ).one()

            assert subscription.app_secret == "secret-launch-secret-snapshot-1"

            waba_account.app_secret = None
            waba_account.webhook_subscribed = True
            waba_account.webhook_verification_status = "verified"
            waba_account.webhook_runtime_status = "healthy"
            subscription.status = "remote_subscribed"
            session.add(waba_account)
            session.add(subscription)
            session.commit()

        response = client.get("/api/runtime/launch-readiness")

        assert response.status_code == 200
        checks = {item["key"]: item for item in response.json()["checks"]}
        account_key = "meta.account.launch-secret-snapshot-account-1.waba-launch-secret-snapshot-1"

        assert checks[account_key]["metadata"]["has_app_secret"] is True
        assert checks[account_key]["metadata"]["ready_for_webhook_delivery"] is True
        assert checks[account_key]["metadata"]["ready_for_outbound_messages"] is True
        assert checks[account_key]["metadata"]["ready_for_meta_activation"] is True
        assert checks[account_key]["metadata"]["blocking_reasons"] == []
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_recovers_after_webhook_verification_retry(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "TEST_MODE": os.environ.get("TEST_MODE"),
        "AUTH_REQUIRED": os.environ.get("AUTH_REQUIRED"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["TEST_MODE"] = "false"
        os.environ["AUTH_REQUIRED"] = "false"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "launch-verify-retry-account-1",
                "display_name": "Launch Verify Retry Account",
                "meta_business_portfolio_id": "biz-launch-verify-retry-1",
                "waba_id": "waba-launch-verify-retry-1",
                "access_token": "token-launch-verify-retry-1",
                "verify_token": "verify-launch-verify-retry-1",
                "app_secret": "secret-launch-verify-retry-1",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-launch-verify-retry-1",
                        "display_phone_number": "+1 555 000 9051",
                        "verified_name": "Launch Verify Retry Number",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert create_response.status_code == 200

        subscribe_response = client.post(
            "/api/meta/accounts/launch-verify-retry-account-1/wabas/waba-launch-verify-retry-1/webhook-subscription",
            json={"callback_url": "https://example.com/launch-verify-retry/webhook"},
        )
        assert subscribe_response.status_code == 200

        failed_verify_response = client.get(
            "/webhooks/whatsapp/launch-verify-retry-account-1/wabas/waba-launch-verify-retry-1",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-launch-verify-retry-token",
                "hub.challenge": "launch-verify-retry-challenge-failed",
            },
        )
        assert failed_verify_response.status_code == 403

        failed_readiness_response = client.get("/api/runtime/launch-readiness")
        assert failed_readiness_response.status_code == 200
        failed_checks = {
            item["key"]: item for item in failed_readiness_response.json()["checks"]
        }
        account_key = "meta.account.launch-verify-retry-account-1.waba-launch-verify-retry-1"
        verification_key = (
            "meta.account.launch-verify-retry-account-1."
            "waba-launch-verify-retry-1.webhook_verification"
        )
        runtime_key = (
            "meta.account.launch-verify-retry-account-1."
            "waba-launch-verify-retry-1.webhook_runtime"
        )

        assert failed_checks["messaging.provider_mode"]["status"] == "blocker"
        assert failed_checks[account_key]["status"] == "warning"
        assert failed_checks[verification_key]["status"] == "blocker"
        assert (
            failed_checks[verification_key]["metadata"]["webhook_last_verification_error"]
            == "Webhook verify token mismatch."
        )

        success_verify_response = client.get(
            "/webhooks/whatsapp/launch-verify-retry-account-1/wabas/waba-launch-verify-retry-1",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-launch-verify-retry-1",
                "hub.challenge": "launch-verify-retry-challenge-success",
            },
        )
        assert success_verify_response.status_code == 200

        ready_response = client.get("/api/runtime/launch-readiness")
        assert ready_response.status_code == 200
        payload = ready_response.json()
        checks = {item["key"]: item for item in payload["checks"]}

        assert payload["summary"]["meta_ready_account_count"] == 1
        assert checks["messaging.provider_mode"]["status"] == "pass"
        assert checks[account_key]["status"] == "pass"
        assert checks[account_key]["metadata"]["ready_for_meta_activation"] is True
        assert checks[verification_key]["status"] == "pass"
        assert checks[verification_key]["metadata"]["webhook_verification_status"] == "verified"
        assert checks[verification_key]["metadata"]["webhook_last_verification_error"] is None
        assert checks[runtime_key]["status"] == "blocker"
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_does_not_regress_after_failed_verify_probe_on_verified_waba(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "TEST_MODE": os.environ.get("TEST_MODE"),
        "AUTH_REQUIRED": os.environ.get("AUTH_REQUIRED"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["TEST_MODE"] = "false"
        os.environ["AUTH_REQUIRED"] = "false"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "launch-verify-stable-account-1",
                "display_name": "Launch Verify Stable Account",
                "meta_business_portfolio_id": "biz-launch-verify-stable-1",
                "waba_id": "waba-launch-verify-stable-1",
                "access_token": "token-launch-verify-stable-1",
                "verify_token": "verify-launch-verify-stable-1",
                "app_secret": "secret-launch-verify-stable-1",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-launch-verify-stable-1",
                        "display_phone_number": "+1 555 000 9052",
                        "verified_name": "Launch Verify Stable Number",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert create_response.status_code == 200

        subscribe_response = client.post(
            "/api/meta/accounts/launch-verify-stable-account-1/"
            "wabas/waba-launch-verify-stable-1/webhook-subscription",
            json={"callback_url": "https://example.com/launch-verify-stable/webhook"},
        )
        assert subscribe_response.status_code == 200

        success_verify_response = client.get(
            "/webhooks/whatsapp/launch-verify-stable-account-1/"
            "wabas/waba-launch-verify-stable-1",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-launch-verify-stable-1",
                "hub.challenge": "launch-verify-stable-challenge-success",
            },
        )
        assert success_verify_response.status_code == 200

        initial_ready_response = client.get("/api/runtime/launch-readiness")
        assert initial_ready_response.status_code == 200
        initial_checks = {
            item["key"]: item for item in initial_ready_response.json()["checks"]
        }
        account_key = "meta.account.launch-verify-stable-account-1.waba-launch-verify-stable-1"
        verification_key = (
            "meta.account.launch-verify-stable-account-1."
            "waba-launch-verify-stable-1.webhook_verification"
        )

        assert initial_checks[account_key]["status"] == "pass"
        assert initial_checks[account_key]["metadata"]["ready_for_webhook_delivery"] is True
        assert initial_checks[account_key]["metadata"]["ready_for_meta_activation"] is True
        assert initial_checks[verification_key]["status"] == "pass"
        assert initial_checks[verification_key]["metadata"]["webhook_verification_status"] == "verified"
        assert initial_checks[verification_key]["metadata"]["webhook_last_verification_error"] is None

        failed_probe_response = client.get(
            "/webhooks/whatsapp/launch-verify-stable-account-1/"
            "wabas/waba-launch-verify-stable-1",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-launch-verify-stable-token",
                "hub.challenge": "launch-verify-stable-challenge-failed",
            },
        )
        assert failed_probe_response.status_code == 403

        stable_ready_response = client.get("/api/runtime/launch-readiness")
        assert stable_ready_response.status_code == 200
        payload = stable_ready_response.json()
        checks = {item["key"]: item for item in payload["checks"]}

        assert payload["summary"]["meta_ready_account_count"] == 1
        assert checks["messaging.provider_mode"]["status"] == "pass"
        assert checks[account_key]["status"] == "pass"
        assert checks[account_key]["metadata"]["ready_for_webhook_delivery"] is True
        assert checks[account_key]["metadata"]["ready_for_meta_activation"] is True
        assert checks[verification_key]["status"] == "pass"
        assert checks[verification_key]["metadata"]["webhook_verification_status"] == "verified"
        assert checks[verification_key]["metadata"]["webhook_last_verification_error"] is None
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_flags_root_verify_token_conflict(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()

        for account_id, display_name, portfolio_id, waba_id in (
            (
                "launch-root-verify-conflict-account-a",
                "Launch Root Verify Conflict A",
                "launch-root-verify-conflict-portfolio-a",
                "waba-launch-root-verify-conflict-a",
            ),
            (
                "launch-root-verify-conflict-account-b",
                "Launch Root Verify Conflict B",
                "launch-root-verify-conflict-portfolio-b",
                "waba-launch-root-verify-conflict-b",
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
                    "verify-launch-root-conflict-shared"
                    if account_id == "launch-root-verify-conflict-account-a"
                    else "verify-launch-root-conflict-unique-b"
                ),
                "app_secret": f"secret-{account_id}",
                "token_source": "system_user",
                "phone_numbers": [],
            },
        )
        assert response.status_code == 200

        with db_session_factory() as session:
            conflicting_waba = session.query(WhatsAppBusinessAccount).filter(
                WhatsAppBusinessAccount.account_id == "launch-root-verify-conflict-account-b",
                WhatsAppBusinessAccount.waba_id == "waba-launch-root-verify-conflict-b",
            ).one()
            conflicting_waba.verify_token = "verify-launch-root-conflict-shared"
            session.add(conflicting_waba)
            session.commit()

        response = client.get("/api/runtime/launch-readiness")
        assert response.status_code == 200
        checks = {item["key"]: item for item in response.json()["checks"]}
        verify_routing_check = checks["meta.webhook_verify_token_routing"]
        assert verify_routing_check["status"] == "blocker"
        assert verify_routing_check["metadata"]["conflict_count"] == 1
        assert len(verify_routing_check["metadata"]["conflicts"][0]["scopes"]) == 2
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_messaging_provider_mode_stays_blocked_when_ready_wabas_are_globally_conflicted(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()

        for account_id, display_name, portfolio_id, waba_id, phone_number_id, verify_token in (
            (
                "launch-root-conflict-ready-account-a",
                "Launch Root Conflict Ready A",
                "launch-root-conflict-ready-portfolio-a",
                "waba-launch-root-conflict-ready-a",
                "pn-launch-root-conflict-ready-a",
                "verify-launch-root-conflict-ready-a",
            ),
            (
                "launch-root-conflict-ready-account-b",
                "Launch Root Conflict Ready B",
                "launch-root-conflict-ready-portfolio-b",
                "waba-launch-root-conflict-ready-b",
                "pn-launch-root-conflict-ready-b",
                "verify-launch-root-conflict-ready-b",
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
            assert create_response.status_code == 200, create_response.text

        with db_session_factory() as session:
            shared_verify_token = "verify-launch-root-conflict-ready-shared"
            for account_id, waba_id in (
                (
                    "launch-root-conflict-ready-account-a",
                    "waba-launch-root-conflict-ready-a",
                ),
                (
                    "launch-root-conflict-ready-account-b",
                    "waba-launch-root-conflict-ready-b",
                ),
            ):
                waba_account = session.query(WhatsAppBusinessAccount).filter(
                    WhatsAppBusinessAccount.account_id == account_id,
                    WhatsAppBusinessAccount.waba_id == waba_id,
                ).one()
                waba_account.webhook_subscribed = True
                waba_account.verify_token = shared_verify_token
                waba_account.webhook_verification_status = "verified"
                waba_account.webhook_last_verified_at = utc_now()
                session.add(
                    WebhookSubscription(
                        account_id=account_id,
                        waba_account_id=waba_account.id,
                        waba_id=waba_id,
                        callback_url=f"https://example.com/{account_id}/webhook",
                        verify_token=shared_verify_token,
                        app_id=None,
                        status="remote_subscribed",
                        subscribed_at=utc_now(),
                    )
                )
                session.add(waba_account)
            session.commit()

        response = client.get("/api/runtime/launch-readiness")
        assert response.status_code == 200
        payload = response.json()
        checks = {item["key"]: item for item in payload["checks"]}

        assert payload["summary"]["meta_ready_account_count"] == 0
        assert checks["meta.webhook_verify_token_routing"]["status"] == "blocker"
        assert checks["messaging.provider_mode"]["status"] == "blocker"
        assert "formal activation" in checks["messaging.provider_mode"]["message"]
        assert (
            checks["meta.account.launch-root-conflict-ready-account-a.waba-launch-root-conflict-ready-a"]["status"]
            == "blocker"
        )
        assert (
            checks["meta.account.launch-root-conflict-ready-account-b.waba-launch-root-conflict-ready-b"]["status"]
            == "blocker"
        )
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_flags_root_receive_signature_conflict(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()

        shared_callback_url = "https://example.com/webhooks/whatsapp"
        for account_id, display_name, portfolio_id, waba_id, verify_token, app_secret in (
            (
                "launch-root-receive-conflict-account-a",
                "Launch Root Receive Conflict A",
                "launch-root-receive-conflict-portfolio-a",
                "waba-launch-root-receive-conflict-a",
                "verify-launch-root-receive-conflict-a",
                "secret-launch-root-receive-conflict-a",
            ),
            (
                "launch-root-receive-conflict-account-b",
                "Launch Root Receive Conflict B",
                "launch-root-receive-conflict-portfolio-b",
                "waba-launch-root-receive-conflict-b",
                "verify-launch-root-receive-conflict-b",
                "secret-launch-root-receive-conflict-b",
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
            assert create_response.status_code == 200, create_response.text

        with db_session_factory() as session:
            for account_id, waba_id in (
                (
                    "launch-root-receive-conflict-account-a",
                    "waba-launch-root-receive-conflict-a",
                ),
                (
                    "launch-root-receive-conflict-account-b",
                    "waba-launch-root-receive-conflict-b",
                ),
            ):
                waba_account = session.query(WhatsAppBusinessAccount).filter(
                    WhatsAppBusinessAccount.account_id == account_id,
                    WhatsAppBusinessAccount.waba_id == waba_id,
                ).one()
                waba_account.webhook_subscribed = True
                session.add(
                    WebhookSubscription(
                        account_id=account_id,
                        waba_account_id=waba_account.id,
                        waba_id=waba_id,
                        callback_url=shared_callback_url,
                        verify_token=waba_account.verify_token,
                        app_id=None,
                        status="remote_subscribed",
                        subscribed_at=utc_now(),
                    )
                )
                session.add(waba_account)
            session.commit()

        response = client.get("/api/runtime/launch-readiness")
        assert response.status_code == 200
        checks = {item["key"]: item for item in response.json()["checks"]}
        signature_routing_check = checks["meta.webhook_root_receive_signature_routing"]

        assert signature_routing_check["status"] == "blocker"
        assert signature_routing_check["metadata"]["conflict_count"] == 1
        assert signature_routing_check["metadata"]["hidden_scope_count"] == 0

        conflicts = signature_routing_check["metadata"]["conflicts"]
        assert len(conflicts) == 1
        assert conflicts[0]["callback_target"] == shared_callback_url
        assert conflicts[0]["distinct_app_secret_count"] == 2
        assert conflicts[0]["hidden_scope_count"] == 0
        assert conflicts[0]["scopes"] == [
            {
                "account_id": "launch-root-receive-conflict-account-a",
                "waba_id": "waba-launch-root-receive-conflict-a",
            },
            {
                "account_id": "launch-root-receive-conflict-account-b",
                "waba_id": "waba-launch-root-receive-conflict-b",
            },
        ]
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_passes_root_receive_signature_routing_with_shared_app_secret(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()

        shared_callback_url = "https://example.com/webhooks/whatsapp"
        shared_app_secret = "secret-launch-root-receive-shared"
        for account_id, display_name, portfolio_id, waba_id, verify_token in (
            (
                "launch-root-receive-shared-secret-account-a",
                "Launch Root Receive Shared Secret A",
                "launch-root-receive-shared-secret-portfolio-a",
                "waba-launch-root-receive-shared-secret-a",
                "verify-launch-root-receive-shared-secret-a",
            ),
            (
                "launch-root-receive-shared-secret-account-b",
                "Launch Root Receive Shared Secret B",
                "launch-root-receive-shared-secret-portfolio-b",
                "waba-launch-root-receive-shared-secret-b",
                "verify-launch-root-receive-shared-secret-b",
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
            assert create_response.status_code == 200, create_response.text

        with db_session_factory() as session:
            for account_id, waba_id in (
                (
                    "launch-root-receive-shared-secret-account-a",
                    "waba-launch-root-receive-shared-secret-a",
                ),
                (
                    "launch-root-receive-shared-secret-account-b",
                    "waba-launch-root-receive-shared-secret-b",
                ),
            ):
                waba_account = session.query(WhatsAppBusinessAccount).filter(
                    WhatsAppBusinessAccount.account_id == account_id,
                    WhatsAppBusinessAccount.waba_id == waba_id,
                ).one()
                waba_account.webhook_subscribed = True
                session.add(
                    WebhookSubscription(
                        account_id=account_id,
                        waba_account_id=waba_account.id,
                        waba_id=waba_id,
                        callback_url=shared_callback_url,
                        verify_token=waba_account.verify_token,
                        app_id=None,
                        status="remote_subscribed",
                        subscribed_at=utc_now(),
                    )
                )
                session.add(waba_account)
            session.commit()

        response = client.get("/api/runtime/launch-readiness")
        assert response.status_code == 200
        checks = {item["key"]: item for item in response.json()["checks"]}
        signature_routing_check = checks["meta.webhook_root_receive_signature_routing"]

        assert signature_routing_check["status"] == "pass"
        assert "at most one app secret" in signature_routing_check["message"]
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_account_checks_reflect_root_receive_signature_conflict(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
    override_meta_management_provider,
) -> None:
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "TEST_MODE": os.environ.get("TEST_MODE"),
        "AUTH_REQUIRED": os.environ.get("AUTH_REQUIRED"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["TEST_MODE"] = "false"
        os.environ["AUTH_REQUIRED"] = "false"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        shared_callback_url = "https://example.com/webhooks/whatsapp"
        for account_id, display_name, portfolio_id, waba_id, verify_token, app_secret, phone_number_id, display_phone in (
            (
                "launch-root-conflict-ready-account-a",
                "Launch Root Conflict Ready A",
                "launch-root-conflict-ready-portfolio-a",
                "waba-launch-root-conflict-ready-a",
                "verify-launch-root-conflict-ready-a",
                "secret-launch-root-conflict-ready-a",
                "pn-launch-root-conflict-ready-a",
                "+1 555 000 9501",
            ),
            (
                "launch-root-conflict-ready-account-b",
                "Launch Root Conflict Ready B",
                "launch-root-conflict-ready-portfolio-b",
                "waba-launch-root-conflict-ready-b",
                "verify-launch-root-conflict-ready-b",
                "secret-launch-root-conflict-ready-b",
                "pn-launch-root-conflict-ready-b",
                "+1 555 000 9502",
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
            assert create_response.status_code == 200, create_response.text

            verify_response = client.get(
                f"/webhooks/whatsapp/{account_id}/wabas/{waba_id}",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": verify_token,
                    "hub.challenge": f"challenge-{account_id}",
                },
            )
            assert verify_response.status_code == 200

        with db_session_factory() as session:
            for account_id, waba_id in (
                (
                    "launch-root-conflict-ready-account-a",
                    "waba-launch-root-conflict-ready-a",
                ),
                (
                    "launch-root-conflict-ready-account-b",
                    "waba-launch-root-conflict-ready-b",
                ),
            ):
                waba_account = session.query(WhatsAppBusinessAccount).filter(
                    WhatsAppBusinessAccount.account_id == account_id,
                    WhatsAppBusinessAccount.waba_id == waba_id,
                ).one()
                waba_account.webhook_subscribed = True
                session.add(
                    WebhookSubscription(
                        account_id=account_id,
                        waba_account_id=waba_account.id,
                        waba_id=waba_id,
                        callback_url=shared_callback_url,
                        verify_token=waba_account.verify_token,
                        app_id=None,
                        status="remote_subscribed",
                        subscribed_at=utc_now(),
                    )
                )
                session.add(waba_account)
            session.commit()

        response = client.get("/api/runtime/launch-readiness")
        assert response.status_code == 200
        payload = response.json()
        checks = {item["key"]: item for item in payload["checks"]}
        global_conflict_check = checks["meta.webhook_root_receive_signature_routing"]
        first_account_key = (
            "meta.account.launch-root-conflict-ready-account-a."
            "waba-launch-root-conflict-ready-a"
        )
        second_account_key = (
            "meta.account.launch-root-conflict-ready-account-b."
            "waba-launch-root-conflict-ready-b"
        )

        assert payload["summary"]["meta_ready_account_count"] == 0
        assert global_conflict_check["status"] == "blocker"
        assert checks[first_account_key]["status"] == "blocker"
        assert checks[second_account_key]["status"] == "blocker"
        assert (
            checks[first_account_key]["message"]
            == "WABA waba-launch-root-conflict-ready-a meets local webhook and outbound prerequisites, but root webhook routing conflicts still block formal activation."
        )
        assert (
            checks[second_account_key]["message"]
            == "WABA waba-launch-root-conflict-ready-b meets local webhook and outbound prerequisites, but root webhook routing conflicts still block formal activation."
        )
        assert (
            checks[first_account_key]["action_hint"]
            == "Resolve root webhook verify-token or app-secret conflicts before formal Meta rollout."
        )
        assert checks[first_account_key]["metadata"]["ready_for_webhook_delivery"] is True
        assert checks[first_account_key]["metadata"]["ready_for_outbound_messages"] is True
        assert checks[first_account_key]["metadata"]["ready_for_meta_activation"] is True
        assert checks[first_account_key]["metadata"]["scope_ready_for_formal_activation"] is False
        assert checks[first_account_key]["metadata"]["has_root_webhook_routing_conflict"] is True
        assert checks[first_account_key]["metadata"]["blocking_reasons"] == []
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_flags_root_receive_signature_conflict_for_query_variants(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()

        shared_callback_target = "https://example.com/webhooks/whatsapp"
        callback_urls = {
            "launch-root-receive-query-conflict-account-a": f"{shared_callback_target}?tenant=alpha",
            "launch-root-receive-query-conflict-account-b": f"{shared_callback_target}?tenant=beta",
        }
        for account_id, display_name, portfolio_id, waba_id, verify_token, app_secret in (
            (
                "launch-root-receive-query-conflict-account-a",
                "Launch Root Receive Query Conflict A",
                "launch-root-receive-query-conflict-portfolio-a",
                "waba-launch-root-receive-query-conflict-a",
                "verify-launch-root-receive-query-conflict-a",
                "secret-launch-root-receive-query-conflict-a",
            ),
            (
                "launch-root-receive-query-conflict-account-b",
                "Launch Root Receive Query Conflict B",
                "launch-root-receive-query-conflict-portfolio-b",
                "waba-launch-root-receive-query-conflict-b",
                "verify-launch-root-receive-query-conflict-b",
                "secret-launch-root-receive-query-conflict-b",
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
            assert create_response.status_code == 200, create_response.text

        with db_session_factory() as session:
            for account_id, waba_id in (
                (
                    "launch-root-receive-query-conflict-account-a",
                    "waba-launch-root-receive-query-conflict-a",
                ),
                (
                    "launch-root-receive-query-conflict-account-b",
                    "waba-launch-root-receive-query-conflict-b",
                ),
            ):
                waba_account = session.query(WhatsAppBusinessAccount).filter(
                    WhatsAppBusinessAccount.account_id == account_id,
                    WhatsAppBusinessAccount.waba_id == waba_id,
                ).one()
                waba_account.webhook_subscribed = True
                session.add(
                    WebhookSubscription(
                        account_id=account_id,
                        waba_account_id=waba_account.id,
                        waba_id=waba_id,
                        callback_url=callback_urls[account_id],
                        verify_token=waba_account.verify_token,
                        app_id=None,
                        status="remote_subscribed",
                        subscribed_at=utc_now(),
                    )
                )
                session.add(waba_account)
            session.commit()

        response = client.get("/api/runtime/launch-readiness")
        assert response.status_code == 200
        checks = {item["key"]: item for item in response.json()["checks"]}
        signature_routing_check = checks["meta.webhook_root_receive_signature_routing"]

        assert signature_routing_check["status"] == "blocker"
        assert signature_routing_check["metadata"]["conflict_count"] == 1
        assert signature_routing_check["metadata"]["hidden_scope_count"] == 0

        conflicts = signature_routing_check["metadata"]["conflicts"]
        assert len(conflicts) == 1
        assert conflicts[0]["callback_target"] == shared_callback_target
        assert conflicts[0]["distinct_app_secret_count"] == 2
        assert conflicts[0]["hidden_scope_count"] == 0
        assert conflicts[0]["scopes"] == [
            {
                "account_id": "launch-root-receive-query-conflict-account-a",
                "waba_id": "waba-launch-root-receive-query-conflict-a",
            },
            {
                "account_id": "launch-root-receive-query-conflict-account-b",
                "waba_id": "waba-launch-root-receive-query-conflict-b",
            },
        ]
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_ignores_historical_root_receive_conflicts_after_latest_subscription_moves_off_root(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    original_env = {
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
    }

    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()

        root_callback_url = "https://example.com/webhooks/whatsapp"
        for account_id, display_name, portfolio_id, waba_id, verify_token, app_secret in (
            (
                "launch-root-receive-history-account-a",
                "Launch Root Receive History A",
                "launch-root-receive-history-portfolio-a",
                "waba-launch-root-receive-history-a",
                "verify-launch-root-receive-history-a",
                "secret-launch-root-receive-history-a",
            ),
            (
                "launch-root-receive-history-account-b",
                "Launch Root Receive History B",
                "launch-root-receive-history-portfolio-b",
                "waba-launch-root-receive-history-b",
                "verify-launch-root-receive-history-b",
                "secret-launch-root-receive-history-b",
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
            assert create_response.status_code == 200, create_response.text

        with db_session_factory() as session:
            first_waba = session.query(WhatsAppBusinessAccount).filter(
                WhatsAppBusinessAccount.account_id == "launch-root-receive-history-account-a",
                WhatsAppBusinessAccount.waba_id == "waba-launch-root-receive-history-a",
            ).one()
            second_waba = session.query(WhatsAppBusinessAccount).filter(
                WhatsAppBusinessAccount.account_id == "launch-root-receive-history-account-b",
                WhatsAppBusinessAccount.waba_id == "waba-launch-root-receive-history-b",
            ).one()

            first_waba.webhook_subscribed = True
            second_waba.webhook_subscribed = True
            session.add_all([first_waba, second_waba])
            session.add_all(
                [
                    WebhookSubscription(
                        account_id=first_waba.account_id,
                        waba_account_id=first_waba.id,
                        waba_id=first_waba.waba_id,
                        callback_url=root_callback_url,
                        verify_token=first_waba.verify_token,
                        app_id=None,
                        status="remote_subscribed",
                        subscribed_at=utc_now(),
                    ),
                    WebhookSubscription(
                        account_id=second_waba.account_id,
                        waba_account_id=second_waba.id,
                        waba_id=second_waba.waba_id,
                        callback_url=root_callback_url,
                        verify_token=second_waba.verify_token,
                        app_id=None,
                        status="remote_subscribed",
                        subscribed_at=utc_now(),
                    ),
                    WebhookSubscription(
                        account_id=second_waba.account_id,
                        waba_account_id=second_waba.id,
                        waba_id=second_waba.waba_id,
                        callback_url="https://example.com/webhooks/whatsapp/launch-root-receive-history-account-b",
                        verify_token=second_waba.verify_token,
                        app_id=None,
                        status="remote_subscribed",
                        subscribed_at=utc_now(),
                    ),
                ]
            )
            session.commit()

        response = client.get("/api/runtime/launch-readiness")
        assert response.status_code == 200
        checks = {item["key"]: item for item in response.json()["checks"]}
        signature_routing_check = checks["meta.webhook_root_receive_signature_routing"]

        assert signature_routing_check["status"] == "pass"
        assert "at most one app secret" in signature_routing_check["message"]
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_account_check_metadata_exposes_blocking_reasons(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "launch-meta-warning-account-1",
            "display_name": "Launch Meta Warning Account",
            "meta_business_portfolio_id": "biz-launch-warning-1",
            "waba_id": "waba-launch-warning-1",
            "access_token": "token-launch-warning-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-launch-warning-1",
                    "display_phone_number": "+1 555 000 9401",
                    "verified_name": "Launch Warning Number",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert create_response.status_code == 200

    response = client.get("/api/runtime/launch-readiness")

    assert response.status_code == 200
    checks = {item["key"]: item for item in response.json()["checks"]}
    account_check = checks["meta.account.launch-meta-warning-account-1.waba-launch-warning-1"]

    assert account_check["status"] == "warning"
    assert account_check["metadata"]["account_is_active"] is True
    assert account_check["metadata"]["waba_is_active"] is True
    assert account_check["metadata"]["ready_for_webhook_delivery"] is False
    assert account_check["metadata"]["ready_for_outbound_messages"] is True
    assert account_check["metadata"]["ready_for_meta_activation"] is False
    assert account_check["metadata"]["blocking_reasons"] == [
        "missing_verify_token",
        "missing_app_secret",
        "missing_webhook_subscription",
    ]


def test_launch_readiness_hides_other_accounts_meta_readiness_checks_for_scoped_actor(
    strict_runtime_client: TestClient,
    override_meta_management_provider,
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-launch-meta-scope",
        "X-Actor-Role": "super_admin",
    }
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        get_settings.cache_clear()
        override_meta_management_provider(strict_runtime_client, StubMetaManagementProvider())

        for account_id, display_name, portfolio_id, waba_id, phone_number_id in (
            (
                "launch-runtime-scope-account-a",
                "Launch Runtime Scope A",
                "biz-launch-runtime-scope-a",
                "waba-launch-runtime-scope-a",
                "pn-launch-runtime-scope-a",
            ),
            (
                "launch-runtime-scope-account-b",
                "Launch Runtime Scope B",
                "biz-launch-runtime-scope-b",
                "waba-launch-runtime-scope-b",
                "pn-launch-runtime-scope-b",
            ),
        ):
            create_response = strict_runtime_client.post(
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
                            "verified_name": f"{display_name} Number",
                            "quality_rating": "GREEN",
                            "is_registered": True,
                        }
                    ],
                },
                headers=admin_headers,
            )
            assert create_response.status_code == 200

            subscribe_response = strict_runtime_client.post(
                f"/api/meta/accounts/{account_id}/wabas/{waba_id}/webhook-subscription",
                json={"callback_url": f"https://example.com/{account_id}/webhook"},
                headers=admin_headers,
            )
            assert subscribe_response.status_code == 200

            verify_response = strict_runtime_client.get(
                f"/webhooks/whatsapp/{account_id}/wabas/{waba_id}",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": f"verify-{account_id}",
                    "hub.challenge": f"challenge-{account_id}",
                },
                headers=admin_headers,
            )
            assert verify_response.status_code == 200

        scoped_response = strict_runtime_client.get(
            "/api/runtime/launch-readiness",
            headers={
                "X-Actor-Id": "readonly-launch-runtime-scope-a",
                "X-Actor-Role": "readonly",
                "X-Actor-Account-Ids": "launch-runtime-scope-account-a",
            },
        )

        assert scoped_response.status_code == 200
        payload = scoped_response.json()
        checks = {item["key"]: item for item in payload["checks"]}
        account_scoped_checks = [
            item for item in payload["checks"] if item.get("scope") == "account"
        ]
        visible_keys = set(checks)
        hidden_prefix = "meta.account.launch-runtime-scope-account-b."

        assert payload["summary"]["active_account_count"] == 1
        assert payload["summary"]["meta_account_count"] == 1
        assert payload["summary"]["meta_ready_account_count"] == 1
        assert "meta.account.launch-runtime-scope-account-a.waba-launch-runtime-scope-a" in visible_keys
        assert (
            "meta.account.launch-runtime-scope-account-a."
            "waba-launch-runtime-scope-a.webhook_verification"
        ) in visible_keys
        assert (
            "meta.account.launch-runtime-scope-account-a."
            "waba-launch-runtime-scope-a.webhook_runtime"
        ) in visible_keys
        assert all(not key.startswith(hidden_prefix) for key in visible_keys)
        assert {item["account_id"] for item in account_scoped_checks} == {
            "launch-runtime-scope-account-a"
        }
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_tracks_webhook_verification_and_runtime_health(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "TEST_MODE": os.environ.get("TEST_MODE"),
        "AUTH_REQUIRED": os.environ.get("AUTH_REQUIRED"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["TEST_MODE"] = "false"
        os.environ["AUTH_REQUIRED"] = "false"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "launch-webhook-health-account-1",
                "display_name": "Launch Webhook Health Account",
                "meta_business_portfolio_id": "biz-launch-health-1",
                "waba_id": "waba-launch-health-1",
                "access_token": "token-launch-health-1",
                "verify_token": "verify-launch-health-1",
                "app_secret": "secret-launch-health-1",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-launch-health-1",
                        "display_phone_number": "+1 555 000 9101",
                        "verified_name": "Launch Health Number",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert create_response.status_code == 200

        subscribe_response = client.post(
            "/api/meta/accounts/launch-webhook-health-account-1/wabas/waba-launch-health-1/webhook-subscription",
            json={"callback_url": "https://example.com/launch-health/webhook"},
        )
        assert subscribe_response.status_code == 200

        verify_response = client.get(
            "/webhooks/whatsapp/launch-webhook-health-account-1/wabas/waba-launch-health-1",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-launch-health-1",
                "hub.challenge": "launch-health-challenge",
            },
        )
        assert verify_response.status_code == 200

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-launch-health-1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 9101",
                                    "phone_number_id": "pn-launch-health-1",
                                },
                                "statuses": [
                                    {
                                        "id": "wamid.launch.health.status.1",
                                        "status": "delivered",
                                        "timestamp": "1712346678",
                                        "recipient_id": "14150009101",
                                        "conversation": {
                                            "id": "meta-conversation-launch-health-1",
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
        signature = WhatsAppProvider.build_signature("secret-launch-health-1", raw_body)

        webhook_response = client.post(
            "/webhooks/whatsapp/launch-webhook-health-account-1/wabas/waba-launch-health-1",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )
        assert webhook_response.status_code == 200

        response = client.get("/api/runtime/launch-readiness")
        assert response.status_code == 200
        payload = response.json()
        checks = {item["key"]: item for item in payload["checks"]}
        account_key = "meta.account.launch-webhook-health-account-1.waba-launch-health-1"

        verification_key = (
            "meta.account.launch-webhook-health-account-1."
            "waba-launch-health-1.webhook_verification"
        )
        runtime_key = (
            "meta.account.launch-webhook-health-account-1."
            "waba-launch-health-1.webhook_runtime"
        )

        assert payload["summary"]["meta_ready_account_count"] == 1
        assert checks["messaging.provider_mode"]["status"] == "pass"
        assert checks[account_key]["status"] == "pass"
        assert checks[account_key]["metadata"]["ready_for_webhook_delivery"] is True
        assert checks[account_key]["metadata"]["ready_for_outbound_messages"] is True
        assert checks[account_key]["metadata"]["ready_for_meta_activation"] is True
        assert checks[account_key]["metadata"]["webhook_verification_status"] == "verified"
        assert checks[account_key]["metadata"]["webhook_runtime_status"] == "healthy"
        assert checks[account_key]["metadata"]["blocking_reasons"] == []
        assert checks[account_key]["metadata"]["webhook_verify_path"] == (
            "/webhooks/whatsapp/launch-webhook-health-account-1/wabas/waba-launch-health-1"
        )
        assert checks[account_key]["metadata"]["webhook_receive_path"] == (
            "/webhooks/whatsapp/launch-webhook-health-account-1/wabas/waba-launch-health-1"
        )
        assert checks[account_key]["metadata"]["webhook_root_receive_path"] == "/webhooks/whatsapp"
        assert checks[verification_key]["status"] == "pass"
        assert checks[verification_key]["metadata"]["webhook_verification_status"] == "verified"
        assert checks[runtime_key]["status"] == "pass"
        assert checks[runtime_key]["metadata"]["webhook_runtime_status"] == "healthy"
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_counts_management_webhook_as_routed_runtime_event(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "TEST_MODE": os.environ.get("TEST_MODE"),
        "AUTH_REQUIRED": os.environ.get("AUTH_REQUIRED"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["TEST_MODE"] = "false"
        os.environ["AUTH_REQUIRED"] = "false"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "launch-management-webhook-account-1",
                "display_name": "Launch Management Webhook Account",
                "meta_business_portfolio_id": "biz-launch-management-1",
                "waba_id": "waba-launch-management-1",
                "access_token": "token-launch-management-1",
                "verify_token": "verify-launch-management-1",
                "app_secret": "secret-launch-management-1",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-launch-management-1",
                        "display_phone_number": "+1 555 000 9301",
                        "verified_name": "Launch Management Number",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert create_response.status_code == 200

        subscribe_response = client.post(
            "/api/meta/accounts/launch-management-webhook-account-1/wabas/waba-launch-management-1/webhook-subscription",
            json={"callback_url": "https://example.com/launch-management/webhook"},
        )
        assert subscribe_response.status_code == 200

        verify_response = client.get(
            "/webhooks/whatsapp/launch-management-webhook-account-1/wabas/waba-launch-management-1",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-launch-management-1",
                "hub.challenge": "launch-management-challenge",
            },
        )
        assert verify_response.status_code == 200

        template_response = client.post(
            "/api/templates/drafts",
            json={
                "account_id": "launch-management-webhook-account-1",
                "waba_id": "waba-launch-management-1",
                "name": "launch_management_template",
                "language": "en",
                "category": "UTILITY",
                "body_text": "Launch management {{first_name}}.",
                "sample_variables": {"first_name": "Customer"},
            },
        )
        assert template_response.status_code == 200
        template_id = template_response.json()["template_id"]
        status_response = client.post(
            f"/api/templates/{template_id}/status",
            json={
                "status": "PENDING",
                "meta_template_id": "meta-template-launch-management",
            },
        )
        assert status_response.status_code == 200

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-launch-management-1",
                    "changes": [
                        {
                            "field": "message_template_status_update",
                            "value": {
                                "event": "APPROVED",
                                "message_template_id": "meta-template-launch-management",
                                "message_template_name": "launch_management_template",
                                "message_template_language": "en",
                            },
                        }
                    ],
                }
            ],
        }
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = WhatsAppProvider.build_signature("secret-launch-management-1", raw_body)
        webhook_response = client.post(
            "/webhooks/whatsapp/launch-management-webhook-account-1/wabas/waba-launch-management-1",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )
        assert webhook_response.status_code == 200
        assert webhook_response.json()["matched_template_updates"] == 1

        response = client.get("/api/runtime/launch-readiness")
        assert response.status_code == 200
        checks = {item["key"]: item for item in response.json()["checks"]}
        runtime_key = (
            "meta.account.launch-management-webhook-account-1."
            "waba-launch-management-1.webhook_runtime"
        )

        assert checks[runtime_key]["status"] == "pass"
        assert checks[runtime_key]["metadata"]["webhook_runtime_status"] == "healthy"
        assert checks[runtime_key]["metadata"]["webhook_last_message_received_at"] is None
        assert checks[runtime_key]["metadata"]["webhook_last_status_update_at"] is None
        assert checks[runtime_key]["metadata"]["webhook_last_management_event_at"] is not None
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_runtime_check_requires_routed_webhook_traffic(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "TEST_MODE": os.environ.get("TEST_MODE"),
        "AUTH_REQUIRED": os.environ.get("AUTH_REQUIRED"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["TEST_MODE"] = "false"
        os.environ["AUTH_REQUIRED"] = "false"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "launch-webhook-empty-account-1",
                "display_name": "Launch Webhook Empty Account",
                "meta_business_portfolio_id": "biz-launch-empty-1",
                "waba_id": "waba-launch-empty-1",
                "access_token": "token-launch-empty-1",
                "verify_token": "verify-launch-empty-1",
                "app_secret": "secret-launch-empty-1",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-launch-empty-1",
                        "display_phone_number": "+1 555 000 9201",
                        "verified_name": "Launch Empty Number",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert create_response.status_code == 200

        subscribe_response = client.post(
            "/api/meta/accounts/launch-webhook-empty-account-1/wabas/waba-launch-empty-1/webhook-subscription",
            json={"callback_url": "https://example.com/launch-empty/webhook"},
        )
        assert subscribe_response.status_code == 200

        verify_response = client.get(
            "/webhooks/whatsapp/launch-webhook-empty-account-1/wabas/waba-launch-empty-1",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-launch-empty-1",
                "hub.challenge": "launch-empty-challenge",
            },
        )
        assert verify_response.status_code == 200

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-launch-empty-1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 9201",
                                    "phone_number_id": "pn-launch-empty-1",
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
        signature = WhatsAppProvider.build_signature("secret-launch-empty-1", raw_body)

        webhook_response = client.post(
            "/webhooks/whatsapp/launch-webhook-empty-account-1/wabas/waba-launch-empty-1",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )
        assert webhook_response.status_code == 200

        response = client.get("/api/runtime/launch-readiness")
        assert response.status_code == 200
        payload = response.json()
        checks = {item["key"]: item for item in payload["checks"]}

        runtime_key = (
            "meta.account.launch-webhook-empty-account-1."
            "waba-launch-empty-1.webhook_runtime"
        )

        assert checks[runtime_key]["status"] == "blocker"
        assert "no in-scope message, status, or management update was accepted" in checks[runtime_key]["message"]
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_runtime_check_reports_missing_app_secret_blocker(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "TEST_MODE": os.environ.get("TEST_MODE"),
        "AUTH_REQUIRED": os.environ.get("AUTH_REQUIRED"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["TEST_MODE"] = "false"
        os.environ["AUTH_REQUIRED"] = "false"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "launch-webhook-missing-secret-account-1",
                "display_name": "Launch Webhook Missing Secret Account",
                "meta_business_portfolio_id": "biz-launch-missing-secret-1",
                "waba_id": "waba-launch-missing-secret-1",
                "access_token": "token-launch-missing-secret-1",
                "verify_token": "verify-launch-missing-secret-1",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-launch-missing-secret-1",
                        "display_phone_number": "+1 555 000 9301",
                        "verified_name": "Launch Missing Secret Number",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert create_response.status_code == 200

        subscribe_response = client.post(
            "/api/meta/accounts/launch-webhook-missing-secret-account-1/"
            "wabas/waba-launch-missing-secret-1/webhook-subscription",
            json={"callback_url": "https://example.com/launch-missing-secret/webhook"},
        )
        assert subscribe_response.status_code == 200

        verify_response = client.get(
            "/webhooks/whatsapp/launch-webhook-missing-secret-account-1/"
            "wabas/waba-launch-missing-secret-1",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-launch-missing-secret-1",
                "hub.challenge": "launch-missing-secret-challenge",
            },
        )
        assert verify_response.status_code == 200

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-launch-missing-secret-1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 9301",
                                    "phone_number_id": "pn-launch-missing-secret-1",
                                },
                                "messages": [
                                    {
                                        "from": "14150009301",
                                        "id": "wamid.launch.missing.secret.1",
                                        "timestamp": "1712345803",
                                        "type": "text",
                                        "text": {"body": "launch runtime missing secret"},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }

        webhook_response = client.post(
            "/webhooks/whatsapp/launch-webhook-missing-secret-account-1/"
            "wabas/waba-launch-missing-secret-1",
            content=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert webhook_response.status_code == 503
        assert webhook_response.json()["detail"] == "Webhook app secret is not configured for this WABA."

        response = client.get("/api/runtime/launch-readiness")
        assert response.status_code == 200
        checks = {item["key"]: item for item in response.json()["checks"]}
        account_key = (
            "meta.account.launch-webhook-missing-secret-account-1."
            "waba-launch-missing-secret-1"
        )
        runtime_key = (
            "meta.account.launch-webhook-missing-secret-account-1."
            "waba-launch-missing-secret-1.webhook_runtime"
        )

        assert checks[account_key]["status"] == "warning"
        assert checks[account_key]["metadata"]["ready_for_webhook_delivery"] is False
        assert checks[account_key]["metadata"]["webhook_verification_status"] == "verified"
        assert checks[account_key]["metadata"]["webhook_runtime_status"] == "signature_unavailable"
        assert checks[account_key]["metadata"]["blocking_reasons"] == [
            "missing_app_secret",
            "webhook_not_ready",
        ]
        assert checks[runtime_key]["status"] == "blocker"
        assert checks[runtime_key]["metadata"]["webhook_runtime_status"] == "signature_unavailable"
        assert checks[runtime_key]["metadata"]["webhook_runtime_error"] == "missing_app_secret"
        assert checks[runtime_key]["metadata"]["webhook_signature_failure_count"] == 0
        assert checks[runtime_key]["metadata"]["webhook_last_event_received_at"] is not None
        assert (
            checks[runtime_key]["message"]
            == "Webhook delivery is still blocked because the app secret is missing."
        )
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_runtime_check_reports_signature_failure_blocker(
    client: TestClient,
    override_meta_management_provider,
) -> None:
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "TEST_MODE": os.environ.get("TEST_MODE"),
        "AUTH_REQUIRED": os.environ.get("AUTH_REQUIRED"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["TEST_MODE"] = "false"
        os.environ["AUTH_REQUIRED"] = "false"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        get_settings.cache_clear()
        override_meta_management_provider(client, StubMetaManagementProvider())

        create_response = client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "launch-webhook-invalid-signature-account-1",
                "display_name": "Launch Webhook Invalid Signature Account",
                "meta_business_portfolio_id": "biz-launch-invalid-signature-1",
                "waba_id": "waba-launch-invalid-signature-1",
                "access_token": "token-launch-invalid-signature-1",
                "verify_token": "verify-launch-invalid-signature-1",
                "app_secret": "secret-launch-invalid-signature-1",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-launch-invalid-signature-1",
                        "display_phone_number": "+1 555 000 9302",
                        "verified_name": "Launch Invalid Signature Number",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
        )
        assert create_response.status_code == 200

        subscribe_response = client.post(
            "/api/meta/accounts/launch-webhook-invalid-signature-account-1/"
            "wabas/waba-launch-invalid-signature-1/webhook-subscription",
            json={"callback_url": "https://example.com/launch-invalid-signature/webhook"},
        )
        assert subscribe_response.status_code == 200

        verify_response = client.get(
            "/webhooks/whatsapp/launch-webhook-invalid-signature-account-1/"
            "wabas/waba-launch-invalid-signature-1",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-launch-invalid-signature-1",
                "hub.challenge": "launch-invalid-signature-challenge",
            },
        )
        assert verify_response.status_code == 200

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-launch-invalid-signature-1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 9302",
                                    "phone_number_id": "pn-launch-invalid-signature-1",
                                },
                                "messages": [
                                    {
                                        "from": "14150009302",
                                        "id": "wamid.launch.invalid.signature.1",
                                        "timestamp": "1712345804",
                                        "type": "text",
                                        "text": {"body": "launch runtime invalid signature"},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }

        webhook_response = client.post(
            "/webhooks/whatsapp/launch-webhook-invalid-signature-account-1/"
            "wabas/waba-launch-invalid-signature-1",
            content=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalid",
            },
        )
        assert webhook_response.status_code == 403
        assert webhook_response.json()["detail"] == "Invalid WhatsApp webhook signature."

        response = client.get("/api/runtime/launch-readiness")
        assert response.status_code == 200
        checks = {item["key"]: item for item in response.json()["checks"]}
        runtime_key = (
            "meta.account.launch-webhook-invalid-signature-account-1."
            "waba-launch-invalid-signature-1.webhook_runtime"
        )

        assert checks[runtime_key]["status"] == "blocker"
        assert checks[runtime_key]["metadata"]["webhook_runtime_status"] == "signature_failed"
        assert checks[runtime_key]["metadata"]["webhook_runtime_error"] == "invalid_signature"
        assert checks[runtime_key]["metadata"]["webhook_signature_failure_count"] == 1
        assert checks[runtime_key]["metadata"]["webhook_last_signature_failed_at"] is not None
        assert (
            checks[runtime_key]["message"]
            == "Webhook signature validation failed: invalid_signature."
        )
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_multi_account_ai_status_is_isolated(client: TestClient) -> None:
    """BE2-008: Two accounts have independent AI status."""
    import os
    from app.core.settings import get_settings

    os.environ["WEBHOOK_SIGNATURE_ENABLED"] = "false"
    get_settings.cache_clear()

    account_a_id = "multi-account-a"
    account_b_id = "multi-account-b"

    register_response_a = client.post(
        "/api/runtime/accounts",
        json={
            "account_id": account_a_id,
            "display_name": "Multi Account A",
            "provider_type": "mock",
        },
    )
    assert register_response_a.status_code == 200

    register_response_b = client.post(
        "/api/runtime/accounts",
        json={
            "account_id": account_b_id,
            "display_name": "Multi Account B",
            "provider_type": "mock",
        },
    )
    assert register_response_b.status_code == 200

    state_response = client.get("/api/runtime/state")
    assert state_response.status_code == 200
    state = state_response.json()
    account_ids = [a["account_id"] for a in state["accounts"]]
    assert account_a_id in account_ids
    assert account_b_id in account_ids

    ai_a_response = client.get(
        f"/api/runtime/accounts/{account_a_id}/ai-status",
    )
    assert ai_a_response.status_code == 404

    # Get account AI status from the state list
    state_after = client.get("/api/runtime/state").json()
    account_a_state = next(a for a in state_after["accounts"] if a["account_id"] == account_a_id)
    assert account_a_state["ai_enabled"] is True

    account_b_state = next(a for a in state_after["accounts"] if a["account_id"] == account_b_id)
    assert account_b_state["ai_enabled"] is True

    # Disable AI for account A only
    set_a_response = client.post(
        f"/api/runtime/accounts/{account_a_id}/ai",
        json={"enabled": False},
    )
    assert set_a_response.status_code == 200

    # Verify account A's AI is disabled
    state_after_toggle = client.get("/api/runtime/state").json()
    account_a_after = next(
        a for a in state_after_toggle["accounts"] if a["account_id"] == account_a_id
    )
    assert account_a_after["ai_enabled"] is False

    # Verify account B's AI is unchanged
    account_b_after = next(
        a for a in state_after_toggle["accounts"] if a["account_id"] == account_b_id
    )
    assert account_b_after["ai_enabled"] is True, "Account B should be unaffected by Account A's change"
