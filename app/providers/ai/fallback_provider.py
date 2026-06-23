import structlog

from app.providers.ai.base import AIProvider, AIReplyRequest

logger = structlog.get_logger()


class FallbackAIProvider(AIProvider):
    """Wraps a chain of AI providers and tries each in order until one succeeds.

    Provider order determines priority:
        [primary, secondary, ..., fallback]
    The last provider in the chain should never raise (e.g. MockAIProvider).
    """

    def __init__(self, providers: list[AIProvider]) -> None:
        if not providers:
            raise ValueError("FallbackAIProvider requires at least one provider.")
        self._providers = providers
        # Expose primary provider metadata for metrics / logging
        self.provider_name = providers[0].provider_name
        self.model = providers[0].model

    @property
    def fallback_chain(self) -> list[dict[str, str]]:
        return [
            {"provider_name": p.provider_name, "model": p.model}
            for p in self._providers
        ]

    async def generate_reply(self, request: AIReplyRequest) -> str:
        last_error: Exception | None = None
        attempted: list[str] = []

        for index, provider in enumerate(self._providers):
            try:
                reply = await provider.generate_reply(request)
                if index > 0:
                    logger.info(
                        "ai_fallback_chain_success",
                        provider=provider.provider_name,
                        model=provider.model,
                        previous_attempts=attempted,
                        account_id=request.account_id,
                        conversation_id=request.conversation_id,
                    )
                return reply
            except Exception as exc:
                attempted.append(f"{provider.provider_name}/{provider.model}")
                last_error = exc
                logger.warning(
                    "ai_fallback_chain_provider_failed",
                    provider=provider.provider_name,
                    model=provider.model,
                    account_id=request.account_id,
                    conversation_id=request.conversation_id,
                    error=str(exc),
                )
                continue

        raise RuntimeError(
            f"All AI providers in fallback chain failed: {', '.join(attempted)}. "
            f"Last error: {last_error}"
        ) from last_error
