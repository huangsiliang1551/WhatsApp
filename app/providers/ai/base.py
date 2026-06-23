from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AIConversationTurn:
    role: str
    text: str
    language_code: str | None = None


@dataclass
class AIModelParams:
    """AI 模型参数 — 从 ai_chat_configs 读取。"""

    temperature: float = 0.3
    max_tokens: int = 300
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop_sequences: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AIReplyRequest:
    account_id: str
    conversation_id: str
    customer_language: str
    user_message: str
    conversation_history: list[AIConversationTurn] = field(default_factory=list)
    system_prompt: str | None = None
    model_params: AIModelParams | None = None
    available_tools: list[dict[str, Any]] = field(default_factory=list)
    verified_user_id: str | None = None
    agency_id: str | None = None


class AIProvider(ABC):
    provider_name: str
    model: str

    def __init__(self, model: str) -> None:
        self.model = model

    @abstractmethod
    async def generate_reply(self, request: AIReplyRequest) -> str:
        raise NotImplementedError
