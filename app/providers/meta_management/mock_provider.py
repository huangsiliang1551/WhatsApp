from app.providers.meta_management.base import (
    MetaEmbeddedSignupCompletionCommand,
    MetaEmbeddedSignupCompletionResult,
    MetaManagementProvider,
    MetaPhoneNumberSyncCommand,
    MetaPhoneNumberSyncResult,
    MetaWebhookSubscriptionCommand,
    MetaWebhookSubscriptionResult,
)


class MockMetaManagementProvider(MetaManagementProvider):
    provider_name = "mock"

    async def health_check(
        self,
        waba_id: str,
        access_token: str,
    ) -> dict[str, object]:
        return {"ok": True, "provider": "mock", "waba_id": waba_id}

    async def subscribe_webhook(
        self,
        payload: MetaWebhookSubscriptionCommand,
    ) -> MetaWebhookSubscriptionResult:
        return MetaWebhookSubscriptionResult(
            provider_name=self.provider_name,
            subscription_status="mock_subscribed",
            remote_confirmed=True,
            raw_response={
                "account_id": payload.account_id,
                "waba_id": payload.waba_id,
                "callback_url": payload.callback_url,
                "mode": "mock",
            },
            message="Mock provider accepted webhook subscription locally.",
        )

    async def sync_phone_numbers(
        self,
        payload: MetaPhoneNumberSyncCommand,
    ) -> MetaPhoneNumberSyncResult:
        return MetaPhoneNumberSyncResult(
            provider_name=self.provider_name,
            sync_mode="mock_echo",
            status="success",
            phone_numbers=list(payload.existing_phone_numbers),
            raw_response={
                "account_id": payload.account_id,
                "waba_id": payload.waba_id,
                "count": len(payload.existing_phone_numbers),
            },
            message="Mock provider echoed current phone-number inventory.",
        )

    async def complete_embedded_signup_session(
        self,
        payload: MetaEmbeddedSignupCompletionCommand,
    ) -> MetaEmbeddedSignupCompletionResult:
        access_token = payload.system_user_access_token
        if access_token is None and payload.authorization_code:
            access_token = f"mock-embedded-signup-token-{payload.session_id}"
        return MetaEmbeddedSignupCompletionResult(
            provider_name=self.provider_name,
            completion_status="callback_recorded",
            remote_confirmed=False,
            resolved_waba_id=payload.requested_waba_id,
            resolved_portfolio_id=payload.meta_business_portfolio_id,
            access_token=access_token,
            phone_number_ids=list(payload.phone_number_ids),
            raw_response={
                "account_id": payload.account_id,
                "session_id": payload.session_id,
                "mode": "mock",
                "authorization_code_exchange": {
                    "access_token_present": bool(access_token),
                },
            },
            message="Mock provider recorded the embedded-signup completion locally.",
        )

    async def send_test_message(
        self,
        waba_id: str,
        access_token: str,
        phone_id: str,
        to: str,
        text: str,
    ) -> dict[str, object]:
        return {
            "ok": True,
            "provider": "mock",
            "waba_id": waba_id,
            "to": to,
            "message_id": f"mock-msg-{waba_id}-{len(text)}",
            "text": text[:50],
        }

    async def query_phone_detail(
        self,
        waba_id: str,
        access_token: str,
        phone_id: str,
    ) -> dict[str, object]:
        return {
            "ok": True,
            "provider": "mock",
            "phone_id": phone_id,
            "raw_response": {
                "id": phone_id,
                "display_phone_number": "+8613800138000",
                "verified_name": "Mock Phone",
                "quality_rating": "GREEN",
                "code_verification_status": "VERIFIED",
                "status": "CONNECTED",
            },
        }

    async def query_business_profile(
        self,
        waba_id: str,
        access_token: str,
        phone_id: str,
    ) -> dict[str, object]:
        return {
            "ok": True,
            "provider": "mock",
            "phone_id": phone_id,
            "raw_response": {
                "about": "Mock Business Profile",
                "description": "This is a mock business profile for testing.",
                "email": "mock@example.com",
                "websites": ["https://example.com"],
                "vertical": "TECH",
            },
        }
