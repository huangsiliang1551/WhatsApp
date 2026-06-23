"""Context window optimization for AI conversation generation.

Provides configurable message limiting, token estimation, and truncation
strategies to keep AI context within budget while preserving critical content.
"""

import structlog

from app.providers.ai.base import AIConversationTurn

logger = structlog.get_logger()

# Rough token estimation: 4 characters ≈ 1 token for most languages
_CHARS_PER_TOKEN = 4.0


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text string."""
    return max(1, round(len(text) / _CHARS_PER_TOKEN))


class ContextWindowStats:
    """Tracks token usage for a single AI generation call."""

    def __init__(self) -> None:
        self.system_prompt_tokens: int = 0
        self.history_tokens: int = 0
        self.user_message_tokens: int = 0
        self.knowledge_base_tokens: int = 0
        self.total_tokens: int = 0

    def record(
        self,
        system_prompt: str,
        history: list[AIConversationTurn],
        user_message: str,
        knowledge_base: str = "",
    ) -> None:
        self.system_prompt_tokens = estimate_tokens(system_prompt)
        self.history_tokens = sum(estimate_tokens(t.text) for t in history)
        self.user_message_tokens = estimate_tokens(user_message)
        self.knowledge_base_tokens = estimate_tokens(knowledge_base)
        self.total_tokens = (
            self.system_prompt_tokens
            + self.history_tokens
            + self.user_message_tokens
            + self.knowledge_base_tokens
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "system_prompt_tokens": self.system_prompt_tokens,
            "history_tokens": self.history_tokens,
            "user_message_tokens": self.user_message_tokens,
            "knowledge_base_tokens": self.knowledge_base_tokens,
            "total_tokens": self.total_tokens,
        }


class ContextWindowOptimizer:
    """Optimizes AI context by limiting and truncating conversation history.

    Truncation strategy (in order):
        1. Keep system prompt intact (highest priority)
        2. Keep current user message intact
        3. Trim knowledge base context first
        4. Trim conversation history from oldest to newest
    """

    def __init__(
        self,
        max_messages: int = 10,
        max_history_chars: int = 2000,
        max_message_chars: int = 500,
        max_total_context_chars: int = 4000,
    ) -> None:
        self._max_messages = max_messages
        self._max_history_chars = max_history_chars
        self._max_message_chars = max_message_chars
        self._max_total_context_chars = max_total_context_chars

    def trim_history(
        self,
        messages: list[object],
        *,
        system_prompt: str = "",
        user_message: str = "",
        knowledge_text: str = "",
    ) -> tuple[list[AIConversationTurn], ContextWindowStats]:
        """Trim conversation history and return optimized turns with token stats.

        Args:
            messages: Raw message objects from the database.
            system_prompt: System-level prompt text (preserved as-is).
            user_message: Current user message (preserved as-is).
            knowledge_text: Knowledge base context text (trimmed if needed).

        Returns:
            A tuple of (optimized_history, token_stats).
        """
        stats = ContextWindowStats()

        if not messages:
            stats.record(system_prompt=system_prompt, history=[], user_message=user_message, knowledge_base=knowledge_text)
            return [], stats

        selected = messages[-self._max_messages:]
        history: list[AIConversationTurn] = []
        remaining_budget = self._max_history_chars

        for message in reversed(selected):
            text = self._safe_message_text(message)
            if not text:
                continue

            role = "user" if getattr(message, "direction", None) == "inbound" else "assistant"
            language_code = getattr(message, "language_code", None)

            truncated = text[: self._max_message_chars]
            if len(text) > self._max_message_chars:
                truncated = truncated.rstrip() + "..."

            if remaining_budget <= 0:
                continue

            if len(truncated) > remaining_budget:
                if remaining_budget > 50:
                    truncated = truncated[-remaining_budget:]
                else:
                    continue

            remaining_budget -= len(truncated)
            history.append(
                AIConversationTurn(
                    role=role,
                    text=truncated,
                    language_code=language_code,
                )
            )

        history.reverse()

        if knowledge_text:
            kb_budget = self._max_total_context_chars - len(system_prompt) - sum(len(t.text) for t in history) - len(user_message)
            if kb_budget <= 0:
                knowledge_text = ""
            elif len(knowledge_text) > kb_budget:
                knowledge_text = knowledge_text[: kb_budget - 50] + "..."

        stats.record(
            system_prompt=system_prompt,
            history=history,
            user_message=user_message,
            knowledge_base=knowledge_text,
        )

        return history, stats

    @staticmethod
    def _safe_message_text(message: object) -> str:
        return (getattr(message, "content_text", None) or "").strip()
