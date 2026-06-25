from app.schemas.h5_member_base import H5MemberCamelModel


class ManualRechargeRequest(H5MemberCamelModel):
    user_id: str
    amount: float
    agency_id: str | None = None
    site_id: str | None = None
