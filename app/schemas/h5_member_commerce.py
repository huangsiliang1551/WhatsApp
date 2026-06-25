from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.h5_member_base import H5MemberCamelModel
from app.schemas.h5_member_fragments import H5FragmentDropLogResponse


class H5TaskPackagePromotionPayload(H5MemberCamelModel):
    metric: str
    current: int
    target: int
    invite_code: str | None = None


class H5TaskPackageItemPayload(H5MemberCamelModel):
    id: str
    product_name: str
    image_url: str | None = None
    price: float
    currency: str
    completed_at: datetime | None = None
    order_id: str | None = None


class H5TaskPackagePayload(H5MemberCamelModel):
    id: str
    title: str
    description: str | None = None
    type: str
    status: str
    reward_ratio: float
    claimed_at: datetime | None = None
    expires_at: datetime | None = None
    completed_at: datetime | None = None
    dispatched_at: datetime
    completion_window_hours: int
    items: list[H5TaskPackageItemPayload] = Field(default_factory=list)
    promotion: H5TaskPackagePromotionPayload | None = None
    task_balance_awarded_at: datetime | None = None
    total_commission: float
    current_commission: float
    completed_items: int
    total_items: int
    countdown_seconds: int


class H5WalletSummaryResponse(H5MemberCamelModel):
    system_balance: float
    task_balance: float
    currency: str
    withdraw_threshold: float
    can_withdraw: bool
    shortfall_amount: float


class H5WalletTransactionResponse(H5MemberCamelModel):
    id: str
    ledger_type: str
    transaction_type: str
    direction: str
    amount: float
    currency: str
    status: str
    note: str | None = None
    display_category: str | None = None
    display_title: str | None = None
    created_at: datetime


class H5MemberOrderResponse(H5MemberCamelModel):
    id: str
    order_no: str
    package_id: str | None = None
    package_title: str | None = None
    product_name: str
    amount: float
    currency: str
    status: str
    created_at: datetime
    source_label: str | None = None


class H5RechargeCreateRequest(H5MemberCamelModel):
    amount: float = Field(gt=0)


class H5WalletTransferRequest(H5MemberCamelModel):
    amount: float = Field(gt=0)


class H5WithdrawalCreateRequest(H5MemberCamelModel):
    amount: float = Field(gt=0)
    withdraw_account_type: str | None = None
    bank_name: str | None = None
    account_no: str | None = None


class H5WithdrawalAuditLogResponse(H5MemberCamelModel):
    id: str
    status: str
    note: str | None = None
    actor_type: str
    actor_id: str | None = None
    created_at: datetime


class H5WithdrawalResponse(H5MemberCamelModel):
    id: str
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
    status: str
    rejection_reason: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    paid_at: datetime | None = None
    history: list[H5WithdrawalAuditLogResponse] = Field(default_factory=list)


class H5WithdrawLeaderboardEntryResponse(H5MemberCamelModel):
    rank: int
    account_id_masked: str
    amount: float
    currency: str


class H5TaskPackagePurchaseResponse(H5MemberCamelModel):
    success: bool
    order: H5MemberOrderResponse | None = None
    task_package: H5TaskPackagePayload
    wallet: H5WalletSummaryResponse
    fragment_drop: H5FragmentDropLogResponse | None = None
    reason: str | None = None


class H5LogisticsEntryResponse(H5MemberCamelModel):
    status: str
    description: str
    timestamp: datetime


class H5LogisticsResponse(H5MemberCamelModel):
    order_no: str
    carrier: str
    tracking_number: str
    current_status: str
    entries: list[H5LogisticsEntryResponse] = Field(default_factory=list)
