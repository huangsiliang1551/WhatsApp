from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


def _to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class WhatsAppCamelModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=_to_camel,
    )


class WhatsAppAuthStartRequest(WhatsAppCamelModel):
    session_type: str
    site_key: str | None = None


class WhatsAppAuthConsumeRequest(WhatsAppCamelModel):
    command_text: str
    wa_id: str
    inbound_phone_number_id: str
    inbound_waba_id: str
    inbound_message_id: str | None = None


class WhatsAppAuthSessionResponse(WhatsAppCamelModel):
    id: str
    account_id: str
    site_id: str
    user_id: str | None = None
    session_type: str
    status: str
    selected_waba_id: str
    selected_phone_number_id: str
    selected_display_phone_number: str
    command_text: str
    wa_link: str
    expires_at: datetime
    confirmed_at: datetime | None = None
    failure_code: str | None = None
    failure_reason: str | None = None


class WhatsAppAutoBindConsumeRequest(WhatsAppCamelModel):
    token: str


class WhatsAppAutoBindConsumeResponse(WhatsAppCamelModel):
    status: str
    site_id: str
    public_user_id: str
    wa_id: str
    invite_id: str
