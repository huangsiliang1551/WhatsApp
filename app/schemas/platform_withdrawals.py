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
    member_profile_id: str | None = None
    request_no: str
    amount: float
    currency: str
    status: PlatformWithdrawalStatus
    rejection_reason: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    paid_at: datetime | None = None
    history: list[H5WithdrawalAuditLogResponse] = Field(default_factory=list)
