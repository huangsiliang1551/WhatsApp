from app.schemas.h5_member_base import H5MemberCamelModel


class H5TaskEntryStateMemberPayload(H5MemberCamelModel):
    public_user_id: str
    site_key: str


class H5TaskEntryStateResponse(H5MemberCamelModel):
    state: str
    redirect_path: str | None = None
    task_package_id: str | None = None
    certification_required_amount: float = 0
    current_real_recharge_amount: float = 0
    remaining_recharge_amount: float = 0
    system_balance: float = 0
    task_balance: float = 0
    member: H5TaskEntryStateMemberPayload
