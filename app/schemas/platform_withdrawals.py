from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.h5_member_base import H5MemberCamelModel
from app.schemas.h5_member_commerce import H5WithdrawalAuditLogResponse

PlatformWithdrawalStatus = Literal["submitted", "reviewing", "approved", "rejected", "paid"]
PlatformWithdrawalTransitionStatus = Literal["reviewing", "approved", "rejected", "paid"]


class PlatformWithdrawalStatusUpdateRequest(H5MemberCamelModel):
    status: PlatformWithdrawalTransitionStatus
    note: str | None = Field(default=None, max_length=4096)
    rejection_reason: str | None = None


class PlatformWithdrawalResponse(H5MemberCamelModel):
    id: str
    account_id: str
    wallet_account_id: str
    user_id: str
    public_user_id: str | None = None
    member_profile_id: str | None = None
    request_no: str
    amount: float
    cash_amount: float = 0
    bonus_amount: float = 0
    actual_payout_amount: float | None = None
    withdraw_account_type: str | None = None
    account_no_masked: str | None = None
    account_fingerprint: str | None = None
    duplicate_account_count: int = 0
    duplicate_member_ids: list[str] = Field(default_factory=list)
    risk_level: str | None = None
    risk_flags: list[str] = Field(default_factory=list)
    currency: str
    status: PlatformWithdrawalStatus
    rejection_reason: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    paid_at: datetime | None = None
    history: list[H5WithdrawalAuditLogResponse] = Field(default_factory=list)


class PlatformWithdrawalDuplicateMemberResponse(H5MemberCamelModel):
    account_id: str
    public_user_id: str
    withdrawal_count: int
    total_withdraw_amount: float
    latest_withdrawal_at: datetime


class PlatformWithdrawalDuplicateAccountsResponse(H5MemberCamelModel):
    withdrawal_id: str
    account_fingerprint: str | None = None
    account_no_masked: str | None = None
    duplicate_account_count: int = 0
    members: list[PlatformWithdrawalDuplicateMemberResponse] = Field(default_factory=list)
