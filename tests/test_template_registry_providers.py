import asyncio
import json

import httpx
import pytest

from app.providers.template_registry.whatsapp_provider import WhatsAppTemplateRegistryProvider
from app.schemas.template_registry import TemplateRegistrySubmitRequest


def test_whatsapp_template_registry_submit_builds_graph_request() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            status_code=200,
            json={
                "id": "meta-template-1",
                "status": "PENDING",
                "category": "UTILITY",
            },
        )

    provider = WhatsAppTemplateRegistryProvider(
        api_base="https://graph.example.com",
        api_version="v99.0",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        result = asyncio.run(
            provider.submit_template(
                TemplateRegistrySubmitRequest(
                    account_id="account-1",
                    waba_id="waba-1",
                    access_token="token-1",
                    name="shipping_update",
                    language="en_US",
                    category="UTILITY",
                    components={
                        "header_text": "Shipping update",
                        "body_text": "Hello {{first_name}}, order {{order_id}} is ready.",
                        "footer_text": "Reply STOP to opt out.",
                        "sample_variables": {
                            "first_name": "Ana",
                            "order_id": "A-100",
                        },
                    },
                )
            )
        )
    finally:
        asyncio.run(provider._client.aclose())

    assert result.provider_name == "whatsapp"
    assert result.provider_template_id == "meta-template-1"
    assert result.remote_status == "PENDING"
    assert result.remote_template is not None
    assert captured["url"] == "https://graph.example.com/v99.0/waba-1/message_templates"
    assert captured["headers"]["authorization"] == "Bearer token-1"
    assert captured["body"] == {
        "name": "shipping_update",
        "language": "en_US",
        "category": "UTILITY",
        "components": [
            {
                "type": "HEADER",
                "format": "TEXT",
                "text": "Shipping update",
            },
            {
                "type": "BODY",
                "text": "Hello {{1}}, order {{2}} is ready.",
                "example": {"body_text": [["Ana", "A-100"]]},
            },
            {
                "type": "FOOTER",
                "text": "Reply STOP to opt out.",
            },
        ],
    }


def test_whatsapp_template_registry_submit_serializes_media_header_handle() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            status_code=200,
            json={"id": "meta-template-media-1", "status": "APPROVED"},
        )

    provider = WhatsAppTemplateRegistryProvider(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        result = asyncio.run(
            provider.submit_template(
                TemplateRegistrySubmitRequest(
                    account_id="account-1",
                    waba_id="waba-1",
                    access_token="token-1",
                    name="invoice_document",
                    language="en_US",
                    category="UTILITY",
                    components={
                        "header_media_asset_type": "document",
                        "header_media_handle": "4:meta-handle-1",
                        "body_text": "Invoice {{invoice_id}} is attached.",
                        "sample_variables": {"invoice_id": "INV-100"},
                    },
                )
            )
        )
    finally:
        asyncio.run(provider._client.aclose())

    assert result.provider_template_id == "meta-template-media-1"
    assert result.remote_status == "APPROVED"
    assert captured["body"]["components"][0] == {
        "type": "HEADER",
        "format": "DOCUMENT",
        "example": {"header_handle": ["4:meta-handle-1"]},
    }
    assert captured["body"]["components"][1] == {
        "type": "BODY",
        "text": "Invoice {{1}} is attached.",
        "example": {"body_text": [["INV-100"]]},
    }


def test_whatsapp_template_registry_submit_wraps_graph_http_errors() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=403, json={"error": {"message": "forbidden"}})

    provider = WhatsAppTemplateRegistryProvider(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        with pytest.raises(
            RuntimeError,
            match="WhatsApp template registry request failed with status 403",
        ):
            asyncio.run(
                provider.submit_template(
                    TemplateRegistrySubmitRequest(
                        account_id="account-1",
                        waba_id="waba-1",
                        access_token="token-1",
                        name="shipping_update",
                        language="en_US",
                        category="UTILITY",
                        components={"body_text": "Hello"},
                    )
                )
            )
    finally:
        asyncio.run(provider._client.aclose())


def test_whatsapp_template_registry_sync_parses_remote_templates_across_pages() -> None:
    seen_urls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        assert request.headers["authorization"] == "Bearer token-1"
        if len(seen_urls) == 1:
            assert str(request.url) == "https://graph.example.com/v99.0/waba-1/message_templates?limit=200"
            return httpx.Response(
                status_code=200,
                json={
                    "data": [
                        {
                            "id": "meta-template-1",
                            "name": "shipping_update",
                            "language": "en_US",
                            "category": "UTILITY",
                            "status": "APPROVED",
                            "components": [
                                {
                                    "type": "HEADER",
                                    "format": "TEXT",
                                    "text": "Shipping update",
                                },
                                {
                                    "type": "BODY",
                                    "text": "Hello {{first_name}}, order {{order_id}} is ready.",
                                },
                                {
                                    "type": "FOOTER",
                                    "text": "Reply STOP to opt out.",
                                },
                            ],
                        }
                    ],
                    "paging": {
                        "next": "https://graph.example.com/v99.0/waba-1/message_templates?after=page-2"
                    },
                },
            )
        assert str(request.url) == "https://graph.example.com/v99.0/waba-1/message_templates?after=page-2"
        return httpx.Response(
            status_code=200,
            json={
                "data": [
                    {
                        "id": "meta-template-2",
                        "name": "invoice_document",
                        "language": {"code": "en_US"},
                        "category": "UTILITY",
                        "status": "PAUSED",
                        "rejected_reason": "MISSING_SAMPLE",
                        "components": [
                            {
                                "type": "HEADER",
                                "format": "DOCUMENT",
                                "example": {"header_handle": ["4:meta-handle-1"]},
                            },
                            {
                                "type": "BODY",
                                "text": "Invoice {{invoice_id}} is attached.",
                            },
                        ],
                    },
                ]
            },
        )

    provider = WhatsAppTemplateRegistryProvider(
        api_base="https://graph.example.com",
        api_version="v99.0",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        result = asyncio.run(
            provider.sync_templates(
                account_id="account-1",
                waba_id="waba-1",
                access_token="token-1",
            )
        )
    finally:
        asyncio.run(provider._client.aclose())

    assert result.provider_name == "whatsapp"
    assert len(result.templates) == 2
    assert len(seen_urls) == 2
    assert result.templates[0].provider_template_id == "meta-template-1"
    assert result.templates[0].components == {
        "header_text": "Shipping update",
        "body_text": "Hello {{first_name}}, order {{order_id}} is ready.",
        "footer_text": "Reply STOP to opt out.",
    }
    assert result.templates[1].provider_template_id == "meta-template-2"
    assert result.templates[1].status == "PAUSED"
    assert result.templates[1].rejected_reason == "MISSING_SAMPLE"
    assert result.templates[1].components == {
        "header_media_type": "document",
        "header_media_handle": "4:meta-handle-1",
        "body_text": "Invoice {{invoice_id}} is attached.",
    }


def test_whatsapp_template_registry_sync_returns_partial_results_when_page_limit_is_reached() -> None:
    seen_urls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        if len(seen_urls) == 1:
            return httpx.Response(
                status_code=200,
                json={
                    "data": [
                        {
                            "id": "meta-template-limit-1",
                            "name": "limit_page_one",
                            "language": "en_US",
                            "category": "UTILITY",
                            "status": "APPROVED",
                            "components": [
                                {
                                    "type": "BODY",
                                    "text": "First page body.",
                                }
                            ],
                        }
                    ],
                    "paging": {
                        "next": "https://graph.example.com/v99.0/waba-limit-1/message_templates?after=page-2"
                    },
                },
            )
        raise AssertionError("sync_templates should stop after reaching the configured page limit")

    provider = WhatsAppTemplateRegistryProvider(
        api_base="https://graph.example.com",
        api_version="v99.0",
        max_sync_pages=1,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        result = asyncio.run(
            provider.sync_templates(
                account_id="account-limit-1",
                waba_id="waba-limit-1",
                access_token="token-limit-1",
            )
        )
    finally:
        asyncio.run(provider._client.aclose())

    assert result.provider_name == "whatsapp"
    assert len(result.templates) == 1
    assert result.templates[0].provider_template_id == "meta-template-limit-1"
    assert seen_urls == ["https://graph.example.com/v99.0/waba-limit-1/message_templates?limit=200"]
