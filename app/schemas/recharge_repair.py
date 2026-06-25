from app.schemas.h5_member_base import H5MemberCamelModel


class RechargeRepairCreateRequest(H5MemberCamelModel):
    account_id: str
    user_id: str
    amount: float
    currency: str = "USD"
    repair_type: str = "callback_missing"
    reason: str
    remark: str | None = None
    channel_id: str | None = None
    platform_order_no: str | None = None
    channel_order_no: str | None = None
