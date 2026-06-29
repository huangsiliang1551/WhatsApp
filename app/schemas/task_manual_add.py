from datetime import datetime

from pydantic import Field

from app.schemas.h5_member_base import H5MemberCamelModel
from app.schemas.h5_member_commerce import H5TaskPackageItemPayload


class TaskManualAddCandidateResponse(H5MemberCamelModel):
    id: str
    product_id: str
    product_name: str
    image_url: str | None = None
    price: float
    currency: str


class TaskManualAddCreateRequest(H5MemberCamelModel):
    pool_item_ids: list[str] = Field(min_length=1)
    reason_text: str | None = Field(default=None, max_length=2000)
    notify_user: bool = False
    user_notice_text: str | None = Field(default=None, max_length=2000)


class TaskPackageStatusActionRequest(H5MemberCamelModel):
    reason_text: str | None = Field(default=None, max_length=2000)


class TaskManualAddResponse(H5MemberCamelModel):
    id: str
    package_id: str
    added_item_count: int
    added_amount: float
    package_manual_added_amount: float
    package_effective_amount: float
    batch_manual_added_amount: float
    batch_effective_day_amount: float


class TaskManualAddPreviewResponse(H5MemberCamelModel):
    package_id: str
    candidate_count: int
    added_item_count: int
    added_amount: float
    package_planned_amount: float
    package_system_generated_amount: float
    package_manual_added_amount_before: float
    package_manual_added_amount_after: float
    package_effective_amount_before: float
    package_effective_amount_after: float
    reward_ratio: float
    estimated_reward_amount_before: float
    estimated_reward_amount_after: float
    items: list[TaskManualAddCandidateResponse] = Field(default_factory=list)


class TaskManualAddLogResponse(H5MemberCamelModel):
    id: str
    package_id: str
    batch_id: str | None = None
    operator_id: str
    reason_text: str | None = None
    notify_user: bool = False
    user_notice_text: str | None = None
    user_notified_at: datetime | None = None
    added_item_count: int
    added_amount: float
    before_manual_added_amount: float
    after_manual_added_amount: float
    before_effective_amount: float
    after_effective_amount: float
    created_at: datetime


class TaskPackageAdminDetailResponse(H5MemberCamelModel):
    id: str
    batch_id: str | None = None
    day_no: int | None = None
    batch_index: int = 1
    batch_total: int = 1
    progress_label: str
    status: str
    day_planned_amount: float = 0
    day_system_generated_amount: float = 0
    day_manual_added_amount: float = 0
    day_effective_amount: float = 0
    planned_amount: float
    system_generated_amount: float
    manual_added_amount: float
    effective_amount: float
    reward_ratio: float
    estimated_reward_amount: float
    claimed_at: datetime | None = None
    completed_at: datetime | None = None
    items: list[H5TaskPackageItemPayload] = Field(default_factory=list)
    manual_add_logs: list[TaskManualAddLogResponse] = Field(default_factory=list)


class TaskPackageAdminListItemResponse(H5MemberCamelModel):
    id: str
    account_id: str
    user_id: str
    public_user_id: str
    site_id: str | None = None
    site_key: str | None = None
    batch_id: str | None = None
    day_no: int | None = None
    batch_index: int = 1
    batch_total: int = 1
    progress_label: str
    status: str
    planned_amount: float
    system_generated_amount: float
    manual_added_amount: float
    effective_amount: float
    estimated_reward_amount: float
    has_manual_add: bool = False
    claimed_at: datetime | None = None
    completed_at: datetime | None = None


class TaskGenerationRunResponse(H5MemberCamelModel):
    id: str
    account_id: str
    site_id: str | None = None
    site_key: str | None = None
    user_id: str
    public_user_id: str
    quota_id: str
    batch_id: str | None = None
    product_pool_id: str
    selection_algorithm: str
    target_day_amount: float
    actual_day_system_amount: float
    tolerance_amount: float
    generated_package_count: int
    generated_item_count: int
    status: str
    failure_reason: str | None = None
    created_at: datetime
