import asyncio

from app.core.settings import Settings
from app.db.models import MessageEvent, WhatsAppBusinessAccount, WhatsAppPhoneNumber
from app.providers.ai.base import AIConversationTurn, AIReplyRequest
from app.providers.ai.deepseek_provider import DeepSeekProvider
from app.providers.ai.openai_provider import OpenAIProvider
from app.providers.factory import get_ai_provider
from app.services.ai_queue_processor import process_ai_generation_job
from app.services.runtime_state import RuntimeStateStore


def build_ai_request() -> AIReplyRequest:
    return AIReplyRequest(
        account_id="account-ai-1",
        conversation_id="conv-ai-1",
        customer_language="es",
        user_message="Necesito saber el estado de mi pedido.",
        conversation_history=[
            AIConversationTurn(role="user", text="Hola"),
            AIConversationTurn(role="assistant", text="Hola, en que puedo ayudarte?"),
        ],
    )


def test_ai_provider_uses_mock_in_test_mode() -> None:
    settings = Settings(
        _env_file=None,
        TEST_MODE=True,
        AI_PROVIDER="openai",
        OPENAI_API_KEY="",
        DEEPSEEK_API_KEY="",
    )

    provider = get_ai_provider(settings)

    assert provider.provider_name == "mock"


def test_ai_provider_uses_openai_when_key_exists() -> None:
    settings = Settings(
        _env_file=None,
        TEST_MODE=False,
        AI_PROVIDER="openai",
        OPENAI_API_KEY="openai-test-key",
        DEEPSEEK_API_KEY="",
    )

    provider = get_ai_provider(settings)

    assert provider.provider_name == "openai"


def test_ai_provider_falls_back_to_mock_without_openai_key() -> None:
    settings = Settings(
        _env_file=None,
        TEST_MODE=False,
        AI_PROVIDER="openai",
        OPENAI_API_KEY="",
        DEEPSEEK_API_KEY="",
    )

    provider = get_ai_provider(settings)

    assert provider.provider_name == "mock"


def test_ai_provider_uses_deepseek_when_key_exists() -> None:
    settings = Settings(
        _env_file=None,
        TEST_MODE=False,
        AI_PROVIDER="deepseek",
        DEEPSEEK_API_KEY="deepseek-test-key",
        OPENAI_API_KEY="",
    )

    provider = get_ai_provider(settings)

    assert provider.provider_name == "deepseek"


def test_openai_provider_extracts_output_text() -> None:
    provider = OpenAIProvider(
        model="gpt-test",
        api_key="openai-test-key",
        timeout_seconds=5,
    )

    class FakeResponses:
        async def create(self, **kwargs):
            assert kwargs["model"] == "gpt-test"
            assert "Customer language: es." in kwargs["instructions"]

            class Response:
                output_text = "  Su pedido ya fue enviado.  "

            return Response()

    class FakeClient:
        responses = FakeResponses()

    provider._client = FakeClient()

    reply = asyncio.run(provider.generate_reply(build_ai_request()))

    assert reply == "Su pedido ya fue enviado."


def test_deepseek_provider_extracts_chat_completion_content() -> None:
    provider = DeepSeekProvider(
        model="deepseek-chat",
        api_key="deepseek-test-key",
        base_url="https://api.deepseek.com/v1",
        timeout_seconds=5,
    )

    class FakeCompletions:
        async def create(self, **kwargs):
            assert kwargs["model"] == "deepseek-chat"
            assert kwargs["messages"][0]["role"] == "system"

            class Message:
                content = "  Tu pedido esta en camino.  "

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    provider._client = FakeClient()

    reply = asyncio.run(provider.generate_reply(build_ai_request()))

    assert reply == "Tu pedido esta en camino."


def test_ai_generation_job_falls_back_to_translated_message_when_provider_fails(
    db_session_factory,
    monkeypatch,
) -> None:
    session = db_session_factory()
    runtime_state = RuntimeStateStore(session)

    try:
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="account-ai-fallback",
                conversation_id="conv-ai-fallback",
                customer_id="user-fallback",
                customer_language="es",
                customer_language_source="detected",
            )
        )
        asyncio.run(
            runtime_state.record_inbound_message(
                account_id="account-ai-fallback",
                conversation_id="conv-ai-fallback",
                sender_id="user-fallback",
                text="Necesito ayuda con mi pedido.",
                language_code="es",
                translated_text="[auto-translated es->zh-CN] Necesito ayuda con mi pedido.",
                translated_language_code="zh-CN",
                payload={"source": "test"},
            )
        )

        class FailingProvider:
            provider_name = "openai"
            model = "gpt-test"

            async def generate_reply(self, request: AIReplyRequest) -> str:
                assert request.customer_language == "es"
                assert len(request.conversation_history) >= 1
                raise RuntimeError("simulated provider failure")

        monkeypatch.setattr(
            "app.services.ai_queue_processor.get_ai_provider",
            lambda settings, account_id=None: FailingProvider(),
        )

        settings = Settings(
            _env_file=None,
            TEST_MODE=True,
            LIVE_TRANSLATION_ENABLED=True,
            TRANSLATION_PROVIDER="fallback",
        )
        result = asyncio.run(
            process_ai_generation_job(
                payload={
                    "account_id": "account-ai-fallback",
                    "conversation_id": "conv-ai-fallback",
                    "recipient_id": "user-fallback",
                    "user_message": "Necesito ayuda con mi pedido.",
                    "language_code": "es",
                },
                settings=settings,
                runtime_state=runtime_state,
            )
        )
        messages = asyncio.run(
            runtime_state.list_message_models(
                account_id="account-ai-fallback",
                conversation_id="conv-ai-fallback",
            )
        )

        assert result["status"] == "completed"
        assert result["degraded"] is True
        assert "provider failure" in str(result["fallback_reason"])
        assert messages[-1].ai_generated is True
        assert messages[-1].payload["degraded"] is True
        assert messages[-1].content_text.startswith("[auto-translated zh-CN->es]")
    finally:
        session.close()


def test_ai_generation_job_skips_when_queued_phone_scope_no_longer_matches_conversation(
    db_session_factory,
    monkeypatch,
) -> None:
    session = db_session_factory()
    runtime_state = RuntimeStateStore(session)
    provider_calls = {"count": 0}

    class CountingProvider:
        provider_name = "openai"
        model = "scope-guard-test"

        async def generate_reply(self, request: AIReplyRequest) -> str:
            del request
            provider_calls["count"] += 1
            return "This should not be generated for a stale phone scope."

    try:
        asyncio.run(
            runtime_state.ensure_account(
                account_id="account-ai-scope",
                display_name="AI Scope Account",
                provider_type="whatsapp",
            )
        )
        waba_account = WhatsAppBusinessAccount(
            account_id="account-ai-scope",
            waba_id="waba-ai-scope",
            onboarding_mode="manual",
            token_source="system_user",
            access_token="token-ai-scope",
            webhook_subscribed=False,
            is_active=True,
            ai_enabled=True,
        )
        session.add(waba_account)
        session.flush()
        session.add_all(
            [
                WhatsAppPhoneNumber(
                    account_id="account-ai-scope",
                    waba_account_id=waba_account.id,
                    waba_id=waba_account.waba_id,
                    phone_number_id="pn-ai-scope-a",
                    display_phone_number="+1 555 000 0801",
                    verified_name="AI Scope A",
                    quality_rating="GREEN",
                    is_registered=True,
                    is_active=True,
                ),
                WhatsAppPhoneNumber(
                    account_id="account-ai-scope",
                    waba_account_id=waba_account.id,
                    waba_id=waba_account.waba_id,
                    phone_number_id="pn-ai-scope-b",
                    display_phone_number="+1 555 000 0802",
                    verified_name="AI Scope B",
                    quality_rating="GREEN",
                    is_registered=True,
                    is_active=True,
                ),
            ]
        )
        session.commit()
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="account-ai-scope",
                conversation_id="conv-ai-scope",
                customer_id="user-ai-scope",
                customer_language="en",
                customer_language_source="hint",
                provider_phone_number_id="pn-ai-scope-a",
            )
        )

        settings = Settings(
            _env_file=None,
            TEST_MODE=True,
            LIVE_TRANSLATION_ENABLED=False,
            TRANSLATION_PROVIDER="fallback",
        )
        monkeypatch.setattr(
            "app.services.ai_queue_processor.get_ai_provider",
            lambda settings: CountingProvider(),
        )
        result = asyncio.run(
            process_ai_generation_job(
                payload={
                    "account_id": "account-ai-scope",
                    "conversation_id": "conv-ai-scope",
                    "recipient_id": "user-ai-scope",
                    "waba_id": "waba-ai-scope",
                    "phone_number_id": "pn-ai-scope-b",
                    "user_message": "Please answer later.",
                    "language_code": "en",
                    "job_id": "job-ai-scope-mismatch",
                },
                settings=settings,
                runtime_state=runtime_state,
            )
        )

        assert result == {
            "status": "skipped",
            "reason": "queue_scope_mismatch_before_processing",
            "queued_waba_id": "waba-ai-scope",
            "queued_phone_number_id": "pn-ai-scope-b",
            "current_waba_id": "waba-ai-scope",
            "current_phone_number_id": "pn-ai-scope-a",
        }
        assert provider_calls["count"] == 0
        queue_event = (
            session.query(MessageEvent)
            .filter_by(
                account_id="account-ai-scope",
                event_type="ai_generation_skipped",
            )
            .one()
        )
        assert queue_event.payload["reason"] == "queue_scope_mismatch_before_processing"
        assert queue_event.payload["queued_phone_number_id"] == "pn-ai-scope-b"
        assert queue_event.payload["current_phone_number_id"] == "pn-ai-scope-a"

        messages = asyncio.run(
            runtime_state.list_message_models(
                account_id="account-ai-scope",
                conversation_id="conv-ai-scope",
            )
        )
        assert messages == []
    finally:
        session.close()


def test_ai_generation_job_deduplicates_repeated_job_id(
    db_session_factory,
) -> None:
    session = db_session_factory()
    runtime_state = RuntimeStateStore(session)

    try:
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="account-ai-dedup",
                conversation_id="conv-ai-dedup",
                customer_id="user-dedup",
                customer_language="en",
                customer_language_source="hint",
            )
        )
        settings = Settings(
            _env_file=None,
            TEST_MODE=True,
            LIVE_TRANSLATION_ENABLED=False,
            TRANSLATION_PROVIDER="fallback",
        )

        first_result = asyncio.run(
            process_ai_generation_job(
                payload={
                    "account_id": "account-ai-dedup",
                    "conversation_id": "conv-ai-dedup",
                    "recipient_id": "user-dedup",
                    "user_message": "Where is my order?",
                    "language_code": "en",
                    "job_id": "job-ai-dedup-1",
                },
                settings=settings,
                runtime_state=runtime_state,
            )
        )
        second_result = asyncio.run(
            process_ai_generation_job(
                payload={
                    "account_id": "account-ai-dedup",
                    "conversation_id": "conv-ai-dedup",
                    "recipient_id": "user-dedup",
                    "user_message": "Where is my order?",
                    "language_code": "en",
                    "job_id": "job-ai-dedup-1",
                },
                settings=settings,
                runtime_state=runtime_state,
            )
        )
        messages = asyncio.run(
            runtime_state.list_message_models(
                account_id="account-ai-dedup",
                conversation_id="conv-ai-dedup",
            )
        )

        assert first_result["status"] == "completed"
        assert second_result["status"] == "deduplicated"
        assert len([message for message in messages if message.direction == "outbound"]) == 1
    finally:
        session.close()
