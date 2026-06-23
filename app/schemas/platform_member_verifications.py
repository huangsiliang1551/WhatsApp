from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.h5_member_base import H5MemberCamelModel

PlatformMemberVerificationStatus = Literal["pending", "under_review", "approved", "rejected"]
PlatformMemberVerificationTransitionStatus = Literal["under_review", "approved", "rejected"]


class PlatformMemberVerificationDocumentResponse(H5MemberCamelModel):
    id: str
    file_name: str
    mime_type: str | None = None
    storage_key: str | None = None
    metadata_json: dict[str, object] | None = None
    created_at: datetime


class PlatformMemberVerificationResponse(H5MemberCamelModel):
    id: str
    account_id: str
    member_profile_id: str
    user_id: str
    public_user_id: str
    member_no: str
    display_name: str | None = None
    request_type: str
    status: PlatformMemberVerificationStatus
    notes: str | None = None
    review_note: str | None = None
    reviewer_actor_id: str | None = None
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None = None
    documents: list[PlatformMemberVerificationDocumentResponse] = Field(default_factory=list)


class PlatformMemberVerificationStatusUpdateRequest(H5MemberCamelModel):
    status: PlatformMemberVerificationTransitionStatus
    note: str | None = Field(default=None, max_length=4096)


class PlatformMemberVerificationActionRequest(H5MemberCamelModel):
    reason: str | None = Field(default=None, max_length=255)
    comment: str | None = Field(default=None, max_length=4096)
