import structlog
from openai import APITimeoutError, AsyncOpenAI, OpenAIError

from app.providers.ai.base import AIProvider, AIReplyRequest

logger = structlog.get_logger()


class OpenAIProvider(AIProvider):
    provider_name = "openai"

    def __init__(self, model: str, api_key: str, timeout_seconds: int) -> None:
        super().__init__(model=model)
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)

    async def generate_reply(self, request: AIReplyRequest) -> str:
        params = request.model_params
        temperature = params.temperature if params else 0.3
        max_tokens = params.max_tokens if params else 300
        system_content = request.system_prompt or _build_system_instructions(request.customer_language)

        kwargs: dict = {
            "model": self.model,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "truncation": "auto",
            "instructions": system_content,
            "input": _build_model_input(request),
        }
        if request.available_tools:
            kwargs["tools"] = request.available_tools
            kwargs["tool_choice"] = "auto"

        try:
            response = await self._client.responses.create(**kwargs)
        except (APITimeoutError, OpenAIError) as exc:
            logger.warning(
                "ai_provider_error",
                provider=self.provider_name,
                model=self.model,
                account_id=request.account_id,
                conversation_id=request.conversation_id,
                error=str(exc),
            )
            raise RuntimeError(f"{self.provider_name} provider request failed.") from exc

        # 处理 function call (OpenAI responses API 的 tool_calls)
        if hasattr(response, "output") and response.output:
            tool_calls = [item for item in response.output if getattr(item, "type", None) == "function_call"]
            if tool_calls:
                import json as _json

                tool_calls_data = [
                    {
                        "id": getattr(tc, "id", ""),
                        "type": "function",
                        "function": {
                            "name": getattr(tc, "name", ""),
                            "arguments": _json.dumps(getattr(tc, "arguments", {})),
                        },
                    }
                    for tc in tool_calls
                ]
                return _json.dumps({"__tool_calls__": tool_calls_data})

        reply_text = response.output_text.strip()
        if not reply_text:
            raise RuntimeError(f"{self.provider_name} provider returned an empty response.")
        return reply_text


def _build_system_instructions(customer_language: str) -> str:
    return (
        "You are the AI assistant for a WhatsApp customer support console. "
        "Reply in the customer's language, keep the answer concise and action-oriented, "
        "do not invent order or policy facts, and ask a short clarifying question when information is missing. "
        f"Customer language: {customer_language}."
    )


def _build_model_input(request: AIReplyRequest) -> str:
    history_lines = [
        f"{turn.role}: {turn.text}"
        for turn in request.conversation_history
        if turn.text.strip()
    ]
    history_block = "\n".join(history_lines) if history_lines else "(no prior conversation)"
    return (
        "Conversation context (oldest to newest):\n"
        f"{history_block}\n\n"
        "Latest customer message:\n"
        f"{request.user_message.strip()}"
    )
