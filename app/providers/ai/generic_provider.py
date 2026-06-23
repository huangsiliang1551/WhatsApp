"""
AIP-002: Generic OpenAI-compatible provider for any provider using the OpenAI SDK.

Supports both responses.create (OpenAI) and chat.completions.create (DeepSeek/Groq/Ollama).
"""

import structlog
from openai import APITimeoutError, AsyncOpenAI, OpenAIError

from typing import Any

from app.providers.ai.base import AIProvider, AIReplyRequest

logger = structlog.get_logger()


class GenericOpenAICompatibleProvider(AIProvider):
    """Supports any OpenAI SDK compatible API (DeepSeek, Groq, Ollama, Together AI, etc.).

    - use_responses_api=True: uses responses.create() (OpenAI native)
    - use_responses_api=False: uses chat.completions.create() (standard)
    """

    provider_name = "generic"

    def __init__(
        self,
        display_name: str,
        model: str,
        api_key: str,
        base_url: str | None,
        timeout_seconds: int,
        use_responses_api: bool = False,
    ) -> None:
        super().__init__(model=model)
        self._display_name = display_name
        self._use_responses_api = use_responses_api
        kwargs: dict = {"api_key": api_key, "timeout": timeout_seconds}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)

    async def generate_reply(self, request: AIReplyRequest) -> str:
        try:
            if self._use_responses_api:
                return await self._generate_via_responses(request)
            return await self._generate_via_chat_completions(request)
        except (APITimeoutError, OpenAIError) as exc:
            logger.warning(
                "ai_provider_error",
                provider=self.provider_name,
                display_name=self._display_name,
                model=self.model,
                account_id=request.account_id,
                conversation_id=request.conversation_id,
                error=str(exc),
            )
            raise RuntimeError(f"'{self._display_name}' provider request failed.") from exc

    async def _generate_via_responses(self, request: AIReplyRequest) -> str:
        params = request.model_params
        temperature = params.temperature if params else 0.3
        max_tokens = params.max_tokens if params else 300
        system_content = request.system_prompt or _build_system_instructions(request.customer_language)

        kwargs: dict[str, Any] = {
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

        response = await self._client.responses.create(**kwargs)

        # 处理 function call
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
            raise RuntimeError(f"'{self._display_name}' provider returned an empty response.")
        return reply_text

    async def _generate_via_chat_completions(self, request: AIReplyRequest) -> str:
        params = request.model_params
        temperature = params.temperature if params else 0.3
        max_tokens = params.max_tokens if params else 300
        system_content = request.system_prompt or (
            "You are the AI assistant for a WhatsApp customer support console. "
            "Reply in the customer's language, keep the answer concise and action-oriented, "
            "do not invent order or policy facts, and ask a short clarifying question when information is missing. "
            f"Customer language: {request.customer_language}."
        )

        kwargs: dict[str, Any] = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": _build_model_input(request)},
            ],
        }
        if request.available_tools:
            kwargs["tools"] = request.available_tools
            kwargs["tool_choice"] = "auto"

        response = await self._client.chat.completions.create(**kwargs)

        message = response.choices[0].message if response.choices else None
        if message is None:
            raise RuntimeError(f"'{self._display_name}' provider returned an empty response.")
        if message.tool_calls:
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
                for tc in message.tool_calls
            ]
            return _json.dumps({"__tool_calls__": tool_calls_data})

        content = message.content
        if not content:
            raise RuntimeError(f"'{self._display_name}' provider returned an empty response.")
        return content.strip()


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
