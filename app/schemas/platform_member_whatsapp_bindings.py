from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.h5_member_base import H5MemberCamelModel

PlatformMemberWhatsAppBindingStatus = Literal["pending", "bound", "failed"]


class PlatformMemberWhatsAppBindingResponse(H5MemberCamelModel):
    id: str
    account_id: str
    user_id: str
    member_profile_id: str
    site_id: str | None = None
    site_key: str | None = None
    public_user_id: str
    member_no: str
    display_name: str | None = None
    status: PlatformMemberWhatsAppBindingStatus
    requested_phone_number: str | None = None
    start_count: int
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
    last_started_at: datetime | None = None
    bound_at: datetime | None = None


class PlatformMemberWhatsAppBindingStatusUpdateRequest(H5MemberCamelModel):
    status: PlatformMemberWhatsAppBindingStatus
    note: str | None = Field(default=None, max_length=4096)
