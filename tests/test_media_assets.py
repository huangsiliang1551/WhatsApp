import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_messaging_service
from app.core.settings import get_settings
from app.db.models import (
    Account,
    Conversation,
    MediaAsset,
    MediaAssetEvent,
    Message,
    TemplateSendLog,
    WhatsAppBusinessAccount,
    WhatsAppPhoneNumber,
)
from app.providers.messaging.mock_provider import MockMessagingProvider
from app.providers.messaging.whatsapp_provider import WhatsAppProvider
from app.schemas.messaging import (
    MediaAssetSyncRequest,
    MediaAssetSyncResult,
    OutboundDispatchRequest,
    OutboundDispatchResult,
    ProviderStatusUpdate,
)
from app.services.media_asset_telemetry import MediaAssetTelemetryRecorder


class CountingMediaSyncProvider(MockMessagingProvider):
    def __init__(self) -> None:
        self.sync_calls = 0

    async def sync_media_asset(self, payload: MediaAssetSyncRequest) -> MediaAssetSyncResult:
        self.sync_calls += 1
        return MediaAssetSyncResult(
            provider_name=self.provider_name,
            phone_number_id=payload.phone_number_id,
            waba_id=payload.waba_id,
            meta_media_id=f"mock-media-resync-{self.sync_calls}",
            sync_status="synced",
            raw_response={"asset_id": payload.asset_id, "sync_calls": self.sync_calls},
        )


class FailingMediaSyncProvider(MockMessagingProvider):
    async def sync_media_asset(self, payload: MediaAssetSyncRequest) -> MediaAssetSyncResult:
        return MediaAssetSyncResult(
            provider_name=self.provider_name,
            phone_number_id=payload.phone_number_id,
            waba_id=payload.waba_id,
            meta_media_id=None,
            sync_status="failed",
            error_code="provider_upload_failed",
            error_message="provider upload failed",
            raw_response={"asset_id": payload.asset_id, "reason": "provider_upload_failed"},
        )


class FailingSecondMediaSyncProvider(MockMessagingProvider):
    def __init__(self) -> None:
        self.sync_calls = 0

    async def sync_media_asset(self, payload: MediaAssetSyncRequest) -> MediaAssetSyncResult:
        self.sync_calls += 1
        if self.sync_calls == 1:
            return MediaAssetSyncResult(
                provider_name=self.provider_name,
                phone_number_id=payload.phone_number_id,
                waba_id=payload.waba_id,
                meta_media_id="mock-media-first-sync",
                sync_status="synced",
                raw_response={"asset_id": payload.asset_id, "sync_calls": self.sync_calls},
            )
        return MediaAssetSyncResult(
            provider_name=self.provider_name,
            phone_number_id=payload.phone_number_id,
            waba_id=payload.waba_id,
            meta_media_id=None,
            sync_status="failed",
            error_code="provider_upload_failed",
            error_message="provider upload failed",
            raw_response={"asset_id": payload.asset_id, "sync_calls": self.sync_calls},
        )


class RuntimeErrorMediaSyncProvider(MockMessagingProvider):
    async def sync_media_asset(self, payload: MediaAssetSyncRequest) -> MediaAssetSyncResult:
        del payload
        raise RuntimeError("provider_sync_unavailable")


class RuntimeErrorMediaSendProvider(MockMessagingProvider):
    async def sync_media_asset(self, payload: MediaAssetSyncRequest) -> MediaAssetSyncResult:
        return MediaAssetSyncResult(
            provider_name=self.provider_name,
            phone_number_id=payload.phone_number_id,
            waba_id=payload.waba_id,
            meta_media_id="mock-media-send-ready",
            sync_status="synced",
            raw_response={"asset_id": payload.asset_id},
        )

    async def send_outbound(self, payload: OutboundDispatchRequest) -> OutboundDispatchResult:
        del payload
        raise RuntimeError("provider_send_unavailable")


def register_media_account(
    client: TestClient,
    *,
    account_id: str = "media-account-1",
    display_name: str = "Media Account 1",
    portfolio_id: str = "portfolio-media-1",
    waba_id: str = "waba-media-1",
    access_token: str = "token-media-1",
    verify_token: str = "verify-media-1",
    app_secret: str = "secret-media-1",
    phone_numbers: list[dict[str, object]] | None = None,
) -> None:
    response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": account_id,
            "display_name": display_name,
            "meta_business_portfolio_id": portfolio_id,
            "waba_id": waba_id,
            "access_token": access_token,
            "verify_token": verify_token,
            "app_secret": app_secret,
            "token_source": "system_user",
            "phone_numbers": phone_numbers
            or [
                {
                    "phone_number_id": "pn-media-1",
                    "display_phone_number": "+1 555 100 0001",
                    "verified_name": "Media Number",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert response.status_code == 200


def load_media_asset_events(
    db_session_factory: sessionmaker[Session],
    *,
    asset_id: str,
) -> list[MediaAssetEvent]:
    with db_session_factory() as session:
        return list(
            session.scalars(
                select(MediaAssetEvent)
                .where(MediaAssetEvent.asset_id == asset_id)
                .order_by(MediaAssetEvent.created_at.asc(), MediaAssetEvent.id.asc())
            )
        )


def recreate_media_waba_row(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    official_waba_id: str,
    phone_number_id: str,
    legacy_waba_id: str,
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


def assert_media_asset_events_have_waba_scope(
    *,
    events: list[dict[str, object]],
    expected_waba_id: str,
    expected_phone_number_id: str,
    expected_event_types: set[str],
) -> None:
    event_by_type = {str(item["event_type"]): item for item in events}
    assert expected_event_types.issubset(event_by_type.keys())
    for event_type in expected_event_types:
        event = event_by_type[event_type]
        assert event["waba_id"] == expected_waba_id, event_type
        assert event["phone_number_id"] == expected_phone_number_id, event_type


def test_media_asset_list_and_detail_do_not_cross_operator_account_scope(
    client: TestClient,
) -> None:
    register_media_account(
        client,
        account_id="media-scope-account-a",
        display_name="Media Scope Account A",
        portfolio_id="portfolio-media-scope-a",
        waba_id="waba-media-scope-a",
        access_token="token-media-scope-a",
        verify_token="verify-media-scope-a",
        app_secret="secret-media-scope-a",
        phone_numbers=[
            {
                "phone_number_id": "pn-media-scope-a",
                "display_phone_number": "+1 555 100 0101",
                "verified_name": "Media Scope A",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    register_media_account(
        client,
        account_id="media-scope-account-b",
        display_name="Media Scope Account B",
        portfolio_id="portfolio-media-scope-b",
        waba_id="waba-media-scope-b",
        access_token="token-media-scope-b",
        verify_token="verify-media-scope-b",
        app_secret="secret-media-scope-b",
        phone_numbers=[
            {
                "phone_number_id": "pn-media-scope-b",
                "display_phone_number": "+1 555 100 0102",
                "verified_name": "Media Scope B",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )

    for account_id, waba_id, phone_number_id, name in (
        ("media-scope-account-a", "waba-media-scope-a", "pn-media-scope-a", "scope-a-image"),
        ("media-scope-account-b", "waba-media-scope-b", "pn-media-scope-b", "scope-b-image"),
    ):
        create_response = client.post(
            "/api/media/assets",
            json={
                "account_id": account_id,
                "waba_id": waba_id,
                "phone_number_id": phone_number_id,
                "name": name,
                "asset_type": "image",
                "mime_type": "image/jpeg",
                "storage_url": f"https://cdn.example.com/{name}.jpg",
                "tags": ["scope"],
            },
        )
        assert create_response.status_code == 200
        if account_id == "media-scope-account-b":
            cross_asset_id = create_response.json()["asset_id"]

    scoped_headers = {
        "X-Actor-Id": "operator-media-scope-a",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "media-scope-account-a",
    }

    own_list_response = client.get(
        "/api/media/assets",
        params={"waba_id": "waba-media-scope-a"},
        headers=scoped_headers,
    )
    assert own_list_response.status_code == 200
    assert [item["name"] for item in own_list_response.json()] == ["scope-a-image"]

    cross_waba_list_response = client.get(
        "/api/media/assets",
        params={"waba_id": "waba-media-scope-b"},
        headers=scoped_headers,
    )
    assert cross_waba_list_response.status_code == 200
    assert cross_waba_list_response.json() == []

    cross_phone_list_response = client.get(
        "/api/media/assets",
        params={"phone_number_id": "pn-media-scope-b"},
        headers=scoped_headers,
    )
    assert cross_phone_list_response.status_code == 200
    assert cross_phone_list_response.json() == []

    cross_detail_response = client.get(
        f"/api/media/assets/{cross_asset_id}",
        headers=scoped_headers,
    )
    assert cross_detail_response.status_code == 403
    assert "accessible account scope" in cross_detail_response.json()["detail"]

    cross_update_response = client.patch(
        f"/api/media/assets/{cross_asset_id}",
        json={"name": "blocked-cross-scope-update"},
        headers=scoped_headers,
    )
    assert cross_update_response.status_code == 403
    assert "accessible account scope" in cross_update_response.json()["detail"]

    cross_sync_response = client.post(
        f"/api/media/assets/{cross_asset_id}/sync",
        json={"phone_number_id": "pn-media-scope-b", "force_resync": False},
        headers=scoped_headers,
    )
    assert cross_sync_response.status_code == 403
    assert "accessible account scope" in cross_sync_response.json()["detail"]


def test_media_asset_list_route_returns_404_for_missing_account_scope(
    client: TestClient,
) -> None:
    missing_account_id = "media-missing-account"
    response = client.get(
        "/api/media/assets",
        params={"account_id": missing_account_id},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == f"Account '{missing_account_id}' was not found."


def test_media_asset_create_and_upload_routes_return_404_without_creating_missing_account(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    missing_account_id = "media-missing-account-write"
    expected_detail = f"Account '{missing_account_id}' was not found."

    create_response = client.post(
        "/api/media/assets",
        json={
            "account_id": missing_account_id,
            "waba_id": "waba-media-missing-write",
            "phone_number_id": "pn-media-missing-write",
            "name": "missing-write-asset",
            "asset_type": "image",
            "mime_type": "image/png",
            "storage_url": "https://cdn.example.com/missing-write.png",
            "source": "manual",
            "tags": ["missing"],
        },
    )
    assert create_response.status_code == 404
    assert create_response.json()["detail"] == expected_detail

    upload_response = client.post(
        "/api/media/assets/upload",
        data={"account_id": missing_account_id},
        files={"file": ("missing-write.png", b"fake-png-bytes", "image/png")},
    )
    assert upload_response.status_code == 404
    assert upload_response.json()["detail"] == expected_detail

    with db_session_factory() as session:
        assert session.get(Account, missing_account_id) is None


def test_media_asset_detail_update_and_sync_return_404_for_missing_asset_id(
    client: TestClient,
) -> None:
    missing_asset_id = "media-missing-asset-id"

    detail_response = client.get(f"/api/media/assets/{missing_asset_id}")
    assert detail_response.status_code == 404
    assert missing_asset_id in detail_response.json()["detail"]

    update_response = client.patch(
        f"/api/media/assets/{missing_asset_id}",
        json={"name": "should-not-exist"},
    )
    assert update_response.status_code == 404
    assert missing_asset_id in update_response.json()["detail"]

    sync_response = client.post(
        f"/api/media/assets/{missing_asset_id}/sync",
        json={"phone_number_id": "pn-media-missing"},
    )
    assert sync_response.status_code == 404
    assert missing_asset_id in sync_response.json()["detail"]


def test_media_asset_list_route_filters_by_waba_and_phone_number_within_account(
    client: TestClient,
) -> None:
    register_media_account(
        client,
        account_id="media-filter-account-1",
        display_name="Media Filter Account",
        portfolio_id="portfolio-media-filter-1",
        waba_id="waba-media-filter-1",
        access_token="token-media-filter-1",
        verify_token="verify-media-filter-1",
        app_secret="secret-media-filter-1",
        phone_numbers=[
            {
                "phone_number_id": "pn-media-filter-1",
                "display_phone_number": "+1 555 100 0401",
                "verified_name": "Media Filter 1",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
            {
                "phone_number_id": "pn-media-filter-2",
                "display_phone_number": "+1 555 100 0402",
                "verified_name": "Media Filter 2",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
        ],
    )

    for phone_number_id, name in (
        ("pn-media-filter-1", "filter-image-1"),
        ("pn-media-filter-2", "filter-image-2"),
    ):
        create_response = client.post(
            "/api/media/assets",
            json={
                "account_id": "media-filter-account-1",
                "waba_id": "waba-media-filter-1",
                "phone_number_id": phone_number_id,
                "name": name,
                "asset_type": "image",
                "mime_type": "image/jpeg",
                "storage_url": f"https://cdn.example.com/{name}.jpg",
                "tags": ["filter"],
            },
        )
        assert create_response.status_code == 200

    filtered_list_response = client.get(
        "/api/media/assets",
        params={
            "account_id": "media-filter-account-1",
            "waba_id": "waba-media-filter-1",
            "phone_number_id": "pn-media-filter-1",
        },
    )
    assert filtered_list_response.status_code == 200
    filtered_assets = filtered_list_response.json()
    assert len(filtered_assets) == 1
    assert filtered_assets[0]["waba_id"] == "waba-media-filter-1"
    assert filtered_assets[0]["phone_number_id"] == "pn-media-filter-1"
    assert filtered_assets[0]["name"] == "filter-image-1"


def test_media_asset_library_and_manual_send_flow(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_media_account(client)

    agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-media-1",
            "display_name": "Media Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert agent_response.status_code == 200

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "shipping-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/shipping-banner.jpg",
            "tags": ["shipping", "banner"],
        },
    )
    assert create_asset_response.status_code == 200
    asset = create_asset_response.json()
    assert asset["account_id"] == "media-account-1"
    assert asset["waba_id"] == "waba-media-1"
    assert asset["phone_number_id"] == "pn-media-1"
    assert asset["asset_type"] == "image"
    assert asset["storage_url"] == "https://cdn.example.com/shipping-banner.jpg"

    list_assets_response = client.get(
        "/api/media/assets",
        params={"account_id": "media-account-1"},
    )
    assert list_assets_response.status_code == 200
    assets = list_assets_response.json()
    assert len(assets) == 1
    assert assets[0]["asset_id"] == asset["asset_id"]

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "media-account-1",
            "conversation_id": "conv-media-1",
            "user_id": "user-media-1",
            "text": "hola",
            "mode": "echo",
            "language_hint": "es",
            "phone_number_id": "pn-media-1",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/media-account-1/conv-media-1/assignment",
        json={
            "agent_id": "agent-media-1",
            "assigned_by_agent_id": "agent-media-1",
            "reason": "manual_media_reply",
        },
    )
    assert assignment_response.status_code == 200

    send_response = client.post(
        "/api/conversations/media-account-1/conv-media-1/messages/media",
        json={
            "asset_id": asset["asset_id"],
            "caption": "您好，这是您的物流图片。",
            "agent_id": "agent-media-1",
        },
    )
    assert send_response.status_code == 200
    send_payload = send_response.json()
    assert send_payload["asset_id"] == asset["asset_id"]
    assert send_payload["conversation_id"] == "conv-media-1"
    assert send_payload["conversation_id"] == send_payload["external_conversation_id"]
    assert send_payload["external_conversation_id"] == "conv-media-1"
    assert send_payload["internal_conversation_id"] != "conv-media-1"
    assert send_payload["waba_id"] == "waba-media-1"
    assert send_payload["phone_number_id"] == "pn-media-1"
    assert send_payload["provider_media_id"].startswith("mock-media-")
    assert send_payload["message_type"] == "image"
    assert send_payload["translated"] is True
    assert "auto-translated zh-CN->es" in send_payload["delivered_caption"]

    status_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-media-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 100 0001",
                                "phone_number_id": "pn-media-1",
                            },
                            "statuses": [
                                {
                                    "id": send_payload["provider_message_id"],
                                    "status": "delivered",
                                    "timestamp": "1712345699",
                                    "recipient_id": "user-media-1",
                                    "conversation": {
                                        "id": "meta-media-conversation-1",
                                        "expiration_timestamp": "1712350000",
                                        "origin": {"type": "business_initiated"},
                                    },
                                    "pricing": {
                                        "billable": True,
                                        "category": "utility",
                                        "pricing_model": "CBP",
                                    },
                                },
                                {
                                    "id": send_payload["provider_message_id"],
                                    "status": "read",
                                    "timestamp": "1712345799",
                                    "recipient_id": "user-media-1",
                                    "conversation": {
                                        "id": "meta-media-conversation-1",
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
    signature = WhatsAppProvider.build_signature("secret-media-1", status_body)
    status_response = client.post(
        "/webhooks/whatsapp/media-account-1/wabas/waba-media-1",
        content=status_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert status_response.status_code == 200

    messages_response = client.get("/api/conversations/media-account-1/conv-media-1/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()
    outbound_message = messages[-1]
    assert outbound_message["message_type"] == "image"
    assert outbound_message["original_text"] == "您好，这是您的物流图片。"
    assert "auto-translated zh-CN->es" in outbound_message["translated_text"]
    assert "auto-translated zh-CN->es" in outbound_message["delivered_text"]
    assert outbound_message["payload"]["asset_id"] == asset["asset_id"]
    assert outbound_message["payload"]["asset_type"] == "image"
    assert outbound_message["payload"]["storage_url"] == "https://cdn.example.com/shipping-banner.jpg"

    detail_response = client.get(f"/api/media/assets/{asset['asset_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["usage"]["total_events"] == 5
    assert detail["usage"]["sync_count"] == 1
    assert detail["usage"]["sync_failed_count"] == 0
    assert detail["usage"]["send_count"] == 1
    assert detail["usage"]["send_failed_count"] == 0
    assert detail["usage"]["delivered_status_count"] == 1
    assert detail["usage"]["read_status_count"] == 1
    assert detail["usage"]["provider_failed_status_count"] == 0
    assert detail["usage"]["last_synced_at"] is not None
    assert detail["usage"]["last_sent_at"] is not None
    assert detail["usage"]["last_delivered_at"] is not None
    assert detail["usage"]["last_read_at"] is not None
    assert len(detail["provider_syncs"]) == 1
    assert detail["provider_syncs"][0]["provider_name"] == "mock"
    assert detail["provider_syncs"][0]["waba_id"] == "waba-media-1"
    assert detail["provider_syncs"][0]["phone_number_id"] == "pn-media-1"
    assert detail["provider_syncs"][0]["sync_status"] == "synced"
    assert detail["provider_syncs"][0]["meta_media_id"].startswith("mock-media-")
    detail_event_by_type = {item["event_type"]: item for item in detail["events"]}
    event_types = [item["event_type"] for item in detail["events"]]
    assert "media_asset_created" in event_types
    assert "media_asset_sync_succeeded" in event_types
    assert "media_asset_sent" in event_types
    assert "media_asset_status_delivered" in event_types
    assert "media_asset_status_read" in event_types
    expected_scoped_event_types = {
        "media_asset_created",
        "media_asset_sync_succeeded",
        "media_asset_sent",
        "media_asset_status_delivered",
        "media_asset_status_read",
    }
    assert_media_asset_events_have_waba_scope(
        events=detail["events"],
        expected_waba_id="waba-media-1",
        expected_phone_number_id="pn-media-1",
        expected_event_types=expected_scoped_event_types,
    )
    assert detail_event_by_type["media_asset_sync_succeeded"]["payload"]["external_conversation_id"] == "conv-media-1"
    assert detail_event_by_type["media_asset_sync_succeeded"]["payload"]["internal_conversation_id"] != "conv-media-1"
    assert detail_event_by_type["media_asset_sent"]["payload"]["external_conversation_id"] == "conv-media-1"
    assert detail_event_by_type["media_asset_sent"]["payload"]["internal_conversation_id"] != "conv-media-1"
    persisted_events = load_media_asset_events(db_session_factory, asset_id=asset["asset_id"])
    persisted_event_by_type = {event.event_type: event for event in persisted_events}
    assert expected_scoped_event_types.issubset(persisted_event_by_type.keys())
    for event_type in expected_scoped_event_types:
        event = persisted_event_by_type[event_type]
        assert event.waba_id == "waba-media-1"
        assert event.phone_number_id == "pn-media-1"


def test_media_asset_send_rejects_non_assigned_agent(client: TestClient) -> None:
    register_media_account(
        client,
        account_id="media-assigned-scope-account-1",
        display_name="Media Assigned Scope Account",
        portfolio_id="portfolio-media-assigned-scope-1",
        waba_id="waba-media-assigned-scope-1",
        access_token="token-media-assigned-scope-1",
        verify_token="verify-media-assigned-scope-1",
        app_secret="secret-media-assigned-scope-1",
        phone_numbers=[
            {
                "phone_number_id": "pn-media-assigned-scope-1",
                "display_phone_number": "+1 555 100 0301",
                "verified_name": "Media Assigned Scope",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )

    for agent_id in ("agent-media-owner-1", "agent-media-other-1"):
        agent_response = client.post(
            "/api/runtime/agents",
            json={
                "account_id": "media-assigned-scope-account-1",
                "agent_id": agent_id,
                "display_name": agent_id,
                "status": "online",
                "is_active": True,
            },
        )
        assert agent_response.status_code == 200

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-assigned-scope-account-1",
            "waba_id": "waba-media-assigned-scope-1",
            "phone_number_id": "pn-media-assigned-scope-1",
            "name": "manual-reply-image",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/manual-reply-image.jpg",
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "media-assigned-scope-account-1",
            "conversation_id": "conv-media-assigned-scope-1",
            "user_id": "user-media-assigned-scope-1",
            "text": "send an image",
            "mode": "echo",
            "phone_number_id": "pn-media-assigned-scope-1",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/media-assigned-scope-account-1/conv-media-assigned-scope-1/assignment",
        json={
            "agent_id": "agent-media-owner-1",
            "assigned_by_agent_id": "agent-media-owner-1",
            "reason": "manual_media_reply",
        },
    )
    assert assignment_response.status_code == 200

    send_response = client.post(
        "/api/conversations/media-assigned-scope-account-1/conv-media-assigned-scope-1/messages/media",
        headers={
            "X-Actor-Id": "agent-media-other-1",
            "X-Actor-Role": "support_agent",
            "X-Actor-Account-Ids": "media-assigned-scope-account-1",
        },
        json={
            "asset_id": asset_id,
            "caption": "Manual image",
            "agent_id": "agent-media-other-1",
        },
    )
    assert send_response.status_code == 403
    assert "assigned to 'agent-media-owner-1'" in send_response.json()["detail"]


def test_media_send_uses_support_actor_identity_when_agent_id_is_omitted(client: TestClient) -> None:
    register_media_account(
        client,
        account_id="media-implicit-actor-account-1",
        display_name="Media Implicit Actor Account",
        portfolio_id="portfolio-media-implicit-actor-1",
        waba_id="waba-media-implicit-actor-1",
        access_token="token-media-implicit-actor-1",
        verify_token="verify-media-implicit-actor-1",
        app_secret="secret-media-implicit-actor-1",
        phone_numbers=[
            {
                "phone_number_id": "pn-media-implicit-actor-1",
                "display_phone_number": "+1 555 100 0301",
                "verified_name": "Media Implicit Actor",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )

    for agent_id in ("agent-media-implicit-owner-1", "agent-media-implicit-other-1"):
        agent_response = client.post(
            "/api/runtime/agents",
            json={
                "account_id": "media-implicit-actor-account-1",
                "agent_id": agent_id,
                "display_name": agent_id,
                "status": "online",
                "is_active": True,
            },
        )
        assert agent_response.status_code == 200

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-implicit-actor-account-1",
            "waba_id": "waba-media-implicit-actor-1",
            "phone_number_id": "pn-media-implicit-actor-1",
            "name": "implicit-actor-image",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/implicit-actor-image.jpg",
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "media-implicit-actor-account-1",
            "conversation_id": "conv-media-implicit-actor-1",
            "user_id": "user-media-implicit-actor-1",
            "text": "send actor-scoped image",
            "mode": "echo",
            "phone_number_id": "pn-media-implicit-actor-1",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/media-implicit-actor-account-1/conv-media-implicit-actor-1/assignment",
        json={
            "agent_id": "agent-media-implicit-owner-1",
            "assigned_by_agent_id": "agent-media-implicit-owner-1",
            "reason": "manual_media_reply",
        },
    )
    assert assignment_response.status_code == 200

    blocked_response = client.post(
        "/api/conversations/media-implicit-actor-account-1/conv-media-implicit-actor-1/messages/media",
        headers={
            "X-Actor-Id": "agent-media-implicit-other-1",
            "X-Actor-Role": "support_agent",
            "X-Actor-Account-Ids": "media-implicit-actor-account-1",
        },
        json={
            "asset_id": asset_id,
            "caption": "Implicit actor media",
        },
    )
    assert blocked_response.status_code == 403
    assert "assigned to 'agent-media-implicit-owner-1'" in blocked_response.json()["detail"]

    owner_response = client.post(
        "/api/conversations/media-implicit-actor-account-1/conv-media-implicit-actor-1/messages/media",
        headers={
            "X-Actor-Id": "agent-media-implicit-owner-1",
            "X-Actor-Role": "support_agent",
            "X-Actor-Account-Ids": "media-implicit-actor-account-1",
        },
        json={
            "asset_id": asset_id,
            "caption": "Implicit actor owner media",
        },
    )
    assert owner_response.status_code == 200
    assert owner_response.json()["account_id"] == "media-implicit-actor-account-1"


def test_media_asset_list_supports_scope_and_search_filters(client: TestClient) -> None:
    register_media_account(client)

    first_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "shipping-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/shipping-banner.jpg",
            "tags": ["shipping", "banner"],
        },
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "invoice-pdf",
            "asset_type": "document",
            "mime_type": "application/pdf",
            "storage_url": "https://cdn.example.com/invoice.pdf",
            "tags": ["invoice", "billing"],
        },
    )
    assert second_response.status_code == 200

    all_assets_response = client.get(
        "/api/media/assets",
        params={"account_id": "media-account-1", "is_active": True},
    )
    assert all_assets_response.status_code == 200
    assert len(all_assets_response.json()) == 2

    tag_filtered_response = client.get(
        "/api/media/assets",
        params={
            "account_id": "media-account-1",
            "tag": "invoice",
        },
    )
    assert tag_filtered_response.status_code == 200
    tag_filtered_assets = tag_filtered_response.json()
    assert len(tag_filtered_assets) == 1
    assert tag_filtered_assets[0]["name"] == "invoice-pdf"

    search_filtered_response = client.get(
        "/api/media/assets",
        params={
            "account_id": "media-account-1",
            "query": "banner",
        },
    )
    assert search_filtered_response.status_code == 200
    search_filtered_assets = search_filtered_response.json()
    assert len(search_filtered_assets) == 1
    assert search_filtered_assets[0]["name"] == "shipping-banner"

    scope_filtered_response = client.get(
        "/api/media/assets",
        params={
            "account_id": "media-account-1",
            "phone_number_id": "pn-media-1",
            "asset_type": "document",
            "waba_id": "waba-media-1",
        },
    )
    assert scope_filtered_response.status_code == 200
    scope_filtered_assets = scope_filtered_response.json()
    assert len(scope_filtered_assets) == 1
    assert scope_filtered_assets[0]["name"] == "invoice-pdf"


def test_media_asset_create_rejects_mismatched_waba_and_phone_scope(client: TestClient) -> None:
    register_media_account(client)

    mismatch_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-other",
            "phone_number_id": "pn-media-1",
            "name": "scope-mismatch",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/scope-mismatch.jpg",
            "tags": ["scope"],
        },
    )

    assert mismatch_response.status_code == 409
    assert "does not match phone number" in mismatch_response.json()["detail"]


def test_media_asset_create_normalizes_phone_scoped_meta_media_id_into_provider_sync(
    client: TestClient,
) -> None:
    register_media_account(client)

    create_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "imported-meta-image",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "meta_media_id": "meta-imported-media-1",
            "meta_media_status": "linked",
            "source": "manual_import",
            "tags": ["imported"],
        },
    )
    assert create_response.status_code == 200
    asset = create_response.json()
    assert asset["phone_number_id"] == "pn-media-1"
    assert asset["meta_media_id"] is None
    assert asset["meta_media_status"] is None

    detail_response = client.get(f"/api/media/assets/{asset['asset_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["asset"]["meta_media_id"] is None
    assert detail["asset"]["meta_media_status"] is None
    assert len(detail["provider_syncs"]) == 1
    assert detail["provider_syncs"][0]["provider_name"] == "mock"
    assert detail["provider_syncs"][0]["phone_number_id"] == "pn-media-1"
    assert detail["provider_syncs"][0]["meta_media_id"] == "meta-imported-media-1"
    assert detail["provider_syncs"][0]["sync_status"] == "linked"

    search_response = client.get(
        "/api/media/assets",
        params={"account_id": "media-account-1", "query": "meta-imported-media-1"},
    )
    assert search_response.status_code == 200
    assert [item["asset_id"] for item in search_response.json()] == [asset["asset_id"]]


def test_media_asset_create_accepts_provider_media_id_as_primary_reference(
    client: TestClient,
) -> None:
    register_media_account(client)

    create_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "imported-provider-image",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "provider_media_id": "provider-imported-media-1",
            "provider_media_status": "linked",
            "source": "manual_import",
            "tags": ["imported", "provider"],
        },
    )
    assert create_response.status_code == 200
    asset = create_response.json()
    assert asset["phone_number_id"] == "pn-media-1"
    assert asset["meta_media_id"] is None
    assert asset["meta_media_status"] is None

    detail_response = client.get(f"/api/media/assets/{asset['asset_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["asset"]["meta_media_id"] is None
    assert detail["asset"]["meta_media_status"] is None
    assert detail["asset"]["legacy_meta_media_id"] is None
    assert len(detail["asset"]["provider_references"]) == 1
    assert detail["asset"]["provider_references"][0]["provider_media_id"] == (
        "provider-imported-media-1"
    )
    assert detail["asset"]["provider_references"][0]["meta_media_id"] == (
        "provider-imported-media-1"
    )
    assert len(detail["provider_syncs"]) == 1
    assert detail["provider_syncs"][0]["provider_media_id"] == "provider-imported-media-1"
    assert detail["provider_syncs"][0]["meta_media_id"] == "provider-imported-media-1"
    assert detail["provider_syncs"][0]["sync_status"] == "linked"
    assert detail["provider_syncs"][0]["raw_response"]["reference_mode"] == (
        "phone_scoped_provider_reference"
    )
    assert detail["provider_syncs"][0]["raw_response"]["legacy_meta_media_id_provided"] is False

    list_response = client.get(
        "/api/media/assets",
        params={"account_id": "media-account-1", "query": "provider-imported-media-1"},
    )
    assert list_response.status_code == 200
    listed_assets = list_response.json()
    assert [item["asset_id"] for item in listed_assets] == [asset["asset_id"]]
    assert listed_assets[0]["legacy_meta_media_id"] is None
    assert listed_assets[0]["provider_references"][0]["provider_media_id"] == (
        "provider-imported-media-1"
    )

    created_event = next(
        item for item in detail["events"] if item["event_type"] == "media_asset_created"
    )
    assert created_event["provider_media_id"] == "provider-imported-media-1"
    assert created_event["meta_media_id"] == "provider-imported-media-1"
    assert created_event["payload"]["provider_media_id"] == "provider-imported-media-1"
    assert created_event["payload"]["provider_media_status"] == "linked"
    assert created_event["payload"]["meta_media_id"] is None
    assert created_event["payload"]["meta_media_status"] is None


def test_media_asset_list_and_detail_preserve_legacy_provider_phone_scope_after_relationship_drift(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_media_account(client)

    create_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "drifted-provider-scope-image",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "provider_media_id": "provider-drifted-media-1",
            "provider_media_status": "linked",
            "source": "manual_import",
            "tags": ["imported", "drifted"],
        },
    )
    assert create_response.status_code == 200
    asset_id = create_response.json()["asset_id"]

    with db_session_factory() as session:
        phone_number = (
            session.query(WhatsAppPhoneNumber)
            .filter(
                WhatsAppPhoneNumber.account_id == "media-account-1",
                WhatsAppPhoneNumber.phone_number_id == "pn-media-1",
            )
            .one()
        )
        phone_number.phone_number_id = "pn-media-1-drifted"
        phone_number.waba_id = "waba-media-1-drifted"
        assert phone_number.waba_account is not None
        phone_number.waba_account.waba_id = "waba-media-1-drifted"
        session.commit()

    list_response = client.get(
        "/api/media/assets",
        params={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
        },
    )
    assert list_response.status_code == 200, list_response.text
    listed_assets = list_response.json()
    assert [item["asset_id"] for item in listed_assets] == [asset_id]
    assert listed_assets[0]["waba_id"] == "waba-media-1"
    assert listed_assets[0]["phone_number_id"] == "pn-media-1"
    assert listed_assets[0]["provider_references"][0]["provider_media_id"] == (
        "provider-drifted-media-1"
    )

    detail_response = client.get(f"/api/media/assets/{asset_id}")
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert detail["asset"]["waba_id"] == "waba-media-1"
    assert detail["asset"]["phone_number_id"] == "pn-media-1"
    assert detail["provider_syncs"][0]["waba_id"] == "waba-media-1"
    assert detail["provider_syncs"][0]["phone_number_id"] == "pn-media-1"
    created_event = next(
        item for item in detail["events"] if item["event_type"] == "media_asset_created"
    )
    assert created_event["waba_id"] == "waba-media-1"
    assert created_event["phone_number_id"] == "pn-media-1"

    with db_session_factory() as session:
        asset = session.get(MediaAsset, asset_id)
        assert asset is not None
        assert asset.waba_id == "waba-media-1"
        assert asset.phone_number is not None
        assert asset.phone_number.phone_number_id == "pn-media-1-drifted"


def test_media_asset_list_and_detail_preserve_snapshot_scope_after_cross_account_phone_row_misbinding(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_media_account(
        client,
        account_id="media-misbind-account-a",
        display_name="Media Misbind Account A",
        portfolio_id="portfolio-media-misbind-a",
        waba_id="waba-media-misbind-a",
        access_token="token-media-misbind-a",
        verify_token="verify-media-misbind-a",
        app_secret="secret-media-misbind-a",
        phone_numbers=[
            {
                "phone_number_id": "pn-media-misbind-a",
                "display_phone_number": "+1 555 100 1111",
                "verified_name": "Media Misbind A",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    register_media_account(
        client,
        account_id="media-misbind-account-b",
        display_name="Media Misbind Account B",
        portfolio_id="portfolio-media-misbind-b",
        waba_id="waba-media-misbind-b",
        access_token="token-media-misbind-b",
        verify_token="verify-media-misbind-b",
        app_secret="secret-media-misbind-b",
        phone_numbers=[
            {
                "phone_number_id": "pn-media-misbind-b",
                "display_phone_number": "+1 555 100 1112",
                "verified_name": "Media Misbind B",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )

    create_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-misbind-account-a",
            "waba_id": "waba-media-misbind-a",
            "phone_number_id": "pn-media-misbind-a",
            "name": "misbound-cross-account-image",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/misbound-cross-account-image.jpg",
            "tags": ["snapshot", "misbind"],
        },
    )
    assert create_response.status_code == 200
    asset_id = create_response.json()["asset_id"]

    sync_response = client.post(
        f"/api/media/assets/{asset_id}/sync",
        json={"force_resync": False},
    )
    assert sync_response.status_code == 200, sync_response.text

    with db_session_factory() as session:
        asset = session.get(MediaAsset, asset_id)
        assert asset is not None
        other_phone = (
            session.query(WhatsAppPhoneNumber)
            .filter(
                WhatsAppPhoneNumber.account_id == "media-misbind-account-b",
                WhatsAppPhoneNumber.phone_number_id == "pn-media-misbind-b",
            )
            .one()
        )
        asset.phone_number_id = other_phone.id
        session.add(asset)
        session.commit()

    list_response = client.get(
        "/api/media/assets",
        params={
            "account_id": "media-misbind-account-a",
            "waba_id": "waba-media-misbind-a",
            "phone_number_id": "pn-media-misbind-a",
        },
    )
    assert list_response.status_code == 200, list_response.text
    listed_assets = list_response.json()
    assert [item["asset_id"] for item in listed_assets] == [asset_id]
    assert listed_assets[0]["account_id"] == "media-misbind-account-a"
    assert listed_assets[0]["waba_id"] == "waba-media-misbind-a"
    assert listed_assets[0]["phone_number_id"] == "pn-media-misbind-a"

    detail_response = client.get(f"/api/media/assets/{asset_id}")
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert detail["asset"]["account_id"] == "media-misbind-account-a"
    assert detail["asset"]["waba_id"] == "waba-media-misbind-a"
    assert detail["asset"]["phone_number_id"] == "pn-media-misbind-a"
    assert detail["provider_syncs"][0]["waba_id"] == "waba-media-misbind-a"
    assert detail["provider_syncs"][0]["phone_number_id"] == "pn-media-misbind-a"


def test_media_asset_sync_prefers_snapshot_scope_over_cross_account_phone_row_misbinding(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_media_account(
        client,
        account_id="media-misbind-sync-account-a",
        display_name="Media Misbind Sync Account A",
        portfolio_id="portfolio-media-misbind-sync-a",
        waba_id="waba-media-misbind-sync-a",
        access_token="token-media-misbind-sync-a",
        verify_token="verify-media-misbind-sync-a",
        app_secret="secret-media-misbind-sync-a",
        phone_numbers=[
            {
                "phone_number_id": "pn-media-misbind-sync-a",
                "display_phone_number": "+1 555 100 1121",
                "verified_name": "Media Misbind Sync A",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    register_media_account(
        client,
        account_id="media-misbind-sync-account-b",
        display_name="Media Misbind Sync Account B",
        portfolio_id="portfolio-media-misbind-sync-b",
        waba_id="waba-media-misbind-sync-b",
        access_token="token-media-misbind-sync-b",
        verify_token="verify-media-misbind-sync-b",
        app_secret="secret-media-misbind-sync-b",
        phone_numbers=[
            {
                "phone_number_id": "pn-media-misbind-sync-b",
                "display_phone_number": "+1 555 100 1122",
                "verified_name": "Media Misbind Sync B",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )

    create_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-misbind-sync-account-a",
            "waba_id": "waba-media-misbind-sync-a",
            "phone_number_id": "pn-media-misbind-sync-a",
            "name": "misbound-cross-account-sync-image",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/misbound-cross-account-sync-image.jpg",
            "tags": ["snapshot", "misbind", "sync"],
        },
    )
    assert create_response.status_code == 200
    asset_id = create_response.json()["asset_id"]

    first_sync_response = client.post(
        f"/api/media/assets/{asset_id}/sync",
        json={"force_resync": False},
    )
    assert first_sync_response.status_code == 200, first_sync_response.text
    assert first_sync_response.json()["phone_number_id"] == "pn-media-misbind-sync-a"

    with db_session_factory() as session:
        asset = session.get(MediaAsset, asset_id)
        assert asset is not None
        other_phone = (
            session.query(WhatsAppPhoneNumber)
            .filter(
                WhatsAppPhoneNumber.account_id == "media-misbind-sync-account-b",
                WhatsAppPhoneNumber.phone_number_id == "pn-media-misbind-sync-b",
            )
            .one()
        )
        asset.phone_number_id = other_phone.id
        session.add(asset)
        session.commit()

    resync_response = client.post(
        f"/api/media/assets/{asset_id}/sync",
        json={"force_resync": False},
    )
    assert resync_response.status_code == 200, resync_response.text
    assert resync_response.json()["reused_existing"] is True
    assert resync_response.json()["waba_id"] == "waba-media-misbind-sync-a"
    assert resync_response.json()["phone_number_id"] == "pn-media-misbind-sync-a"


def test_media_asset_create_rejects_conflicting_provider_and_legacy_media_ids(
    client: TestClient,
) -> None:
    register_media_account(client)

    create_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "conflicting-provider-reference",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "provider_media_id": "provider-media-1",
            "meta_media_id": "legacy-media-1",
            "source": "manual_import",
        },
    )

    assert create_response.status_code == 422
    assert (
        "provider_media_id and legacy meta_media_id must match"
        in create_response.text
    )


def test_media_asset_create_rejects_provider_media_reference_without_phone_number_scope(
    client: TestClient,
) -> None:
    register_media_account(client)

    create_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "name": "unscoped-provider-reference",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "meta_media_id": "meta-unscoped-media-1",
            "source": "manual_import",
        },
    )

    assert create_response.status_code == 422
    assert "provider_media_id requires phone_number_id" in create_response.text


def test_media_asset_sync_endpoint_creates_provider_sync_record(client: TestClient) -> None:
    register_media_account(client)

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "invoice-pdf",
            "asset_type": "document",
            "mime_type": "application/pdf",
            "storage_url": "https://cdn.example.com/invoice.pdf",
            "tags": ["invoice"],
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    sync_response = client.post(
        f"/api/media/assets/{asset_id}/sync",
        json={"force_resync": False},
    )
    assert sync_response.status_code == 200
    sync_payload = sync_response.json()
    assert sync_payload["asset_id"] == asset_id
    assert sync_payload["provider_name"] == "mock"
    assert sync_payload["waba_id"] == "waba-media-1"
    assert sync_payload["phone_number_id"] == "pn-media-1"
    assert sync_payload["provider_media_id"] == sync_payload["meta_media_id"]
    assert sync_payload["sync_status"] == "synced"
    assert sync_payload["meta_media_id"].startswith("mock-media-")
    assert sync_payload["reused_existing"] is False

    detail_response = client.get(f"/api/media/assets/{asset_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert len(detail["provider_syncs"]) == 1
    assert detail["provider_syncs"][0]["waba_id"] == "waba-media-1"
    assert detail["provider_syncs"][0]["provider_media_id"] == sync_payload["provider_media_id"]
    assert detail["provider_syncs"][0]["sync_status"] == "synced"


def test_media_asset_list_route_rejects_mismatched_waba_and_phone_scope_filters(
    client: TestClient,
) -> None:
    register_media_account(client)

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "scope-filter-image",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/scope-filter-image.jpg",
        },
    )
    assert create_asset_response.status_code == 200

    mismatch_response = client.get(
        "/api/media/assets",
        params={
            "account_id": "media-account-1",
            "waba_id": "waba-media-other",
            "phone_number_id": "pn-media-1",
        },
    )

    assert mismatch_response.status_code == 400
    assert "belongs to WABA 'waba-media-1'" in mismatch_response.json()["detail"]


def test_media_asset_list_route_rejects_cross_account_waba_scope_without_phone_filter(
    client: TestClient,
) -> None:
    register_media_account(client)
    register_media_account(
        client,
        account_id="media-account-2",
        display_name="Media Account 2",
        portfolio_id="portfolio-media-2",
        waba_id="waba-media-2",
        access_token="token-media-2",
        verify_token="verify-media-2",
        app_secret="secret-media-2",
        phone_numbers=[
            {
                "phone_number_id": "pn-media-2",
                "display_phone_number": "+1 555 100 0002",
                "verified_name": "Media Number 2",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )

    mismatch_response = client.get(
        "/api/media/assets",
        params={
            "account_id": "media-account-1",
            "waba_id": "waba-media-2",
        },
    )

    assert mismatch_response.status_code == 400
    assert mismatch_response.json()["detail"] == (
        "WABA 'waba-media-2' belongs to account 'media-account-2', not 'media-account-1'."
    )


def test_media_asset_sync_endpoint_persists_failed_provider_sync_record(
    client: TestClient,
) -> None:
    client.app.dependency_overrides[get_messaging_service] = lambda: FailingMediaSyncProvider()
    register_media_account(client)

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "failed-sync-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/failed-sync-banner.jpg",
            "tags": ["sync-failure"],
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    sync_response = client.post(
        f"/api/media/assets/{asset_id}/sync",
        json={"force_resync": False},
    )
    assert sync_response.status_code == 409
    assert "provider upload failed" in sync_response.json()["detail"]

    detail_response = client.get(f"/api/media/assets/{asset_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert len(detail["provider_syncs"]) == 1
    assert detail["provider_syncs"][0]["sync_status"] == "failed"
    assert detail["provider_syncs"][0]["last_error_code"] == "provider_upload_failed"
    assert detail["provider_syncs"][0]["last_error_message"] == "provider upload failed"
    failed_events = [
        item for item in detail["events"] if item["event_type"] == "media_asset_sync_failed"
    ]
    assert len(failed_events) == 1
    assert failed_events[0]["waba_id"] == "waba-media-1"
    assert failed_events[0]["phone_number_id"] == "pn-media-1"
    assert failed_events[0]["payload"]["error_code"] == "provider_upload_failed"

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "media-account-1",
            "action": "media_asset_sync_failed",
            "target_type": "media_asset",
            "target_id": asset_id,
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"]["error_code"] == "provider_upload_failed"
    assert audit_logs[0]["payload"]["phone_number_id"] == "pn-media-1"


def test_media_asset_sync_endpoint_returns_503_for_missing_whatsapp_access_token(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    client.app.dependency_overrides[get_messaging_service] = lambda: WhatsAppProvider()
    register_media_account(client)

    with db_session_factory() as session:
        waba_account = session.query(WhatsAppBusinessAccount).filter_by(
            account_id="media-account-1",
            waba_id="waba-media-1",
        ).one()
        waba_account.access_token = None
        session.commit()

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "missing-token-sync-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/missing-token-sync-banner.jpg",
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    sync_response = client.post(
        f"/api/media/assets/{asset_id}/sync",
        json={"force_resync": False},
    )

    assert sync_response.status_code == 503
    assert "access_token" in sync_response.json()["detail"]


def test_media_asset_sync_endpoint_returns_502_for_provider_runtime_failure(
    client: TestClient,
) -> None:
    client.app.dependency_overrides[get_messaging_service] = lambda: RuntimeErrorMediaSyncProvider()
    register_media_account(client)

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "runtime-sync-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/runtime-sync-banner.jpg",
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    sync_response = client.post(
        f"/api/media/assets/{asset_id}/sync",
        json={"force_resync": False},
    )

    assert sync_response.status_code == 502
    assert sync_response.json()["detail"] == "provider_sync_unavailable"


def test_media_asset_sync_reuses_existing_record_unless_force_resync(
    client: TestClient,
) -> None:
    provider = CountingMediaSyncProvider()
    client.app.dependency_overrides[get_messaging_service] = lambda: provider
    register_media_account(client)

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "resync-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/resync-banner.jpg",
            "tags": ["resync"],
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    first_sync_response = client.post(
        f"/api/media/assets/{asset_id}/sync",
        json={"force_resync": False},
    )
    assert first_sync_response.status_code == 200
    first_sync = first_sync_response.json()
    assert first_sync["reused_existing"] is False
    assert first_sync["sync_status"] == "synced"
    assert provider.sync_calls == 1

    reused_sync_response = client.post(
        f"/api/media/assets/{asset_id}/sync",
        json={"force_resync": False},
    )
    assert reused_sync_response.status_code == 200
    reused_sync = reused_sync_response.json()
    assert reused_sync["reused_existing"] is True
    assert reused_sync["sync_status"] == "reused"
    assert reused_sync["meta_media_id"] == first_sync["meta_media_id"]
    assert provider.sync_calls == 1

    forced_sync_response = client.post(
        f"/api/media/assets/{asset_id}/sync",
        json={"force_resync": True},
    )
    assert forced_sync_response.status_code == 200
    forced_sync = forced_sync_response.json()
    assert forced_sync["reused_existing"] is False
    assert forced_sync["sync_status"] == "synced"
    assert forced_sync["meta_media_id"] != first_sync["meta_media_id"]
    assert provider.sync_calls == 2

    detail_response = client.get(f"/api/media/assets/{asset_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert len(detail["provider_syncs"]) == 1
    assert detail["provider_syncs"][0]["sync_status"] == "synced"
    event_types = [item["event_type"] for item in detail["events"]]
    assert event_types.count("media_asset_sync_succeeded") == 2
    assert event_types.count("media_asset_sync_reused") == 1


def test_media_asset_force_resync_failure_preserves_last_known_provider_media_id(
    client: TestClient,
) -> None:
    provider = FailingSecondMediaSyncProvider()
    client.app.dependency_overrides[get_messaging_service] = lambda: provider
    register_media_account(client)

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "force-resync-failure-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/force-resync-failure-banner.jpg",
            "tags": ["resync", "failure"],
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    first_sync_response = client.post(
        f"/api/media/assets/{asset_id}/sync",
        json={"force_resync": False},
    )
    assert first_sync_response.status_code == 200
    assert first_sync_response.json()["meta_media_id"] == "mock-media-first-sync"

    failed_sync_response = client.post(
        f"/api/media/assets/{asset_id}/sync",
        json={"force_resync": True},
    )
    assert failed_sync_response.status_code == 409
    assert "provider upload failed" in failed_sync_response.json()["detail"]

    detail_response = client.get(f"/api/media/assets/{asset_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert len(detail["provider_syncs"]) == 1
    provider_sync = detail["provider_syncs"][0]
    assert provider_sync["sync_status"] == "synced"
    assert provider_sync["meta_media_id"] == "mock-media-first-sync"
    assert provider_sync["last_error_code"] == "provider_upload_failed"

    failed_event = next(
        item for item in detail["events"] if item["event_type"] == "media_asset_sync_failed"
    )
    assert failed_event["meta_media_id"] == "mock-media-first-sync"
    assert failed_event["payload"]["provider_media_id"] is None
    assert failed_event["payload"]["failed_provider_media_id"] is None
    assert failed_event["payload"]["last_known_provider_media_id"] == "mock-media-first-sync"
    assert failed_event["payload"]["last_known_meta_media_id"] == "mock-media-first-sync"

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "media-account-1",
            "action": "media_asset_sync_failed",
            "target_type": "media_asset",
            "target_id": asset_id,
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"]["provider_media_id"] is None
    assert audit_logs[0]["payload"]["failed_provider_media_id"] is None
    assert audit_logs[0]["payload"]["last_known_provider_media_id"] == "mock-media-first-sync"
    assert audit_logs[0]["payload"]["last_known_meta_media_id"] == "mock-media-first-sync"


def test_media_asset_manual_send_persists_failed_sync_without_outbound_message(
    client: TestClient,
) -> None:
    client.app.dependency_overrides[get_messaging_service] = lambda: FailingMediaSyncProvider()
    register_media_account(client)

    agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-media-sync-failure",
            "display_name": "Media Sync Failure Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert agent_response.status_code == 200

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "manual-send-sync-failure",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/manual-send-sync-failure.jpg",
            "tags": ["manual-send", "sync-failure"],
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "media-account-1",
            "conversation_id": "conv-media-sync-failure",
            "user_id": "user-media-sync-failure",
            "text": "need image",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-media-1",
            "agent_id": "agent-media-sync-failure",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/media-account-1/conv-media-sync-failure/assignment",
        json={
            "agent_id": "agent-media-sync-failure",
            "assigned_by_agent_id": "agent-media-sync-failure",
            "reason": "manual_media_reply",
        },
    )
    assert assignment_response.status_code == 200

    send_response = client.post(
        "/api/conversations/media-account-1/conv-media-sync-failure/messages/media",
        json={
            "asset_id": asset_id,
            "caption": "image attached",
            "agent_id": "agent-media-sync-failure",
        },
    )
    assert send_response.status_code == 409
    assert "provider upload failed" in send_response.json()["detail"]

    messages_response = client.get(
        "/api/conversations/media-account-1/conv-media-sync-failure/messages"
    )
    assert messages_response.status_code == 200
    assert not any(
        message.get("payload", {}).get("asset_id") == asset_id
        for message in messages_response.json()
    )

    detail_response = client.get(f"/api/media/assets/{asset_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert len(detail["provider_syncs"]) == 1
    assert detail["provider_syncs"][0]["sync_status"] == "failed"
    failed_events = [
        item for item in detail["events"] if item["event_type"] == "media_asset_sync_failed"
    ]
    assert len(failed_events) == 1
    assert failed_events[0]["waba_id"] == "waba-media-1"
    assert failed_events[0]["phone_number_id"] == "pn-media-1"
    assert failed_events[0]["payload"]["conversation_id"] == "conv-media-sync-failure"
    assert failed_events[0]["payload"]["external_conversation_id"] == "conv-media-sync-failure"
    assert failed_events[0]["payload"]["internal_conversation_id"] != "conv-media-sync-failure"

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "media-account-1",
            "action": "media_asset_sync_failed",
            "target_type": "media_asset",
            "target_id": asset_id,
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"]["error_code"] == "provider_upload_failed"
    assert audit_logs[0]["payload"]["phone_number_id"] == "pn-media-1"
    assert audit_logs[0]["payload"]["conversation_id"] == "conv-media-sync-failure"
    assert audit_logs[0]["payload"]["external_conversation_id"] == "conv-media-sync-failure"
    assert audit_logs[0]["payload"]["internal_conversation_id"] != "conv-media-sync-failure"


def test_media_asset_manual_send_returns_503_for_missing_whatsapp_access_token(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    client.app.dependency_overrides[get_messaging_service] = lambda: WhatsAppProvider()
    register_media_account(client)

    agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-media-missing-token",
            "display_name": "Media Missing Token Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert agent_response.status_code == 200

    with db_session_factory() as session:
        waba_account = session.query(WhatsAppBusinessAccount).filter_by(
            account_id="media-account-1",
            waba_id="waba-media-1",
        ).one()
        waba_account.access_token = None
        session.commit()

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "missing-token-manual-send",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/missing-token-manual-send.jpg",
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "media-account-1",
            "conversation_id": "conv-media-missing-token",
            "user_id": "user-media-missing-token",
            "text": "need image",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-media-1",
            "agent_id": "agent-media-missing-token",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/media-account-1/conv-media-missing-token/assignment",
        json={
            "agent_id": "agent-media-missing-token",
            "assigned_by_agent_id": "agent-media-missing-token",
            "reason": "manual_media_reply",
        },
    )
    assert assignment_response.status_code == 200

    send_response = client.post(
        "/api/conversations/media-account-1/conv-media-missing-token/messages/media",
        json={
            "asset_id": asset_id,
            "caption": "image attached",
            "agent_id": "agent-media-missing-token",
        },
    )

    assert send_response.status_code == 503
    assert "access token" in send_response.json()["detail"].lower()


def test_media_asset_manual_send_returns_502_for_provider_runtime_failure(
    client: TestClient,
) -> None:
    client.app.dependency_overrides[get_messaging_service] = lambda: RuntimeErrorMediaSendProvider()
    register_media_account(client)

    agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-media-runtime-send",
            "display_name": "Media Runtime Send Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert agent_response.status_code == 200

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "runtime-manual-send",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/runtime-manual-send.jpg",
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "media-account-1",
            "conversation_id": "conv-media-runtime-send",
            "user_id": "user-media-runtime-send",
            "text": "need image",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-media-1",
            "agent_id": "agent-media-runtime-send",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/media-account-1/conv-media-runtime-send/assignment",
        json={
            "agent_id": "agent-media-runtime-send",
            "assigned_by_agent_id": "agent-media-runtime-send",
            "reason": "manual_media_reply",
        },
    )
    assert assignment_response.status_code == 200

    send_response = client.post(
        "/api/conversations/media-account-1/conv-media-runtime-send/messages/media",
        json={
            "asset_id": asset_id,
            "caption": "image attached",
            "agent_id": "agent-media-runtime-send",
        },
    )

    assert send_response.status_code == 502
    assert send_response.json()["detail"] == "Media asset send failed: provider_send_unavailable"


def test_media_asset_sync_rejects_phone_number_from_different_waba(
    client: TestClient,
) -> None:
    register_media_account(
        client,
        account_id="media-cross-waba-account",
        display_name="Media Cross WABA Account",
        portfolio_id="portfolio-media-cross-waba",
        waba_id="waba-media-cross-a",
        access_token="token-media-cross-a",
        verify_token="verify-media-cross-a",
        app_secret="secret-media-cross-a",
        phone_numbers=[
            {
                "phone_number_id": "pn-media-cross-a",
                "display_phone_number": "+1 555 100 0201",
                "verified_name": "Media Cross A",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    register_media_account(
        client,
        account_id="media-cross-waba-account",
        display_name="Media Cross WABA Account",
        portfolio_id="portfolio-media-cross-waba",
        waba_id="waba-media-cross-b",
        access_token="token-media-cross-b",
        verify_token="verify-media-cross-b",
        app_secret="secret-media-cross-b",
        phone_numbers=[
            {
                "phone_number_id": "pn-media-cross-b",
                "display_phone_number": "+1 555 100 0202",
                "verified_name": "Media Cross B",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-cross-waba-account",
            "waba_id": "waba-media-cross-a",
            "phone_number_id": "pn-media-cross-a",
            "name": "cross-waba-image",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/cross-waba-image.jpg",
            "tags": ["scope"],
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    sync_response = client.post(
        f"/api/media/assets/{asset_id}/sync",
        json={"phone_number_id": "pn-media-cross-b", "force_resync": False},
    )
    assert sync_response.status_code == 409
    assert "is bound to Phone-Number-ID 'pn-media-cross-a'" in sync_response.json()["detail"]


def test_media_asset_sync_rejects_cross_account_bound_phone_row(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_media_account(
        client,
        account_id="media-cross-account-asset-a",
        display_name="Media Cross Account Asset A",
        portfolio_id="portfolio-media-cross-account-a",
        waba_id="waba-media-cross-account-a",
        access_token="token-media-cross-account-a",
        verify_token="verify-media-cross-account-a",
        app_secret="secret-media-cross-account-a",
        phone_numbers=[
            {
                "phone_number_id": "pn-media-cross-account-a",
                "display_phone_number": "+1 555 100 0211",
                "verified_name": "Media Cross Account A",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    register_media_account(
        client,
        account_id="media-cross-account-asset-b",
        display_name="Media Cross Account Asset B",
        portfolio_id="portfolio-media-cross-account-b",
        waba_id="waba-media-cross-account-b",
        access_token="token-media-cross-account-b",
        verify_token="verify-media-cross-account-b",
        app_secret="secret-media-cross-account-b",
        phone_numbers=[
            {
                "phone_number_id": "pn-media-cross-account-b",
                "display_phone_number": "+1 555 100 0212",
                "verified_name": "Media Cross Account B",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-cross-account-asset-a",
            "waba_id": "waba-media-cross-account-a",
            "phone_number_id": "pn-media-cross-account-a",
            "name": "cross-account-sync-image",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/cross-account-sync-image.jpg",
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    with db_session_factory() as session:
        asset = session.query(MediaAsset).filter(MediaAsset.id == asset_id).one()
        cross_account_phone = (
            session.query(WhatsAppPhoneNumber)
            .filter(
                WhatsAppPhoneNumber.account_id == "media-cross-account-asset-b",
                WhatsAppPhoneNumber.phone_number_id == "pn-media-cross-account-b",
            )
            .one()
        )
        asset.phone_number_id = cross_account_phone.id
        session.add(asset)
        session.commit()

    sync_response = client.post(
        f"/api/media/assets/{asset_id}/sync",
        json={"force_resync": False},
    )
    assert sync_response.status_code == 409
    assert "requires phone_number_id because it is account scoped" in sync_response.json()["detail"]


def test_media_asset_send_uses_conversation_phone_scope_when_asset_row_is_cross_account_misbound(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_media_account(
        client,
        account_id="media-cross-account-send-a",
        display_name="Media Cross Account Send A",
        portfolio_id="portfolio-media-cross-account-send-a",
        waba_id="waba-media-cross-account-send-a",
        access_token="token-media-cross-account-send-a",
        verify_token="verify-media-cross-account-send-a",
        app_secret="secret-media-cross-account-send-a",
        phone_numbers=[
            {
                "phone_number_id": "pn-media-cross-account-send-a",
                "display_phone_number": "+1 555 100 0213",
                "verified_name": "Media Cross Send A",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    register_media_account(
        client,
        account_id="media-cross-account-send-b",
        display_name="Media Cross Account Send B",
        portfolio_id="portfolio-media-cross-account-send-b",
        waba_id="waba-media-cross-account-send-b",
        access_token="token-media-cross-account-send-b",
        verify_token="verify-media-cross-account-send-b",
        app_secret="secret-media-cross-account-send-b",
        phone_numbers=[
            {
                "phone_number_id": "pn-media-cross-account-send-b",
                "display_phone_number": "+1 555 100 0214",
                "verified_name": "Media Cross Send B",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )

    agent_response = client.post(
        "/api/runtime/agents",
        json={
            "account_id": "media-cross-account-send-a",
            "agent_id": "agent-media-cross-account-send-a",
            "display_name": "agent-media-cross-account-send-a",
            "status": "online",
            "is_active": True,
        },
    )
    assert agent_response.status_code == 200

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-cross-account-send-a",
            "waba_id": "waba-media-cross-account-send-a",
            "phone_number_id": "pn-media-cross-account-send-a",
            "name": "cross-account-send-image",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/cross-account-send-image.jpg",
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "media-cross-account-send-a",
            "conversation_id": "conv-media-cross-account-send-a",
            "user_id": "user-media-cross-account-send-a",
            "text": "send the image",
            "mode": "echo",
            "phone_number_id": "pn-media-cross-account-send-a",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/media-cross-account-send-a/conv-media-cross-account-send-a/assignment",
        json={
            "agent_id": "agent-media-cross-account-send-a",
            "assigned_by_agent_id": "agent-media-cross-account-send-a",
            "reason": "cross_account_media_scope_guard",
        },
    )
    assert assignment_response.status_code == 200

    with db_session_factory() as session:
        asset = session.query(MediaAsset).filter(MediaAsset.id == asset_id).one()
        cross_account_phone = (
            session.query(WhatsAppPhoneNumber)
            .filter(
                WhatsAppPhoneNumber.account_id == "media-cross-account-send-b",
                WhatsAppPhoneNumber.phone_number_id == "pn-media-cross-account-send-b",
            )
            .one()
        )
        asset.phone_number_id = cross_account_phone.id
        session.add(asset)
        session.commit()

    send_response = client.post(
        "/api/conversations/media-cross-account-send-a/conv-media-cross-account-send-a/messages/media",
        json={
            "asset_id": asset_id,
            "caption": "manual media reply",
            "agent_id": "agent-media-cross-account-send-a",
        },
    )
    assert send_response.status_code == 200, send_response.text
    send_payload = send_response.json()
    assert send_payload["asset_id"] == asset_id
    assert send_payload["conversation_id"] == "conv-media-cross-account-send-a"
    assert send_payload["waba_id"] == "waba-media-cross-account-send-a"
    assert send_payload["phone_number_id"] == "pn-media-cross-account-send-a"

    detail_response = client.get(f"/api/media/assets/{asset_id}")
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert detail["asset"]["account_id"] == "media-cross-account-send-a"
    assert detail["asset"]["waba_id"] == "waba-media-cross-account-send-a"
    assert detail["asset"]["phone_number_id"] == "pn-media-cross-account-send-a"
    assert detail["provider_syncs"][-1]["waba_id"] == "waba-media-cross-account-send-a"
    assert detail["provider_syncs"][-1]["phone_number_id"] == "pn-media-cross-account-send-a"


def test_media_asset_update_supports_scope_activation_and_audit_logs(client: TestClient) -> None:
    register_media_account(
        client,
        phone_numbers=[
            {
                "phone_number_id": "pn-media-1",
                "display_phone_number": "+1 555 100 0001",
                "verified_name": "Media Number 1",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
            {
                "phone_number_id": "pn-media-2",
                "display_phone_number": "+1 555 100 0002",
                "verified_name": "Media Number 2",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
        ],
    )

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "shipping-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/shipping-banner.jpg",
            "tags": ["shipping", "banner"],
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    update_response = client.patch(
        f"/api/media/assets/{asset_id}",
        json={
            "name": "shipping-banner-v2",
            "phone_number_id": "pn-media-2",
            "tags": ["shipping", "summer"],
        },
    )
    assert update_response.status_code == 200
    updated_asset = update_response.json()
    assert updated_asset["name"] == "shipping-banner-v2"
    assert updated_asset["phone_number_id"] == "pn-media-2"
    assert updated_asset["waba_id"] == "waba-media-1"
    assert updated_asset["tags"] == ["shipping", "summer"]
    assert updated_asset["is_active"] is True

    deactivate_response = client.patch(
        f"/api/media/assets/{asset_id}",
        json={"is_active": False},
    )
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False

    active_assets_response = client.get(
        "/api/media/assets",
        params={"account_id": "media-account-1", "is_active": True},
    )
    assert active_assets_response.status_code == 200
    assert active_assets_response.json() == []

    inactive_assets_response = client.get(
        "/api/media/assets",
        params={"account_id": "media-account-1", "is_active": False},
    )
    assert inactive_assets_response.status_code == 200
    assert [item["asset_id"] for item in inactive_assets_response.json()] == [asset_id]

    reactivate_response = client.patch(
        f"/api/media/assets/{asset_id}",
        json={"is_active": True},
    )
    assert reactivate_response.status_code == 200
    assert reactivate_response.json()["is_active"] is True

    detail_response = client.get(f"/api/media/assets/{asset_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["asset"]["phone_number_id"] == "pn-media-2"
    assert detail["asset"]["is_active"] is True
    event_types = [item["event_type"] for item in detail["events"]]
    assert event_types.count("media_asset_updated") == 3

    audit_logs_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "media-account-1",
            "target_type": "media_asset",
            "target_id": asset_id,
            "limit": 10,
        },
    )
    assert audit_logs_response.status_code == 200
    audit_logs = audit_logs_response.json()
    actions = [item["action"] for item in audit_logs]
    assert "media_asset_updated" in actions
    assert "media_asset_deactivated" in actions
    assert "media_asset_reactivated" in actions
    updated_log = next(item for item in audit_logs if item["action"] == "media_asset_updated")
    assert updated_log["payload"]["changes"]["phone_number_id"]["to"] == "pn-media-2"
    assert updated_log["payload"]["changes"]["name"]["to"] == "shipping-banner-v2"


def test_media_asset_rebind_keeps_current_phone_scope_distinct_from_historical_syncs(
    client: TestClient,
) -> None:
    register_media_account(
        client,
        phone_numbers=[
            {
                "phone_number_id": "pn-media-rebind-1",
                "display_phone_number": "+1 555 100 2101",
                "verified_name": "Media Rebind 1",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
            {
                "phone_number_id": "pn-media-rebind-2",
                "display_phone_number": "+1 555 100 2102",
                "verified_name": "Media Rebind 2",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
        ],
    )

    agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-media-rebind",
            "display_name": "Media Rebind Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert agent_response.status_code == 200

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-rebind-1",
            "name": "rebind-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/rebind-banner.jpg",
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    first_sync_response = client.post(
        f"/api/media/assets/{asset_id}/sync",
        json={"phone_number_id": "pn-media-rebind-1", "force_resync": False},
    )
    assert first_sync_response.status_code == 200
    first_sync = first_sync_response.json()

    update_response = client.patch(
        f"/api/media/assets/{asset_id}",
        json={"phone_number_id": "pn-media-rebind-2"},
    )
    assert update_response.status_code == 200
    updated_asset = update_response.json()
    assert updated_asset["phone_number_id"] == "pn-media-rebind-2"

    list_response = client.get(
        "/api/media/assets",
        params={"account_id": "media-account-1", "phone_number_id": "pn-media-rebind-2"},
    )
    assert list_response.status_code == 200
    listed_assets = list_response.json()
    assert [item["asset_id"] for item in listed_assets] == [asset_id]
    assert listed_assets[0]["phone_number_id"] == "pn-media-rebind-2"
    assert {item["phone_number_id"] for item in listed_assets[0]["provider_references"]} == {
        "pn-media-rebind-1"
    }

    detail_response = client.get(f"/api/media/assets/{asset_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["asset"]["phone_number_id"] == "pn-media-rebind-2"
    assert {item["phone_number_id"] for item in detail["provider_syncs"]} == {"pn-media-rebind-1"}

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "media-account-1",
            "conversation_id": "conv-media-rebind-2",
            "user_id": "user-media-rebind-2",
            "text": "send rebound banner",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-media-rebind-2",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/media-account-1/conv-media-rebind-2/assignment",
        json={
            "agent_id": "agent-media-rebind",
            "assigned_by_agent_id": "agent-media-rebind",
            "reason": "manual_media_reply",
        },
    )
    assert assignment_response.status_code == 200

    send_response = client.post(
        "/api/conversations/media-account-1/conv-media-rebind-2/messages/media",
        json={
            "asset_id": asset_id,
            "caption": "rebound banner attached",
            "agent_id": "agent-media-rebind",
        },
    )
    assert send_response.status_code == 200, send_response.text
    send_payload = send_response.json()
    assert send_payload["phone_number_id"] == "pn-media-rebind-2"
    assert send_payload["provider_media_id"] != first_sync["provider_media_id"]

    refreshed_detail_response = client.get(f"/api/media/assets/{asset_id}")
    assert refreshed_detail_response.status_code == 200
    refreshed_detail = refreshed_detail_response.json()
    assert refreshed_detail["asset"]["phone_number_id"] == "pn-media-rebind-2"
    assert {item["phone_number_id"] for item in refreshed_detail["provider_syncs"]} == {
        "pn-media-rebind-1",
        "pn-media-rebind-2",
    }


def test_media_asset_update_rejects_mismatched_waba_and_phone_scope(client: TestClient) -> None:
    register_media_account(client)

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "shipping-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/shipping-banner.jpg",
            "tags": ["shipping"],
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    mismatch_response = client.patch(
        f"/api/media/assets/{asset_id}",
        json={
            "waba_id": "waba-media-other",
            "phone_number_id": "pn-media-1",
        },
    )
    assert mismatch_response.status_code == 409
    assert "does not match phone number" in mismatch_response.json()["detail"]


def test_media_asset_supports_storage_key_reference(client: TestClient, tmp_path: Path) -> None:
    register_media_account(client)

    local_asset_path = tmp_path / "shipping-banner.jpg"
    local_asset_path.write_bytes(b"mock-image")

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "local-shipping-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_key": str(local_asset_path),
            "tags": ["local", "shipping"],
        },
    )
    assert create_asset_response.status_code == 200
    asset = create_asset_response.json()
    assert asset["storage_key"] == str(local_asset_path)
    assert asset["storage_url"] is None

    sync_response = client.post(
        f"/api/media/assets/{asset['asset_id']}/sync",
        json={"force_resync": False},
    )
    assert sync_response.status_code == 200
    sync_payload = sync_response.json()
    assert sync_payload["asset_id"] == asset["asset_id"]
    assert sync_payload["provider_name"] == "mock"
    assert sync_payload["sync_status"] == "synced"
    assert sync_payload["meta_media_id"].startswith("mock-media-")

    detail_response = client.get(f"/api/media/assets/{asset['asset_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["asset"]["storage_key"] == str(local_asset_path)
    assert detail["asset"]["storage_url"] is None
    assert detail["provider_syncs"][0]["sync_status"] == "synced"
    sync_event = next(item for item in detail["events"] if item["event_type"] == "media_asset_sync_succeeded")
    assert sync_event["payload"]["storage_key"] == str(local_asset_path)
    created_event = next(item for item in detail["events"] if item["event_type"] == "media_asset_created")
    assert created_event["payload"]["storage_key"] == str(local_asset_path)


def test_media_asset_sync_prefers_phone_snapshot_waba_when_relationship_drifts(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_media_account(client)

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "snapshot-sync-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/snapshot-sync-banner.jpg",
            "tags": ["snapshot", "sync"],
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    with db_session_factory() as session:
        waba_account = (
            session.query(WhatsAppBusinessAccount)
            .filter(
                WhatsAppBusinessAccount.account_id == "media-account-1",
                WhatsAppBusinessAccount.waba_id == "waba-media-1",
            )
            .one()
        )
        waba_account.waba_id = "waba-media-relationship-drifted-sync"
        session.commit()

    sync_response = client.post(
        f"/api/media/assets/{asset_id}/sync",
        json={"force_resync": False},
    )
    assert sync_response.status_code == 200
    sync_payload = sync_response.json()
    assert sync_payload["waba_id"] == "waba-media-1"

    detail_response = client.get(f"/api/media/assets/{asset_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["asset"]["waba_id"] == "waba-media-1"
    assert detail["provider_syncs"][0]["waba_id"] == "waba-media-1"
    sync_event = next(
        item for item in detail["events"] if item["event_type"] == "media_asset_sync_succeeded"
    )
    assert sync_event["waba_id"] == "waba-media-1"


def test_media_asset_sync_keeps_official_waba_after_local_waba_row_recreation(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_media_account(client)

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "recreated-waba-sync-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/recreated-waba-sync-banner.jpg",
            "tags": ["snapshot", "recreated-waba"],
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    with db_session_factory() as session:
        legacy_waba = (
            session.query(WhatsAppBusinessAccount)
            .filter(
                WhatsAppBusinessAccount.account_id == "media-account-1",
                WhatsAppBusinessAccount.waba_id == "waba-media-1",
            )
            .one()
        )
        legacy_waba.waba_id = "waba-media-1-legacy"
        session.commit()

        recreated_waba = WhatsAppBusinessAccount(
            account_id="media-account-1",
            portfolio_id=legacy_waba.portfolio_id,
            waba_id="waba-media-1",
            onboarding_mode="manual",
            token_source="system_user",
            access_token="token-media-1-recreated",
            verify_token="verify-media-1-recreated",
            app_secret="secret-media-1-recreated",
            webhook_subscribed=False,
            is_active=True,
            ai_enabled=True,
        )
        session.add(recreated_waba)
        session.commit()

    sync_response = client.post(
        f"/api/media/assets/{asset_id}/sync",
        json={"force_resync": False},
    )
    assert sync_response.status_code == 200
    sync_payload = sync_response.json()
    assert sync_payload["waba_id"] == "waba-media-1"

    detail_response = client.get(f"/api/media/assets/{asset_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["asset"]["waba_id"] == "waba-media-1"
    assert detail["provider_syncs"][0]["waba_id"] == "waba-media-1"
    sync_event = next(
        item for item in detail["events"] if item["event_type"] == "media_asset_sync_succeeded"
    )
    assert sync_event["waba_id"] == "waba-media-1"


def test_media_asset_library_send_keeps_official_waba_after_local_waba_row_recreation(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_media_account(client)

    agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-media-recreated-send",
            "display_name": "Media Recreated Send Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert agent_response.status_code == 200

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "recreated-waba-send-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/recreated-waba-send-banner.jpg",
            "tags": ["snapshot", "recreated-waba", "send"],
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "media-account-1",
            "conversation_id": "conv-media-recreated-send",
            "user_id": "user-media-recreated-send",
            "text": "need the recreated send banner",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-media-1",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/media-account-1/conv-media-recreated-send/assignment",
        json={
            "agent_id": "agent-media-recreated-send",
            "assigned_by_agent_id": "agent-media-recreated-send",
            "reason": "manual_media_reply",
        },
    )
    assert assignment_response.status_code == 200

    recreate_media_waba_row(
        db_session_factory,
        account_id="media-account-1",
        official_waba_id="waba-media-1",
        phone_number_id="pn-media-1",
        legacy_waba_id="waba-media-1-legacy",
    )

    send_response = client.post(
        "/api/conversations/media-account-1/conv-media-recreated-send/messages/media",
        json={
            "asset_id": asset_id,
            "caption": "recreated banner attached",
            "agent_id": "agent-media-recreated-send",
        },
    )
    assert send_response.status_code == 200
    send_payload = send_response.json()
    assert send_payload["asset_id"] == asset_id
    assert send_payload["conversation_id"] == "conv-media-recreated-send"
    assert send_payload["conversation_id"] == send_payload["external_conversation_id"]
    assert send_payload["internal_conversation_id"] != "conv-media-recreated-send"
    assert send_payload["waba_id"] == "waba-media-1"
    assert send_payload["phone_number_id"] == "pn-media-1"
    assert send_payload["provider_media_id"].startswith("mock-media-")

    scoped_list_response = client.get(
        "/api/media/assets",
        params={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
        },
    )
    assert scoped_list_response.status_code == 200
    scoped_asset_ids = {item["asset_id"] for item in scoped_list_response.json()}
    assert asset_id in scoped_asset_ids

    legacy_list_response = client.get(
        "/api/media/assets",
        params={"account_id": "media-account-1", "waba_id": "waba-media-1-legacy"},
    )
    assert legacy_list_response.status_code == 200
    assert legacy_list_response.json() == []

    detail_response = client.get(f"/api/media/assets/{asset_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["asset"]["waba_id"] == "waba-media-1"
    assert detail["provider_syncs"][0]["waba_id"] == "waba-media-1"
    assert_media_asset_events_have_waba_scope(
        events=detail["events"],
        expected_waba_id="waba-media-1",
        expected_phone_number_id="pn-media-1",
        expected_event_types={"media_asset_created", "media_asset_sync_succeeded", "media_asset_sent"},
    )


def test_media_asset_send_prefers_phone_scoped_provider_sync_over_asset_snapshot(
    client: TestClient,
) -> None:
    register_media_account(
        client,
        account_id="media-shared-sync-account",
        display_name="Media Shared Sync Account",
        portfolio_id="portfolio-media-shared-sync",
        waba_id="waba-media-shared-sync",
        access_token="token-media-shared-sync",
        verify_token="verify-media-shared-sync",
        app_secret="secret-media-shared-sync",
        phone_numbers=[
            {
                "phone_number_id": "pn-media-shared-sync-1",
                "display_phone_number": "+1 555 100 0001",
                "verified_name": "Media Number 1",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
            {
                "phone_number_id": "pn-media-shared-sync-2",
                "display_phone_number": "+1 555 100 0002",
                "verified_name": "Media Number 2",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
        ],
    )

    agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-media-scope-bound",
            "display_name": "Media Scope Bound Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert agent_response.status_code == 200

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-shared-sync-account",
            "waba_id": "waba-media-shared-sync",
            "name": "shared-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/shared-banner.jpg",
            "tags": ["shared"],
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    first_sync_response = client.post(
        f"/api/media/assets/{asset_id}/sync",
        json={"phone_number_id": "pn-media-shared-sync-1", "force_resync": False},
    )
    assert first_sync_response.status_code == 200
    first_sync = first_sync_response.json()

    second_sync_response = client.post(
        f"/api/media/assets/{asset_id}/sync",
        json={"phone_number_id": "pn-media-shared-sync-2", "force_resync": False},
    )
    assert second_sync_response.status_code == 200
    second_sync = second_sync_response.json()
    assert first_sync["meta_media_id"] != second_sync["meta_media_id"]

    detail_response = client.get(f"/api/media/assets/{asset_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["asset"]["phone_number_id"] is None
    assert detail["asset"]["meta_media_id"] is None
    assert detail["asset"]["meta_media_status"] is None
    assert {item["phone_number_id"] for item in detail["provider_syncs"]} == {
        "pn-media-shared-sync-1",
        "pn-media-shared-sync-2",
    }

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "media-shared-sync-account",
            "conversation_id": "conv-media-bound-1",
            "user_id": "user-media-bound-1",
            "text": "need the banner for phone 1",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-media-shared-sync-1",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/media-shared-sync-account/conv-media-bound-1/assignment",
        json={
            "agent_id": "agent-media-scope-bound",
            "assigned_by_agent_id": "agent-media-scope-bound",
            "reason": "manual_media_reply",
        },
    )
    assert assignment_response.status_code == 200

    send_response = client.post(
        "/api/conversations/media-shared-sync-account/conv-media-bound-1/messages/media",
        json={
            "asset_id": asset_id,
            "caption": "banner attached",
            "agent_id": "agent-media-scope-bound",
        },
    )
    assert send_response.status_code == 200
    first_send_payload = send_response.json()
    assert first_send_payload["conversation_id"] == "conv-media-bound-1"
    assert first_send_payload["conversation_id"] == first_send_payload["external_conversation_id"]
    assert first_send_payload["internal_conversation_id"] != "conv-media-bound-1"
    assert first_send_payload["phone_number_id"] == "pn-media-shared-sync-1"
    assert first_send_payload["provider_media_id"] == first_sync["provider_media_id"]

    messages_response = client.get("/api/conversations/media-shared-sync-account/conv-media-bound-1/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()
    outbound_message = messages[-1]
    assert outbound_message["payload"]["provider_media_id"] == first_sync["provider_media_id"]
    assert outbound_message["payload"]["meta_media_id"] == first_sync["meta_media_id"]
    assert outbound_message["payload"]["phone_number_id"] == "pn-media-shared-sync-1"

    second_inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "media-shared-sync-account",
            "conversation_id": "conv-media-bound-2",
            "user_id": "user-media-bound-2",
            "text": "need the banner for phone 2",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-media-shared-sync-2",
        },
    )
    assert second_inbound_response.status_code == 200

    second_assignment_response = client.post(
        "/api/conversations/media-shared-sync-account/conv-media-bound-2/assignment",
        json={
            "agent_id": "agent-media-scope-bound",
            "assigned_by_agent_id": "agent-media-scope-bound",
            "reason": "manual_media_reply",
        },
    )
    assert second_assignment_response.status_code == 200

    cross_phone_send_response = client.post(
        "/api/conversations/media-shared-sync-account/conv-media-bound-2/messages/media",
        json={
            "asset_id": asset_id,
            "caption": "banner attached",
            "agent_id": "agent-media-scope-bound",
        },
    )
    assert cross_phone_send_response.status_code == 200
    second_send_payload = cross_phone_send_response.json()
    assert second_send_payload["conversation_id"] == "conv-media-bound-2"
    assert second_send_payload["conversation_id"] == second_send_payload["external_conversation_id"]
    assert second_send_payload["internal_conversation_id"] != "conv-media-bound-2"
    assert second_send_payload["phone_number_id"] == "pn-media-shared-sync-2"
    assert second_send_payload["provider_media_id"] == second_sync["provider_media_id"]

    second_messages_response = client.get("/api/conversations/media-shared-sync-account/conv-media-bound-2/messages")
    assert second_messages_response.status_code == 200
    second_messages = second_messages_response.json()
    second_outbound_message = second_messages[-1]
    assert second_outbound_message["payload"]["asset_id"] == asset_id
    assert second_outbound_message["payload"]["provider_media_id"] == second_sync["provider_media_id"]
    assert second_outbound_message["payload"]["meta_media_id"] == second_sync["meta_media_id"]
    assert second_outbound_message["payload"]["meta_media_id"] != first_sync["meta_media_id"]
    assert second_outbound_message["payload"]["phone_number_id"] == "pn-media-shared-sync-2"


def test_media_asset_telemetry_prefers_phone_snapshot_waba_when_relationship_drifts(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_media_account(client)

    agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-media-telemetry-snapshot",
            "display_name": "Media Telemetry Snapshot Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert agent_response.status_code == 200

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "snapshot-telemetry-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/snapshot-telemetry-banner.jpg",
            "tags": ["snapshot", "telemetry"],
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "media-account-1",
            "conversation_id": "conv-media-telemetry-snapshot",
            "user_id": "user-media-telemetry-snapshot",
            "text": "need snapshot banner",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-media-1",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/media-account-1/conv-media-telemetry-snapshot/assignment",
        json={
            "agent_id": "agent-media-telemetry-snapshot",
            "assigned_by_agent_id": "agent-media-telemetry-snapshot",
            "reason": "manual_media_reply",
        },
    )
    assert assignment_response.status_code == 200

    send_response = client.post(
        "/api/conversations/media-account-1/conv-media-telemetry-snapshot/messages/media",
        json={
            "asset_id": asset_id,
            "caption": "snapshot banner attached",
            "agent_id": "agent-media-telemetry-snapshot",
        },
    )
    assert send_response.status_code == 200
    send_payload = send_response.json()
    assert send_payload["conversation_id"] == "conv-media-telemetry-snapshot"
    assert send_payload["conversation_id"] == send_payload["external_conversation_id"]
    assert send_payload["internal_conversation_id"] != "conv-media-telemetry-snapshot"
    provider_message_id = send_payload["provider_message_id"]

    with db_session_factory() as session:
        waba_account = (
            session.query(WhatsAppBusinessAccount)
            .filter(
                WhatsAppBusinessAccount.account_id == "media-account-1",
                WhatsAppBusinessAccount.waba_id == "waba-media-1",
            )
            .one()
        )
        waba_account.waba_id = "waba-media-relationship-drifted-telemetry"
        session.commit()

    with db_session_factory() as session:
        message = (
            session.query(Message)
            .filter(Message.provider_message_id == provider_message_id)
            .one()
        )
        conversation = (
            session.query(Conversation)
            .filter(Conversation.external_conversation_id == "conv-media-telemetry-snapshot")
            .one()
        )
        recorder = MediaAssetTelemetryRecorder(session)
        recorder.record_provider_status_update(
            account_id="media-account-1",
            update=ProviderStatusUpdate(
                provider_name="whatsapp",
                account_id="media-account-1",
                provider_message_id=provider_message_id or "",
                external_status="delivered",
                recipient_id="user-media-telemetry-snapshot",
                occurred_at="2026-06-08T12:15:00Z",
                phone_number_id="pn-media-1",
            ),
            message=message,
            conversation=conversation,
            template_send_log=None,
        )
        session.commit()

        delivered_event = (
            session.query(MediaAssetEvent)
            .filter(
                MediaAssetEvent.asset_id == asset_id,
                MediaAssetEvent.event_type == "media_asset_status_delivered",
            )
            .order_by(MediaAssetEvent.created_at.desc(), MediaAssetEvent.id.desc())
            .first()
        )

        assert delivered_event is not None
        assert delivered_event.waba_id == "waba-media-1"
        assert delivered_event.phone_number_id == "pn-media-1"
        assert delivered_event.provider_media_id == message.payload["provider_media_id"]
        assert delivered_event.payload["conversation_id"] == "conv-media-telemetry-snapshot"
        assert (
            delivered_event.payload["external_conversation_id"] == "conv-media-telemetry-snapshot"
        )
        assert (
            delivered_event.payload["internal_conversation_id"]
            == conversation.id
        )
        assert (
            delivered_event.payload["internal_conversation_id"]
            != delivered_event.payload["external_conversation_id"]
        )
        assert delivered_event.payload["provider_message_id"] == provider_message_id
        assert delivered_event.payload["provider_media_reference_source"] == "provider_media_id"
        assert delivered_event.payload["legacy_meta_media_id_used_as_provider_reference"] is False


def test_media_asset_telemetry_extracts_scope_from_nested_message_payload(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_media_account(client)
    agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-media-telemetry-nested",
            "display_name": "Media Telemetry Nested Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert agent_response.status_code == 200

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "nested-telemetry-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/nested-telemetry-banner.jpg",
            "tags": ["nested", "telemetry"],
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "media-account-1",
            "conversation_id": "conv-media-telemetry-nested",
            "user_id": "user-media-telemetry-nested",
            "text": "need nested telemetry banner",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-media-1",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/media-account-1/conv-media-telemetry-nested/assignment",
        json={
            "agent_id": "agent-media-telemetry-nested",
            "assigned_by_agent_id": "agent-media-telemetry-nested",
            "reason": "manual_media_reply",
        },
    )
    assert assignment_response.status_code == 200

    send_response = client.post(
        "/api/conversations/media-account-1/conv-media-telemetry-nested/messages/media",
        json={
            "asset_id": asset_id,
            "caption": "nested telemetry banner attached",
            "agent_id": "agent-media-telemetry-nested",
        },
    )
    assert send_response.status_code == 200
    provider_message_id = send_response.json()["provider_message_id"]

    with db_session_factory() as session:
        message = (
            session.query(Message)
            .filter(Message.provider_message_id == provider_message_id)
            .one()
        )
        conversation = (
            session.query(Conversation)
            .filter(Conversation.external_conversation_id == "conv-media-telemetry-nested")
            .one()
        )
        message.payload = {
            "asset_id": asset_id,
            "provider_media_id": message.payload["provider_media_id"],
            "provider_payload": {
                "waba_id": "waba-media-1",
                "metadata": {
                    "phone_number_id": "pn-media-1",
                },
            },
        }
        recorder = MediaAssetTelemetryRecorder(session)
        recorder.record_provider_status_update(
            account_id="media-account-1",
            update=ProviderStatusUpdate(
                provider_name="whatsapp",
                account_id="media-account-1",
                provider_message_id=provider_message_id or "",
                external_status="delivered",
                recipient_id="user-media-telemetry-nested",
                occurred_at="2026-06-10T08:15:00Z",
                phone_number_id=None,
            ),
            message=message,
            conversation=conversation,
            template_send_log=None,
        )
        session.commit()

        delivered_event = (
            session.query(MediaAssetEvent)
            .filter(
                MediaAssetEvent.asset_id == asset_id,
                MediaAssetEvent.event_type == "media_asset_status_delivered",
            )
            .order_by(MediaAssetEvent.created_at.desc(), MediaAssetEvent.id.desc())
            .first()
        )

        assert delivered_event is not None
        assert delivered_event.waba_id == "waba-media-1"
        assert delivered_event.phone_number_id == "pn-media-1"
        assert delivered_event.payload["provider_message_id"] == provider_message_id
        assert delivered_event.payload["provider_media_reference_source"] == "provider_media_id"


def test_media_asset_upload_persists_local_file_and_records_event(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media_root = tmp_path / "media-assets"
    monkeypatch.setenv("MEDIA_STORAGE_ROOT", str(media_root))
    get_settings.cache_clear()

    register_media_account(client)

    upload_response = client.post(
        "/api/media/assets/upload",
        data={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "invoice-upload",
            "asset_type": "document",
            "source": "upload",
            "tags": "invoice",
        },
        files={"file": ("invoice.pdf", b"mock-pdf-content", "application/pdf")},
    )

    assert upload_response.status_code == 200
    asset = upload_response.json()
    assert asset["name"] == "invoice-upload"
    assert asset["asset_type"] == "document"
    assert asset["waba_id"] == "waba-media-1"
    assert asset["phone_number_id"] == "pn-media-1"
    assert asset["mime_type"] == "application/pdf"
    assert asset["file_size"] == len(b"mock-pdf-content")
    assert asset["storage_url"] is None
    assert asset["meta_media_id"] is None
    assert asset["tags"] == ["invoice"]

    storage_path = Path(asset["storage_key"])
    assert storage_path.exists()
    assert storage_path.read_bytes() == b"mock-pdf-content"
    assert media_root.resolve() in storage_path.parents
    assert storage_path.parent.name == "pn-media-1"

    detail_response = client.get(f"/api/media/assets/{asset['asset_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["usage"]["total_events"] == 1
    assert detail["provider_syncs"] == []
    assert detail["events"][0]["event_type"] == "media_asset_uploaded"
    assert detail["events"][0]["waba_id"] == "waba-media-1"
    assert detail["events"][0]["phone_number_id"] == "pn-media-1"
    assert detail["events"][0]["payload"]["storage_key"] == asset["storage_key"]
    assert detail["events"][0]["payload"]["file_name"] == "invoice.pdf"

    persisted_events = load_media_asset_events(db_session_factory, asset_id=asset["asset_id"])
    assert len(persisted_events) == 1
    assert persisted_events[0].event_type == "media_asset_uploaded"
    assert persisted_events[0].waba_id == "waba-media-1"
    assert persisted_events[0].phone_number_id == "pn-media-1"

    get_settings.cache_clear()


def test_media_asset_upload_rejects_mismatched_scope(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media_root = tmp_path / "media-assets"
    monkeypatch.setenv("MEDIA_STORAGE_ROOT", str(media_root))
    get_settings.cache_clear()

    register_media_account(client)

    upload_response = client.post(
        "/api/media/assets/upload",
        data={
            "account_id": "media-account-1",
            "waba_id": "waba-media-other",
            "phone_number_id": "pn-media-1",
        },
        files={"file": ("scope.jpg", b"image-bytes", "image/jpeg")},
    )

    assert upload_response.status_code == 409
    assert "does not match phone number" in upload_response.json()["detail"]
    assert not media_root.exists()

    get_settings.cache_clear()


def test_media_asset_telemetry_prefers_phone_and_asset_waba_snapshots() -> None:
    class FakeSession:
        def __init__(self, asset: object | None) -> None:
            self._asset = asset

        def get(self, model: object, asset_id: str) -> object | None:
            if asset_id == "asset-snapshot-1":
                return self._asset
            return None

    message = SimpleNamespace(
        phone_number=SimpleNamespace(
            waba_id="waba-message-snapshot",
            waba_account=SimpleNamespace(waba_id="waba-message-relationship"),
        ),
        payload={},
    )
    recorder = MediaAssetTelemetryRecorder(FakeSession(None))  # type: ignore[arg-type]

    assert (
        recorder._resolve_waba_id(
            asset_id="asset-snapshot-0",
            message=message,
            conversation=None,
            template_send_log=None,
        )
        == "waba-message-snapshot"
    )

    asset = SimpleNamespace(
        waba_id=None,
        phone_number=SimpleNamespace(
            waba_id="waba-asset-snapshot",
            waba_account=SimpleNamespace(waba_id="waba-asset-relationship"),
        ),
    )
    recorder_with_asset = MediaAssetTelemetryRecorder(FakeSession(asset))  # type: ignore[arg-type]

    assert (
        recorder_with_asset._resolve_waba_id(
            asset_id="asset-snapshot-1",
            message=None,
            conversation=None,
            template_send_log=None,
        )
        == "waba-asset-snapshot"
    )


def test_media_asset_template_telemetry_keeps_send_log_snapshot_scope_after_phone_drift(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_media_account(client)

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "snapshot-template-header-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/snapshot-template-header-banner.jpg",
            "tags": ["snapshot", "template-header"],
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    with db_session_factory() as session:
        account = session.get(Account, "media-account-1")
        assert account is not None

        template_send_log = TemplateSendLog(
            account_id="media-account-1",
            waba_id="waba-media-1",
            phone_number_id="pn-media-1",
            template_name="header_media_snapshot",
            template_language="en",
            template_category="MARKETING",
            template_code="meta-header-media-snapshot",
            header_media_asset_id=asset_id,
            header_media_asset_name="snapshot-template-header-banner",
            header_media_asset_type="image",
            header_media_provider_media_id="provider-template-header-media-1",
            header_media_meta_media_id="provider-template-header-media-1",
            header_media_sync_status="synced",
            wa_id="wa-template-header-snapshot",
            message_id="msg-template-header-snapshot",
            status="SENT",
        )
        session.add(template_send_log)
        session.flush()

        phone_number = (
            session.query(WhatsAppPhoneNumber)
            .filter(
                WhatsAppPhoneNumber.account_id == "media-account-1",
                WhatsAppPhoneNumber.phone_number_id == "pn-media-1",
            )
            .one()
        )
        phone_number.phone_number_id = "pn-media-1-current"
        phone_number.waba_id = "waba-media-1-current"
        assert phone_number.waba_account is not None
        phone_number.waba_account.waba_id = "waba-media-1-current"

        recorder = MediaAssetTelemetryRecorder(session)
        recorder.record_provider_status_update(
            account_id="media-account-1",
            update=ProviderStatusUpdate(
                provider_name="whatsapp",
                account_id="media-account-1",
                provider_message_id="msg-template-header-snapshot",
                external_status="delivered",
                recipient_id="user-template-header-snapshot",
                occurred_at="2026-06-09T10:15:00Z",
                phone_number_id=None,
            ),
            message=None,
            conversation=None,
            template_send_log=template_send_log,
        )
        session.commit()

        delivered_event = (
            session.query(MediaAssetEvent)
            .filter(
                MediaAssetEvent.account_id == "media-account-1",
                MediaAssetEvent.asset_id == asset_id,
                MediaAssetEvent.event_type == "media_asset_template_status_delivered",
            )
            .order_by(MediaAssetEvent.created_at.desc(), MediaAssetEvent.id.desc())
            .first()
        )

        assert delivered_event is not None
        assert delivered_event.waba_id == "waba-media-1"
        assert delivered_event.phone_number_id == "pn-media-1"
        assert delivered_event.provider_media_id == "provider-template-header-media-1"
        assert delivered_event.payload["template_name"] == "header_media_snapshot"
        assert delivered_event.payload["provider_message_id"] == "msg-template-header-snapshot"
        assert delivered_event.payload["provider_media_reference_source"] == "provider_media_id"
        assert delivered_event.payload["legacy_meta_media_id_used_as_provider_reference"] is False


def test_media_asset_template_telemetry_keeps_compat_phone_scope_and_conversation_aliases_after_phone_row_recreation(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_media_account(client)

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "compat-template-header-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/compat-template-header-banner.jpg",
            "tags": ["compat", "template-header"],
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "media-account-1",
            "conversation_id": "conv-media-template-compat",
            "user_id": "user-media-template-compat",
            "text": "need template header banner",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-media-1",
        },
    )
    assert inbound_response.status_code == 200

    with db_session_factory() as session:
        conversation = (
            session.query(Conversation)
            .filter(
                Conversation.account_id == "media-account-1",
                Conversation.external_conversation_id == "conv-media-template-compat",
            )
            .one()
        )
        legacy_phone_number = (
            session.query(WhatsAppPhoneNumber)
            .filter(
                WhatsAppPhoneNumber.account_id == "media-account-1",
                WhatsAppPhoneNumber.phone_number_id == "pn-media-1",
            )
            .one()
        )
        legacy_phone_number.phone_number_id = "pn-media-1-legacy"
        session.flush()

        session.add(
            WhatsAppPhoneNumber(
                account_id="media-account-1",
                waba_account_id=legacy_phone_number.waba_account_id,
                waba_id="waba-media-1",
                phone_number_id="pn-media-1",
                display_phone_number=legacy_phone_number.display_phone_number,
                verified_name=legacy_phone_number.verified_name,
                quality_rating=legacy_phone_number.quality_rating,
                quality_event=legacy_phone_number.quality_event,
                previous_quality_rating=legacy_phone_number.previous_quality_rating,
                messaging_limit_tier=legacy_phone_number.messaging_limit_tier,
                max_daily_conversations_per_business=(
                    legacy_phone_number.max_daily_conversations_per_business
                ),
                last_quality_event_at=legacy_phone_number.last_quality_event_at,
                last_status_payload=legacy_phone_number.last_status_payload,
                is_registered=legacy_phone_number.is_registered,
                is_active=legacy_phone_number.is_active,
            )
        )

        template_send_log = TemplateSendLog(
            account_id="media-account-1",
            conversation_id=conversation.id,
            waba_id="waba-media-1",
            phone_number_id="pn-media-1",
            template_name="header_media_compat_snapshot",
            template_language="en",
            template_category="MARKETING",
            template_code="meta-header-media-compat-snapshot",
            header_media_asset_id=asset_id,
            header_media_asset_name="compat-template-header-banner",
            header_media_asset_type="image",
            header_media_provider_media_id="provider-template-header-media-compat-1",
            header_media_meta_media_id="provider-template-header-media-compat-1",
            header_media_sync_status="synced",
            wa_id="wa-template-header-compat-snapshot",
            message_id="msg-template-header-compat-snapshot",
            status="SENT",
        )
        session.add(template_send_log)
        session.flush()

        recorder = MediaAssetTelemetryRecorder(session)
        recorder.record_provider_status_update(
            account_id="media-account-1",
            update=ProviderStatusUpdate(
                provider_name="whatsapp",
                account_id="media-account-1",
                provider_message_id="msg-template-header-compat-snapshot",
                external_status="delivered",
                recipient_id="user-media-template-compat",
                occurred_at="2026-06-09T11:15:00Z",
                phone_number_id=None,
            ),
            message=None,
            conversation=conversation,
            template_send_log=template_send_log,
        )
        session.commit()

        delivered_event = (
            session.query(MediaAssetEvent)
            .filter(
                MediaAssetEvent.account_id == "media-account-1",
                MediaAssetEvent.asset_id == asset_id,
                MediaAssetEvent.event_type == "media_asset_template_status_delivered",
            )
            .order_by(MediaAssetEvent.created_at.desc(), MediaAssetEvent.id.desc())
            .first()
        )

        assert delivered_event is not None
        assert delivered_event.waba_id == "waba-media-1"
        assert delivered_event.phone_number_id == "pn-media-1"
        assert delivered_event.provider_media_id == "provider-template-header-media-compat-1"
        assert delivered_event.payload["conversation_id"] == "conv-media-template-compat"
        assert (
            delivered_event.payload["external_conversation_id"]
            == "conv-media-template-compat"
        )
        assert delivered_event.payload["internal_conversation_id"] == conversation.id
        assert delivered_event.payload["template_send_log_id"] == template_send_log.id
        assert delivered_event.payload["provider_message_id"] == "msg-template-header-compat-snapshot"
        assert delivered_event.payload["provider_media_reference_source"] == "provider_media_id"
        assert delivered_event.payload["legacy_meta_media_id_used_as_provider_reference"] is False


def test_media_asset_template_telemetry_marks_legacy_provider_reference_fallback(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_media_account(client)

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "legacy-template-header-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/legacy-template-header-banner.jpg",
            "tags": ["compat", "legacy-template-header"],
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    with db_session_factory() as session:
        template_send_log = TemplateSendLog(
            account_id="media-account-1",
            waba_id="waba-media-1",
            phone_number_id="pn-media-1",
            template_name="header_media_legacy_fallback",
            template_language="en",
            template_category="MARKETING",
            template_code="meta-header-media-legacy-fallback",
            header_media_asset_id=asset_id,
            header_media_asset_name="legacy-template-header-banner",
            header_media_asset_type="image",
            header_media_provider_media_id=None,
            header_media_meta_media_id="legacy-template-header-media-1",
            header_media_sync_status="synced",
            wa_id="wa-template-header-legacy-fallback",
            message_id="msg-template-header-legacy-fallback",
            status="SENT",
        )
        session.add(template_send_log)
        session.flush()

        recorder = MediaAssetTelemetryRecorder(session)
        recorder.record_provider_status_update(
            account_id="media-account-1",
            update=ProviderStatusUpdate(
                provider_name="whatsapp",
                account_id="media-account-1",
                provider_message_id="msg-template-header-legacy-fallback",
                external_status="delivered",
                recipient_id="user-template-header-legacy-fallback",
                occurred_at="2026-06-10T03:15:00Z",
                phone_number_id=None,
            ),
            message=None,
            conversation=None,
            template_send_log=template_send_log,
        )
        session.commit()

        delivered_event = (
            session.query(MediaAssetEvent)
            .filter(
                MediaAssetEvent.account_id == "media-account-1",
                MediaAssetEvent.asset_id == asset_id,
                MediaAssetEvent.event_type == "media_asset_template_status_delivered",
            )
            .order_by(MediaAssetEvent.created_at.desc(), MediaAssetEvent.id.desc())
            .first()
        )

        assert delivered_event is not None
        assert delivered_event.provider_media_id == "legacy-template-header-media-1"
        assert delivered_event.meta_media_id == "legacy-template-header-media-1"
        assert delivered_event.payload["provider_media_reference_source"] == "legacy_meta_media_id"
        assert delivered_event.payload["legacy_meta_media_id_used_as_provider_reference"] is True


def test_media_asset_template_telemetry_prefers_nested_update_scope_over_stale_send_log_scope(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_media_account(client)

    create_asset_response = client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-1",
            "waba_id": "waba-media-1",
            "phone_number_id": "pn-media-1",
            "name": "nested-update-scope-template-banner",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/nested-update-scope-template-banner.jpg",
            "tags": ["nested", "update-scope", "template-header"],
        },
    )
    assert create_asset_response.status_code == 200
    asset_id = create_asset_response.json()["asset_id"]

    with db_session_factory() as session:
        template_send_log = TemplateSendLog(
            account_id="media-account-1",
            waba_id="waba-media-stale",
            phone_number_id="pn-media-stale",
            template_name="header_media_nested_update_scope",
            template_language="en",
            template_category="MARKETING",
            template_code="meta-header-media-nested-update-scope",
            header_media_asset_id=asset_id,
            header_media_asset_name="nested-update-scope-template-banner",
            header_media_asset_type="image",
            header_media_provider_media_id="provider-template-header-media-nested-scope-1",
            header_media_meta_media_id="provider-template-header-media-nested-scope-1",
            header_media_sync_status="synced",
            wa_id="wa-template-header-nested-update-scope",
            message_id="msg-template-header-nested-update-scope",
            status="SENT",
        )
        session.add(template_send_log)
        session.flush()

        recorder = MediaAssetTelemetryRecorder(session)
        recorder.record_provider_status_update(
            account_id="media-account-1",
            update=ProviderStatusUpdate(
                provider_name="whatsapp",
                account_id="media-account-1",
                provider_message_id="msg-template-header-nested-update-scope",
                external_status="delivered",
                recipient_id="user-template-header-nested-update-scope",
                occurred_at="2026-06-10T05:15:00Z",
                payload={
                    "provider_payload": {
                        "waba_id": "waba-media-1",
                        "metadata": {
                            "phone_number_id": "pn-media-1",
                        },
                    }
                },
            ),
            message=None,
            conversation=None,
            template_send_log=template_send_log,
        )
        session.commit()

        delivered_event = (
            session.query(MediaAssetEvent)
            .filter(
                MediaAssetEvent.account_id == "media-account-1",
                MediaAssetEvent.asset_id == asset_id,
                MediaAssetEvent.event_type == "media_asset_template_status_delivered",
            )
            .order_by(MediaAssetEvent.created_at.desc(), MediaAssetEvent.id.desc())
            .first()
        )

        assert delivered_event is not None
        assert delivered_event.waba_id == "waba-media-1"
        assert delivered_event.phone_number_id == "pn-media-1"
        assert delivered_event.provider_media_id == "provider-template-header-media-nested-scope-1"
        assert delivered_event.payload["provider_message_id"] == "msg-template-header-nested-update-scope"
