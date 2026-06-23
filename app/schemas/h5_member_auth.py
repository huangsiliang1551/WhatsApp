from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.h5_member_base import H5MemberCamelModel
from app.schemas.h5_member_commerce import H5WithdrawLeaderboardEntryResponse
from app.schemas.h5_member_messages import H5MemberMessageResponse


class H5MemberRegisterRequest(H5MemberCamelModel):
    site_key: str = Field(min_length=1, max_length=64)
    phone: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=6, max_length=128)
    confirm_password: str = Field(min_length=6, max_length=128)
    display_name: str | None = Field(default=None, max_length=255)
    invite_code: str | None = Field(default=None, min_length=1, max_length=64)
    language_code: str = Field(default="zh-CN", min_length=2, max_length=32)


class H5MemberLoginRequest(H5MemberCamelModel):
    site_key: str = Field(min_length=1, max_length=64)
    phone: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=6, max_length=128)


class H5MemberSessionPayload(H5MemberCamelModel):
    expires_at: datetime
    refresh_expires_at: datetime


class H5MemberSitePayload(H5MemberCamelModel):
    id: str
    account_id: str
    site_key: str
    brand_name: str
    domain: str
    default_language: str


class H5MemberIdentityPayload(H5MemberCamelModel):
    user_id: str
    public_user_id: str
    account_id: str
    site_id: str
    site_key: str
    member_no: str
    account_id_masked: str | None = None
    invite_code: str | None = None
    phone: str
    display_name: str | None = None
    language_code: str
    created_at: datetime
    last_login_at: datetime | None = None


class H5MemberAuthResponse(H5MemberCamelModel):
    member: H5MemberIdentityPayload
    site: H5MemberSitePayload
    session: H5MemberSessionPayload


class H5MemberTaskSummary(H5MemberCamelModel):
    total: int = 0
    available: int = 0
    claimed: int = 0
    pending_review: int = 0
    completed: int = 0
    rejected: int = 0


class H5MemberWalletSummary(H5MemberCamelModel):
    system_balance: float | None = None
    task_balance: float | None = None
    currency: str | None = None


class H5MemberHomeVerificationSummary(H5MemberCamelModel):
    current_status: str = "not_submitted"
    has_active_request: bool = False


class H5MemberHomeFragmentSummary(H5MemberCamelModel):
    reward_name: str | None = None
    completed_count: int = 0
    total_count: int = 0
    missing_count: int = 0
    can_exchange: bool = False
    shipping_order_count: int = 0
    latest_shipping_status: str | None = None


class H5MemberHomeResponse(H5MemberCamelModel):
    member: H5MemberIdentityPayload
    site: H5MemberSitePayload
    task_summary: H5MemberTaskSummary
    open_ticket_count: int = 0
    unread_message_count: int = 0
    pending_claim_count: int = 0
    active_count: int = 0
    expiring_count: int = 0
    recent_messages: list[H5MemberMessageResponse] = Field(default_factory=list)
    leaderboard: list[H5WithdrawLeaderboardEntryResponse] = Field(default_factory=list)
    wallet: H5MemberWalletSummary = Field(default_factory=H5MemberWalletSummary)
    verification: H5MemberHomeVerificationSummary = Field(default_factory=H5MemberHomeVerificationSummary)
    fragments: H5MemberHomeFragmentSummary = Field(default_factory=H5MemberHomeFragmentSummary)
