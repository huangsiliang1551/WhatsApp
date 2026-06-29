from __future__ import annotations

from pydantic import BaseModel, Field


class PermissionGrantCreateRequest(BaseModel):
    grantee_subject_type: str = Field(min_length=1)
    grantee_subject_id: str = Field(min_length=1)
    permission_code: str = Field(min_length=1)
    can_delegate: bool = False
    scope_type: str = "inherit"


class DataScopeGrantCreateRequest(BaseModel):
    subject_type: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    scope_type: str = Field(min_length=1)
    scope_id: str | None = None


class CustomerOwnershipTransferRequest(BaseModel):
    customer_id: str = Field(min_length=1)
    agency_id: str = Field(min_length=1)
    account_id: str | None = None
    site_id: str | None = None
    new_owner_staff_id: str | None = None
    new_supervisor_id: str | None = None
    new_team_id: str | None = None
    reason: str | None = None
    assignment_type: str = "permanent_transfer"


class ConversationHandoverRequest(BaseModel):
    conversation_id: str = Field(min_length=1)
    assigned_staff_id: str | None = None
    team_id: str | None = None
    supervisor_id: str | None = None
    assigned_queue_id: str | None = None
    reason: str | None = None
    is_temporary: bool = True
    assignment_type: str = "human_handover"
