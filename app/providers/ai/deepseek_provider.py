import structlog
from openai import APITimeoutError, AsyncOpenAI, OpenAIError

from app.providers.ai.base import AIProvider, AIReplyRequest

logger = structlog.get_logger()


class DeepSeekProvider(AIProvider):
    provider_name = "deepseek"

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        timeout_seconds: int,
    ) -> None:
        super().__init__(model=model)
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
        )

    async def generate_reply(self, request: AIReplyRequest) -> str:
        params = request.model_params
        temperature = params.temperature if params else 0.3
        max_tokens = params.max_tokens if params else 300
        system_content = request.system_prompt or (
            "You are the AI assistant for a WhatsApp customer support console. "
            "Reply in the customer's language, keep the answer concise and action-oriented, "
            "do not invent order or policy facts, and ask a short clarifying question when information is missing. "
            f"Customer language: {request.customer_language}."
        )
        kwargs: dict = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": _build_model_input(request)},
            ],
        }
        # 支持 function calling
        if request.available_tools:
            kwargs["tools"] = request.available_tools
            kwargs["tool_choice"] = "auto"

        try:
            response = await self._client.chat.completions.create(**kwargs)
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

        # 处理 function call
        message = response.choices[0].message if response.choices else None
        if message is None:
            raise RuntimeError(f"{self.provider_name} provider returned an empty response.")
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            # 将 tool_calls 编码到回复文本中，供上层 AIToolExecutor 处理
            import json as _json

            tool_calls_data = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tool_calls
            ]
            return _json.dumps({"__tool_calls__": tool_calls_data})

        content = message.content
        if not content:
            raise RuntimeError(f"{self.provider_name} provider returned an empty response.")
        return content.strip()


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
