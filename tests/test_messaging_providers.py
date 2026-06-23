import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.providers.messaging.mock_provider import MockMessagingProvider
from app.providers.messaging.whatsapp_provider import WhatsAppProvider
from app.schemas.messaging import MediaAssetSyncRequest, OutboundDispatchRequest
from app.schemas.mock_message import MockInboundMessage
from app.schemas.whatsapp_webhook import WhatsAppWebhookPayload


def test_mock_messaging_provider_send_outbound_returns_provider_message_id() -> None:
    provider = MockMessagingProvider()

    result = asyncio.run(
        provider.send_outbound(
            OutboundDispatchRequest(
                account_id="account-1",
                conversation_id="conv-1",
                recipient_id="user-1",
                text="hello",
            )
        )
    )

    assert result.provider_name == "mock"
    assert result.accepted is True
    assert result.provider_message_id is not None
    assert result.provider_message_id.startswith("mock-wa-")


def test_mock_messaging_provider_normalize_inbound_preserves_scope_and_provider_message_id() -> None:
    provider = MockMessagingProvider()

    result = asyncio.run(
        provider.normalize_inbound(
            MockInboundMessage(
                account_id="account-1",
                conversation_id="conv-1",
                user_id="user-1",
                text="hello",
                waba_id="waba-1",
                phone_number_id="pn-1",
                message_type="image",
                external_message_id="mock-external-1",
                metadata={"media_kind": "image", "has_meaningful_text": False},
            )
        )
    )

    assert len(result) == 1
    assert result[0].provider == "mock"
    assert result[0].waba_id == "waba-1"
    assert result[0].phone_number_id == "pn-1"
    assert result[0].message_type == "image"
    assert result[0].external_message_id == "mock-external-1"
    assert result[0].metadata == {"media_kind": "image", "has_meaningful_text": False}


def test_whatsapp_provider_send_outbound_builds_text_graph_payload() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            status_code=200,
            json={"messages": [{"id": "wamid.text.1"}]},
        )

    provider = WhatsAppProvider(
        api_base="https://graph.example.com",
        api_version="v99.0",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        result = asyncio.run(
            provider.send_outbound(
                OutboundDispatchRequest(
                    account_id="account-1",
                    conversation_id="conv-1",
                    recipient_id="14150000001",
                    text="Hello from support",
                    phone_number_id="pn-1",
                    access_token="token-1",
                )
            )
        )
    finally:
        asyncio.run(provider._client.aclose())

    assert result.provider_name == "whatsapp"
    assert result.provider_message_id == "wamid.text.1"
    assert captured["url"] == "https://graph.example.com/v99.0/pn-1/messages"
    assert captured["headers"]["authorization"] == "Bearer token-1"
    assert captured["body"] == {
        "messaging_product": "whatsapp",
        "to": "14150000001",
        "type": "text",
        "text": {"body": "Hello from support"},
    }


def test_whatsapp_provider_send_outbound_builds_template_graph_payload() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            status_code=200,
            json={"messages": [{"id": "wamid.template.1"}]},
        )

    provider = WhatsAppProvider(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        result = asyncio.run(
            provider.send_outbound(
                OutboundDispatchRequest(
                    account_id="account-1",
                    conversation_id="conv-1",
                    recipient_id="14150000001",
                    text="unused",
                    message_type="template",
                    phone_number_id="pn-1",
                    access_token="token-1",
                    template_name="shipping_update",
                    template_language="en_US",
                    template_variables={"first_name": "Ana", "order_id": "A-100"},
                )
            )
        )
    finally:
        asyncio.run(provider._client.aclose())

    assert result.provider_message_id == "wamid.template.1"
    assert captured["body"] == {
        "messaging_product": "whatsapp",
        "to": "14150000001",
        "type": "template",
        "template": {
            "name": "shipping_update",
            "language": {"code": "en_US"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": "Ana"},
                        {"type": "text", "text": "A-100"},
                    ],
                }
            ],
        },
    }


def test_whatsapp_provider_send_outbound_wraps_graph_http_errors() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=400, json={"error": {"message": "bad request"}})

    provider = WhatsAppProvider(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        with pytest.raises(RuntimeError, match="WhatsApp provider request failed with status 400"):
            asyncio.run(
                provider.send_outbound(
                    OutboundDispatchRequest(
                        account_id="account-1",
                        conversation_id="conv-1",
                        recipient_id="14150000001",
                        text="Hello from support",
                        phone_number_id="pn-1",
                        access_token="token-1",
                    )
                )
            )
    finally:
        asyncio.run(provider._client.aclose())


def test_whatsapp_provider_send_outbound_builds_template_graph_payload_with_header_media() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            status_code=200,
            json={"messages": [{"id": "wamid.template.media.1"}]},
        )

    provider = WhatsAppProvider(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        result = asyncio.run(
            provider.send_outbound(
                OutboundDispatchRequest(
                    account_id="account-1",
                    conversation_id="conv-1",
                    recipient_id="14150000001",
                    text="unused",
                    message_type="template",
                    phone_number_id="pn-1",
                    access_token="token-1",
                    template_name="shipping_update_media",
                    template_language="en_US",
                    template_variables={"order_id": "A-100"},
                    template_header_media_type="document",
                    media_asset_id="meta-doc-1",
                    file_name="shipping.pdf",
                )
            )
        )
    finally:
        asyncio.run(provider._client.aclose())

    assert result.provider_message_id == "wamid.template.media.1"
    assert captured["body"] == {
        "messaging_product": "whatsapp",
        "to": "14150000001",
        "type": "template",
        "template": {
            "name": "shipping_update_media",
            "language": {"code": "en_US"},
            "components": [
                {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "document",
                            "document": {"id": "meta-doc-1", "filename": "shipping.pdf"},
                        }
                    ],
                },
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": "A-100"}],
                },
            ],
        },
    }


def test_whatsapp_provider_send_outbound_builds_image_graph_payload() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            status_code=200,
            json={"messages": [{"id": "wamid.image.1"}]},
        )

    provider = WhatsAppProvider(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        result = asyncio.run(
            provider.send_outbound(
                OutboundDispatchRequest(
                    account_id="account-1",
                    conversation_id="conv-1",
                    recipient_id="14150000001",
                    message_type="image",
                    phone_number_id="pn-1",
                    access_token="token-1",
                    media_url="https://cdn.example.com/asset.png",
                    media_caption="Order receipt",
                )
            )
        )
    finally:
        asyncio.run(provider._client.aclose())

    assert result.provider_message_id == "wamid.image.1"
    assert captured["body"] == {
        "messaging_product": "whatsapp",
        "to": "14150000001",
        "type": "image",
        "image": {
            "link": "https://cdn.example.com/asset.png",
            "caption": "Order receipt",
        },
    }


def test_mock_messaging_provider_sync_media_asset_returns_provider_media_id() -> None:
    provider = MockMessagingProvider()

    result = asyncio.run(
        provider.sync_media_asset(
            MediaAssetSyncRequest(
                account_id="account-1",
                asset_id="asset-1",
                asset_name="shipping-banner",
                asset_type="image",
                mime_type="image/jpeg",
                phone_number_id="pn-1",
                storage_url="https://cdn.example.com/shipping-banner.jpg",
            )
        )
    )

    assert result.provider_name == "mock"
    assert result.sync_status == "synced"
    assert result.provider_media_id is not None
    assert result.provider_media_id.startswith("mock-media-")


def test_whatsapp_provider_sync_media_asset_reuses_existing_provider_media_id() -> None:
    provider = WhatsAppProvider()

    result = asyncio.run(
        provider.sync_media_asset(
            MediaAssetSyncRequest(
                account_id="account-1",
                asset_id="asset-1",
                asset_name="shipping-banner",
                asset_type="image",
                mime_type="image/jpeg",
                phone_number_id="pn-1",
                access_token="token-1",
                existing_provider_media_id="meta-existing-1",
            )
        )
    )

    assert result.provider_name == "whatsapp"
    assert result.sync_status == "reused"
    assert result.provider_media_id == "meta-existing-1"


def test_whatsapp_provider_sync_media_asset_uploads_storage_url_to_graph_endpoint() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://cdn.example.com/shipping-banner.jpg":
            return httpx.Response(
                status_code=200,
                content=b"binary-image-data",
                headers={"Content-Type": "image/jpeg"},
            )
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["content_type"] = request.headers.get("content-type")
        captured["body"] = request.content
        return httpx.Response(
            status_code=200,
            json={"id": "meta-uploaded-media-1"},
        )

    provider = WhatsAppProvider(
        api_base="https://graph.example.com",
        api_version="v99.0",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        result = asyncio.run(
            provider.sync_media_asset(
                MediaAssetSyncRequest(
                    account_id="account-1",
                    asset_id="asset-1",
                    asset_name="shipping-banner",
                    asset_type="image",
                    mime_type="image/jpeg",
                    phone_number_id="pn-1",
                    access_token="token-1",
                    storage_url="https://cdn.example.com/shipping-banner.jpg",
                )
            )
        )
    finally:
        asyncio.run(provider._client.aclose())

    assert result.provider_name == "whatsapp"
    assert result.sync_status == "synced"
    assert result.provider_media_id == "meta-uploaded-media-1"
    assert captured["url"] == "https://graph.example.com/v99.0/pn-1/media"
    assert captured["headers"]["authorization"] == "Bearer token-1"
    assert "multipart/form-data" in str(captured["content_type"])
    body = captured["body"]
    assert isinstance(body, bytes)
    assert b'name="messaging_product"' in body
    assert b"whatsapp" in body
    assert b'name="type"' in body
    assert b"image/jpeg" in body
    assert b'name="file"; filename="shipping-banner.jpg"' in body
    assert b"binary-image-data" in body


def test_whatsapp_provider_sync_media_asset_uploads_storage_key_file(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}
    media_path = tmp_path / "invoice.pdf"
    media_path.write_bytes(b"pdf-bytes")

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["content_type"] = request.headers.get("content-type")
        captured["body"] = request.content
        return httpx.Response(
            status_code=200,
            json={"id": "meta-uploaded-media-2"},
        )

    provider = WhatsAppProvider(
        api_base="https://graph.example.com",
        api_version="v99.0",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        result = asyncio.run(
            provider.sync_media_asset(
                MediaAssetSyncRequest(
                    account_id="account-1",
                    asset_id="asset-2",
                    asset_name="invoice",
                    asset_type="document",
                    mime_type="application/pdf",
                    phone_number_id="pn-1",
                    access_token="token-1",
                    storage_key=str(media_path),
                )
            )
        )
    finally:
        asyncio.run(provider._client.aclose())

    assert result.provider_name == "whatsapp"
    assert result.sync_status == "synced"
    assert result.provider_media_id == "meta-uploaded-media-2"
    assert captured["url"] == "https://graph.example.com/v99.0/pn-1/media"
    assert "multipart/form-data" in str(captured["content_type"])
    body = captured["body"]
    assert isinstance(body, bytes)
    assert b'name="type"' in body
    assert b"application/pdf" in body
    assert b'name="file"; filename="invoice.pdf"' in body
    assert b"pdf-bytes" in body


def test_whatsapp_provider_normalizes_status_updates() -> None:
    provider = WhatsAppProvider()

    result = asyncio.run(
        provider.normalize_status_updates(
            WhatsAppWebhookPayload.model_validate(
                {
                    "object": "whatsapp_business_account",
                    "entry": [
                        {
                            "id": "waba-1",
                        "changes": [
                            {
                                "field": "messages",
                                "value": {
                                    "metadata": {
                                        "phone_number_id": "pn-1",
                                    },
                                    "statuses": [
                                        {
                                            "id": "wamid.status.1",
                                            "status": "delivered",
                                            "timestamp": "1712345678",
                                            "recipient_id": "14150000001",
                                            "conversation": {
                                                "id": "conversation-meta-1",
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
            )
        )
    )

    assert len(result) == 1
    assert result[0].provider_name == "whatsapp"
    assert result[0].waba_id == "waba-1"
    assert result[0].phone_number_id == "pn-1"
    assert result[0].provider_message_id == "wamid.status.1"
    assert result[0].external_status == "delivered"
    assert result[0].payload["conversation_id"] == "conversation-meta-1"
    assert result[0].payload["conversation_origin_type"] == "business_initiated"
    assert result[0].payload["conversation_category"] == "utility"
    assert result[0].payload["pricing_model"] == "CBP"
    assert result[0].payload["billable"] is True


def test_whatsapp_provider_normalizes_interactive_reply_messages() -> None:
    provider = WhatsAppProvider()

    result = asyncio.run(
        provider.normalize_inbound(
            WhatsAppWebhookPayload.model_validate(
                {
                    "object": "whatsapp_business_account",
                    "entry": [
                        {
                            "id": "waba-1",
                            "changes": [
                                {
                                    "field": "messages",
                                    "value": {
                                        "metadata": {
                                            "display_phone_number": "+1 555 000 0001",
                                            "phone_number_id": "pn-1",
                                        },
                                        "messages": [
                                            {
                                                "from": "14150000001",
                                                "id": "wamid.interactive.button.1",
                                                "timestamp": "1712345678",
                                                "type": "interactive",
                                                "interactive": {
                                                    "type": "button_reply",
                                                    "button_reply": {
                                                        "id": "track-order",
                                                        "title": "Track order",
                                                    },
                                                },
                                            },
                                            {
                                                "from": "14150000002",
                                                "id": "wamid.interactive.list.1",
                                                "timestamp": "1712345688",
                                                "type": "interactive",
                                                "interactive": {
                                                    "type": "list_reply",
                                                    "list_reply": {
                                                        "id": "faq-shipping",
                                                        "title": "Shipping FAQ",
                                                    },
                                                },
                                            },
                                        ],
                                    },
                                }
                            ],
                        }
                    ],
                }
            )
        )
    )

    assert len(result) == 2
    assert result[0].message_type == "interactive"
    assert result[0].text == "Track order"
    assert result[0].metadata["interactive_type"] == "button_reply"
    assert result[0].metadata["interactive_reply_id"] == "track-order"
    assert result[0].metadata["interactive_reply_title"] == "Track order"
    assert result[0].metadata["has_meaningful_text"] is True
    assert result[1].message_type == "interactive"
    assert result[1].text == "Shipping FAQ"
    assert result[1].metadata["interactive_type"] == "list_reply"
    assert result[1].metadata["interactive_reply_id"] == "faq-shipping"
    assert result[1].metadata["interactive_reply_title"] == "Shipping FAQ"
    assert result[1].metadata["has_meaningful_text"] is True


def test_whatsapp_provider_normalizes_flow_reply_messages() -> None:
    provider = WhatsAppProvider()

    result = asyncio.run(
        provider.normalize_inbound(
            WhatsAppWebhookPayload.model_validate(
                {
                    "object": "whatsapp_business_account",
                    "entry": [
                        {
                            "id": "waba-1",
                            "changes": [
                                {
                                    "field": "messages",
                                    "value": {
                                        "metadata": {
                                            "display_phone_number": "+1 555 000 0001",
                                            "phone_number_id": "pn-1",
                                        },
                                        "messages": [
                                            {
                                                "from": "14150000003",
                                                "id": "wamid.interactive.flow.1",
                                                "timestamp": "1712345698",
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
            )
        )
    )

    assert len(result) == 1
    assert result[0].message_type == "interactive"
    assert result[0].text == "Submitted order support request"
    assert result[0].metadata["interactive_type"] == "nfm_reply"
    assert result[0].metadata["interactive_flow_name"] == "order_support_flow"
    assert result[0].metadata["interactive_flow_body"] == "Submitted order support request"
    assert result[0].metadata["interactive_flow_response"]["order_id"] == "A-100"
    assert result[0].metadata["has_meaningful_text"] is True


def test_whatsapp_provider_preserves_unknown_interactive_subtypes_as_placeholder_messages() -> None:
    provider = WhatsAppProvider()

    result = asyncio.run(
        provider.normalize_inbound(
            WhatsAppWebhookPayload.model_validate(
                {
                    "object": "whatsapp_business_account",
                    "entry": [
                        {
                            "id": "waba-1",
                            "changes": [
                                {
                                    "field": "messages",
                                    "value": {
                                        "metadata": {
                                            "display_phone_number": "+1 555 000 0001",
                                            "phone_number_id": "pn-1",
                                        },
                                        "messages": [
                                            {
                                                "from": "14150000004",
                                                "id": "wamid.interactive.unknown.1",
                                                "timestamp": "1712345700",
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
            )
        )
    )

    assert len(result) == 1
    assert result[0].message_type == "interactive"
    assert result[0].text == "[interactive message]"
    assert result[0].metadata["interactive_type"] == "galaxy_reply"
    assert result[0].metadata["has_meaningful_text"] is False


def test_whatsapp_provider_normalize_inbound_preserves_contact_profile_metadata() -> None:
    provider = WhatsAppProvider()

    result = asyncio.run(
        provider.normalize_inbound(
            WhatsAppWebhookPayload.model_validate(
                {
                    "object": "whatsapp_business_account",
                    "entry": [
                        {
                            "id": "waba-1",
                            "changes": [
                                {
                                    "field": "messages",
                                    "value": {
                                        "metadata": {
                                            "display_phone_number": "+1 555 000 0001",
                                            "phone_number_id": "pn-1",
                                        },
                                        "contacts": [
                                            {
                                                "wa_id": "14150000001",
                                                "profile": {"name": "Root Webhook Customer"},
                                            }
                                        ],
                                        "messages": [
                                            {
                                                "from": "14150000001",
                                                "id": "wamid.contact.profile.1",
                                                "timestamp": "1712345678",
                                                "type": "text",
                                                "text": {"body": "hello from contact profile"},
                                            }
                                        ],
                                    },
                                }
                            ],
                        }
                    ],
                }
            )
        )
    )

    assert len(result) == 1
    assert result[0].text == "hello from contact profile"
    assert result[0].metadata["contact_wa_id"] == "14150000001"
    assert result[0].metadata["contact_profile_name"] == "Root Webhook Customer"


def test_whatsapp_provider_normalizes_media_messages() -> None:
    provider = WhatsAppProvider()

    result = asyncio.run(
        provider.normalize_inbound(
            WhatsAppWebhookPayload.model_validate(
                {
                    "object": "whatsapp_business_account",
                    "entry": [
                        {
                            "id": "waba-1",
                            "changes": [
                                {
                                    "field": "messages",
                                    "value": {
                                        "metadata": {
                                            "display_phone_number": "+1 555 000 0001",
                                            "phone_number_id": "pn-1",
                                        },
                                        "messages": [
                                            {
                                                "from": "14150000001",
                                                "id": "wamid.image.1",
                                                "timestamp": "1712345678",
                                                "type": "image",
                                                "image": {
                                                    "id": "meta-image-1",
                                                    "mime_type": "image/jpeg",
                                                    "sha256": "sha-image-1",
                                                },
                                            },
                                            {
                                                "from": "14150000001",
                                                "id": "wamid.document.1",
                                                "timestamp": "1712345688",
                                                "type": "document",
                                                "document": {
                                                    "id": "meta-document-1",
                                                    "mime_type": "application/pdf",
                                                    "sha256": "sha-document-1",
                                                    "filename": "invoice.pdf",
                                                },
                                            },
                                            {
                                                "from": "14150000001",
                                                "id": "wamid.video.1",
                                                "timestamp": "1712345698",
                                                "type": "video",
                                                "video": {
                                                    "id": "meta-video-1",
                                                    "mime_type": "video/mp4",
                                                    "sha256": "sha-video-1",
                                                    "caption": "shipment arrived",
                                                },
                                            },
                                        ],
                                    },
                                }
                            ],
                        }
                    ],
                }
            )
        )
    )

    assert len(result) == 3
    assert result[0].message_type == "image"
    assert result[0].text == "[image attachment]"
    assert result[0].metadata["media_id"] == "meta-image-1"
    assert result[0].metadata["has_meaningful_text"] is False
    assert result[1].message_type == "document"
    assert result[1].text == "invoice.pdf"
    assert result[1].metadata["file_name"] == "invoice.pdf"
    assert result[1].metadata["has_meaningful_text"] is False
    assert result[2].message_type == "video"
    assert result[2].text == "shipment arrived"
    assert result[2].metadata["caption"] == "shipment arrived"
    assert result[2].metadata["has_meaningful_text"] is True


def test_whatsapp_provider_normalizes_additional_official_inbound_message_types() -> None:
    provider = WhatsAppProvider()

    result = asyncio.run(
        provider.normalize_inbound(
            WhatsAppWebhookPayload.model_validate(
                {
                    "object": "whatsapp_business_account",
                    "entry": [
                        {
                            "id": "waba-1",
                            "changes": [
                                {
                                    "field": "messages",
                                    "value": {
                                        "metadata": {
                                            "display_phone_number": "+1 555 000 0001",
                                            "phone_number_id": "pn-1",
                                        },
                                        "messages": [
                                            {
                                                "from": "14150000000",
                                                "id": "wamid.button.1",
                                                "timestamp": "1712345668",
                                                "type": "button",
                                                "button": {
                                                    "text": "Track order",
                                                    "payload": "track-order",
                                                },
                                            },
                                            {
                                                "from": "14150000001",
                                                "id": "wamid.location.1",
                                                "timestamp": "1712345678",
                                                "type": "location",
                                                "location": {
                                                    "latitude": 37.4848,
                                                    "longitude": -122.1484,
                                                    "name": "Meta HQ",
                                                    "address": "1 Hacker Way",
                                                },
                                            },
                                            {
                                                "from": "14150000002",
                                                "id": "wamid.sticker.1",
                                                "timestamp": "1712345688",
                                                "type": "sticker",
                                                "sticker": {
                                                    "id": "meta-sticker-1",
                                                    "mime_type": "image/webp",
                                                },
                                            },
                                            {
                                                "from": "14150000003",
                                                "id": "wamid.reaction.1",
                                                "timestamp": "1712345698",
                                                "type": "reaction",
                                                "reaction": {
                                                    "message_id": "wamid.original.1",
                                                    "emoji": "👍",
                                                },
                                            },
                                        ],
                                    },
                                }
                            ],
                        }
                    ],
                }
            )
        )
    )

    assert len(result) == 4
    assert result[0].message_type == "button"
    assert result[0].text == "Track order"
    assert result[0].metadata["button_payload"] == "track-order"
    assert result[0].metadata["has_meaningful_text"] is True
    assert result[1].message_type == "location"
    assert result[1].text == "Meta HQ"
    assert result[1].metadata["location_address"] == "1 Hacker Way"
    assert result[1].metadata["latitude"] == 37.4848
    assert result[1].metadata["has_meaningful_text"] is False
    assert result[2].message_type == "sticker"
    assert result[2].text == "[sticker message]"
    assert result[2].metadata["media_kind"] == "sticker"
    assert result[2].metadata["has_meaningful_text"] is False
    assert result[3].message_type == "reaction"
    assert result[3].text == "👍"
    assert result[3].metadata["reaction_to_message_id"] == "wamid.original.1"
    assert result[3].metadata["has_meaningful_text"] is False


def test_whatsapp_provider_normalizes_order_messages() -> None:
    provider = WhatsAppProvider()

    result = asyncio.run(
        provider.normalize_inbound(
            WhatsAppWebhookPayload.model_validate(
                {
                    "object": "whatsapp_business_account",
                    "entry": [
                        {
                            "id": "waba-1",
                            "changes": [
                                {
                                    "field": "messages",
                                    "value": {
                                        "metadata": {
                                            "display_phone_number": "+1 555 000 0001",
                                            "phone_number_id": "pn-1",
                                        },
                                        "messages": [
                                            {
                                                "from": "14150000004",
                                                "id": "wamid.order.1",
                                                "timestamp": "1712345704",
                                                "type": "order",
                                                "order": {
                                                    "catalog_id": "catalog-1",
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
            )
        )
    )

    assert len(result) == 1
    assert result[0].message_type == "order"
    assert result[0].text == "[order message]"
    assert result[0].metadata["order_catalog_id"] == "catalog-1"
    assert result[0].metadata["order_product_count"] == 2
    assert result[0].metadata["order_product_items"][0]["product_retailer_id"] == "sku-1001"
    assert result[0].metadata["order_product_items"][0]["quantity"] == 2
    assert result[0].metadata["has_meaningful_text"] is False


def test_whatsapp_provider_preserves_referral_context_on_text_messages() -> None:
    provider = WhatsAppProvider()

    result = asyncio.run(
        provider.normalize_inbound(
            WhatsAppWebhookPayload.model_validate(
                {
                    "object": "whatsapp_business_account",
                    "entry": [
                        {
                            "id": "waba-1",
                            "changes": [
                                {
                                    "field": "messages",
                                    "value": {
                                        "metadata": {
                                            "display_phone_number": "+1 555 000 0001",
                                            "phone_number_id": "pn-1",
                                        },
                                        "messages": [
                                            {
                                                "from": "14150000005",
                                                "id": "wamid.referral.text.1",
                                                "timestamp": "1712345705",
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
            )
        )
    )

    assert len(result) == 1
    assert result[0].message_type == "text"
    assert result[0].text == "I want this offer"
    assert result[0].metadata["referral_source_id"] == "fb-ad-123"
    assert result[0].metadata["referral_source_type"] == "ad"
    assert result[0].metadata["referral_headline"] == "Summer Sale"
    assert result[0].metadata["referral_ctwa_clid"] == "clid-123"
    assert result[0].metadata["referral_payload"]["image_url"] == "https://cdn.example.com/ad.jpg"
    assert result[0].metadata["has_meaningful_text"] is True


def test_whatsapp_provider_preserves_context_reply_and_referred_product_metadata() -> None:
    provider = WhatsAppProvider()

    result = asyncio.run(
        provider.normalize_inbound(
            WhatsAppWebhookPayload.model_validate(
                {
                    "object": "whatsapp_business_account",
                    "entry": [
                        {
                            "id": "waba-1",
                            "changes": [
                                {
                                    "field": "messages",
                                    "value": {
                                        "metadata": {
                                            "display_phone_number": "+1 555 000 0001",
                                            "phone_number_id": "pn-1",
                                        },
                                        "messages": [
                                            {
                                                "from": "14150000006",
                                                "id": "wamid.context.text.1",
                                                "timestamp": "1712345706",
                                                "type": "text",
                                                "text": {"body": "I want this exact product"},
                                                "context": {
                                                    "from": "14150000999",
                                                    "id": "wamid.original.999",
                                                    "forwarded": True,
                                                    "frequently_forwarded": False,
                                                    "referred_product": {
                                                        "catalog_id": "catalog-ctx-1",
                                                        "product_retailer_id": "sku-ctx-1001",
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
            )
        )
    )

    assert len(result) == 1
    assert result[0].message_type == "text"
    assert result[0].text == "I want this exact product"
    assert result[0].metadata["context_reply_to_message_id"] == "wamid.original.999"
    assert result[0].metadata["context_reply_to_user_id"] == "14150000999"
    assert result[0].metadata["context_forwarded"] is True
    assert result[0].metadata["context_frequently_forwarded"] is False
    assert result[0].metadata["context_referred_product_catalog_id"] == "catalog-ctx-1"
    assert (
        result[0].metadata["context_referred_product_retailer_id"]
        == "sku-ctx-1001"
    )
    assert result[0].metadata["context_payload"]["referred_product"]["catalog_id"] == "catalog-ctx-1"
    assert result[0].metadata["has_meaningful_text"] is True


def test_whatsapp_provider_preserves_still_unsupported_inbound_message_types() -> None:
    provider = WhatsAppProvider()

    result = asyncio.run(
        provider.normalize_inbound(
            WhatsAppWebhookPayload.model_validate(
                {
                    "object": "whatsapp_business_account",
                    "entry": [
                        {
                            "id": "waba-1",
                            "changes": [
                                {
                                    "field": "messages",
                                    "value": {
                                        "metadata": {
                                            "display_phone_number": "+1 555 000 0001",
                                            "phone_number_id": "pn-1",
                                        },
                                        "messages": [
                                            {
                                                "from": "14150000004",
                                                "id": "wamid.referral.1",
                                                "timestamp": "1712345708",
                                                "type": "referral",
                                            }
                                        ],
                                    },
                                }
                            ],
                        }
                    ],
                }
            )
        )
    )

    assert len(result) == 1
    assert result[0].message_type == "referral"
    assert result[0].text == "[referral message]"
    assert result[0].metadata["unsupported_message_type"] == "referral"
    assert result[0].metadata["has_meaningful_text"] is False


def test_whatsapp_provider_normalizes_contact_card_messages() -> None:
    provider = WhatsAppProvider()

    result = asyncio.run(
        provider.normalize_inbound(
            WhatsAppWebhookPayload.model_validate(
                {
                    "object": "whatsapp_business_account",
                    "entry": [
                        {
                            "id": "waba-1",
                            "changes": [
                                {
                                    "field": "messages",
                                    "value": {
                                        "metadata": {
                                            "display_phone_number": "+1 555 000 0001",
                                            "phone_number_id": "pn-1",
                                        },
                                        "messages": [
                                            {
                                                "from": "14150000004",
                                                "id": "wamid.contacts.card.1",
                                                "timestamp": "1712345718",
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
            )
        )
    )

    assert len(result) == 1
    assert result[0].message_type == "contacts"
    assert result[0].text == "Ana Support"
    assert result[0].metadata["shared_contact_count"] == 1
    shared_contact = result[0].metadata["shared_contacts"][0]
    assert shared_contact["formatted_name"] == "Ana Support"
    assert shared_contact["phones"][0]["wa_id"] == "14150000100"
    assert shared_contact["emails"][0]["email"] == "ana@example.com"
    assert shared_contact["organization"]["company"] == "Example Inc"
    assert result[0].metadata["has_meaningful_text"] is False


def test_whatsapp_provider_normalizes_system_messages() -> None:
    provider = WhatsAppProvider()

    result = asyncio.run(
        provider.normalize_inbound(
            WhatsAppWebhookPayload.model_validate(
                {
                    "object": "whatsapp_business_account",
                    "entry": [
                        {
                            "id": "waba-1",
                            "changes": [
                                {
                                    "field": "messages",
                                    "value": {
                                        "metadata": {
                                            "display_phone_number": "+1 555 000 0001",
                                            "phone_number_id": "pn-1",
                                        },
                                        "messages": [
                                            {
                                                "from": "14150000005",
                                                "id": "wamid.system.1",
                                                "timestamp": "1712345728",
                                                "type": "system",
                                                "system": {
                                                    "body": "Customer changed from +1 555 000 0005 to +1 555 000 0099",
                                                    "identity": "14150000005",
                                                    "new_wa_id": "14150000099",
                                                    "wa_id": "14150000005",
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
            )
        )
    )

    assert len(result) == 1
    assert result[0].message_type == "system"
    assert result[0].text == "Customer changed from +1 555 000 0005 to +1 555 000 0099"
    assert result[0].metadata["system_type"] == "customer_changed_number"
    assert result[0].metadata["system_identity"] == "14150000005"
    assert result[0].metadata["system_new_wa_id"] == "14150000099"
    assert result[0].metadata["system_wa_id"] == "14150000005"
    assert result[0].metadata["has_meaningful_text"] is False
