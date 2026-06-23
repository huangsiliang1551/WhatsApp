from typing import Literal

from pydantic import BaseModel, Field


AgentStatus = Literal["offline", "online", "busy", "away"]


class AgentPresenceRecordSchema(BaseModel):
    """Schema for agent presence record from Redis."""

    account_id: str | None = None
    agent_id: str
    status: AgentStatus
    last_heartbeat: float
    display_name: str = ""


class AgentRegistrationRequest(BaseModel):
    account_id: str | None = None
    agent_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    email: str | None = None
    status: AgentStatus = "offline"
    is_active: bool = True


class AgentStatusUpdateRequest(BaseModel):
    status: AgentStatus


class AgentSummary(BaseModel):
    account_id: str | None = None
    agent_id: str
    display_name: str
    email: str | None = None
    status: AgentStatus
    is_active: bool


class AgentWorkloadSummary(AgentSummary):
    assigned_open_conversations: int
    assigned_total_conversations: int
    assigned_account_count: int


class ConversationAssignmentRequest(BaseModel):
    agent_id: str = Field(min_length=1)
    assigned_by_agent_id: str | None = None
    reason: str | None = None


class ConversationCloseRequest(BaseModel):
    agent_id: str | None = None
    reason: str | None = None
