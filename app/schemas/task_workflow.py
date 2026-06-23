from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TaskProofFileResponse(BaseModel):
    id: str
    account_id: str | None = None
    task_instance_id: str
    user_id: str
    site_id: str | None = None
    storage_provider: str
    object_key: str
    read_url: str | None = None
    original_filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    status: str
    uploaded_by_type: str
    created_at: datetime


class TaskSubmissionCreateRequest(BaseModel):
    public_user_id: str | None = Field(default=None, min_length=1, max_length=128)
    site_id: str | None = Field(default=None, max_length=36)
    site_key: str | None = Field(default=None, max_length=64)
    proof_file_ids: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=4000)
    payload_json: dict[str, Any] = Field(default_factory=dict)


class TaskSubmissionResponse(BaseModel):
    id: str
    account_id: str | None = None
    task_instance_id: str
    submission_no: int
    status: str
    submitted_by_user_id: str
    public_user_id: str
    site_id: str | None = None
    site_key: str | None = None
    source_channel: str
    submitted_at: datetime
    review_started_at: datetime | None = None
    review_completed_at: datetime | None = None
    review_required_snapshot: bool
    payload_json: dict[str, Any] = Field(default_factory=dict)
    proofs: list[TaskProofFileResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class TaskReviewDecisionActionRequest(BaseModel):
    reason_code: str | None = Field(default=None, max_length=64)
    reason_text: str | None = Field(default=None, max_length=2000)
    evidence_json: dict[str, Any] = Field(default_factory=dict)


class TaskReviewDecisionResponse(BaseModel):
    id: str
    account_id: str | None = None
    submission_id: str
    task_instance_id: str
    decision: str
    decision_source: str
    reviewer_actor_id: str | None = None
    reason_code: str | None = None
    reason_text: str | None = None
    evidence_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ReviewQueueItemResponse(BaseModel):
    task_instance_id: str
    template_id: str
    template_task_key: str
    template_name: str
    template_title: str
    template_description: str | None = None
    task_type: str
    reward_points: int
    account_id: str | None = None
    user_id: str
    public_user_id: str
    site_id: str | None = None
    site_key: str | None = None
    task_status: str
    review_required: bool
    submission: TaskSubmissionResponse
    latest_decision: TaskReviewDecisionResponse | None = None


class TicketMessageCreateRequest(BaseModel):
    sender_type: str = Field(min_length=1, max_length=32)
    sender_id: str | None = Field(default=None, max_length=128)
    body_text: str | None = Field(default=None, max_length=4000)
    attachments_json: list[dict[str, Any]] = Field(default_factory=list)
    is_internal: bool = False


class TicketStatusUpdateRequest(BaseModel):
    status: str = Field(min_length=1, max_length=32)


class TicketMessageResponse(BaseModel):
    id: str
    account_id: str | None = None
    ticket_id: str
    sender_type: str
    sender_id: str | None = None
    body_text: str | None = None
    attachments_json: list[dict[str, Any]] = Field(default_factory=list)
    is_internal: bool
    created_at: datetime


class TicketCreateRequest(BaseModel):
    account_id: str | None = Field(default=None, max_length=128)
    public_user_id: str | None = Field(default=None, min_length=1, max_length=128)
    site_id: str | None = Field(default=None, max_length=36)
    site_key: str | None = Field(default=None, max_length=64)
    ticket_type: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=255)
    body_text: str = Field(min_length=1, max_length=4000)
    linked_task_instance_id: str | None = Field(default=None, max_length=36)
    linked_submission_id: str | None = Field(default=None, max_length=36)
    priority: str = Field(default="normal", min_length=1, max_length=32)
    attachments_json: list[dict[str, Any]] = Field(default_factory=list)


class LegacyTicketCreateRequest(BaseModel):
    ticket_type: str = Field(min_length=1, max_length=32)
    task_instance_id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=4000)


class TicketResponse(BaseModel):
    id: str
    account_id: str | None = None
    ticket_no: str
    ticket_type: str
    status: str
    priority: str
    site_id: str | None = None
    site_key: str | None = None
    user_id: str
    public_user_id: str
    linked_task_instance_id: str | None = None
    linked_submission_id: str | None = None
    review_decision_id: str | None = None
    title: str
    latest_reply_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    is_active: bool
    messages: list[TicketMessageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class H5SiteSummaryResponse(BaseModel):
    id: str
    account_id: str | None = None
    site_key: str
    brand_name: str
    domain: str
    default_language: str


class H5UserSummaryResponse(BaseModel):
    id: str
    public_user_id: str
    display_name: str | None = None
    language_code: str


class H5BootstrapResponse(BaseModel):
    site: H5SiteSummaryResponse
    user: H5UserSummaryResponse
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    open_ticket_count: int = 0
