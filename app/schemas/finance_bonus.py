from pydantic import Field

from app.schemas.h5_member_base import H5MemberCamelModel


class BonusGrantCreateRequest(H5MemberCamelModel):
    account_id: str
    user_id: str
    amount: float
    currency: str = "USD"
    source_type: str = "admin_bonus"
    reason: str
    remark: str | None = None


class BonusGrantDecisionRequest(H5MemberCamelModel):
    reason: str | None = Field(default=None)
