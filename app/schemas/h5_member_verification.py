from datetime import datetime

from pydantic import Field

from app.schemas.h5_member_base import H5MemberCamelModel


class H5MemberVerificationDocumentCreate(H5MemberCamelModel):
    file_name: str = Field(min_length=1, max_length=255)
    mime_type: str | None = Field(default=None, max_length=128)
    storage_key: str | None = Field(default=None, max_length=512)
    metadata_json: dict[str, object] | None = None


class H5MemberVerificationCreateRequest(H5MemberCamelModel):
    request_type: str = Field(default="identity", min_length=1, max_length=32)
    notes: str | None = None
    documents: list[H5MemberVerificationDocumentCreate] = Field(default_factory=list)


class H5MemberVerificationDocumentResponse(H5MemberCamelModel):
    id: str
    file_name: str
    mime_type: str | None = None
    storage_key: str | None = None
    metadata_json: dict[str, object] | None = None
    created_at: datetime


class H5MemberVerificationRequestResponse(H5MemberCamelModel):
    id: str
    request_type: str
    status: str
    notes: str | None = None
    review_note: str | None = None
    reviewer_actor_id: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    documents: list[H5MemberVerificationDocumentResponse] = Field(default_factory=list)


class H5MemberVerificationSummaryResponse(H5MemberCamelModel):
    current_status: str = "not_submitted"
    has_active_request: bool = False
    active_request: H5MemberVerificationRequestResponse | None = None
    history: list[H5MemberVerificationRequestResponse] = Field(default_factory=list)
