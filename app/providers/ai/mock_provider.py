from app.providers.ai.base import AIProvider, AIReplyRequest


class MockAIProvider(AIProvider):
    provider_name = "mock"

    async def generate_reply(self, request: AIReplyRequest) -> str:
        return (
            f"[MockAI:{self.model}][{request.customer_language}] "
            f"Received message: {request.user_message}"
        )
