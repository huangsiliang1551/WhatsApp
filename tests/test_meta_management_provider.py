import asyncio

import httpx

from app.providers.meta_management.base import (
    MetaEmbeddedSignupCompletionCommand,
    MetaManagementProviderError,
    MetaPhoneNumberRecord,
    MetaPhoneNumberSyncCommand,
    MetaWebhookSubscriptionCommand,
)
from app.providers.meta_management.whatsapp_provider import WhatsAppMetaManagementProvider


def test_whatsapp_meta_management_provider_subscribe_webhook_builds_graph_request() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        captured["headers"] = dict(request.headers)
        return httpx.Response(status_code=200, json={"success": True})

    provider = WhatsAppMetaManagementProvider(
        api_base="https://graph.example.com",
        api_version="v99.0",
        subscribed_fields="messages,message_template_status_update",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        result = asyncio.run(
            provider.subscribe_webhook(
                MetaWebhookSubscriptionCommand(
                    account_id="account-1",
                    waba_id="waba-1",
                    callback_url="https://example.com/webhooks/meta",
                    verify_token="verify-1",
                    app_id="app-1",
                    access_token="token-1",
                )
            )
        )
    finally:
        asyncio.run(provider._client.aclose())

    assert result.provider_name == "whatsapp"
    assert result.subscription_status == "remote_subscribed"
    assert result.remote_confirmed is True
    assert captured["method"] == "POST"
    assert captured["url"] == (
        "https://graph.example.com/v99.0/waba-1/subscribed_apps"
        "?subscribed_fields=messages%2Cmessage_template_status_update"
    )
    assert captured["path"] == "/v99.0/waba-1/subscribed_apps"
    assert captured["params"] == {
        "subscribed_fields": "messages,message_template_status_update",
    }
    assert captured["headers"]["authorization"] == "Bearer token-1"


def test_whatsapp_meta_management_provider_sync_phone_numbers_parses_remote_inventory() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        captured["headers"] = dict(request.headers)
        return httpx.Response(
            status_code=200,
            json={
                "data": [
                    {
                        "id": "pn-1",
                        "display_phone_number": "+1 555 000 1001",
                        "verified_name": "Primary",
                        "quality_rating": "GREEN",
                        "code_verification_status": "VERIFIED",
                        "status": "CONNECTED",
                    },
                    {
                        "id": "pn-2",
                        "quality_rating": "unexpected",
                        "status": "PENDING",
                    },
                ]
            },
        )

    provider = WhatsAppMetaManagementProvider(
        api_base="https://graph.example.com",
        api_version="v99.0",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        result = asyncio.run(
            provider.sync_phone_numbers(
                MetaPhoneNumberSyncCommand(
                    account_id="account-1",
                    waba_id="waba-1",
                    access_token="token-1",
                    existing_phone_numbers=[
                        MetaPhoneNumberRecord(
                            phone_number_id="pn-2",
                            display_phone_number="+1 555 000 1002",
                            verified_name="Existing Backup",
                            quality_rating="YELLOW",
                            is_registered=True,
                        )
                    ],
                )
            )
        )
    finally:
        asyncio.run(provider._client.aclose())

    assert result.provider_name == "whatsapp"
    assert result.sync_mode == "remote_fetch"
    assert result.status == "success"
    assert captured["path"] == "/v99.0/waba-1/phone_numbers"
    assert captured["params"]["fields"] == (
        "id,display_phone_number,verified_name,quality_rating,"
        "code_verification_status,name_status,status"
    )
    assert captured["headers"]["authorization"] == "Bearer token-1"
    assert [item.phone_number_id for item in result.phone_numbers] == ["pn-1", "pn-2"]
    assert result.phone_numbers[0].display_phone_number == "+1 555 000 1001"
    assert result.phone_numbers[0].is_registered is True
    assert result.phone_numbers[1].display_phone_number == "+1 555 000 1002"
    assert result.phone_numbers[1].verified_name == "Existing Backup"
    assert result.phone_numbers[1].quality_rating == "UNKNOWN"
    assert result.phone_numbers[1].is_registered is True


def test_whatsapp_meta_management_provider_confirms_embedded_signup_via_remote_phone_sync() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == (
            "https://graph.example.com/v99.0/waba-embedded-1/phone_numbers"
            "?fields=id%2Cdisplay_phone_number%2Cverified_name%2Cquality_rating%2C"
            "code_verification_status%2Cname_status%2Cstatus"
        )
        assert request.headers["authorization"] == "Bearer token-embedded-1"
        return httpx.Response(
            status_code=200,
            json={
                "data": [
                    {
                        "id": "pn-embedded-1",
                        "display_phone_number": "+1 555 000 3001",
                        "verified_name": "Embedded Primary",
                        "quality_rating": "GREEN",
                        "code_verification_status": "VERIFIED",
                    }
                ]
            },
        )

    provider = WhatsAppMetaManagementProvider(
        api_base="https://graph.example.com",
        api_version="v99.0",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        result = asyncio.run(
            provider.complete_embedded_signup_session(
                MetaEmbeddedSignupCompletionCommand(
                    account_id="account-1",
                    session_id="session-1",
                    redirect_uri="https://example.com/embedded-signup/callback",
                    requested_waba_id="waba-embedded-1",
                    meta_business_portfolio_id="biz-embedded-1",
                    phone_number_ids=["pn-placeholder"],
                    system_user_access_token="token-embedded-1",
                )
            )
        )
    finally:
        asyncio.run(provider._client.aclose())

    assert result.provider_name == "whatsapp"
    assert result.completion_status == "remote_confirmed"
    assert result.remote_confirmed is True
    assert result.resolved_waba_id == "waba-embedded-1"
    assert result.resolved_portfolio_id == "biz-embedded-1"
    assert result.phone_number_ids == ["pn-embedded-1"]
    assert result.raw_response == {
        "session_id": "session-1",
        "requested_waba_id": "waba-embedded-1",
        "phone_number_sync": {
            "data": [
                {
                    "id": "pn-embedded-1",
                    "display_phone_number": "+1 555 000 3001",
                    "verified_name": "Embedded Primary",
                    "quality_rating": "GREEN",
                    "code_verification_status": "VERIFIED",
                }
            ]
        },
    }


def test_whatsapp_meta_management_provider_exchanges_embedded_signup_code_before_phone_sync() -> None:
    captured_requests: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(
            {
                "method": request.method,
                "path": request.url.path,
                "params": dict(request.url.params),
                "headers": dict(request.headers),
            }
        )
        if request.url.path == "/v99.0/oauth/access_token":
            return httpx.Response(
                status_code=200,
                json={
                    "access_token": "token-exchanged-embedded",
                    "token_type": "bearer",
                },
            )
        if request.url.path == "/v99.0/waba-embedded-code/phone_numbers":
            assert request.headers["authorization"] == "Bearer token-exchanged-embedded"
            return httpx.Response(
                status_code=200,
                json={
                    "data": [
                        {
                            "id": "pn-embedded-code-1",
                            "display_phone_number": "+1 555 000 4001",
                            "verified_name": "Code Primary",
                            "quality_rating": "GREEN",
                            "code_verification_status": "VERIFIED",
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected Meta request path: {request.url.path}")

    provider = WhatsAppMetaManagementProvider(
        api_base="https://graph.example.com",
        api_version="v99.0",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        result = asyncio.run(
            provider.complete_embedded_signup_session(
                MetaEmbeddedSignupCompletionCommand(
                    account_id="account-code",
                    session_id="session-code",
                    redirect_uri="https://example.com/embedded-signup/code",
                    app_id="app-code",
                    app_secret="secret-code",
                    requested_waba_id="waba-embedded-code",
                    meta_business_portfolio_id="biz-embedded-code",
                    authorization_code="auth-code-embedded",
                )
            )
        )
    finally:
        asyncio.run(provider._client.aclose())

    assert [request["path"] for request in captured_requests] == [
        "/v99.0/oauth/access_token",
        "/v99.0/waba-embedded-code/phone_numbers",
    ]
    oauth_request = captured_requests[0]
    assert oauth_request["method"] == "GET"
    assert oauth_request["params"] == {
        "client_id": "app-code",
        "client_secret": "secret-code",
        "code": "auth-code-embedded",
        "redirect_uri": "https://example.com/embedded-signup/code",
    }
    assert "authorization" not in oauth_request["headers"]
    assert result.provider_name == "whatsapp"
    assert result.completion_status == "remote_confirmed"
    assert result.remote_confirmed is True
    assert result.access_token == "token-exchanged-embedded"
    assert result.resolved_waba_id == "waba-embedded-code"
    assert result.resolved_portfolio_id == "biz-embedded-code"
    assert result.phone_number_ids == ["pn-embedded-code-1"]
    assert result.raw_response == {
        "session_id": "session-code",
        "requested_waba_id": "waba-embedded-code",
        "authorization_code_exchange": {
            "access_token_present": True,
            "token_type": "bearer",
            "expires_in": None,
        },
        "phone_number_sync": {
            "data": [
                {
                    "id": "pn-embedded-code-1",
                    "display_phone_number": "+1 555 000 4001",
                    "verified_name": "Code Primary",
                    "quality_rating": "GREEN",
                    "code_verification_status": "VERIFIED",
                }
            ]
        },
    }


def test_whatsapp_meta_management_provider_keeps_callback_recorded_without_app_credentials() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected remote Meta request: {request.method} {request.url}")

    provider = WhatsAppMetaManagementProvider(
        api_base="https://graph.example.com",
        api_version="v99.0",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        result = asyncio.run(
            provider.complete_embedded_signup_session(
                MetaEmbeddedSignupCompletionCommand(
                    account_id="account-code-missing-creds",
                    session_id="session-code-missing-creds",
                    redirect_uri="https://example.com/embedded-signup/missing-creds",
                    requested_waba_id="waba-code-missing-creds",
                    meta_business_portfolio_id="biz-code-missing-creds",
                    authorization_code="auth-code-without-app-creds",
                    phone_number_ids=["pn-local-missing-creds"],
                )
            )
        )
    finally:
        asyncio.run(provider._client.aclose())

    assert result.provider_name == "whatsapp"
    assert result.completion_status == "callback_recorded"
    assert result.remote_confirmed is False
    assert result.access_token is None
    assert result.resolved_waba_id == "waba-code-missing-creds"
    assert result.resolved_portfolio_id == "biz-code-missing-creds"
    assert result.phone_number_ids == ["pn-local-missing-creds"]
    assert result.raw_response == {
        "session_id": "session-code-missing-creds",
        "requested_waba_id": "waba-code-missing-creds",
        "authorization_code_exchange": {
            "access_token_present": False,
            "skipped_reason": "missing_meta_app_credentials",
        },
    }


def test_whatsapp_meta_management_provider_exchanges_authorization_code_before_phone_sync() -> None:
    captured: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(
            {
                "method": request.method,
                "path": request.url.path,
                "params": dict(request.url.params),
                "authorization": request.headers.get("authorization"),
            }
        )
        if request.url.path == "/v99.0/oauth/access_token":
            return httpx.Response(
                status_code=200,
                json={
                    "access_token": "token-exchanged-1",
                    "token_type": "bearer",
                    "expires_in": 3600,
                },
            )
        if request.url.path == "/v99.0/waba-embedded-code-1/phone_numbers":
            return httpx.Response(
                status_code=200,
                json={
                    "data": [
                        {
                            "id": "pn-embedded-code-1",
                            "display_phone_number": "+1 555 000 3002",
                            "quality_rating": "GREEN",
                            "code_verification_status": "VERIFIED",
                        }
                    ]
                },
            )
        return httpx.Response(status_code=404, json={"error": {"message": "unexpected path"}})

    provider = WhatsAppMetaManagementProvider(
        api_base="https://graph.example.com",
        api_version="v99.0",
        app_id="app-embedded-1",
        app_secret="secret-embedded-1",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        result = asyncio.run(
            provider.complete_embedded_signup_session(
                MetaEmbeddedSignupCompletionCommand(
                    account_id="account-1",
                    session_id="session-code-1",
                    redirect_uri="https://example.com/embedded-signup/callback",
                    requested_waba_id="waba-embedded-code-1",
                    authorization_code="code-embedded-1",
                )
            )
        )
    finally:
        asyncio.run(provider._client.aclose())

    assert [item["path"] for item in captured] == [
        "/v99.0/oauth/access_token",
        "/v99.0/waba-embedded-code-1/phone_numbers",
    ]
    assert captured[0]["params"] == {
        "client_id": "app-embedded-1",
        "client_secret": "secret-embedded-1",
        "code": "code-embedded-1",
        "redirect_uri": "https://example.com/embedded-signup/callback",
    }
    assert captured[0]["authorization"] is None
    assert captured[1]["authorization"] == "Bearer token-exchanged-1"
    assert result.completion_status == "remote_confirmed"
    assert result.remote_confirmed is True
    assert result.access_token == "token-exchanged-1"
    assert result.phone_number_ids == ["pn-embedded-code-1"]
    assert result.raw_response["authorization_code_exchange"] == {
        "access_token_present": True,
        "token_type": "bearer",
        "expires_in": 3600,
    }


def test_whatsapp_meta_management_provider_records_code_when_app_credentials_are_missing() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected remote request to {request.url}")

    provider = WhatsAppMetaManagementProvider(
        api_base="https://graph.example.com",
        api_version="v99.0",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        result = asyncio.run(
            provider.complete_embedded_signup_session(
                MetaEmbeddedSignupCompletionCommand(
                    account_id="account-1",
                    session_id="session-code-missing-creds",
                    redirect_uri="https://example.com/embedded-signup/callback",
                    requested_waba_id="waba-embedded-code-missing-creds",
                    authorization_code="code-embedded-missing-creds",
                )
            )
        )
    finally:
        asyncio.run(provider._client.aclose())

    assert result.completion_status == "callback_recorded"
    assert result.remote_confirmed is False
    assert result.access_token is None
    assert result.raw_response["authorization_code_exchange"] == {
        "access_token_present": False,
        "skipped_reason": "missing_meta_app_credentials",
    }


def test_whatsapp_meta_management_provider_resolves_nested_raw_payload_for_embedded_signup() -> None:
    captured_requests: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(
            {
                "method": request.method,
                "path": request.url.path,
                "params": dict(request.url.params),
                "authorization": request.headers.get("authorization"),
            }
        )
        if request.url.path == "/v99.0/oauth/access_token":
            return httpx.Response(
                status_code=200,
                json={
                    "access_token": "token-nested-raw",
                    "token_type": "bearer",
                    "expires_in": 1800,
                },
            )
        if request.url.path == "/v99.0/waba-nested-raw-1/phone_numbers":
            return httpx.Response(
                status_code=200,
                json={
                    "data": [
                        {
                            "id": "pn-nested-raw-1",
                            "display_phone_number": "+1 555 000 5001",
                            "quality_rating": "GREEN",
                            "code_verification_status": "VERIFIED",
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected Meta request path: {request.url.path}")

    provider = WhatsAppMetaManagementProvider(
        api_base="https://graph.example.com",
        api_version="v99.0",
        app_id="app-nested-raw",
        app_secret="secret-nested-raw",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        result = asyncio.run(
            provider.complete_embedded_signup_session(
                MetaEmbeddedSignupCompletionCommand(
                    account_id="account-nested-raw",
                    session_id="session-nested-raw",
                    redirect_uri="https://example.com/embedded-signup/nested-raw",
                    raw_payload={
                        "data": {
                            "waba_id": "waba-nested-raw-1",
                            "meta_business_portfolio_id": "biz-nested-raw-1",
                            "phone_number_ids": ["pn-request-nested-raw-1"],
                            "setup_session_id": "setup-nested-raw-1",
                            "authorization": {
                                "code": "code-nested-raw-1",
                            },
                        }
                    },
                )
            )
        )
    finally:
        asyncio.run(provider._client.aclose())

    assert [item["path"] for item in captured_requests] == [
        "/v99.0/oauth/access_token",
        "/v99.0/waba-nested-raw-1/phone_numbers",
    ]
    assert captured_requests[0]["params"] == {
        "client_id": "app-nested-raw",
        "client_secret": "secret-nested-raw",
        "code": "code-nested-raw-1",
        "redirect_uri": "https://example.com/embedded-signup/nested-raw",
    }
    assert captured_requests[1]["authorization"] == "Bearer token-nested-raw"
    assert result.completion_status == "remote_confirmed"
    assert result.remote_confirmed is True
    assert result.resolved_waba_id == "waba-nested-raw-1"
    assert result.resolved_portfolio_id == "biz-nested-raw-1"
    assert result.access_token == "token-nested-raw"
    assert result.phone_number_ids == ["pn-nested-raw-1"]


def test_whatsapp_meta_management_provider_surfaces_graph_errors() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=400,
            json={"error": {"message": "Unsupported get request."}},
        )

    provider = WhatsAppMetaManagementProvider(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    try:
        try:
            asyncio.run(
                provider.sync_phone_numbers(
                    MetaPhoneNumberSyncCommand(
                        account_id="account-1",
                        waba_id="waba-missing",
                        access_token="token-1",
                    )
                )
            )
        except MetaManagementProviderError as exc:
            assert exc.remote_status_code == 400
            assert exc.raw_response == {"error": {"message": "Unsupported get request."}}
            assert "Unsupported get request." in str(exc)
        else:
            raise AssertionError("Expected MetaManagementProviderError")
    finally:
        asyncio.run(provider._client.aclose())
