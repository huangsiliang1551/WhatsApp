from typing import Literal

from pydantic import BaseModel, Field


class MockInboundMessage(BaseModel):
    account_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    mode: Literal["echo", "ai"] = "echo"
    language_hint: str | None = None
    waba_id: str | None = None
    phone_number_id: str | None = None
    message_type: str = "text"
    external_message_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class NormalizedMessage(BaseModel):
    account_id: str
    provider: str
    conversation_id: str
    user_id: str
    text: str
    message_type: str = "text"
    waba_id: str | None = None
    phone_number_id: str | None = None
    external_message_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
